# Middleware Orchestrator Service
# Responsibilities:
# - Receive order from client portal
# - Send order to CMS (SOAP)
# - Publish order to RabbitMQ
# - Call ROS REST API asynchronously
# - Handle failures using Saga pattern
