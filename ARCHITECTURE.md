# SwiftLogistics Middleware Architecture

## Table of Contents
1. [Middleware Architecture Overview](#middleware-architecture-overview)
2. [System Integration Patterns](#system-integration-patterns)
3. [Asynchronous Processing Architecture](#asynchronous-processing-architecture)
4. [Saga Pattern for Distributed Transactions](#saga-pattern-for-distributed-transactions)
5. [Message Reliability Strategies](#message-reliability-strategies)
6. [Deployment Architecture](#deployment-architecture)

---

## Middleware Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  (Web Portal, Mobile App, Partner Systems)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴─────────────┐
        │                          │
┌───────▼──────────┐      ┌────────▼──────────┐
│   REST API       │      │   SOAP Web        │
│   (Flask)        │      │   Service         │
│   :5001          │      │   :5002           │
└───────┬──────────┘      └────────┬──────────┘
        │                          │
        └────────────┬─────────────┘
                     │
        ┌────────────▼──────────────┐
        │  MIDDLEWARE ORCHESTRATOR   │
        │  (Core Processing Logic)   │
        │  - Transformation          │
        │  - Validation              │
        │  - Routing                 │
        │  - Error Handling          │
        └────────────┬───────────────┘
                     │
        ┌────────────▼──────────────────┐
        │   MESSAGE BROKER (RabbitMQ)   │
        │  - Asynchronous Communication │
        │  - Message Queuing            │
        │  - Pub/Sub Pattern            │
        └────────────┬──────────────────┘
        │
    ┌───┴──────┬──────────┬──────────┐
    │          │          │          │
┌───▼──┐  ┌───▼──┐  ┌───▼──┐  ┌───▼──┐
│ CMS  │  │ ROS  │  │ WMS  │  │ TCP  │
│Queue │  │Queue │  │Queue │  │ Sink │
│      │  │      │  │      │  │      │
└──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘
   │         │         │         │
┌──▼──┐  ┌──▼──┐  ┌──▼──┐      │
│ CMS │  │ ROS │  │ WMS │      │
│:80  │  │:81  │  │:82  │      │
└─────┘  └─────┘  └─────┘   ┌──▼──────┐
                             │TCP/IP   │
                             │Server   │
                             │:9000    │
                             └─────────┘
```

### Core Components

| Component | Role | Protocol | Technology |
|-----------|------|----------|-----------|
| **REST API Gateway** | Order intake & queries | HTTP/REST | Flask |
| **SOAP Service** | Legacy system integration | SOAP/XML | zeep |
| **Middleware Orchestrator** | Business logic & routing | In-Process | Python |
| **Message Broker** | Asynchronous messaging | AMQP | RabbitMQ |
| **CMS Service** | Order management | REST/SOAP | Python |
| **ROS Service** | Routing & optimization | REST | Python |
| **WMS Service** | Warehouse management | REST | Python |
| **TCP/IP Sink** | Legacy TCP systems | TCP Binary | Python |

---

## System Integration Patterns

### 1. **Adapter Pattern (Protocol Translation)**

Translates between different protocols:
- REST ↔ SOAP conversion
- JSON ↔ XML transformation
- Different data format mappings

```
REST Client → REST API Gateway → Adapter → SOAP Backend
                                    ↓
                            XML Serialization
                                    ↓
                            SOAP Envelope
```

### 2. **Facade Pattern (Simplified Interface)**

Provides unified interface to multiple heterogeneous systems:
- Single entry point for all order operations
- Abstracts system complexity
- Handles cross-system coordination

```
Client → Facade → {CMS, ROS, WMS} Operations
```

### 3. **Message Queue Pattern (Decoupling)**

Decouples producers from consumers:
- Order submitter doesn't wait for processing
- Multiple consumers can process independently
- Enables retry logic and backpressure

```
Producer → Message Queue ← Consumer 1
                        ← Consumer 2
                        ← Consumer 3
```

### 4. **Orchestration Pattern (Workflow Coordination)**

Centralized control of multi-step workflows:
- Middleware orchestrator coordinates all steps
- Tracks state and transitions
- Handles failures and retries

```
Order Received → CMS Processing ✓
              → ROS Routing ✓
              → WMS Pickup ✓
              → Confirmation
```

---

## Asynchronous Processing Architecture

### Pattern: Event-Driven Asynchronous Processing

```
┌──────────────────────────────────────────────────────┐
│  SYNCHRONOUS REQUEST-RESPONSE (REST API)             │
│  Returns immediately with order confirmation         │
└──────────────┬───────────────────────────────────────┘
               │
         ┌─────▼──────┐
         │ Order Event│
         │ Published  │
         └─────┬──────┘
               │
    ┌──────────┴──────────┬──────────┐
    │                     │          │
┌───▼────────┐    ┌──────▼──┐  ┌───▼────────┐
│CMS Handler │    │ROS Queue│  │WMS Handler │
│(Async)     │    │(Async)  │  │(Async)     │
└────────────┘    └─────────┘  └────────────┘
```

### Key Benefits

- **Low Latency**: API returns immediately
- **High Throughput**: Multiple orders can be submitted rapidly
- **Scalability**: Independent consumer scaling
- **Resilience**: Failures don't block submission
- **Flexibility**: New consumers can be added dynamically

### Queue Architecture for High Volume

```
orders_exchange (topic)
    ↓
┌───────────────────┬──────────────────┬─────────────────┐
│                   │                  │                 │
order.created    order.created      order.created    order.created
│                   │                  │                 │
↓                   ↓                  ↓                 ↓
cms_queue         ros_queue         wms_queue         archive_queue
(Prefetch: 10)   (Prefetch: 20)    (Prefetch: 15)   (Prefetch: 1)
│                 │                 │                 │
↓                 ↓                 ↓                 ↓
CMS           Route              Warehouse        Long-term
Order         Optimization       Operations       Storage
```

### Consumer Priority & Prefetch Strategy

```python
# Configure optimal prefetch for each consumer type
CONSUMER_CONFIG = {
    'cms_consumer': {
        'prefetch_count': 10,      # Process 10 orders in parallel
        'priority': 'HIGH',         # Process immediately
        'timeout': 300              # 5 minute processing window
    },
    'ros_consumer': {
        'prefetch_count': 20,       # CPU-intensive routing
        'priority': 'MEDIUM',
        'timeout': 600              # 10 minute processing window
    },
    'wms_consumer': {
        'prefetch_count': 15,       # Balanced performance
        'priority': 'MEDIUM',
        'timeout': 450              # 7.5 minute processing window
    }
}
```

---

## Saga Pattern for Distributed Transactions

### Problem: Distributed Transactions Across Multiple Services

Traditional ACID transactions don't work across multiple independent services. The Saga pattern provides an alternative.

### Solution: Saga Pattern

A saga is a sequence of local transactions, each compensated by a corresponding compensating transaction.

#### Two Implementation Approaches:

### 1. **Choreography-Based Saga** (Event-Driven)

Each service listens to events and triggers compensating actions:

```
Order Created Event
    ↓
CMS Service receives event → processes order
    ↓ publishes (OrderApproved or OrderFailed)
    ↓
ROS Service receives event → plans route
    ↓ publishes (RoutePlanned or RouteFailed)
    ↓
WMS Service receives event → allocates inventory
    ↓ publishes (AllocationConfirmed or AllocationFailed)
    ↓
If any fails, compensating transactions are triggered:
    - WMS rollback → release allocation
    - ROS rollback → cancel route
    - CMS rollback → reject order
```

### 2. **Orchestration-Based Saga** (Centralized)

Middleware orchestrator controls the entire workflow:

```
Orchestrator                CMS              ROS              WMS
    │                        │                │                │
    ├──ReserveOrder─────────→│                │                │
    │                        ├─✓ Approved────→│                │
    │                        │                ├─✓ Route OK────→│
    │                        │                │                ├─✓ Allocated
    │                        │                │                │
    │←─────Confirmation─────────────────────────────────────────┤
    │
    │ (If any step fails)
    ├──Rollback─────────────→│                │                │
    │                        ├─✗ Cancel──────→│                │
    │                        │                ├─✗ Undo────────→│
    │                        │                │                ├─✗ Release
```

### Implementation: Orchestration-Based Saga

**Why Orchestration for SwiftLogistics:**
- Clearer transaction flow
- Easier to debug
- Better visibility into order status
- Simpler rollback logic
- Suitable for your architecture

---

## Message Reliability Strategies

### Challenge: Ensuring No Message Loss in High-Volume Processing

### Strategy 1: **Message Persistence**

```python
# RabbitMQ Queue Declaration
channel.queue_declare(
    queue='orders_queue',
    durable=True,           # Queue survives broker restart
    arguments={
        'x-max-length': 1000000  # Max 1M messages
    }
)

# Message Publishing
channel.basic_publish(
    exchange='orders_exchange',
    routing_key='order.created',
    body=json.dumps(order),
    properties=pika.BasicProperties(
        delivery_mode=2,        # 2 = Persistent (survives restart)
        content_type='application/json'
    )
)
```

### Strategy 2: **Acknowledgment Guarantees**

```python
# Manual Acknowledgments (Not auto-ack)
def callback(ch, method, properties, body):
    try:
        process_order(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)  # Explicit ACK
    except Exception as e:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)  # Requeue

channel.basic_qos(prefetch_count=10)  # Process only 10 at a time
channel.basic_consume(
    queue='orders_queue',
    on_message_callback=callback,
    auto_ack=False  # CRITICAL: Manual acknowledgment
)
```

### Strategy 3: **Dead Letter Queues (DLQ)**

```
orders_queue (main)
    ↓ (fails after max retries)
orders_dlq (dead letter)
    ↓
Manual Review/Recovery
    ↓
orders_retry_queue (after fix)
    ↓
Reprocess
```

### Strategy 4: **Idempotency**

Process same message multiple times safely:

```python
# Check if order already processed
def process_order(order_data):
    # Use order_id as idempotency key
    existing = db.orders.find_one({'order_id': order_data['order_id']})
    if existing:
        return existing  # Return cached result
    
    # Process new order
    result = do_processing(order_data)
    db.orders.insert_one(result)
    return result
```

### Strategy 5: **Transactional Outbox Pattern**

Ensures message is published if and only if database update succeeds:

```python
def create_order(order_data):
    # Single transaction
    with db.transaction():
        # 1. Save order to database
        order = Order(**order_data)
        db.session.add(order)
        db.session.flush()  # Get order_id
        
        # 2. Write to outbox table (in same transaction)
        outbox_entry = OutboxEntry(
            event_type='order.created',
            payload=order.to_json(),
            created_at=datetime.utcnow()
        )
        db.session.add(outbox_entry)
        db.session.commit()  # Atomic
    
    # 3. Separate process reads outbox and publishes
    # If publisher crashes, outbox ensures no loss
```

### Strategy 6: **Circuit Breaker & Retry Logic**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),           # Max 5 retries
    wait=wait_exponential(multiplier=1, min=2, max=60)  # Exponential backoff
)
def publish_to_rabbitmq(message):
    publisher.publish(message)

# Exponential backoff: 2s, 4s, 8s, 16s, 32s+...
```

### Strategy 7: **Monitoring & Alerting**

```python
import prometheus_client

# Track message processing
messages_received = Counter('messages_received', 'Messages received')
messages_processed = Counter('messages_processed', 'Messages successfully processed')
messages_failed = Counter('messages_failed', 'Messages that failed processing')
queue_depth = Gauge('queue_depth', 'Current queue depth')
processing_time = Histogram('processing_time_seconds', 'Message processing time')

def monitor_queue():
    """Alert if queue depth exceeds threshold"""
    if queue_depth > 10000:
        alert('High queue depth detected')
```

### Complete Reliability Architecture

```
Order Submission (REST API)
    ↓
Transactional Save + Outbox
    ↓
RabbitMQ with Persistence
    ↓
Manual Acknowledgment
    ↓
Processing with Idempotency Check
    ↓
Success: ACK
    ↓
Failure: NACK + Requeue (max 3 times)
    ↓
Max Retries Exceeded: Move to DLQ
    ↓
DLQ Handler: Manual Review/Fix
    ↓
Reprocess from DLQ
```

---

## Deployment Architecture

### Container-Based Deployment

```yaml
# docker-compose.yml
services:
  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"      # AMQP
      - "15672:15672"    # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

  order-intake-api:
    build: ./order-intake-service
    ports:
      - "5001:5001"
    depends_on:
      - rabbitmq
    environment:
      RABBITMQ_HOST: rabbitmq

  cms-service:
    build: ./cms-soap-service
    ports:
      - "5002:5002"
    depends_on:
      - rabbitmq

  ros-service:
    build: ./ros-rest-service
    ports:
      - "5003:5003"
    depends_on:
      - rabbitmq

  wms-service:
    build: ./wms-mock-service
    ports:
      - "5004:5004"
    depends_on:
      - rabbitmq

  middleware-orchestrator:
    build: ./middleware-orchestrator
    depends_on:
      - rabbitmq
      - order-intake-api
      - cms-service
```

### Load Balancing & Scaling

```
Load Balancer (Nginx)
    ↓
┌───────────────┬────────────────┬────────────────┐
│               │                │                │
Order API #1  Order API #2   Order API #3
(5001)        (5001)         (5001)
    │               │                │
    └───────────────┴────────────────┘
                    ↓
            RabbitMQ Cluster
    ┌───────────────┬────────────────┬────────────────┐
    │               │                │                │
  Node 1          Node 2           Node 3
  
    ↓               ↓                ↓
CMS Consumers (scaled independently)
ROS Consumers (scaled independently)
WMS Consumers (scaled independently)
```

---

## Summary: Key Architectural Principles

1. **Loose Coupling**: Message broker decouples producers from consumers
2. **Asynchronous Processing**: Non-blocking order submission
3. **Orchestration**: Centralized workflow coordination
4. **Reliability**: Multiple strategies ensure no message loss
5. **Scalability**: Independent scaling of components
6. **Resilience**: Circuit breakers, retries, fallbacks
7. **Observability**: Comprehensive logging and monitoring
8. **Idempotency**: Safe message replay
9. **Compensation**: Saga pattern for distributed transactions
10. **Adaptability**: Protocol adapters for system integration
