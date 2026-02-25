# RabbitMQ Publisher and Consumer Guide

## Overview

This directory contains production-ready examples of RabbitMQ publisher and consumer implementations for the SwiftLogistics middleware.

## Files

- `publisher.py` - Reliable order publisher with retry logic
- `consumer.py` - Order consumer with manual acknowledgments

## Key Concepts

### Publisher (publisher.py)

**Reliable Publishing Features:**

1. **Persistent Messages** - Messages survive broker restart
   ```python
   delivery_mode=2  # 1 = transient, 2 = persistent
   ```

2. **Message Metadata**
   - `message_id`: Unique message identifier
   - `correlation_id`: Order ID for tracking
   - `timestamp`: When message was published

3. **Error Handling**
   ```python
   - Connection failures trigger reconnection
   - Automatic retry with exponential backoff
   - Metrics tracking (published, failed, retried)
   ```

4. **Batch Publishing**
   ```python
   publisher.publish_batch(orders)  # Efficient bulk operations
   ```

### Consumer (consumer.py)

**Reliable Consumption Features:**

1. **Manual Acknowledgments** - Critical for reliability
   ```python
   ch.basic_ack(delivery_tag=delivery_tag)      # Success
   ch.basic_nack(delivery_tag=delivery_tag, requeue=True)  # Retry
   ```

2. **Prefetch Control** - Prevents message loss on consumer crash
   ```python
   channel.basic_qos(prefetch_count=10)  # Process only 10 at a time
   ```

3. **Dead Letter Queue** - Capture failed messages
   ```
   Main Queue (failures after retries)
        ↓
   Dead Letter Exchange (orders_dlx)
        ↓
   Dead Letter Queue (cms_queue_dlq)
   ```

4. **Processor Pattern** - Pluggable order processing
   ```python
   class OrderProcessor(ABC):
       @abstractmethod
       def process(self, order) -> bool:
           pass
   ```

5. **Graceful Shutdown** - Signal handling
   ```python
   SIGINT/SIGTERM triggers clean shutdown
   ```

## Running Examples

### Prerequisites

```bash
# Install dependencies
pip install pika

# Ensure RabbitMQ is running
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management
```

### Run Publisher

```bash
python publisher.py
```

Output:
```
2026-02-04 12:00:00 - __main__ - INFO - Connected to RabbitMQ at localhost:5672
2026-02-04 12:00:00 - __main__ - INFO - RabbitMQ resources declared successfully
2026-02-04 12:00:01 - __main__ - INFO - Message published - RoutingKey: order.created, OrderID: ORD-2026-001, Total: 1
```

### Run Consumer

```bash
python consumer.py
```

Output:
```
2026-02-04 12:00:00 - __main__ - INFO - Connected to RabbitMQ at localhost:5672
2026-02-04 12:00:00 - __main__ - INFO - Starting consumer for queue 'cms_queue' with prefetch=10
2026-02-04 12:00:01 - __main__ - INFO - Received message: ORD-2026-001
2026-02-04 12:00:01 - __main__ - INFO - CMS processing order ORD-2026-001
2026-02-04 12:00:01 - __main__ - INFO - Order ORD-2026-001 processed successfully
```

## Message Flow

```
┌──────────┐
│ Publisher│
└────┬─────┘
     │ (publishes to orders_exchange with routing_key=order.created)
     ↓
┌──────────────────┐
│ RabbitMQ Broker  │
│ orders_exchange  │
└────┬─────────────┘
     │ (routes based on binding)
     ↓
┌──────────────────┐
│ cms_queue        │
│ (durable)        │ ← Messages persisted here
│ (prefetch=10)    │
└────┬─────────────┘
     │
     ↓
┌──────────────────┐
│ Consumer         │
│ (manual ACK)     │
└────┬─────────────┘
     │
     ├─ Success? → Send ACK → Message deleted from queue
     │
     └─ Failure? → Send NACK (requeue=true) → Message returns to queue
                                    ↓
                        (after max retries)
                                    ↓
                          Dead Letter Queue
```

## Configuration Examples

### High Throughput Consumer
```python
consumer = RabbitMQConsumer(
    queue_name='ros_queue',
    processor=ros_processor,
    prefetch_count=20  # Process 20 in parallel
)
```

### Low Latency Consumer
```python
consumer = RabbitMQConsumer(
    queue_name='cms_queue',
    processor=cms_processor,
    prefetch_count=5  # Process 5 in parallel
)
```

### Batch Publisher
```python
orders = [...]  # 1000 orders
published = publisher.publish_batch(orders)
print(f"Published {published}/1000 orders")
```

## Message Format

All messages are JSON:

```json
{
  "order_id": "ORD-2026-001",
  "customer_id": "CUST-123",
  "customer_name": "John Doe",
  "items": [
    {
      "product_id": "PROD-001",
      "quantity": 2,
      "price": 29.99
    }
  ],
  "shipping_address": {
    "street": "123 Main St",
    "city": "Springfield",
    "zip": "12345"
  },
  "timestamp": "2026-02-04T12:00:00",
  "status": "received"
}
```

## Monitoring

### Check Queue Depth

```bash
# Via RabbitMQ Management UI (http://localhost:15672)
# Or via rabbitmqctl
docker exec rabbitmq rabbitmqctl list_queues

# Output:
# Listing queues for vhost / ...
# cms_queue       45
# ros_queue       12
# wms_queue       8
```

### View Dead Letter Queue

```bash
# Messages that failed after max retries are in DLQ
# cms_queue_dlq contains failed orders
```

## Troubleshooting

### Messages not being consumed

```python
# Check 1: Ensure queue is bound to exchange
consumer.channel.queue_bind(
    exchange='orders_exchange',
    queue='cms_queue',
    routing_key='order.*'
)

# Check 2: Verify prefetch count
consumer.channel.basic_qos(prefetch_count=10)

# Check 3: Check consumer callback is registered
consumer.channel.basic_consume(
    queue='cms_queue',
    on_message_callback=callback,
    auto_ack=False
)
```

### Messages being lost

```python
# Ensure persistent delivery mode
properties=pika.BasicProperties(delivery_mode=2)

# Ensure manual acknowledgment
auto_ack=False
ch.basic_ack(delivery_tag=delivery_tag)  # Only after success
```

### Consumer crashes and loses messages

```python
# Solution 1: Use manual acknowledgment (prefetch works)
auto_ack=False
ch.basic_qos(prefetch_count=10)

# Solution 2: Use durable queues
queue_declare(queue='cms_queue', durable=True)

# Solution 3: Use Dead Letter Queue for recovery
arguments={'x-dead-letter-exchange': 'orders_dlx'}
```

## Performance Tuning

| Setting | Value | Use Case |
|---------|-------|----------|
| prefetch_count | 5-10 | Reliable processing, error handling critical |
| prefetch_count | 20-50 | High throughput, fast processors |
| delivery_mode | 2 | All production scenarios |
| heartbeat | 600 | Default (10 min), good for most cases |
| channel.basic_qos | Per consumer | Apply before basic_consume |

## Production Considerations

1. **Connection Pooling** - Reuse connections across threads
2. **Circuit Breaker** - Stop retrying if service is down
3. **Timeout Handling** - Set processing timeout per message
4. **Metrics** - Track published, consumed, failed, retried
5. **Logging** - Log all significant events
6. **DLQ Monitoring** - Alert on messages in DLQ
7. **Graceful Shutdown** - Process remaining messages before shutdown
