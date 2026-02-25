# Message Reliability & Order Processing Guarantee Strategies

## Overview

This document provides strategies to ensure that **no orders are lost** in the SwiftLogistics middleware, even in the face of failures, crashes, and network issues.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Strategy 1: Persistence](#strategy-1-persistence)
3. [Strategy 2: Acknowledgments](#strategy-2-acknowledgments)
4. [Strategy 3: Dead Letter Queues](#strategy-3-dead-letter-queues)
5. [Strategy 4: Idempotency](#strategy-4-idempotency)
6. [Strategy 5: Transactional Outbox](#strategy-5-transactional-outbox)
7. [Strategy 6: Retry Logic](#strategy-6-retry-logic)
8. [Strategy 7: Circuit Breaker](#strategy-7-circuit-breaker)
9. [Complete Reliability Architecture](#complete-reliability-architecture)
10. [Monitoring & Alerting](#monitoring--alerting)

---

## Core Concepts

### Message Loss Scenarios

```
Scenario 1: Publisher Crash
├─ Order submitted to REST API
├─ Order saved to database
├─ Publisher crashes BEFORE publishing to RabbitMQ
└─ Order lost from queue (never processed)

Scenario 2: Network Failure
├─ Order published to RabbitMQ
├─ Network partition occurs
├─ Publisher never receives ACK
└─ Unsure if message was received or not

Scenario 3: Consumer Crash
├─ Order delivered to consumer
├─ Consumer processing (50% complete)
├─ Consumer process crashes
├─ Message auto-ack sent before completion
└─ Order partially processed (inconsistent state)

Scenario 4: Processing Timeout
├─ Order processing takes > consumer timeout
├─ Message redelivered while being processed
├─ Duplicate processing occurs
└─ Data corruption or transaction conflict
```

---

## Strategy 1: Persistence

### RabbitMQ Message Persistence

Ensures messages survive broker crashes.

#### ✓ Enable Persistence

```python
# Publisher: Set delivery_mode=2
channel.basic_publish(
    exchange='orders_exchange',
    routing_key='order.created',
    body=json.dumps(order),
    properties=pika.BasicProperties(
        delivery_mode=2,  # 1 = transient, 2 = persistent
        content_type='application/json'
    )
)
```

#### ✓ Durable Queues

```python
# Consumer: Declare durable queue
channel.queue_declare(
    queue='orders_queue',
    durable=True,  # Survives broker restart
    auto_delete=False  # Not deleted when no consumers
)
```

#### ✓ Durable Exchanges

```python
# Declare durable exchange
channel.exchange_declare(
    exchange='orders_exchange',
    exchange_type='topic',
    durable=True,  # Survives broker restart
    auto_delete=False
)
```

### What Persistence Guarantees

✓ Messages written to disk before ACK sent
✓ Messages survive broker crashes
✓ Queue definitions survive broker restarts

### What Persistence Does NOT Guarantee

✗ Messages aren't lost if publisher crashes before publishing
✗ Messages aren't lost if consumer crashes before ACK

---

## Strategy 2: Acknowledgments

### Manual Acknowledgments (Critical)

Ensures consumer processes message completely before it's removed from queue.

#### ❌ Anti-Pattern: Auto-Acknowledgment

```python
# DANGEROUS: Message removed from queue immediately after delivery
# If consumer crashes, message is lost!
channel.basic_consume(
    queue='orders_queue',
    on_message_callback=callback,
    auto_ack=True  # DON'T DO THIS
)
```

#### ✓ Pattern: Manual Acknowledgment

```python
# CORRECT: Message removed only after callback returns successfully
def callback(ch, method, properties, body):
    try:
        # Process message
        order = json.loads(body)
        process_order(order)
        
        # Only acknowledge after successful processing
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    except Exception as e:
        # If processing fails, negatively acknowledge
        # Message returns to queue for retry
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
        )

# Register callback with auto_ack=False
channel.basic_consume(
    queue='orders_queue',
    on_message_callback=callback,
    auto_ack=False  # Manual control
)
```

### ACK vs NACK Behavior

| Action | Behavior | Message Fate |
|--------|----------|--------------|
| `basic_ack()` | Acknowledge | Removed from queue ✓ |
| `basic_nack(..., requeue=True)` | Negative ACK with requeue | Returns to queue for retry ↻ |
| `basic_nack(..., requeue=False)` | Negative ACK without requeue | Sent to DLQ ✗ |
| No ACK (crash) | Message not acknowledged | Returns to queue after timeout ↻ |

### Implementation Pattern

```python
@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    """REST API with guaranteed delivery"""
    try:
        data = request.get_json()
        
        # 1. Save to database (transactional)
        order = Order(**data)
        db.session.add(order)
        db.session.commit()  # Durable storage
        
        # 2. Publish to RabbitMQ
        success = publisher.publish_with_retry(order.to_dict())
        
        if success:
            return jsonify({'order_id': order.id}), 201
        else:
            # Log for manual recovery
            logger.critical(f"Failed to publish order {order.id}")
            return jsonify({'error': 'Processing failed'}), 500
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

---

## Strategy 3: Dead Letter Queues (DLQ)

### Purpose

Capture messages that fail processing after max retries.

### Architecture

```
Main Processing Queue
    ├─ Message 1: Success → ACK → Removed
    ├─ Message 2: Fail 3 times → NACK → DLQ
    ├─ Message 3: Success → ACK → Removed
    └─ Message 4: Fail 3 times → NACK → DLQ
         │
         └──────────────────────────────┐
                                        │
                            Dead Letter Queue
                                        │
                            ┌───────────┴───────────┐
                            │                       │
                        Review              Fix & Retry
                       (Manual)             (Automatic)
```

### Implementation

#### Declare DLX and DLQ

```python
# Dead Letter Exchange (DLX)
channel.exchange_declare(
    exchange='orders_dlx',
    exchange_type='topic',
    durable=True
)

# Dead Letter Queue (DLQ)
channel.queue_declare(
    queue='orders_queue_dlq',
    durable=True
)

# Bind DLQ to DLX
channel.queue_bind(
    exchange='orders_dlx',
    queue='orders_queue_dlq',
    routing_key='*'
)

# Configure main queue to use DLX
channel.queue_declare(
    queue='orders_queue',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'orders_dlx',
        'x-max-retries': 3  # Custom: max retry count
    }
)
```

#### Message Flow

```python
def callback(ch, method, properties, body):
    retry_count = properties.headers.get('x-death', [{}])[0].get('count', 0)
    
    try:
        order = json.loads(body)
        process_order(order)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    except Exception as e:
        if retry_count < 3:
            # Requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            logger.warning(f"Retry {retry_count + 1}/3 for order {order['order_id']}")
        else:
            # Max retries exceeded, send to DLQ
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.error(f"Order {order['order_id']} sent to DLQ after max retries")
```

### DLQ Handler (Manual Recovery)

```python
def dlq_handler():
    """Monitor DLQ and handle failed messages"""
    
    def callback(ch, method, properties, body):
        order = json.loads(body)
        
        logger.critical(
            f"DLQ Message: {order['order_id']} - "
            f"Attempt {properties.headers.get('x-death', [{}])[0].get('count')}"
        )
        
        # Option 1: Manual review
        # - Alert human operator
        # - Manual inspection and fix
        # - Requeue after fix
        
        # Option 2: Automatic recovery attempt
        try:
            # Try to fix the issue
            if is_recoverable(order):
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except:
            pass
        
        # Record in database for manual review
        FailedOrder.create(order_data=order, reason='DLQ')
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    channel.basic_consume(
        queue='orders_queue_dlq',
        on_message_callback=callback,
        auto_ack=False
    )
    channel.start_consuming()
```

---

## Strategy 4: Idempotency

### Problem: Duplicate Processing

```
Scenario: Message delivered twice
├─ Order 1 processed successfully
├─ Consumer sends ACK
├─ Network fails, ACK not received
├─ Message redelivered
└─ Order 1 processed AGAIN (duplicate payment, duplicate inventory!)
```

### Solution: Idempotent Processing

Process same message multiple times with same result.

### Implementation Pattern

```python
def process_order(order):
    # Use order_id as idempotency key
    idempotency_key = f"order:{order['order_id']}"
    
    # Check if already processed
    existing = cache.get(idempotency_key)
    if existing:
        logger.info(f"Order {order['order_id']} already processed, returning cached result")
        return existing
    
    # Process
    result = do_processing(order)
    
    # Cache result (with TTL)
    cache.set(idempotency_key, result, ttl=3600)  # 1 hour
    
    return result
```

### Database-Level Idempotency

```python
def create_order_idempotent(order_data):
    """Use database unique constraint to ensure idempotency"""
    
    try:
        # Attempt insert with unique constraint on order_id
        order = Order(
            order_id=order_data['order_id'],
            customer_id=order_data['customer_id'],
            total_amount=order_data['total_amount'],
            status='PROCESSED'
        )
        db.session.add(order)
        db.session.commit()
        return order
    
    except IntegrityError:
        # Order already exists
        db.session.rollback()
        existing = Order.query.filter_by(order_id=order_data['order_id']).first()
        logger.info(f"Order {order_data['order_id']} already exists")
        return existing
```

### What Idempotency Requires

✓ Unique identifier for each message (order_id)
✓ Result storage (cache or database)
✓ Comparison logic to detect duplicates

---

## Strategy 5: Transactional Outbox

### Problem: Dual Write

```
Risky approach:
1. Save order to database
2. Publish to RabbitMQ (crash here?)
→ Order in DB but not in queue!
```

### Solution: Outbox Pattern

```
Safe approach:
1. Save order to database
2. Save event to outbox table (same transaction)
3. Separate process reads outbox and publishes
→ Atomic write or nothing!
```

### Implementation

#### Database Schema

```sql
CREATE TABLE orders (
    order_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    total_amount DECIMAL(10, 2),
    status VARCHAR(20),
    created_at TIMESTAMP,
    PRIMARY KEY (order_id)
);

CREATE TABLE outbox (
    outbox_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_id VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(255) NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    UNIQUE KEY unique_unpublished (aggregate_id, aggregate_type, event_type)
);

CREATE INDEX idx_unpublished ON outbox(published_at) WHERE published_at IS NULL;
```

#### Transactional Write

```python
def create_order_with_outbox(order_data):
    """Create order and add outbox event in single transaction"""
    
    try:
        # Single transaction
        with db.transaction():
            # 1. Create order
            order = Order(
                order_id=order_data['order_id'],
                customer_id=order_data['customer_id'],
                total_amount=order_data['total_amount'],
                status='RECEIVED'
            )
            db.session.add(order)
            db.session.flush()  # Get order_id
            
            # 2. Add to outbox (in same transaction)
            outbox_entry = OutboxEvent(
                aggregate_id=order.order_id,
                aggregate_type='Order',
                event_type='OrderCreated',
                payload={
                    'order_id': order.order_id,
                    'customer_id': order.customer_id,
                    'total_amount': order.total_amount,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            db.session.add(outbox_entry)
            
            # Commit both atomically
            db.session.commit()
        
        return order
    
    except Exception:
        db.session.rollback()
        raise
```

#### Outbox Publisher (Background Process)

```python
def publish_outbox_events():
    """Periodically read unpublished events and publish them"""
    
    while True:
        try:
            # Read unpublished events
            unpublished = db.session.query(OutboxEvent).filter(
                OutboxEvent.published_at == None
            ).limit(100).all()
            
            for event in unpublished:
                try:
                    # Publish to RabbitMQ
                    publisher.publish(
                        message=event.payload,
                        routing_key=f"order.{event.event_type}"
                    )
                    
                    # Mark as published
                    event.published_at = datetime.utcnow()
                    db.session.commit()
                    
                    logger.info(f"Published event {event.event_type} for {event.aggregate_id}")
                
                except Exception as e:
                    logger.error(f"Failed to publish event: {str(e)}")
                    db.session.rollback()
            
            # Sleep before next poll
            time.sleep(5)  # Poll every 5 seconds
        
        except Exception as e:
            logger.error(f"Outbox error: {str(e)}")
            time.sleep(10)
```

### Why This Works

1. **Atomicity:** Order and event written together or not at all
2. **Durability:** Both persisted in database
3. **Eventual Consistency:** Publisher eventually publishes all events
4. **Recovery:** If publisher crashes, it reads and publishes remaining events on restart

---

## Strategy 6: Retry Logic

### Exponential Backoff

Prevents overwhelming the system when services are down.

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),  # Max 5 attempts
    wait=wait_exponential(
        multiplier=1,  # Base multiplier
        min=2,         # Minimum 2 seconds
        max=60         # Maximum 60 seconds
    )
)
def publish_with_backoff(message):
    """
    Retry delays:
    1st attempt: Immediate
    2nd attempt: 2 seconds
    3rd attempt: 4 seconds
    4th attempt: 8 seconds
    5th attempt: 16 seconds
    6th attempt: Stop (max attempts reached)
    """
    publisher.publish(message)
```

### Jittered Backoff (Prevent Thundering Herd)

```python
import random

def publish_with_jitter(message, attempt=1, max_attempts=5):
    """Add randomness to prevent all services retrying at once"""
    
    try:
        publisher.publish(message)
    
    except Exception as e:
        if attempt < max_attempts:
            # Exponential backoff with jitter
            base_delay = 2 ** attempt
            jitter = random.uniform(0, base_delay)
            delay = min(60, base_delay + jitter)
            
            logger.warning(f"Retry {attempt}/{max_attempts} after {delay:.1f}s: {str(e)}")
            time.sleep(delay)
            
            return publish_with_jitter(message, attempt + 1, max_attempts)
        else:
            logger.error(f"Max retries exceeded: {str(e)}")
            raise
```

---

## Strategy 7: Circuit Breaker

### Problem: Cascading Failures

```
Scenario: RabbitMQ broker down
├─ Publisher keeps retrying
├─ Connection timeout = 30 seconds
├─ 5 retries × 30 seconds = 150 seconds delay
├─ REST API times out
└─ Customers get 500 errors
```

### Solution: Circuit Breaker

```
Normal        Degraded          Failed
  ✓    →         ⚠      →         ✗
(allow)     (partial allow)    (fail fast)
    ↓             ↓                ↓
All calls     Some calls      Immediate
succeed       fail after       error,
              timeout        check health
                              every 30s
```

### Implementation

```python
from pybreaker import CircuitBreaker

# Create circuit breaker
breaker = CircuitBreaker(
    fail_max=5,           # Fail 5 times before opening
    reset_timeout=60,     # Try again after 60 seconds
    listeners=[
        CircuitBreakerListener()  # Custom listener
    ]
)

def publish_with_breaker(message):
    """Publish with circuit breaker protection"""
    
    try:
        # If circuit is OPEN, raises CircuitBreakerListenerError
        with breaker:
            publisher.publish(message)
    
    except CircuitBreakerListenerError:
        logger.error("Circuit breaker OPEN - RabbitMQ appears down")
        # Return error quickly without retrying
        raise Exception("Service unavailable")
    
    except Exception as e:
        # Circuit breaker tracks failures
        logger.error(f"Publish failed: {str(e)}")
        raise
```

### States

| State | Behavior | When |
|-------|----------|------|
| CLOSED | Allow all calls | Normal, healthy |
| OPEN | Reject calls | Too many failures |
| HALF_OPEN | Allow trial call | Reset timeout reached |

---

## Complete Reliability Architecture

### Message Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT REQUEST                             │
│              POST /api/v1/orders → Create Order                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
        ┌────────────────────┐
        │  SAVE TO DATABASE  │
        │  (Durable Storage) │
        └────────┬───────────┘
                 │
                 ↓
        ┌────────────────────┐
        │  ADD TO OUTBOX     │
        │  (Same Transaction)│
        └────┬───────────────┘
             │
        ┌────┴──────────────────────┐
        │   Return 201 to Client    │
        │   (Order Confirmed)       │
        └────┬──────────────────────┘
             │ (Asynchronous)
             ↓
    ┌──────────────────────┐
    │ OUTBOX POLLER        │
    │ (Background Process) │
    └────────┬─────────────┘
             │
             ├─ Read unpublished events
             ├─ Publish to RabbitMQ
             │  (with Circuit Breaker)
             │  (with Exponential Backoff)
             │  (with Jitter)
             └─ Mark as published
                     │
                     ↓
        ┌──────────────────────────┐
        │ RabbitMQ BROKER          │
        │ (Durable Exchange)       │
        │ (Durable Queue)          │
        │ (Persistent Messages)    │
        └────────┬─────────────────┘
                 │
        ┌────────┴──────────────────┬─────────────────┐
        │                           │                 │
        ↓                           ↓                 ↓
    ┌────────────┐          ┌────────────┐      ┌────────────┐
    │ CMS Queue  │          │ ROS Queue  │      │ WMS Queue  │
    │ (Prefetch) │          │ (Prefetch) │      │ (Prefetch) │
    └─────┬──────┘          └─────┬──────┘      └─────┬──────┘
          │                       │                    │
          ↓                       ↓                    ↓
    ┌─────────────┐         ┌─────────────┐    ┌──────────────┐
    │ CMS Consumer│         │ ROS Consumer│    │ WMS Consumer │
    │             │         │             │    │              │
    │ 1. Receive  │         │ 1. Receive  │    │ 1. Receive   │
    │ 2. Process  │         │ 2. Process  │    │ 2. Process   │
    │ 3. Success? │         │ 3. Success? │    │ 3. Success?  │
    │    ├─ Yes   │         │    ├─ Yes   │    │    ├─ Yes    │
    │    │ ACK    │         │    │ ACK    │    │    │ ACK      │
    │    │ ↓ Rem. │         │    │ ↓ Rem. │    │    │ ↓ Rem.   │
    │    └─ No    │         │    └─ No    │    │    └─ No     │
    │       NACK  │         │       NACK  │    │       NACK   │
    │    ↓ Requeue│         │    ↓ Requeue│    │    ↓ Requeue │
    └─────────────┘         └─────────────┘    └──────────────┘
         │ (Failure)            │ (Failure)        │ (Failure)
         │ After 3 retries      │ After 3 retries  │ After 3 retries
         │                      │                  │
         ↓                      ↓                  ↓
    ┌──────────────────────────────────────────────────────┐
    │ DEAD LETTER QUEUE                                    │
    │ (For Manual Review & Recovery)                       │
    │                                                      │
    │ Format:                                              │
    │ {                                                    │
    │   "order_id": "ORD-2026-001",                        │
    │   "error": "Inventory allocation failed",            │
    │   "attempts": 3,                                     │
    │   "last_error_time": "2026-02-04T12:05:00"          │
    │ }                                                    │
    └──────────────────────────────────────────────────────┘
              │
              └─ Manual Review Process
                   ├─ Analyze root cause
                   ├─ Fix underlying issue
                   ├─ Republish to main queue
                   └─ Order eventually processed
```

---

## Monitoring & Alerting

### Key Metrics

```python
# Publisher metrics
publisher_messages_sent = Counter('publisher_messages_sent_total')
publisher_messages_failed = Counter('publisher_messages_failed_total')
publisher_publish_latency = Histogram('publisher_publish_latency_seconds')
publisher_retries = Counter('publisher_retries_total')

# Consumer metrics
consumer_messages_received = Counter('consumer_messages_received_total')
consumer_messages_processed = Counter('consumer_messages_processed_total')
consumer_messages_failed = Counter('consumer_messages_failed_total')
consumer_process_latency = Histogram('consumer_process_latency_seconds')
consumer_nacks = Counter('consumer_nacks_total')

# Queue metrics
queue_depth = Gauge('queue_depth')  # Should not grow unbounded
queue_age = Gauge('queue_message_age_seconds')  # How long message in queue

# DLQ metrics
dlq_depth = Gauge('dlq_depth')  # Critical alert if > 0
dlq_messages_total = Counter('dlq_messages_total')
```

### Alerting Rules

```yaml
# Alert if DLQ has messages (indicates persistent failures)
- alert: DLQHasMessages
  expr: dlq_depth > 0
  for: 1m
  annotations:
    summary: "Dead Letter Queue has {{ $value }} messages"
    action: "Check DLQ and fix root cause"

# Alert if queue is backing up
- alert: QueueDepthHigh
  expr: queue_depth > 10000
  for: 5m
  annotations:
    summary: "Queue depth: {{ $value }} (threshold: 10000)"
    action: "Scale consumers or check for processing bottlenecks"

# Alert if message age is high
- alert: MessageAgeTooHigh
  expr: queue_message_age_seconds > 300  # 5 minutes
  for: 5m
  annotations:
    summary: "Messages waiting {{ $value }}s in queue"
    action: "Messages are delayed, check consumer health"

# Alert if publish failure rate high
- alert: PublishFailureRate
  expr: rate(publisher_messages_failed_total[5m]) > 0.01  # 1% failure
  for: 1m
  annotations:
    summary: "Publish failure rate: {{ $value }}"
    action: "Check RabbitMQ connectivity and broker health"
```

### Health Check Endpoint

```python
@app.route('/health/detailed', methods=['GET'])
def detailed_health():
    """Comprehensive health check"""
    return {
        'status': 'healthy',
        'components': {
            'database': check_database(),
            'rabbitmq': check_rabbitmq(),
            'publisher': {
                'connected': publisher.is_connected(),
                'messages_published': publisher.metrics['published'],
                'messages_failed': publisher.metrics['failed']
            },
            'consumers': {
                'cms': {
                    'messages_processed': cms_consumer.metrics['processed'],
                    'messages_failed': cms_consumer.metrics['failed']
                },
                'ros': {
                    'messages_processed': ros_consumer.metrics['processed'],
                    'messages_failed': ros_consumer.metrics['failed']
                }
            },
            'queue_stats': {
                'orders_queue_depth': get_queue_depth('orders_queue'),
                'dlq_depth': get_queue_depth('orders_queue_dlq'),
                'average_message_age': get_message_age('orders_queue')
            }
        }
    }
```

---

## Summary: Reliability Checklist

- [ ] **Persistence:** Messages and queues are durable
- [ ] **Acknowledgments:** Using manual ACK, not auto-ack
- [ ] **Dead Letter Queue:** Configured for failed messages
- [ ] **Idempotency:** All operations are safe to retry
- [ ] **Outbox Pattern:** Orders saved before publishing
- [ ] **Retry Logic:** Exponential backoff configured
- [ ] **Circuit Breaker:** Prevents cascading failures
- [ ] **Monitoring:** Metrics and alerting in place
- [ ] **Testing:** Chaos engineering tests for failure scenarios
- [ ] **Documentation:** Runbooks for operational issues

---

## References

1. **Apache Kafka Blog:** The Log: What every software engineer should know about real-time data's unifying abstraction
2. **RabbitMQ Docs:** Reliability Features
3. **Microsoft Patterns:** Saga Pattern, Circuit Breaker Pattern
4. **Redis Streams:** Message Reliability Guarantees
5. **Temporal Workflows:** Distributed Transaction Orchestration
