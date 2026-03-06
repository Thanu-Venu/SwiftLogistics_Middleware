# Saga Pattern Implementation for Distributed Transactions

## Overview

This directory implements the **Orchestration-Based Saga Pattern** for managing distributed transactions across multiple services in the SwiftLogistics middleware.

## What is a Saga?

A saga is a sequence of local transactions that are coordinated to achieve a global transaction across multiple services.

### Problem Solved

In a microservices architecture, traditional ACID transactions don't work because:
- Each service has its own database
- Services are independent and asynchronous
- Network failures can occur at any time

**Solution: The Saga Pattern**
- Breaks down the distributed transaction into a series of local transactions
- Each local transaction updates the service's database and publishes an event
- If a transaction fails, compensating transactions are triggered to rollback previous changes

## Two Approaches

### 1. Choreography-Based Saga
Each service listens to events and triggers the next step

```
Order Created Event
    ↓ (Published by Order Service)
CMS Service hears event → Approves Order
    ↓ publishes (OrderApproved)
ROS Service hears event → Plans Route
    ↓ publishes (RoutePlanned)
WMS Service hears event → Allocates Inventory
    ↓ publishes (AllocationConfirmed)
```

**Pros:** Decoupled, flexible
**Cons:** Hard to track, complex logic spread across services

### 2. Orchestration-Based Saga ✓ (Implemented Here)
Centralized orchestrator controls the workflow

```
Orchestrator (Central Controller)
    │
    ├─ Call CMS Service
    │       └─ Approve Order
    ├─ Call ROS Service
    │       └─ Plan Route
    ├─ Call WMS Service
    │       └─ Allocate Inventory
    │
    If any step fails:
    ├─ Call WMS Compensation
    │       └─ Release Inventory
    ├─ Call ROS Compensation
    │       └─ Cancel Route
    ├─ Call CMS Compensation
    │       └─ Reject Order
```

**Pros:** Clear workflow, easy to debug, centralized control
**Cons:** Orchestrator becomes a bottleneck

## File: order_saga_orchestrator.py

### Key Components

#### 1. SagaStep
Represents a single step in the saga with action and compensation

```python
SagaStep(
    name='CMS Approval',
    action=lambda o: cms_client.execute(o),        # Forward transaction
    compensation=lambda o: cms_client.compensate(o) # Rollback
)
```

#### 2. SagaExecution
Tracks the execution of a saga for an order

```python
execution = SagaExecution(order_id='ORD-2026-001')
execution.status  # PENDING → CMS_APPROVED → ROUTE_PLANNED → CONFIRMED
execution.steps   # List of SagaStep objects with status
```

#### 3. OrderSagaOrchestrator
Main orchestrator that executes the saga

```python
orchestrator = OrderSagaOrchestrator(cms_client, ros_client, wms_client)
execution = orchestrator.execute_saga(order)
```

### Saga Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     ORDER RECEIVED                             │
│              order_id: ORD-2026-001                            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓
        ┌────────────────────────┐
        │  STEP 1: CMS APPROVAL  │
        │  ├─ Validate customer  │
        │  ├─ Check credit limit │
        │  └─ Create order       │
        └────────┬───────────────┘
                 │
          ┌──────┴──────┐
          │             │
        SUCCESS       FAILURE
          │             │
          ↓             ├─ Record error
        ┌─┘             ├─ No compensation needed
        │               └─ Update status to CMS_REJECTED
        │
        ↓
    ┌────────────────────────┐
    │ STEP 2: ROUTE PLANNING │
    │ ├─ Get delivery points │
    │ ├─ Optimize route      │
    │ └─ Estimate ETA        │
    └────────┬───────────────┘
             │
      ┌──────┴──────┐
      │             │
    SUCCESS       FAILURE
      │             │
      ↓             ├─ Record error
    ┌─┘             ├─ Compensate Step 1: Reject in CMS
      │             └─ Update status to ROUTE_FAILED
      │
      ↓
  ┌────────────────────────────┐
  │ STEP 3: INVENTORY ALLOCATION│
  │ ├─ Reserve items           │
  │ ├─ Update stock            │
  │ └─ Generate pick list      │
  └────────┬────────────────────┘
           │
    ┌──────┴──────┐
    │             │
  SUCCESS       FAILURE
    │             │
    ↓             ├─ Record error
  ┌─┘             ├─ Compensate Step 2: Cancel route
    │             ├─ Compensate Step 1: Reject in CMS
    │             └─ Update status to INVENTORY_FAILED
    │
    ↓
 CONFIRMED
```

## Usage Example

### Basic Usage

```python
from order_saga_orchestrator import (
    OrderSagaOrchestrator,
    CMSServiceClient,
    ROSServiceClient,
    WMSServiceClient
)

# Create orchestrator
orchestrator = OrderSagaOrchestrator(
    cms_client=CMSServiceClient(),
    ros_client=ROSServiceClient(),
    wms_client=WMSServiceClient()
)

# Execute saga
order = {
    'order_id': 'ORD-2026-001',
    'customer_id': 'CUST-123',
    'items': [...],
    'shipping_address': {...}
}

execution = orchestrator.execute_saga(order)

# Check result
print(f"Status: {execution.status.value}")  # CONFIRMED or FAILED
print(f"Saga ID: {execution.saga_id}")
```

### Successful Order Flow

```
Order Status Timeline:
├─ PENDING
├─ CMS_APPROVED (Step 1 succeeded)
├─ ROUTE_PLANNED (Step 2 succeeded)
├─ INVENTORY_ALLOCATED (Step 3 succeeded)
└─ CONFIRMED (All steps completed)
```

### Failed Order with Compensation

```
Order Status Timeline:
├─ PENDING
├─ CMS_APPROVED (Step 1 succeeded)
├─ ROUTE_FAILED (Step 2 failed)
├─ COMPENSATING
│  ├─ Step 1 compensated (CMS order rejected)
│  └─ Step 2 compensation skipped (didn't complete)
└─ FAILED
```

## Service Clients

Each service implements the `ServiceClient` interface:

### CMSServiceClient

**Execute:** Approve order in CMS system
```python
def execute(order):
    # Validate customer
    # Check credit
    # Create order
    return {'cms_order_id': 'CMS-ORD-001', 'status': 'APPROVED'}
```

**Compensate:** Reject order in CMS
```python
def compensate(order):
    # Mark order as rejected
    return {'status': 'REJECTED'}
```

### ROSServiceClient

**Execute:** Plan route for delivery
```python
def execute(order):
    # Optimize route
    # Calculate ETA
    return {'route_id': 'ROUTE-001', 'status': 'PLANNED'}
```

**Compensate:** Cancel route
```python
def compensate(order):
    # Remove from route plan
    return {'status': 'CANCELLED'}
```

### WMSServiceClient

**Execute:** Allocate inventory
```python
def execute(order):
    # Reserve items from warehouse
    # Update stock
    return {'allocation_id': 'ALLOC-001', 'status': 'ALLOCATED'}
```

**Compensate:** Release inventory
```python
def compensate(order):
    # Return items to warehouse
    # Update stock
    return {'status': 'RELEASED'}
```

## Compensation Strategy

### Key Principle
**Compensating transactions must be able to undo any state change**

### Compensation Order
Compensations run in **reverse order** of execution:
1. If Step 3 fails → Compensate Step 2, then Step 1
2. If Step 2 fails → Compensate Step 1 (Step 2 never completed)
3. If Step 1 fails → No compensation (no previous steps)

### Idempotent Compensation
Compensations must be idempotent (safe to call multiple times):
```python
def compensate_order(order):
    # First call: Delete order from queue
    # Second call: Already deleted, return success
    # → Same result regardless of call count
```

## Running the Example

```bash
python order_saga_orchestrator.py
```

Output:
```
======================================================================
EXAMPLE 1: Successful Order Processing
======================================================================
[INFO] Saga started for order ORD-2026-001
[INFO] Executing: CMS Approval
[INFO] ✓ CMS Approval succeeded
[INFO] Executing: Route Planning
[INFO] ✓ Route Planning succeeded
[INFO] Executing: Inventory Allocation
[INFO] ✓ Inventory Allocation succeeded
[INFO] ✓ Saga completed successfully

Final Status: CONFIRMED
{
  "order_id": "ORD-2026-001",
  "saga_id": "...",
  "status": "CONFIRMED",
  "steps": [...]
}

======================================================================
EXAMPLE 2: Failed Order (Invalid Customer) - Compensation Triggered
======================================================================
[INFO] Saga started for order ORD-2026-002
[INFO] Executing: CMS Approval
[ERROR] ✗ CMS Approval failed: Missing customer_id
[WARNING] Starting compensation
[INFO] Starting compensation for order ORD-2026-002
[INFO] ✓ Saga completed with compensation

Final Status: FAILED
{
  "order_id": "ORD-2026-002",
  "saga_id": "...",
  "status": "FAILED",
  "steps": [...]
}
```

## Status Codes

| Status | Meaning | What Happened |
|--------|---------|---------------|
| PENDING | Saga not started | Initial state |
| CMS_APPROVED | CMS step succeeded | Step 1 completed |
| ROUTE_PLANNED | Route planning succeeded | Step 2 completed |
| INVENTORY_ALLOCATED | Inventory allocated | Step 3 completed |
| CONFIRMED | All steps succeeded | Saga successful |
| CMS_REJECTED | CMS step failed | Order not created |
| ROUTE_FAILED | Route planning failed | Failed after CMS approval |
| INVENTORY_FAILED | Inventory allocation failed | Failed after routing |
| COMPENSATING | Running compensation | Rolling back changes |
| FAILED | Saga failed | Some step failed |

## Step Status Codes

| Status | Meaning |
|--------|---------|
| PENDING | Not started |
| IN_PROGRESS | Currently executing |
| SUCCESS | Completed successfully |
| FAILED | Failed during execution |
| COMPENSATED | Rollback executed successfully |

## Integration with RabbitMQ

In production, integrate with RabbitMQ:

```python
# After saga completes, publish event
if execution.status == OrderStatus.CONFIRMED:
    publisher.publish({
        'event': 'order.confirmed',
        'order_id': order['order_id'],
        'saga_id': execution.saga_id
    })
elif execution.status == OrderStatus.FAILED:
    publisher.publish({
        'event': 'order.failed',
        'order_id': order['order_id'],
        'error': execution.error
    })

# Downstream services subscribe to these events
```

## Error Handling

### Unrecoverable Errors
If a compensation fails, log and alert:
```python
try:
    step.compensation(order)
except Exception as e:
    logger.critical(f"Compensation failed for {step.name}: {str(e)}")
    alert("MANUAL INTERVENTION REQUIRED")
```

### Timeout Handling
Add timeout to prevent hanging:
```python
from tenacity import retry, stop_after_delay

@retry(stop=stop_after_delay(300))  # 5 minute timeout
def execute_with_timeout(step, order):
    return step.action(order)
```

## Production Considerations

1. **Persistence:** Store saga execution in database for recovery
2. **Idempotency:** Ensure all actions and compensations are idempotent
3. **Timeouts:** Set reasonable timeouts for each step
4. **Monitoring:** Track saga execution metrics
5. **Alerting:** Alert on failed sagas and compensation failures
6. **Logging:** Comprehensive logging for troubleshooting
7. **Versioning:** Handle schema changes gracefully

## Common Pitfalls

### ❌ Non-Idempotent Actions
```python
# BAD: Can't be called twice safely
def charge_card(customer_id, amount):
    customer.balance -= amount  # If called twice, balance is wrong
```

### ✓ Idempotent Actions
```python
# GOOD: Safe to call multiple times
def mark_order_as_paid(order_id):
    order = db.get(order_id)
    if order.status != 'PAID':
        order.status = 'PAID'
        db.save(order)
    return 'PAID'
```

### ❌ Missing Compensation
```python
# BAD: No way to undo
def allocate_inventory(items):
    warehouse.reserve(items)
    # What if next step fails? Items stay reserved!
```

### ✓ Compensation Defined
```python
# GOOD: Can undo
def compensate_inventory(items):
    warehouse.release(items)
```

## Testing

```python
def test_saga_success():
    orchestrator = OrderSagaOrchestrator(...)
    order = create_valid_order()
    execution = orchestrator.execute_saga(order)
    assert execution.status == OrderStatus.CONFIRMED

def test_saga_compensation():
    orchestrator = OrderSagaOrchestrator(...)
    order = create_invalid_order()  # Will fail at step 2
    execution = orchestrator.execute_saga(order)
    assert execution.status == OrderStatus.FAILED
    assert execution.steps[0].status == StepStatus.COMPENSATED  # Step 1 rolled back
```
