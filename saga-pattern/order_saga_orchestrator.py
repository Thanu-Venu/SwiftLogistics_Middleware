"""
Orchestration-Based Saga Pattern Implementation
Implements distributed transaction management for order processing across multiple services
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Callable, Optional
from enum import Enum
from abc import ABC, abstractmethod
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Models
# ============================================================================

class OrderStatus(Enum):
    """Order status throughout saga execution"""
    PENDING = "PENDING"
    CMS_APPROVED = "CMS_APPROVED"
    ROUTE_PLANNED = "ROUTE_PLANNED"
    INVENTORY_ALLOCATED = "INVENTORY_ALLOCATED"
    CONFIRMED = "CONFIRMED"
    CMS_REJECTED = "CMS_REJECTED"
    ROUTE_FAILED = "ROUTE_FAILED"
    INVENTORY_FAILED = "INVENTORY_FAILED"
    COMPENSATING = "COMPENSATING"
    FAILED = "FAILED"


class StepStatus(Enum):
    """Individual step status"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"


class SagaStep:
    """Represents a step in the saga"""
    
    def __init__(
        self,
        name: str,
        action: Callable,
        compensation: Callable,
        timeout: int = 300
    ):
        self.name = name
        self.action = action  # Function to execute
        self.compensation = compensation  # Compensating transaction
        self.timeout = timeout
        self.status = StepStatus.PENDING
        self.result = None
        self.error = None
        self.executed_at = None
        self.compensated_at = None
    
    def __repr__(self):
        return f"SagaStep({self.name}, status={self.status.value})"


class SagaExecution:
    """Tracks the execution of a saga"""
    
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.saga_id = str(uuid.uuid4())
        self.started_at = datetime.utcnow()
        self.completed_at = None
        self.steps: List[SagaStep] = []
        self.current_step_index = 0
        self.status = OrderStatus.PENDING
        self.error = None
    
    def add_step(self, step: SagaStep):
        """Add step to saga"""
        self.steps.append(step)
    
    def get_current_step(self) -> Optional[SagaStep]:
        """Get current step"""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def move_to_next_step(self):
        """Move to next step"""
        self.current_step_index += 1
    
    def get_completed_steps(self) -> List[SagaStep]:
        """Get all completed steps"""
        return self.steps[:self.current_step_index]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'order_id': self.order_id,
            'saga_id': self.saga_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'steps': [
                {
                    'name': step.name,
                    'status': step.status.value,
                    'result': step.result,
                    'error': step.error
                }
                for step in self.steps
            ]
        }


# ============================================================================
# Service Interfaces
# ============================================================================

class ServiceClient(ABC):
    """Abstract service client"""
    
    @abstractmethod
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute service operation"""
        pass
    
    @abstractmethod
    def compensate(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Undo service operation"""
        pass


class CMSServiceClient(ServiceClient):
    """CMS Order Management Service Client"""
    
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Process order in CMS"""
        logger.info(f"CMS: Approving order {order.get('order_id')}")
        
        # Simulate validation
        if not order.get('customer_id'):
            raise ValueError("Missing customer_id")
        
        # Simulate processing
        return {
            'cms_order_id': f"CMS-{order.get('order_id')}",
            'status': 'APPROVED',
            'message': 'Order approved in CMS'
        }
    
    def compensate(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Reject order in CMS"""
        logger.info(f"CMS: Rejecting order {order.get('order_id')}")
        
        # Simulate rollback
        return {
            'status': 'REJECTED',
            'message': 'Order rejected in CMS'
        }


class ROSServiceClient(ServiceClient):
    """Route Optimization Service Client"""
    
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Plan route for order"""
        logger.info(f"ROS: Planning route for order {order.get('order_id')}")
        
        # Simulate validation
        if not order.get('shipping_address'):
            raise ValueError("Missing shipping_address")
        
        # Simulate processing
        return {
            'route_id': f"ROUTE-{order.get('order_id')}",
            'status': 'PLANNED',
            'estimated_delivery': '2026-02-06T15:00:00',
            'message': 'Route planned successfully'
        }
    
    def compensate(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel route"""
        logger.info(f"ROS: Cancelling route for order {order.get('order_id')}")
        
        # Simulate rollback
        return {
            'status': 'CANCELLED',
            'message': 'Route cancelled'
        }


class WMSServiceClient(ServiceClient):
    """Warehouse Management System Client"""
    
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate inventory for order"""
        logger.info(f"WMS: Allocating inventory for order {order.get('order_id')}")
        
        # Simulate validation
        items = order.get('items', [])
        if not items:
            raise ValueError("Order has no items")
        
        # Simulate processing
        return {
            'allocation_id': f"ALLOC-{order.get('order_id')}",
            'status': 'ALLOCATED',
            'items_allocated': len(items),
            'message': 'Inventory allocated successfully'
        }
    
    def compensate(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Release inventory"""
        logger.info(f"WMS: Releasing inventory for order {order.get('order_id')}")
        
        # Simulate rollback
        return {
            'status': 'RELEASED',
            'message': 'Inventory released'
        }


# ============================================================================
# Saga Orchestrator
# ============================================================================

class OrderSagaOrchestrator:
    """
    Orchestrates the distributed order processing saga
    
    Flow:
    1. CMS Approval (validate customer, check credit)
    2. Route Planning (optimize route, calculate eta)
    3. Inventory Allocation (reserve items from warehouse)
    4. Confirmation (finalize order)
    
    If any step fails, compensating transactions run in reverse order:
    4. Cancel order (N/A)
    3. Release inventory
    2. Cancel route
    1. Reject in CMS
    """
    
    def __init__(
        self,
        cms_client: CMSServiceClient,
        ros_client: ROSServiceClient,
        wms_client: WMSServiceClient
    ):
        self.cms_client = cms_client
        self.ros_client = ros_client
        self.wms_client = wms_client
        
        # In-memory execution tracking (in production, use database)
        self.executions: Dict[str, SagaExecution] = {}
    
    def start_saga(self, order: Dict[str, Any]) -> SagaExecution:
        """
        Start a new saga for order processing
        
        Args:
            order: Order data
        
        Returns:
            SagaExecution with order flow
        """
        order_id = order.get('order_id')
        
        if not order_id:
            raise ValueError("Order must have order_id")
        
        # Create saga execution
        execution = SagaExecution(order_id)
        
        # Define saga steps
        execution.add_step(SagaStep(
            name='CMS Approval',
            action=lambda o: self.cms_client.execute(o),
            compensation=lambda o: self.cms_client.compensate(o)
        ))
        
        execution.add_step(SagaStep(
            name='Route Planning',
            action=lambda o: self.ros_client.execute(o),
            compensation=lambda o: self.ros_client.compensate(o)
        ))
        
        execution.add_step(SagaStep(
            name='Inventory Allocation',
            action=lambda o: self.wms_client.execute(o),
            compensation=lambda o: self.wms_client.compensate(o)
        ))
        
        # Store execution
        self.executions[order_id] = execution
        
        logger.info(
            f"Saga started for order {order_id} "
            f"(saga_id={execution.saga_id})"
        )
        
        return execution
    
    def execute_saga(self, order: Dict[str, Any]) -> SagaExecution:
        """
        Execute the saga for an order
        
        Executes steps sequentially:
        - If all succeed: Update status to CONFIRMED
        - If any fails: Run compensating transactions and update to FAILED
        """
        execution = self.start_saga(order)
        
        try:
            # Execute each step
            while execution.get_current_step():
                step = execution.get_current_step()
                
                try:
                    # Execute step
                    logger.info(f"Executing: {step.name}")
                    step.status = StepStatus.IN_PROGRESS
                    
                    result = step.action(order)
                    
                    step.status = StepStatus.SUCCESS
                    step.result = result
                    step.executed_at = datetime.utcnow()
                    
                    # Update order status based on step
                    if step.name == 'CMS Approval':
                        execution.status = OrderStatus.CMS_APPROVED
                    elif step.name == 'Route Planning':
                        execution.status = OrderStatus.ROUTE_PLANNED
                    elif step.name == 'Inventory Allocation':
                        execution.status = OrderStatus.INVENTORY_ALLOCATED
                    
                    logger.info(
                        f"✓ {step.name} succeeded for order {order.get('order_id')}"
                    )
                    
                    execution.move_to_next_step()
                
                except Exception as e:
                    # Step failed
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    
                    logger.error(
                        f"✗ {step.name} failed for order {order.get('order_id')}: {str(e)}"
                    )
                    
                    # Set appropriate failure status
                    if step.name == 'CMS Approval':
                        execution.status = OrderStatus.CMS_REJECTED
                    elif step.name == 'Route Planning':
                        execution.status = OrderStatus.ROUTE_FAILED
                    elif step.name == 'Inventory Allocation':
                        execution.status = OrderStatus.INVENTORY_FAILED
                    
                    # Trigger compensation
                    self._compensate(execution, order)
                    execution.completed_at = datetime.utcnow()
                    execution.status = OrderStatus.FAILED
                    execution.error = str(e)
                    
                    return execution
            
            # All steps succeeded
            execution.status = OrderStatus.CONFIRMED
            execution.completed_at = datetime.utcnow()
            
            logger.info(
                f"✓ Saga completed successfully for order {order.get('order_id')} "
                f"(saga_id={execution.saga_id})"
            )
        
        except Exception as e:
            logger.error(f"Unexpected saga error: {str(e)}")
            execution.status = OrderStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
        
        return execution
    
    def _compensate(self, execution: SagaExecution, order: Dict[str, Any]):
        """
        Run compensating transactions in reverse order
        
        Executes compensation for all successfully completed steps
        in reverse order
        """
        execution.status = OrderStatus.COMPENSATING
        
        logger.warning(
            f"Starting compensation for order {order.get('order_id')} "
            f"(saga_id={execution.saga_id})"
        )
        
        # Get completed steps in reverse order
        completed_steps = execution.get_completed_steps()
        
        for step in reversed(completed_steps):
            try:
                logger.info(f"Compensating: {step.name}")
                
                result = step.compensation(order)
                
                step.status = StepStatus.COMPENSATED
                step.compensated_at = datetime.utcnow()
                
                logger.info(f"✓ {step.name} compensated for order {order.get('order_id')}")
            
            except Exception as e:
                # Compensation failed - log but continue
                logger.error(
                    f"✗ Compensation failed for {step.name}: {str(e)}. "
                    f"Manual intervention may be required."
                )
    
    def get_execution(self, order_id: str) -> Optional[SagaExecution]:
        """Get saga execution by order ID"""
        return self.executions.get(order_id)
    
    def get_execution_status(self, order_id: str) -> Dict[str, Any]:
        """Get saga execution status as dictionary"""
        execution = self.get_execution(order_id)
        
        if not execution:
            raise ValueError(f"Order {order_id} not found")
        
        return execution.to_dict()


# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Demo saga orchestration"""
    
    # Create service clients
    cms_client = CMSServiceClient()
    ros_client = ROSServiceClient()
    wms_client = WMSServiceClient()
    
    # Create orchestrator
    orchestrator = OrderSagaOrchestrator(cms_client, ros_client, wms_client)
    
    # Example 1: Successful order
    print("\n" + "="*70)
    print("EXAMPLE 1: Successful Order Processing")
    print("="*70)
    
    order_1 = {
        'order_id': 'ORD-2026-001',
        'customer_id': 'CUST-123',
        'customer_name': 'John Doe',
        'items': [
            {'product_id': 'PROD-001', 'quantity': 2, 'price': 29.99}
        ],
        'shipping_address': {
            'street': '123 Main St',
            'city': 'Springfield',
            'zip': '12345'
        }
    }
    
    execution_1 = orchestrator.execute_saga(order_1)
    print(f"\nFinal Status: {execution_1.status.value}")
    print(json.dumps(execution_1.to_dict(), indent=2))
    
    # Example 2: Failed order (invalid customer)
    print("\n" + "="*70)
    print("EXAMPLE 2: Failed Order (Invalid Customer) - Compensation Triggered")
    print("="*70)
    
    order_2 = {
        'order_id': 'ORD-2026-002',
        'customer_id': None,  # Invalid - will fail CMS step
        'customer_name': 'Jane Doe',
        'items': [
            {'product_id': 'PROD-001', 'quantity': 1, 'price': 29.99}
        ],
        'shipping_address': {
            'street': '456 Oak St',
            'city': 'Springfield',
            'zip': '12345'
        }
    }
    
    execution_2 = orchestrator.execute_saga(order_2)
    print(f"\nFinal Status: {execution_2.status.value}")
    print(json.dumps(execution_2.to_dict(), indent=2))
    
    # Example 3: Failed order (missing shipping address)
    print("\n" + "="*70)
    print("EXAMPLE 3: Failed Order (Missing Address) - Partial Compensation")
    print("="*70)
    
    order_3 = {
        'order_id': 'ORD-2026-003',
        'customer_id': 'CUST-456',
        'customer_name': 'Bob Smith',
        'items': [
            {'product_id': 'PROD-002', 'quantity': 3, 'price': 19.99}
        ],
        'shipping_address': None  # Invalid - will fail ROS step
    }
    
    execution_3 = orchestrator.execute_saga(order_3)
    print(f"\nFinal Status: {execution_3.status.value}")
    print(json.dumps(execution_3.to_dict(), indent=2))
    
    print("\n" + "="*70)
    print("Saga Examples Complete")
    print("="*70)


if __name__ == '__main__':
    main()
