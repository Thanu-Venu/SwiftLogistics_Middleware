"""
Order Intake REST API Service
Accepts order data and publishes it to RabbitMQ for downstream processing
"""

import json
import pika
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASSWORD = 'guest'
RABBITMQ_VHOST = '/'
ORDER_QUEUE = 'orders_queue'
ORDER_EXCHANGE = 'orders_exchange'


class RabbitMQPublisher:
    """Handles RabbitMQ connection and message publishing"""
    
    def __init__(self, host=RABBITMQ_HOST, port=RABBITMQ_PORT, 
                 user=RABBITMQ_USER, password=RABBITMQ_PASSWORD,
                 vhost=RABBITMQ_VHOST):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.vhost = vhost
        self.connection = None
        self.channel = None
        self.connect()
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                heartbeat=600
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange and queue
            self.channel.exchange_declare(
                exchange=ORDER_EXCHANGE,
                exchange_type='direct',
                durable=True
            )
            
            self.channel.queue_declare(
                queue=ORDER_QUEUE,
                durable=True
            )
            
            self.channel.queue_bind(
                exchange=ORDER_EXCHANGE,
                queue=ORDER_QUEUE,
                routing_key='order.created'
            )
            
            logger.info("Connected to RabbitMQ successfully")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise
    
    def publish_message(self, message: Dict[str, Any], routing_key: str = 'order.created'):
        """Publish a message to RabbitMQ"""
        try:
            self.channel.basic_publish(
                exchange=ORDER_EXCHANGE,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2  # Persistent
                )
            )
            logger.info(f"Message published to {ORDER_EXCHANGE} with routing key {routing_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return False
    
    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed")


# Initialize RabbitMQ Publisher
try:
    publisher = RabbitMQPublisher()
except Exception as e:
    logger.warning(f"RabbitMQ not available on startup: {str(e)}")
    publisher = None


def validate_order(data: Dict[str, Any]) -> tuple[bool, str]:
    """Validate order data"""
    required_fields = ['order_id', 'customer_id', 'items', 'shipping_address']
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if not isinstance(data.get('items'), list) or len(data['items']) == 0:
        return False, "Items must be a non-empty list"
    
    for idx, item in enumerate(data['items']):
        if 'product_id' not in item or 'quantity' not in item or 'price' not in item:
            return False, f"Item {idx} missing required fields: product_id, quantity, price"
    
    return True, ""


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'order-intake-service',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    """
    Create a new order
    Accepts JSON order data and publishes to RabbitMQ
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate order
        is_valid, error_msg = validate_order(data)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Add metadata
        order = {
            **data,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'received'
        }
        
        # Publish to RabbitMQ
        if publisher:
            success = publisher.publish_message(order)
            if not success:
                return jsonify({'error': 'Failed to process order'}), 500
        else:
            logger.warning("RabbitMQ not available, order not published")
            return jsonify({'error': 'Message broker unavailable'}), 503
        
        logger.info(f"Order {data['order_id']} created and published")
        
        return jsonify({
            'message': 'Order created successfully',
            'order_id': data['order_id'],
            'status': 'received',
            'timestamp': order['timestamp']
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/v1/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """
    Get order status
    Note: In a real system, this would query a database
    """
    return jsonify({
        'order_id': order_id,
        'message': 'Order status would be retrieved from database',
        'status': 'pending'
    }), 200


@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """Get service statistics"""
    return jsonify({
        'service': 'order-intake-service',
        'status': 'running',
        'rabbitmq_connected': publisher is not None,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    try:
        logger.info("Starting Order Intake Service...")
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if publisher:
            publisher.close()
