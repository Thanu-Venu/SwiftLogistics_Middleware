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
from typing import Dict, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASSWORD = 'guest'
RABBITMQ_VHOST = '/'
ORDER_QUEUE = 'orders_queue'
ORDER_EXCHANGE = 'orders_exchange'
ROUTING_KEY = 'order.created'


class RabbitMQPublisher:
    """Handles RabbitMQ connection and message publishing"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.connect()

    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                virtual_host=RABBITMQ_VHOST,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchange
            self.channel.exchange_declare(
                exchange=ORDER_EXCHANGE,
                exchange_type='direct',
                durable=True
            )

            # Declare queue
            self.channel.queue_declare(
                queue=ORDER_QUEUE,
                durable=True
            )

            # Bind queue
            self.channel.queue_bind(
                exchange=ORDER_EXCHANGE,
                queue=ORDER_QUEUE,
                routing_key=ROUTING_KEY
            )

            logger.info("Connected to RabbitMQ successfully")

        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {e}")
            self.connection = None
            self.channel = None

    def publish_message(self, message: Dict[str, Any]) -> bool:
        """Publish message safely"""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("Reconnecting to RabbitMQ...")
                self.connect()

            if not self.channel:
                return False

            self.channel.basic_publish(
                exchange=ORDER_EXCHANGE,
                routing_key=ROUTING_KEY,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2  # Persistent message
                )
            )

            logger.info(f"Message published: {message.get('order_id')}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed")


# Initialize publisher
publisher = RabbitMQPublisher()


def validate_order(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate order data"""
    required_fields = ['order_id', 'customer_id', 'items', 'shipping_address']

    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    if not isinstance(data.get('items'), list) or len(data['items']) == 0:
        return False, "Items must be a non-empty list"

    for idx, item in enumerate(data['items']):
        if not all(k in item for k in ('product_id', 'quantity', 'price')):
            return False, f"Item {idx} missing required fields"

    return True, ""


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'order-intake-service',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Validate
        is_valid, error_msg = validate_order(data)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        order = {
            **data,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'received'
        }

        success = publisher.publish_message(order)

        if not success:
            return jsonify({'error': 'Message broker unavailable'}), 503

        return jsonify({
            'message': 'Order created successfully',
            'order_id': data['order_id'],
            'status': 'received',
            'timestamp': order['timestamp']
        }), 201

    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/v1/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    return jsonify({
        'order_id': order_id,
        'status': 'pending',
        'message': 'Mock response - database not connected'
    }), 200


@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'service': 'order-intake-service',
        'rabbitmq_connected': publisher.connection is not None,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


if __name__ == '__main__':
    try:
        logger.info("Starting Order Intake Service on port 5001...")
        app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        publisher.close()
