"""
Mock SOAP Web Service for Order Management
Simulates a legacy CMS SOAP interface for order submission and tracking
"""

from zeep import xsd
from zeep.wsdl import wsdl
from zeep.server import TcpServer
from flask import Flask
from lxml import etree
import logging
from datetime import datetime
import json
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Mock database
ORDERS_DB = {}
ORDER_COUNTER = 1000

# WSDL Definition
WSDL_CONTENT = """
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:tns="http://swiftlogistics.com/cms"
             xmlns:http="http://schemas.xmlsoap.org/wsdl/http/"
             xmlns:mime="http://schemas.xmlsoap.org/wsdl/mime/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
             targetNamespace="http://swiftlogistics.com/cms"
             name="CMSOrderService">

    <types>
        <xsd:schema targetNamespace="http://swiftlogistics.com/cms">
            
            <!-- Order Item Type -->
            <xsd:complexType name="OrderItem">
                <xsd:sequence>
                    <xsd:element name="productId" type="xsd:string"/>
                    <xsd:element name="productName" type="xsd:string"/>
                    <xsd:element name="quantity" type="xsd:int"/>
                    <xsd:element name="unitPrice" type="xsd:decimal"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Address Type -->
            <xsd:complexType name="Address">
                <xsd:sequence>
                    <xsd:element name="street" type="xsd:string"/>
                    <xsd:element name="city" type="xsd:string"/>
                    <xsd:element name="state" type="xsd:string" minOccurs="0"/>
                    <xsd:element name="zipCode" type="xsd:string"/>
                    <xsd:element name="country" type="xsd:string"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Submit Order Request -->
            <xsd:complexType name="SubmitOrderRequest">
                <xsd:sequence>
                    <xsd:element name="customerId" type="xsd:string"/>
                    <xsd:element name="customerName" type="xsd:string"/>
                    <xsd:element name="items" type="tns:OrderItem" maxOccurs="unbounded"/>
                    <xsd:element name="shippingAddress" type="tns:Address"/>
                    <xsd:element name="orderPriority" type="xsd:string" minOccurs="0"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Submit Order Response -->
            <xsd:complexType name="SubmitOrderResponse">
                <xsd:sequence>
                    <xsd:element name="orderId" type="xsd:string"/>
                    <xsd:element name="status" type="xsd:string"/>
                    <xsd:element name="totalAmount" type="xsd:decimal"/>
                    <xsd:element name="createdTime" type="xsd:dateTime"/>
                    <xsd:element name="message" type="xsd:string"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Get Order Status Request -->
            <xsd:complexType name="GetOrderStatusRequest">
                <xsd:sequence>
                    <xsd:element name="orderId" type="xsd:string"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Get Order Status Response -->
            <xsd:complexType name="GetOrderStatusResponse">
                <xsd:sequence>
                    <xsd:element name="orderId" type="xsd:string"/>
                    <xsd:element name="status" type="xsd:string"/>
                    <xsd:element name="customerId" type="xsd:string"/>
                    <xsd:element name="customerName" type="xsd:string"/>
                    <xsd:element name="totalAmount" type="xsd:decimal"/>
                    <xsd:element name="createdTime" type="xsd:dateTime"/>
                    <xsd:element name="lastUpdated" type="xsd:dateTime"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Cancel Order Request -->
            <xsd:complexType name="CancelOrderRequest">
                <xsd:sequence>
                    <xsd:element name="orderId" type="xsd:string"/>
                    <xsd:element name="reason" type="xsd:string" minOccurs="0"/>
                </xsd:sequence>
            </xsd:complexType>

            <!-- Cancel Order Response -->
            <xsd:complexType name="CancelOrderResponse">
                <xsd:sequence>
                    <xsd:element name="orderId" type="xsd:string"/>
                    <xsd:element name="status" type="xsd:string"/>
                    <xsd:element name="message" type="xsd:string"/>
                </xsd:sequence>
            </xsd:complexType>

        </xsd:schema>
    </types>

    <!-- Messages -->
    <message name="SubmitOrderRequestMessage">
        <part name="body" type="tns:SubmitOrderRequest"/>
    </message>
    <message name="SubmitOrderResponseMessage">
        <part name="body" type="tns:SubmitOrderResponse"/>
    </message>
    <message name="GetOrderStatusRequestMessage">
        <part name="body" type="tns:GetOrderStatusRequest"/>
    </message>
    <message name="GetOrderStatusResponseMessage">
        <part name="body" type="tns:GetOrderStatusResponse"/>
    </message>
    <message name="CancelOrderRequestMessage">
        <part name="body" type="tns:CancelOrderRequest"/>
    </message>
    <message name="CancelOrderResponseMessage">
        <part name="body" type="tns:CancelOrderResponse"/>
    </message>

    <!-- Port Type (Interface) -->
    <portType name="CMSOrderServicePortType">
        <operation name="submitOrder">
            <input message="tns:SubmitOrderRequestMessage"/>
            <output message="tns:SubmitOrderResponseMessage"/>
        </operation>
        <operation name="getOrderStatus">
            <input message="tns:GetOrderStatusRequestMessage"/>
            <output message="tns:GetOrderStatusResponseMessage"/>
        </operation>
        <operation name="cancelOrder">
            <input message="tns:CancelOrderRequestMessage"/>
            <output message="tns:CancelOrderResponseMessage"/>
        </operation>
    </portType>

    <!-- Binding -->
    <binding name="CMSOrderServiceBinding" type="tns:CMSOrderServicePortType">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="submitOrder">
            <soap:operation soapAction="submitOrder"/>
            <input><soap:body use="literal"/></input>
            <output><soap:body use="literal"/></output>
        </operation>
        <operation name="getOrderStatus">
            <soap:operation soapAction="getOrderStatus"/>
            <input><soap:body use="literal"/></input>
            <output><soap:body use="literal"/></output>
        </operation>
        <operation name="cancelOrder">
            <soap:operation soapAction="cancelOrder"/>
            <input><soap:body use="literal"/></input>
            <output><soap:body use="literal"/></output>
        </operation>
    </binding>

    <!-- Service -->
    <service name="CMSOrderService">
        <port name="CMSOrderServicePort" binding="tns:CMSOrderServiceBinding">
            <soap:address location="http://localhost:5002/soap/cms"/>
        </port>
    </service>

</definitions>
"""


class CMSOrderService:
    """Mock CMS Order Management Service"""
    
    def submit_order(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a new order via SOAP"""
        try:
            global ORDER_COUNTER
            ORDER_COUNTER += 1
            order_id = f"CMS-ORD-{ORDER_COUNTER}"
            
            # Calculate total
            total_amount = sum(
                item['quantity'] * item['unitPrice'] 
                for item in request_data.get('items', [])
            )
            
            # Create order
            order = {
                'order_id': order_id,
                'customer_id': request_data['customerId'],
                'customer_name': request_data['customerName'],
                'items': request_data.get('items', []),
                'shipping_address': request_data['shippingAddress'],
                'total_amount': total_amount,
                'status': 'RECEIVED',
                'priority': request_data.get('orderPriority', 'NORMAL'),
                'created_time': datetime.utcnow().isoformat(),
                'last_updated': datetime.utcnow().isoformat()
            }
            
            ORDERS_DB[order_id] = order
            logger.info(f"Order {order_id} submitted via SOAP: ${total_amount}")
            
            return {
                'orderId': order_id,
                'status': 'RECEIVED',
                'totalAmount': str(total_amount),
                'createdTime': order['created_time'],
                'message': f'Order {order_id} successfully created'
            }
        except Exception as e:
            logger.error(f"Error submitting order: {str(e)}")
            raise
    
    def get_order_status(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get order status via SOAP"""
        try:
            order_id = request_data['orderId']
            
            if order_id not in ORDERS_DB:
                raise ValueError(f"Order {order_id} not found")
            
            order = ORDERS_DB[order_id]
            
            return {
                'orderId': order['order_id'],
                'status': order['status'],
                'customerId': order['customer_id'],
                'customerName': order['customer_name'],
                'totalAmount': str(order['total_amount']),
                'createdTime': order['created_time'],
                'lastUpdated': order['last_updated']
            }
        except Exception as e:
            logger.error(f"Error getting order status: {str(e)}")
            raise
    
    def cancel_order(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel an order via SOAP"""
        try:
            order_id = request_data['orderId']
            reason = request_data.get('reason', 'User requested cancellation')
            
            if order_id not in ORDERS_DB:
                raise ValueError(f"Order {order_id} not found")
            
            order = ORDERS_DB[order_id]
            
            # Check if cancellable
            if order['status'] in ['DELIVERED', 'CANCELLED']:
                return {
                    'orderId': order_id,
                    'status': order['status'],
                    'message': f'Order cannot be cancelled. Current status: {order["status"]}'
                }
            
            # Cancel order
            order['status'] = 'CANCELLED'
            order['last_updated'] = datetime.utcnow().isoformat()
            
            logger.info(f"Order {order_id} cancelled. Reason: {reason}")
            
            return {
                'orderId': order_id,
                'status': 'CANCELLED',
                'message': f'Order {order_id} successfully cancelled'
            }
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            raise


# Initialize service
cms_service = CMSOrderService()


# REST endpoints that simulate SOAP behavior
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'mock-soap-cms-service',
        'timestamp': datetime.utcnow().isoformat()
    }, 200


@app.route('/soap/cms', methods=['POST'])
def soap_endpoint():
    """
    SOAP endpoint
    Receives SOAP requests and routes to appropriate operations
    """
    try:
        from flask import request as flask_request
        
        # Get SOAP body
        soap_body = flask_request.data.decode('utf-8')
        logger.debug(f"Received SOAP request: {soap_body}")
        
        # Parse XML
        from xml.etree import ElementTree as ET
        root = ET.fromstring(soap_body)
        
        # Extract namespace
        ns = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
              'tns': 'http://swiftlogistics.com/cms'}
        
        # Find operation
        body = root.find('.//soap:Body', ns)
        
        if body is None:
            raise ValueError("Invalid SOAP request")
        
        # Handle different operations
        submit_order_elem = body.find('.//tns:SubmitOrderRequest', ns)
        if submit_order_elem is not None:
            request_data = parse_submit_order_request(submit_order_elem)
            response = cms_service.submit_order(request_data)
            return build_soap_response('SubmitOrderResponse', response), 200
        
        get_status_elem = body.find('.//tns:GetOrderStatusRequest', ns)
        if get_status_elem is not None:
            request_data = parse_get_status_request(get_status_elem)
            response = cms_service.get_order_status(request_data)
            return build_soap_response('GetOrderStatusResponse', response), 200
        
        cancel_order_elem = body.find('.//tns:CancelOrderRequest', ns)
        if cancel_order_elem is not None:
            request_data = parse_cancel_order_request(cancel_order_elem)
            response = cms_service.cancel_order(request_data)
            return build_soap_response('CancelOrderResponse', response), 200
        
        raise ValueError("Unknown operation")
    
    except Exception as e:
        logger.error(f"SOAP Error: {str(e)}")
        return build_soap_fault(str(e)), 500


@app.route('/wsdl', methods=['GET'])
def get_wsdl():
    """Return WSDL definition"""
    from flask import Response
    return Response(WSDL_CONTENT, mimetype='application/xml')


def parse_submit_order_request(elem):
    """Parse SubmitOrderRequest from XML element"""
    from xml.etree import ElementTree as ET
    
    ns = {'tns': 'http://swiftlogistics.com/cms'}
    
    items = []
    for item_elem in elem.findall('.//tns:OrderItem', ns):
        items.append({
            'productId': get_element_text(item_elem, 'productId', ns),
            'productName': get_element_text(item_elem, 'productName', ns),
            'quantity': int(get_element_text(item_elem, 'quantity', ns)),
            'unitPrice': float(get_element_text(item_elem, 'unitPrice', ns))
        })
    
    address_elem = elem.find('.//tns:Address', ns)
    
    return {
        'customerId': get_element_text(elem, 'customerId', ns),
        'customerName': get_element_text(elem, 'customerName', ns),
        'items': items,
        'shippingAddress': {
            'street': get_element_text(address_elem, 'street', ns),
            'city': get_element_text(address_elem, 'city', ns),
            'state': get_element_text(address_elem, 'state', ns),
            'zipCode': get_element_text(address_elem, 'zipCode', ns),
            'country': get_element_text(address_elem, 'country', ns)
        },
        'orderPriority': get_element_text(elem, 'orderPriority', ns)
    }


def parse_get_status_request(elem):
    """Parse GetOrderStatusRequest from XML element"""
    from xml.etree import ElementTree as ET
    ns = {'tns': 'http://swiftlogistics.com/cms'}
    
    return {
        'orderId': get_element_text(elem, 'orderId', ns)
    }


def parse_cancel_order_request(elem):
    """Parse CancelOrderRequest from XML element"""
    ns = {'tns': 'http://swiftlogistics.com/cms'}
    
    return {
        'orderId': get_element_text(elem, 'orderId', ns),
        'reason': get_element_text(elem, 'reason', ns)
    }


def get_element_text(elem, tag_name, ns):
    """Safely get element text"""
    child = elem.find(f'tns:{tag_name}', ns)
    return child.text if child is not None else None


def build_soap_response(operation_name, data):
    """Build SOAP response XML"""
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://swiftlogistics.com/cms">
    <soap:Body>
        <tns:{operation_name}>
"""
    
    for key, value in data.items():
        camel_key = ''.join(word.capitalize() if i > 0 else word 
                           for i, word in enumerate(key.split('_')))
        response_xml += f"            <tns:{camel_key}>{value}</tns:{camel_key}>\n"
    
    response_xml += f"""        </tns:{operation_name}>
    </soap:Body>
</soap:Envelope>"""
    
    return response_xml


def build_soap_fault(error_message):
    """Build SOAP fault response"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>{error_message}</faultstring>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""


if __name__ == '__main__':
    logger.info("Starting Mock CMS SOAP Service...")
    app.run(debug=True, host='0.0.0.0', port=5002)
