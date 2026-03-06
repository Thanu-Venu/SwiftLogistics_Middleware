"""
RabbitMQ Publisher - Publishes Order Events
Demonstrates reliable message publishing with persistence and error handling
"""

import json
import pika
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """
    Reliable RabbitMQ Publisher with:
    - Connection pooling
    - Message persistence
    - Error handling and retry logic
    - Monitoring and metrics
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5672,
        username: str = 'guest',
        password: str = 'guest',
        vhost: str = '/',
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.connection = None
        self.channel = None
        self.metrics = {
            'published': 0,
            'failed': 0,
            'retried': 0
        }
        
        self._initialize()
    
    def _initialize(self):
        """Initialize RabbitMQ connection and declare resources"""
        self._connect()
        self._declare_resources()
    
    def _connect(self):
        """Establish connection to RabbitMQ with retries"""
        for attempt in range(self.max_retries):
            try:
                credentials = pika.PlainCredentials(self.username, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.vhost,
                    credentials=credentials,
                    heartbeat=600,
                    connection_attempts=3,
                    retry_delay=2
                )
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
                return
            
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error("Failed to connect to RabbitMQ after all retries")
                    raise
    
    def _declare_resources(self):
        """Declare exchanges and queues"""
        try:
            # Declare durable exchange
            self.channel.exchange_declare(
                exchange='orders_exchange',
                exchange_type='topic',
                durable=True,
                auto_delete=False
            )
            
            # Declare durable queues
            queues = {
                'cms_queue': 'order.#',
                'ros_queue': 'order.created',
                'wms_queue': 'order.#',
                'archive_queue': 'order.#'
            }
            
            for queue_name, routing_pattern in queues.items():
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    auto_delete=False,
                    arguments={
                        'x-max-length': 1000000  # Max 1M messages
                    }
                )
                
                self.channel.queue_bind(
                    exchange='orders_exchange',
                    queue=queue_name,
                    routing_key=routing_pattern
                )
            
            logger.info("RabbitMQ resources declared successfully")
        
        except Exception as e:
            logger.error(f"Error declaring resources: {str(e)}")
            raise
    
    def publish(
        self,
        message: Dict[str, Any],
        routing_key: str = 'order.created',
        mandatory: bool = False
    ) -> bool:
        """
        Publish message to RabbitMQ
        
        Args:
            message: Message payload as dictionary
            routing_key: RabbitMQ routing key
            mandatory: If True, message must be routable
        
        Returns:
            True if successful, False otherwise
        """
        try:
            body = json.dumps(message)
            
            # Persistent properties
            properties = pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2,  # Persistent
                timestamp=int(time.time()),
                message_id=message.get('message_id'),
                correlation_id=message.get('order_id')
            )
            
            # Publish with mandatory flag
            self.channel.basic_publish(
                exchange='orders_exchange',
                routing_key=routing_key,
                body=body,
                properties=properties,
                mandatory=mandatory
            )
            
            self.metrics['published'] += 1
            logger.info(
                f"Message published - "
                f"RoutingKey: {routing_key}, "
                f"OrderID: {message.get('order_id')}, "
                f"Total: {self.metrics['published']}"
            )
            
            return True
        
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            self.metrics['failed'] += 1
            self._reconnect()
            return False
        
        except Exception as e:
            logger.error(f"Error publishing message: {str(e)}")
            self.metrics['failed'] += 1
            return False
    
    def publish_with_retry(
        self,
        message: Dict[str, Any],
        routing_key: str = 'order.created'
    ) -> bool:
        """Publish with automatic retry logic"""
        for attempt in range(self.max_retries):
            try:
                if self.publish(message, routing_key):
                    return True
                
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} "
                        f"for order {message.get('order_id')}"
                    )
                    self.metrics['retried'] += 1
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
            
            except Exception as e:
                logger.error(f"Retry {attempt + 1} failed: {str(e)}")
        
        return False
    
    def _reconnect(self):
        """Reconnect to RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            
            self._connect()
            self._declare_resources()
        
        except Exception as e:
            logger.error(f"Reconnection failed: {str(e)}")
    
    def publish_batch(self, messages: list, routing_key: str = 'order.created') -> int:
        """
        Publish multiple messages in batch
        
        Returns:
            Number of successfully published messages
        """
        success_count = 0
        
        for message in messages:
            if self.publish(message, routing_key):
                success_count += 1
        
        logger.info(f"Batch publish: {success_count}/{len(messages)} messages published")
        return success_count
    
    def get_metrics(self) -> Dict[str, int]:
        """Get publisher metrics"""
        return self.metrics.copy()
    
    def close(self):
        """Close connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Publisher connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")


# Example usage
def main():
    """Demo publisher"""
    publisher = RabbitMQPublisher(
        host='localhost',
        port=5672,
        username='guest',
        password='guest'
    )
    
    try:
        # Publish single order
        order = {
            'order_id': 'ORD-2026-001',
            'customer_id': 'CUST-123',
            'customer_name': 'John Doe',
            'items': [
                {
                    'product_id': 'PROD-001',
                    'quantity': 2,
                    'price': 29.99
                }
            ],
            'shipping_address': {
                'street': '123 Main St',
                'city': 'Springfield',
                'zip': '12345'
            },
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'received'
        }
        
        publisher.publish(order, routing_key='order.created')
        
        # Publish batch
        batch_orders = [
            {
                'order_id': f'ORD-2026-{100 + i}',
                'customer_id': f'CUST-{i}',
                'items': [
                    {'product_id': 'PROD-001', 'quantity': 1, 'price': 29.99}
                ],
                'shipping_address': {
                    'street': f'{i} Main St',
                    'city': 'City',
                    'zip': '12345'
                },
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'received'
            }
            for i in range(5)
        ]
        
        publisher.publish_batch(batch_orders)
        
        # Print metrics
        metrics = publisher.get_metrics()
        print(f"\nPublisher Metrics:")
        print(f"  Published: {metrics['published']}")
        print(f"  Failed: {metrics['failed']}")
        print(f"  Retried: {metrics['retried']}")
    
    finally:
        publisher.close()


if __name__ == '__main__':
    main()
