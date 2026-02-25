"""
Mock SOAP Web Service for Order Management
Simulates a legacy CMS SOAP interface
"""

from flask import Flask, request, Response
from datetime import datetime
import logging
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ORDERS_DB = {}
ORDER_COUNTER = 1000


# ---------------------------
# BUSINESS LOGIC
# ---------------------------

class CMSOrderService:

    def submit_order(self, data):
        global ORDER_COUNTER
        ORDER_COUNTER += 1

        order_id = f"CMS-ORD-{ORDER_COUNTER}"

        total = sum(
            item["quantity"] * item["unitPrice"]
            for item in data["items"]
        )

        order = {
            "orderId": order_id,
            "customerId": data["customerId"],
            "customerName": data["customerName"],
            "items": data["items"],
            "totalAmount": total,
            "status": "RECEIVED",
            "createdTime": datetime.utcnow().isoformat(),
            "lastUpdated": datetime.utcnow().isoformat()
        }

        ORDERS_DB[order_id] = order

        return {
            "orderId": order_id,
            "status": "RECEIVED",
            "totalAmount": total,
            "createdTime": order["createdTime"],
            "message": "Order created successfully"
        }

    def get_order_status(self, data):
        order_id = data["orderId"]

        if order_id not in ORDERS_DB:
            raise Exception("Order not found")

        return ORDERS_DB[order_id]

    def cancel_order(self, data):
        order_id = data["orderId"]

        if order_id not in ORDERS_DB:
            raise Exception("Order not found")

        order = ORDERS_DB[order_id]

        if order["status"] in ["DELIVERED", "CANCELLED"]:
            return {
                "orderId": order_id,
                "status": order["status"],
                "message": "Cannot cancel"
            }

        order["status"] = "CANCELLED"
        order["lastUpdated"] = datetime.utcnow().isoformat()

        return {
            "orderId": order_id,
            "status": "CANCELLED",
            "message": "Order cancelled successfully"
        }


service = CMSOrderService()


# ---------------------------
# SOAP ENDPOINT
# ---------------------------

@app.route("/soap/cms", methods=["POST"])
def soap_endpoint():
    try:
        xml_data = request.data.decode("utf-8")
        root = ET.fromstring(xml_data)

        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "tns": "http://swiftlogistics.com/cms"
        }

        body = root.find("soap:Body", ns)

        # SUBMIT ORDER
        submit = body.find("tns:SubmitOrderRequest", ns)
        if submit is not None:
            data = parse_submit_request(submit, ns)
            result = service.submit_order(data)
            return Response(build_response("SubmitOrderResponse", result),
                            mimetype="text/xml")

        # GET STATUS
        status = body.find("tns:GetOrderStatusRequest", ns)
        if status is not None:
            data = {"orderId": status.find("tns:orderId", ns).text}
            result = service.get_order_status(data)
            return Response(build_response("GetOrderStatusResponse", result),
                            mimetype="text/xml")

        # CANCEL
        cancel = body.find("tns:CancelOrderRequest", ns)
        if cancel is not None:
            data = {"orderId": cancel.find("tns:orderId", ns).text}
            result = service.cancel_order(data)
            return Response(build_response("CancelOrderResponse", result),
                            mimetype="text/xml")

        raise Exception("Unknown operation")

    except Exception as e:
        return Response(build_fault(str(e)), mimetype="text/xml", status=500)


# ---------------------------
# HELPERS
# ---------------------------

def parse_submit_request(elem, ns):
    items = []
    for item in elem.findall("tns:items", ns):
        items.append({
            "productId": item.find("tns:productId", ns).text,
            "productName": item.find("tns:productName", ns).text,
            "quantity": int(item.find("tns:quantity", ns).text),
            "unitPrice": float(item.find("tns:unitPrice", ns).text)
        })

    return {
        "customerId": elem.find("tns:customerId", ns).text,
        "customerName": elem.find("tns:customerName", ns).text,
        "items": items
    }


def build_response(operation, data):
    xml = f"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://swiftlogistics.com/cms">
<soap:Body>
<tns:{operation}>
"""

    for k, v in data.items():
        xml += f"<tns:{k}>{v}</tns:{k}>"

    xml += f"""
</tns:{operation}>
</soap:Body>
</soap:Envelope>"""

    return xml


def build_fault(msg):
    return f"""<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
<soap:Body>
<soap:Fault>
<faultcode>soap:Server</faultcode>
<faultstring>{msg}</faultstring>
</soap:Fault>
</soap:Body>
</soap:Envelope>"""


@app.route("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    app.run(port=5002, debug=True)
