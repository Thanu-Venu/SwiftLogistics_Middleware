# Order Intake REST API Service

A Flask-based REST API service that accepts order data and publishes it to RabbitMQ for downstream processing in the SwiftLogistics middleware architecture.

## Features

- **REST API Endpoints**: Accept order data via HTTP POST
- **RabbitMQ Integration**: Publish orders to message broker for asynchronous processing
- **Data Validation**: Validate order structure and required fields
- **Error Handling**: Comprehensive error handling and logging
- **Health Checks**: Monitor service status
- **CORS Support**: Enable cross-origin requests

## Architecture

```
Client Request (HTTP POST)
    ↓
Flask API (Validation)
    ↓
RabbitMQ Publisher
    ↓
orders_queue (RabbitMQ)
    ↓
Downstream Services (CMS, WMS, ROS)
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure RabbitMQ is running:
```bash
# Using Docker
docker run -d --name rabbitmq -p 5672:15672 rabbitmq:3.12-management
```

## Configuration

Update the following environment variables in `order_intake_service.py`:

- `RABBITMQ_HOST`: RabbitMQ host (default: localhost)
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `RABBITMQ_USER`: RabbitMQ username (default: guest)
- `RABBITMQ_PASSWORD`: RabbitMQ password (default: guest)
- `ORDER_QUEUE`: Queue name (default: orders_queue)

## Running the Service

```bash
python order_intake_service.py
```

The service will start on `http://0.0.0.0:5001`

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status.

### Create Order
```
POST /api/v1/orders
Content-Type: application/json

{
  "order_id": "ORD-2026-001",
  "customer_id": "CUST-123",
  "items": [
    {
      "product_id": "PROD-456",
      "quantity": 2,
      "price": 29.99
    }
  ],
  "shipping_address": {
    "street": "123 Main St",
    "city": "Springfield",
    "zip": "12345"
  }
}
```

**Response (201 Created):**
```json
{
  "message": "Order created successfully",
  "order_id": "ORD-2026-001",
  "status": "received",
  "timestamp": "2026-02-04T12:00:00"
}
```

### Get Order Status
```
GET /api/v1/orders/{order_id}
```

### Service Statistics
```
GET /api/v1/stats
```

## Order Format

Required fields:
- `order_id` (string): Unique order identifier
- `customer_id` (string): Customer identifier
- `items` (array): List of order items
  - `product_id` (string): Product identifier
  - `quantity` (number): Quantity ordered
  - `price` (number): Item price
- `shipping_address` (object): Shipping destination

Optional fields:
- `notes`: Order notes
- `priority`: Order priority

## Testing with curl

```bash
# Health check
curl http://localhost:5001/health

# Create order
curl -X POST http://localhost:5001/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-2026-001",
    "customer_id": "CUST-123",
    "items": [
      {
        "product_id": "PROD-456",
        "quantity": 2,
        "price": 29.99
      }
    ],
    "shipping_address": {
      "street": "123 Main St",
      "city": "Springfield",
      "zip": "12345"
    }
  }'

# Get stats
curl http://localhost:5001/api/v1/stats
```

## Monitoring

The service logs all activities to console with timestamps and severity levels:
- INFO: Service operations (orders received, published)
- ERROR: Failures and exceptions
- WARNING: Non-critical issues

## Integration with Other Services

The order-intake service publishes messages to the RabbitMQ `orders_exchange` with routing key `order.created`. Other services in the middleware can subscribe to this exchange to:
- Process orders (CMS)
- Update inventory (WMS)
- Route shipments (ROS)

## Error Handling

- **400 Bad Request**: Missing required fields or invalid data
- **500 Internal Server Error**: Processing error
- **503 Service Unavailable**: RabbitMQ connection unavailable

## Future Enhancements

- Order persistence in database
- Order tracking and status updates
- Rate limiting and authentication
- Order history and audit logs
- Batch order processing
