import json
import os
import socket
import sys
import time
from typing import Any, Dict, Optional, Tuple, List

import pika
import psycopg2
import requests

# ---------------- Retry tuning ----------------
BASE_RETRY_TTL_MS = 2000       # 2s
MAX_RETRY_TTL_MS  = 60000      # 60s cap

# ---------------- Env ----------------
DATABASE_URL = os.getenv("DATABASE_URL")
RABBIT_URL = os.getenv("RABBIT_URL")
CMS_URL = os.getenv("CMS_URL")
ROS_URL = os.getenv("ROS_URL")
WMS_HOST = os.getenv("WMS_HOST")
WMS_PORT = int(os.getenv("WMS_PORT", "9200"))

API_INTERNAL_STATUS = "http://api-gateway:8000/internal/orders/{order_id}/status"
API_INTERNAL_NOTIFY = "http://api-gateway:8000/internal/driver/{driver_id}/notify"
QUEUE_MAIN = "order.created"
QUEUE_RETRY = "order.created.retry"
QUEUE_DLQ = "order.created.dlq"

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
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
    orders.created_at BIGINT (your schema), updated_at TIMESTAMPTZ (we set NOW()).
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

def notify_driver(driver_id: str, msg: dict):
    # best-effort (never crash worker)
    try:
        requests.post(
            API_INTERNAL_NOTIFY.format(driver_id=driver_id),
            json=msg,
            timeout=2,
        )
    except Exception as e:
        print(f"[WARN] notify_driver failed driver={driver_id} err={e}")

def add_event(order_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
    """
    Matches your table:
    order_events(order_id text, event_type text, details jsonb, created_at timestamptz default now()).
    """
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

def already_processed(order_id: str, event_id: str) -> bool:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_event_id FROM orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
    return bool(row and row[0] == event_id)

def mark_processed(order_id: str, event_id: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET last_event_id=%s, updated_at=now() WHERE id=%s",
                (event_id, order_id),
            )
            conn.commit()

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
    params.heartbeat = 30
    params.blocked_connection_timeout = 30
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel

def declare_queues(channel):
    # main + dlq durable
    channel.queue_declare(queue=QUEUE_MAIN, durable=True)
    channel.queue_declare(queue=QUEUE_DLQ, durable=True)

    # IMPORTANT:
    # Retry queue should NOT use x-message-ttl if you want per-message TTL.
    # We only configure DLX back to main; each message will carry its own expiration.
    channel.queue_declare(
        queue=QUEUE_RETRY,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_MAIN,
        },
    )

def rabbit_get_channel():
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
    expiration_ms: Optional[int] = None,
):
    # per-message TTL: set properties.expiration (string in ms)
    expiration = str(int(expiration_ms)) if expiration_ms is not None else None

    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
            headers=headers,
            content_type=properties.content_type or "application/json",
            correlation_id=properties.correlation_id,
            expiration=expiration,
        ),
    )

def publish_retry(channel, body: bytes, properties: pika.BasicProperties, retry_count: int, ttl_ms: int):
    headers = dict(properties.headers or {})
    headers["x-retries"] = retry_count
    headers["x-ttl-ms"] = ttl_ms
    publish_to_queue(channel, QUEUE_RETRY, body, properties, headers, expiration_ms=ttl_ms)

def publish_dlq(channel, body: bytes, properties: pika.BasicProperties, reason: str):
    headers = dict(properties.headers or {})
    headers["x-dlq-reason"] = (reason or "")[:200]
    publish_to_queue(channel, QUEUE_DLQ, body, properties, headers)

def safe_extract_order_id(body: bytes) -> str:
    data = json.loads(body.decode("utf-8"))
    return data["order_id"]

def safe_extract_event_id(body: bytes, properties: pika.BasicProperties) -> Optional[str]:
    """
    Prefer JSON field 'event_id'. If missing, fallback to correlation_id (outbox_id).
    """
    try:
        data = json.loads(body.decode("utf-8"))
        ev = data.get("event_id")
        if ev:
            return str(ev)
    except Exception:
        pass

    if properties and properties.correlation_id:
        return str(properties.correlation_id)
    return None

# ---------------- Processing ----------------
def maybe_sleep(sec: float):
    if DEMO_DELAYS:
        time.sleep(sec)

def pick_driver_id() -> Optional[str]:
    """
    Pick a driver from users table.
    Simplest: first driver. You can later change to round-robin.
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE role='driver' ORDER BY id ASC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None


def assign_driver_if_missing(order_id: str) -> Optional[str]:
    """
    Assign a driver only if assigned_driver_id is NULL.
    Returns driver_id if assigned or already assigned, else None.
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            # if already assigned, return it
            cur.execute("SELECT assigned_driver_id FROM orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
            if not row:
                return None
            if row[0]:
                return row[0]

            driver_id = pick_driver_id()
            if not driver_id:
                return None

            cur.execute(
                """
                UPDATE orders
                SET assigned_driver_id=%s, updated_at=NOW()
                WHERE id=%s AND assigned_driver_id IS NULL
                """,
                (driver_id, order_id),
            )
            conn.commit()
            return driver_id


def mark_ready_for_driver(order_id: str):
    """
    Set READY_FOR_DRIVER + auto-assign driver.
    """
    set_status(order_id, "READY_FOR_DRIVER")
    driver_id = assign_driver_if_missing(order_id)

    add_event(order_id, "READY_FOR_DRIVER", {"assigned_driver_id": driver_id})
    if driver_id:
        add_event(order_id, "DRIVER_ASSIGNED", {"driver_id": driver_id})

        # ✅ realtime notify to driver portal (WS)
        notify_driver(driver_id, {
            "type": "NEW_ASSIGNMENT",
            "order_id": order_id,
            "message": "New order assigned",
            "payload": {"status": "READY_FOR_DRIVER"}
        })
    else:
        add_event(order_id, "DRIVER_ASSIGN_FAILED", {"reason": "no_driver_found"})


def process_order(order_id: str):
    st = get_status(order_id)

    if st in ("READY_FOR_DRIVER", "DELIVERED", "FAILED", "DLQ"):
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
    # ROS
    set_status(order_id, "ROS_CALLING")
    add_event(order_id, "ROS_CALLING")
    maybe_sleep(0.5)

    route = call_ros_rest(order_id)  # ✅ capture actual response

    # ✅ save route into orders.payload.route
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
            """
            UPDATE orders
            SET payload = jsonb_set(
                COALESCE(payload, '{}'::jsonb),
                '{route}',
                %s::jsonb,
                true
            ),
            updated_at = NOW()
            WHERE id=%s
            """,
            (json.dumps(route), order_id),
        )
    conn.commit()

    add_event(order_id, "ROUTE_SAVED", {"route": route})

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

    mark_ready_for_driver(order_id)
# ---------------- Outbox publisher (schema matches your table) ----------------
def outbox_fetch_batch(conn, limit: int = 50) -> List[Tuple[int, str, str, Dict[str, Any]]]:
    """
    Your outbox columns:
      id (bigint), aggregate_type (text), aggregate_id (text), event_type (text), payload (jsonb)
    No published flag -> after publishing we DELETE the row (simple outbox consumer pattern).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, aggregate_type, aggregate_id, payload
            FROM outbox
            ORDER BY id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        return cur.fetchall()

def outbox_delete(conn, outbox_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE id=%s", (outbox_id,))

def run_outbox_publisher():
    print("[OUTBOX] starting outbox publisher loop...")
    conn_rabbit, ch = rabbit_get_channel()

    while True:
        try:
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

                for outbox_id, agg_type, order_id, payload in rows:
                    # event_id = outbox_id (stable) -> supports idempotency
                    msg = {
                        "order_id": str(order_id),
                        "event_id": str(outbox_id),
                        "aggregate_type": agg_type,
                        "payload": payload,
                    }
                    body = json.dumps(msg).encode("utf-8")

                    try:
                        ch.basic_publish(
                            exchange="",
                            routing_key=QUEUE_MAIN,
                            body=body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                content_type="application/json",
                                correlation_id=str(outbox_id),
                            ),
                        )

                        outbox_delete(conn_db, outbox_id)

                        # optional: mark order queued + event
                        try:
                            set_status(str(order_id), "QUEUED")
                            add_event(str(order_id), "QUEUED", {"outbox_id": outbox_id})
                        except Exception:
                            pass

                        print(f"[OUTBOX] published order={order_id} outbox_id={outbox_id}")

                    except Exception as e:
                        # if publish fails, do NOT delete row -> will retry later
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
                    event_id = safe_extract_event_id(body, properties)

                    print(f"[INFO] received order={order_id} event_id={event_id}")

                    # idempotency: if same event already applied -> ack + skip
                    if order_id and event_id and already_processed(order_id, event_id):
                        print(f"[SKIP] duplicate event order={order_id} event_id={event_id}")
                        add_event(order_id, "DUPLICATE_SKIP", {"event_id": event_id})
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        return

                    process_order(order_id)

                    if order_id and event_id:
                        mark_processed(order_id, event_id)

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

                    # ack current message
                    channel.basic_ack(delivery_tag=method.delivery_tag)

                    # schedule retry/DLQ
                    if retries < MAX_RETRIES:
                        next_retry = retries + 1
                        ttl_ms = min(MAX_RETRY_TTL_MS, BASE_RETRY_TTL_MS * (2 ** (next_retry - 1)))

                        publish_retry(channel, body, properties, next_retry, ttl_ms=ttl_ms)
                        print(f"[RETRY] order={order_id} -> retry={next_retry} ttl={ttl_ms}ms")
                        if order_id:
                            add_event(order_id, "RETRY_SCHEDULED", {"retry": next_retry, "ttl_ms": ttl_ms})
                    else:
                        publish_dlq(channel, body, properties, reason=err_msg)
                        print(f"[DLQ] order={order_id} moved to DLQ")
                        if order_id:
                            # final state
                            set_status(order_id, "DLQ", last_error=err_msg, inc_retry=False)
                            add_event(order_id, "DLQ", {"err": err_msg, "retries": retries})

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