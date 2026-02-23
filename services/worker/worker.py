import json
import os
import socket
import time
from typing import Any, Dict

import pika
import psycopg2
import requests

DATABASE_URL = os.getenv("DATABASE_URL")
RABBIT_URL = os.getenv("RABBIT_URL")
CMS_URL = os.getenv("CMS_URL")
ROS_URL = os.getenv("ROS_URL")
WMS_HOST = os.getenv("WMS_HOST")
WMS_PORT = int(os.getenv("WMS_PORT", "9200"))

API_INTERNAL_STATUS = "http://api-gateway:8000/internal/orders/{order_id}/status"

QUEUE_MAIN = "order.created"
QUEUE_DLQ = "order.created.dlq"

MAX_RETRIES = 3

# ---------- DB ----------
def db_conn():
    return psycopg2.connect(DATABASE_URL)

def set_status(order_id: str, status: str):
    # update DB
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
            conn.commit()

    # push WS via gateway (best-effort)
    try:
        requests.post(
            API_INTERNAL_STATUS.format(order_id=order_id),
            json={"status": status},
            timeout=5,
        )
    except Exception as e:
        print(f"[WARN] status push failed order={order_id} status={status} err={e}")

# ---------- External Calls ----------
def call_cms_soap(order_id: str) -> str:
    xml = f"""<?xml version="1.0"?>
<Envelope>
  <Body>
    <CreateOrder>
      <OrderId>{order_id}</OrderId>
    </CreateOrder>
  </Body>
</Envelope>
"""
    r = requests.post(CMS_URL, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml"}, timeout=5)
    r.raise_for_status()
    return r.text

def call_ros_rest(order_id: str) -> dict:
    r = requests.post(ROS_URL, json={"order_id": order_id}, timeout=5)
    r.raise_for_status()
    return r.json()

def call_wms_tcp(order_id: str) -> str:
    msg = f"ADD_PACKAGE|{order_id}\n".encode("utf-8")
    with socket.create_connection((WMS_HOST, WMS_PORT), timeout=5) as s:
        s.sendall(msg)
        data = s.recv(1024).decode("utf-8", errors="ignore").strip()
    return data

# ---------- Pipeline ----------
def process_order(order_id: str):
    # demo visualization delays (keep)
    set_status(order_id, "PROCESSING")
    time.sleep(1)

    # CMS
    set_status(order_id, "CMS_CALLING")
    time.sleep(1)
    call_cms_soap(order_id)
    set_status(order_id, "CMS_OK")
    time.sleep(0.5)

    # ROS
    set_status(order_id, "ROS_CALLING")
    time.sleep(1)
    call_ros_rest(order_id)
    set_status(order_id, "ROS_OK")
    time.sleep(0.5)

    # WMS
    set_status(order_id, "WMS_CALLING")
    time.sleep(1)
    call_wms_tcp(order_id)
    set_status(order_id, "WMS_OK")
    time.sleep(0.5)

    set_status(order_id, "READY_FOR_DRIVER")

# ---------- Retry Helpers ----------
def get_retry_count(properties: pika.BasicProperties) -> int:
    headers = properties.headers or {}
    v = headers.get("x-retries", 0)
    try:
        return int(v)
    except Exception:
        return 0

def publish_retry(channel, body: bytes, properties: pika.BasicProperties, retry_count: int):
    headers = dict(properties.headers or {})
    headers["x-retries"] = retry_count

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_MAIN,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            headers=headers,
            content_type=properties.content_type,
            correlation_id=properties.correlation_id,
        ),
    )

def publish_dlq(channel, body: bytes, properties: pika.BasicProperties, reason: str):
    headers = dict(properties.headers or {})
    headers["x-dlq-reason"] = reason

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_DLQ,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            headers=headers,
            content_type=properties.content_type,
            correlation_id=properties.correlation_id,
        ),
    )

def safe_extract_order_id(body: bytes) -> str:
    data = json.loads(body.decode("utf-8"))
    return data["order_id"]

# ---------- Main ----------
def main():
    time.sleep(3)

    params = pika.URLParameters(RABBIT_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_MAIN, durable=True)
    channel.queue_declare(queue=QUEUE_DLQ, durable=True)

    channel.basic_qos(prefetch_count=1)

    def on_msg(ch, method, properties, body):
        order_id = None
        try:
            order_id = safe_extract_order_id(body)
            print(f"[INFO] received order={order_id}")

            process_order(order_id)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[OK] done order={order_id}")

        except Exception as e:
            # step-specific status (best-effort)
            if order_id:
                msg = str(e)
                # simple mapping based on current stage keywords
                if "CMS" in msg or "soap" in msg.lower():
                    set_status(order_id, "CMS_ERROR")
                elif "ROS" in msg or "optimize" in msg.lower():
                    set_status(order_id, "ROS_ERROR")
                elif "WMS" in msg or "socket" in msg.lower():
                    set_status(order_id, "WMS_ERROR")
                else:
                    set_status(order_id, "FAILED")

            retries = get_retry_count(properties)
            print(f"[ERROR] order={order_id} retries={retries} err={e}")

            # IMPORTANT: ack current message, then republish (avoid infinite redelivery loop)
            ch.basic_ack(delivery_tag=method.delivery_tag)

            if retries < MAX_RETRIES:
                next_retry = retries + 1
                # small backoff
                time.sleep(1 * next_retry)
                publish_retry(ch, body, properties, next_retry)
                print(f"[RETRY] order={order_id} -> retry={next_retry}")
            else:
                publish_dlq(ch, body, properties, reason=str(e)[:200])
                print(f"[DLQ] order={order_id} moved to DLQ")

    channel.basic_consume(queue=QUEUE_MAIN, on_message_callback=on_msg)
    print("Worker consuming order.created ...")
    channel.start_consuming()

if __name__ == "__main__":
    main()