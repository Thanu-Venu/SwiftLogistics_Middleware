import json
import os
import socket
import time

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


def db_conn():
    return psycopg2.connect(DATABASE_URL)


def set_status(order_id: str, status: str):
    # update DB directly (optional)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
            conn.commit()

    # update gateway to push websocket
    requests.post(API_INTERNAL_STATUS.format(order_id=order_id), json={"status": status}, timeout=5)


def call_cms_soap(order_id: str) -> str:
    # super-minimal SOAP-like XML POST
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


def process_message(body: bytes):
    data = json.loads(body.decode("utf-8"))
    order_id = data["order_id"]

    set_status(order_id, "PROCESSING")
    time.sleep(3)

    set_status(order_id, "CMS_CALLING")
    time.sleep(3)
    call_cms_soap(order_id)
    set_status(order_id, "CMS_OK")
    

    set_status(order_id, "ROS_CALLING")
    time.sleep(3)
    call_ros_rest(order_id)
    set_status(order_id, "ROS_OK")
    

    set_status(order_id, "WMS_CALLING")
    time.sleep(3)
    call_wms_tcp(order_id)
    set_status(order_id, "WMS_OK")
    

    set_status(order_id, "READY_FOR_DRIVER")
    time.sleep(2)


def main():
    # wait a bit for rabbit/postgres
    time.sleep(3)

    params = pika.URLParameters(RABBIT_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue="order.created", durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_msg(ch, method, properties, body):
        try:
            process_message(body)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            # requeue for demo (in real use: DLQ)
            print("ERROR:", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_consume(queue="order.created", on_message_callback=on_msg)
    print("Worker consuming order.created ...")
    channel.start_consuming()


if __name__ == "__main__":
    main()