import json
import os
import socket
import sys
import time
from typing import Any, Dict, Optional, Tuple, List

import pika
import psycopg2
import requests

# ---------------- Env ----------------
DATABASE_URL = os.getenv("DATABASE_URL")
RABBIT_URL = os.getenv("RABBIT_URL")
CMS_URL = os.getenv("CMS_URL")
ROS_URL = os.getenv("ROS_URL")
WMS_HOST = os.getenv("WMS_HOST")
WMS_PORT = int(os.getenv("WMS_PORT", "9200"))

API_INTERNAL_STATUS = "http://api-gateway:8000/internal/orders/{order_id}/status"

QUEUE_MAIN = "order.created"
QUEUE_RETRY = "order.created.retry"
QUEUE_DLQ = "order.created.dlq"

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_TTL_MS = int(os.getenv("RETRY_TTL_MS", "5000"))
DEMO_DELAYS = os.getenv("DEMO_DELAYS", "true").lower() in ("1", "true", "yes", "y")

# ---------------- DB ----------------
def db_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema='public' AND table_name=%s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def get_status(order_id: str) -> Optional[str]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
            return row[0] if row else None


def set_status(
    order_id: str,
    status: str,
    last_error: Optional[str] = None,
    inc_retry: bool = False,
):
    """
    Note: your schema has created_at BIGINT and updated_at TIMESTAMPTZ.
    We always set updated_at=NOW() on status updates.
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            if inc_retry:
                cur.execute(
                    """
                    UPDATE orders
                    SET status=%s,
                        retry_count = retry_count + 1,
                        last_error = COALESCE(%s, last_error),
                        updated_at = NOW()
                    WHERE id=%s
                    """,
                    (status, last_error, order_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE orders
                    SET status=%s,
                        last_error = COALESCE(%s, last_error),
                        updated_at = NOW()
                    WHERE id=%s
                    """,
                    (status, last_error, order_id),
                )
            conn.commit()

    # best-effort push to gateway for WS/UI
    try:
        requests.post(
            API_INTERNAL_STATUS.format(order_id=order_id),
            json={"status": status},
            timeout=3,
        )
    except Exception as e:
        print(f"[WARN] status push failed order={order_id} status={status} err={e}")


def add_event(order_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
    details = details or {}
    try:
        with db_conn() as conn:
            if not _table_exists(conn, "order_events"):
                return
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO order_events(order_id, event_type, details) VALUES (%s,%s,%s::jsonb)",
                    (order_id, event_type, json.dumps(details)),
                )
                conn.commit()
    except Exception as e:
        print(f"[WARN] add_event failed order={order_id} event={event_type} err={e}")


# ---------------- External Calls ----------------
def call_cms_soap(order_id: str) -> str:
    if not CMS_URL:
        raise RuntimeError("CMS_URL not set")

    xml = f"""<?xml version="1.0"?>
<Envelope>
  <Body>
    <CreateOrder>
      <OrderId>{order_id}</OrderId>
    </CreateOrder>
  </Body>
</Envelope>
"""
    r = requests.post(
        CMS_URL,
        data=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
        timeout=5,
    )
    r.raise_for_status()
    return r.text


def call_ros_rest(order_id: str) -> dict:
    if not ROS_URL:
        raise RuntimeError("ROS_URL not set")

    r = requests.post(ROS_URL, json={"order_id": order_id}, timeout=5)
    r.raise_for_status()
    return r.json()


def call_wms_tcp(order_id: str) -> str:
    if not WMS_HOST:
        raise RuntimeError("WMS_HOST not set")

    msg = f"ADD_PACKAGE|{order_id}\n".encode("utf-8")
    with socket.create_connection((WMS_HOST, WMS_PORT), timeout=5) as s:
        s.sendall(msg)
        data = s.recv(1024).decode("utf-8", errors="ignore").strip()
    return data


# ---------------- RabbitMQ plumbing ----------------
def rabbit_connect() -> Tuple[pika.BlockingConnection, pika.adapters.blocking_connection.BlockingChannel]:
    if not RABBIT_URL:
        raise RuntimeError("RABBIT_URL not set")

    params = pika.URLParameters(RABBIT_URL)
    # Helpful defaults for stability
    params.heartbeat = 30
    params.blocked_connection_timeout = 30

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel


def declare_queues(channel):
    channel.queue_declare(queue=QUEUE_MAIN, durable=True)
    channel.queue_declare(queue=QUEUE_DLQ, durable=True)
    channel.queue_declare(
        queue=QUEUE_RETRY,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_TTL_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_MAIN,
        },
    )


def rabbit_get_channel():
    """
    Always returns a fresh open connection+channel.
    Retries forever.
    """
    while True:
        try:
            conn, ch = rabbit_connect()
            declare_queues(ch)
            return conn, ch
        except Exception as e:
            print(f"[RABBIT][ERROR] connect failed err={e}")
            time.sleep(2)


def get_retry_count(properties: pika.BasicProperties) -> int:
    headers = properties.headers or {}
    v = headers.get("x-retries", 0)
    try:
        return int(v)
    except Exception:
        return 0


def publish_to_queue(
    channel,
    queue_name: str,
    body: bytes,
    properties: pika.BasicProperties,
    headers: Dict[str, Any],
):
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            headers=headers,
            content_type=properties.content_type or "application/json",
            correlation_id=properties.correlation_id,
        ),
    )


def publish_retry(channel, body: bytes, properties: pika.BasicProperties, retry_count: int):
    headers = dict(properties.headers or {})
    headers["x-retries"] = retry_count
    publish_to_queue(channel, QUEUE_RETRY, body, properties, headers)


def publish_dlq(channel, body: bytes, properties: pika.BasicProperties, reason: str):
    headers = dict(properties.headers or {})
    headers["x-dlq-reason"] = (reason or "")[:200]
    publish_to_queue(channel, QUEUE_DLQ, body, properties, headers)


def safe_extract_order_id(body: bytes) -> str:
    data = json.loads(body.decode("utf-8"))
    return data["order_id"]


# ---------------- Processing (idempotent-ish) ----------------
def maybe_sleep(sec: float):
    if DEMO_DELAYS:
        time.sleep(sec)


def process_order(order_id: str):
    st = get_status(order_id)

    if st in ("READY_FOR_DRIVER", "COMPLETED"):
        print(f"[SKIP] order={order_id} already done status={st}")
        add_event(order_id, "SKIP_ALREADY_DONE", {"status": st})
        return

    set_status(order_id, "PROCESSING")
    add_event(order_id, "PROCESSING")
    maybe_sleep(0.5)

    # CMS
    set_status(order_id, "CMS_CALLING")
    add_event(order_id, "CMS_CALLING")
    maybe_sleep(0.5)
    call_cms_soap(order_id)
    set_status(order_id, "CMS_OK")
    add_event(order_id, "CMS_OK")
    maybe_sleep(0.2)

    # ROS
    set_status(order_id, "ROS_CALLING")
    add_event(order_id, "ROS_CALLING")
    maybe_sleep(0.5)
    call_ros_rest(order_id)
    set_status(order_id, "ROS_OK")
    add_event(order_id, "ROS_OK")
    maybe_sleep(0.2)

    # WMS
    set_status(order_id, "WMS_CALLING")
    add_event(order_id, "WMS_CALLING")
    maybe_sleep(0.5)
    call_wms_tcp(order_id)
    set_status(order_id, "WMS_OK")
    add_event(order_id, "WMS_OK")
    maybe_sleep(0.2)

    set_status(order_id, "READY_FOR_DRIVER")
    add_event(order_id, "READY_FOR_DRIVER")


# ---------------- Outbox publisher ----------------
def outbox_fetch_batch(conn, limit: int = 50) -> List[Tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, aggregate_id
            FROM outbox
            WHERE published = FALSE
            ORDER BY created_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        return cur.fetchall()


def outbox_mark_published(conn, outbox_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE outbox SET published=TRUE, published_at=NOW() WHERE id=%s",
            (outbox_id,),
        )


def outbox_mark_failed(conn, outbox_id: int, err: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE outbox
            SET publish_attempts = publish_attempts + 1,
                last_error = %s
            WHERE id=%s
            """,
            (err[:400], outbox_id),
        )


def run_outbox_publisher():
    print("[OUTBOX] starting outbox publisher loop...")

    conn_rabbit, ch = rabbit_get_channel()

    while True:
        try:
            # reconnect if closed
            if conn_rabbit.is_closed or ch.is_closed:
                print("[OUTBOX][WARN] rabbit conn/channel closed -> reconnecting")
                try:
                    conn_rabbit.close()
                except Exception:
                    pass
                conn_rabbit, ch = rabbit_get_channel()

            with db_conn() as conn_db:
                if not _table_exists(conn_db, "outbox"):
                    print("[OUTBOX] outbox table missing. Sleeping...")
                    time.sleep(2)
                    continue

                rows = outbox_fetch_batch(conn_db, limit=50)

                if not rows:
                    conn_db.commit()
                    time.sleep(1)
                    continue

                for outbox_id, order_id in rows:
                    body = json.dumps({"order_id": str(order_id)}).encode("utf-8")

                    try:
                        ch.basic_publish(
                            exchange="",
                            routing_key=QUEUE_MAIN,
                            body=body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                content_type="application/json",
                            ),
                        )

                        outbox_mark_published(conn_db, outbox_id)

                        # optional status update
                        try:
                            set_status(str(order_id), "QUEUED")
                            add_event(str(order_id), "QUEUED")
                        except Exception:
                            pass

                        print(f"[OUTBOX] published order={order_id} outbox_id={outbox_id}")

                    except Exception as e:
                        outbox_mark_failed(conn_db, outbox_id, str(e))
                        conn_db.commit()
                        print(f"[OUTBOX][WARN] publish failed outbox_id={outbox_id} err={e}")

                        # force reconnect
                        try:
                            conn_rabbit.close()
                        except Exception:
                            pass
                        conn_rabbit, ch = rabbit_get_channel()

                conn_db.commit()

        except Exception as loop_err:
            print(f"[OUTBOX][ERROR] loop err={loop_err}")
            time.sleep(2)


# ---------------- Consumer (with reconnect loop) ----------------
def run_consumer():
    print(f"[WORKER] starting consumer on {QUEUE_MAIN} ...")
    time.sleep(3)

    while True:
        conn, ch = rabbit_get_channel()
        try:
            ch.basic_qos(prefetch_count=1)

            def on_msg(channel, method, properties, body):
                order_id = None
                try:
                    order_id = safe_extract_order_id(body)
                    print(f"[INFO] received order={order_id}")

                    process_order(order_id)

                    channel.basic_ack(delivery_tag=method.delivery_tag)
                    print(f"[OK] done order={order_id}")

                except Exception as e:
                    retries = get_retry_count(properties)
                    err_msg = str(e)
                    print(f"[ERROR] order={order_id} retries={retries} err={err_msg}")

                    # best-effort update
                    if order_id:
                        lower = err_msg.lower()
                        if "soap" in lower or "cms" in lower:
                            set_status(order_id, "CMS_ERROR", last_error=err_msg, inc_retry=True)
                            add_event(order_id, "CMS_ERROR", {"err": err_msg})
                        elif "ros" in lower or "optimize" in lower or "route" in lower:
                            set_status(order_id, "ROS_ERROR", last_error=err_msg, inc_retry=True)
                            add_event(order_id, "ROS_ERROR", {"err": err_msg})
                        elif "wms" in lower or "socket" in lower or "tcp" in lower:
                            set_status(order_id, "WMS_ERROR", last_error=err_msg, inc_retry=True)
                            add_event(order_id, "WMS_ERROR", {"err": err_msg})
                        else:
                            set_status(order_id, "FAILED", last_error=err_msg, inc_retry=True)
                            add_event(order_id, "FAILED", {"err": err_msg})

                    # ack current
                    channel.basic_ack(delivery_tag=method.delivery_tag)

                    # schedule retry/DLQ
                    if retries < MAX_RETRIES:
                        next_retry = retries + 1
                        publish_retry(channel, body, properties, next_retry)
                        print(f"[RETRY] order={order_id} -> retry={next_retry} via {QUEUE_RETRY} ttl={RETRY_TTL_MS}ms")
                        if order_id:
                            add_event(order_id, "RETRY_SCHEDULED", {"retry": next_retry, "ttl_ms": RETRY_TTL_MS})
                    else:
                        publish_dlq(channel, body, properties, reason=err_msg)
                        print(f"[DLQ] order={order_id} moved to DLQ")
                        if order_id:
                            set_status(order_id, "DEAD_LETTERED", last_error=err_msg)
                            add_event(order_id, "DEAD_LETTERED", {"err": err_msg})

            ch.basic_consume(queue=QUEUE_MAIN, on_message_callback=on_msg)
            print(f"[WORKER] consuming {QUEUE_MAIN} ...")
            ch.start_consuming()

        except Exception as e:
            print(f"[WORKER][WARN] consumer loop error (will reconnect) err={e}")
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(2)


# ---------------- Main ----------------
def main():
    mode = "consume"
    if len(sys.argv) >= 2:
        mode = sys.argv[1].strip().lower()

    if mode in ("consume", "worker"):
        run_consumer()
    elif mode in ("outbox", "publisher"):
        run_outbox_publisher()
    else:
        print("Usage:")
        print("  python worker.py consume   # consume main queue and process pipeline")
        print("  python worker.py outbox    # publish DB outbox -> rabbit main queue")
        sys.exit(2)


if __name__ == "__main__":
    main()