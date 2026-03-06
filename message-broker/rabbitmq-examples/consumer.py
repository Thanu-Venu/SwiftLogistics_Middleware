"""
RabbitMQ Consumer - Processes Order Events
Demonstrates reliable message consumption with acknowledgments and error handling
"""

import json
import pika
import logging
from datetime import datetime
from typing import Callable, Dict, Any
import signal
import sys
from abc import ABC, abstractmethod

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrderProcessor(ABC):
    """Abstract base class for order processors"""
    
    @abstractmethod
    def process(self, order: Dict[str, Any]) -> bool:
        """
        Process an order
        
        Returns:
            True if successful, False if should retry
        """
        pass


class CMSOrderProcessor(OrderProcessor):
    """Process orders in the CMS"""
    
    def process(self, order: Dict[str, Any]) -> bool:
        logger.info(f"CMS processing order {order.get('order_id')}")
        # Simulate processing
        return True


class ROSOrderProcessor(OrderProcessor):
    """Process orders in the Route Optimization Service"""
    
    def process(self, order: Dict[str, Any]) -> bool:
        logger.info(f"ROS calculating route for order {order.get('order_id')}")
        # Simulate processing
        return True


class WMSOrderProcessor(OrderProcessor):
    """Process orders in the Warehouse Management System"""
    
    def process(self, order: Dict[str, Any]) -> bool:
        logger.info(f"WMS allocating inventory for order {order.get('order_id')}")
        # Simulate processing
        return True


class RabbitMQConsumer:
    """
    Reliable RabbitMQ Consumer with:
    - Manual acknowledgments (no message loss)
    - Prefetch count management
    - Error handling with dead letter queues
    - Graceful shutdown
    """
    
    def __init__(
        self,
        queue_name: str,
        processor: OrderProcessor,
        host: str = 'localhost',
        port: int = 5672,
        username: str = 'guest',
        password: str = 'guest',
        vhost: str = '/',
        prefetch_count: int = 10
    ):
        self.queue_name = queue_name
        self.processor = processor
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.prefetch_count = prefetch_count
        
        self.connection = None
        self.channel = None
        self.running = False
        
        self.metrics = {
            'received': 0,
            'processed': 0,
            'failed': 0,
            'nacked': 0
        }
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._connect()
        self._declare_resources()
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received, stopping consumer...")
        self.stop()
        sys.exit(0)
    
    def _connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                heartbeat=600
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
        
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
    
    def _declare_resources(self):
        """Declare exchanges, queues, and dead letter queue"""
        try:
            # Main exchange
            self.channel.exchange_declare(
                exchange='orders_exchange',
                exchange_type='topic',
                durable=True
            )
            
            # Dead letter exchange (for failed messages)
            self.channel.exchange_declare(
                exchange='orders_dlx',
                exchange_type='topic',
                durable=True
            )
            
            # Dead letter queue
            self.channel.queue_declare(
                queue=f'{self.queue_name}_dlq',
                durable=True
            )
            
            self.channel.queue_bind(
                exchange='orders_dlx',
                queue=f'{self.queue_name}_dlq',
                routing_key='*'
            )
            
            # Main queue with DLX configuration
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': 'orders_dlx',
                    'x-max-length': 1000000
                }
            )
            
            self.channel.queue_bind(
                exchange='orders_exchange',
                queue=self.queue_name,
                routing_key='order.*'
            )
            
            # Set QoS (prefetch)
            self.channel.basic_qos(prefetch_count=self.prefetch_count)
            
            logger.info(f"Queue '{self.queue_name}' declared with DLQ")
        
        except Exception as e:
            logger.error(f"Error declaring resources: {str(e)}")
            raise
    
    def start(self):
        """Start consuming messages"""
        try:
            self.running = True
            
            logger.info(
                f"Starting consumer for queue '{self.queue_name}' "
                f"with prefetch={self.prefetch_count}"
            )
            
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self._message_callback,
                auto_ack=False  # CRITICAL: Manual acknowledgment
            )
            
            self.channel.start_consuming()
        
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Consumer error: {str(e)}")
            raise
    
    def _message_callback(self, ch, method, properties, body):
        """
        Process incoming message with error handling
        
        Auto-ACK: Don't send ACK until processing completes
        Requeue on failure: Failed messages return to queue
        DLQ: Messages that fail max retries go to DLQ
        """
        delivery_tag = method.delivery_tag
        
        try:
            self.metrics['received'] += 1
            
            # Parse message
            message = json.loads(body)
            order_id = message.get('order_id')
            
            logger.info(f"Received message: {order_id}")
            
            # Process order
            if self._process_order(message):
                # Success: Acknowledge message
                ch.basic_ack(delivery_tag=delivery_tag)
                self.metrics['processed'] += 1
                logger.info(f"Order {order_id} processed successfully")
            else:
                # Failure: Negative acknowledge with requeue
                ch.basic_nack(
                    delivery_tag=delivery_tag,
                    requeue=True  # Return to queue for retry
                )
                self.metrics['nacked'] += 1
                logger.warning(f"Order {order_id} processing failed, requeued")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {str(e)}")
            # Don't requeue malformed messages
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
            self.metrics['failed'] += 1
        
        except Exception as e:
            logger.error(f"Message processing error: {str(e)}")
            # Requeue for retry
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
            self.metrics['failed'] += 1
    
    def _process_order(self, order: Dict[str, Any]) -> bool:
        """Process order using configured processor"""
        try:
            return self.processor.process(order)
        except Exception as e:
            logger.error(f"Processor error: {str(e)}")
            return False
    
    def stop(self):
        """Stop consuming messages"""
        self.running = False
        
        try:
            self.channel.stop_consuming()
            self.connection.close()
            logger.info("Consumer stopped")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get consumer metrics"""
        return self.metrics.copy()


class MultiConsumer:
    """
    Manages multiple consumers for different services
    """
    
    def __init__(self):
        self.consumers = {}
    
    def add_consumer(
        self,
        queue_name: str,
        processor: OrderProcessor,
        prefetch_count: int = 10
    ):
        """Register a new consumer"""
        consumer = RabbitMQConsumer(
            queue_name=queue_name,
            processor=processor,
            prefetch_count=prefetch_count
        )
        self.consumers[queue_name] = consumer
        logger.info(f"Consumer registered for {queue_name}")
    
    def start_all(self):
        """Start all consumers (blocking)"""
        if len(self.consumers) == 0:
            raise ValueError("No consumers registered")
        
        # For simplicity, start the first consumer
        # In production, use threading or asyncio for parallel consumption
        first_consumer = list(self.consumers.values())[0]
        first_consumer.start()


# Example usage
def main():
    """Demo consumer setup"""
    
    # Create processors
    cms_processor = CMSOrderProcessor()
    ros_processor = ROSOrderProcessor()
    wms_processor = WMSOrderProcessor()
    
    # Create consumers
    cms_consumer = RabbitMQConsumer(
        queue_name='cms_queue',
        processor=cms_processor,
        prefetch_count=10
    )
    
    logger.info("Starting CMS consumer (press Ctrl+C to stop)...")
    
    try:
        cms_consumer.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        metrics = cms_consumer.get_metrics()
        print(f"\nConsumer Metrics:")
        print(f"  Received: {metrics['received']}")
        print(f"  Processed: {metrics['processed']}")
        print(f"  Failed: {metrics['failed']}")
        print(f"  Nacked: {metrics['nacked']}")


if __name__ == '__main__':
    main()
