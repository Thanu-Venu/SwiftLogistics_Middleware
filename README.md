# SwiftTrack Middleware Integration Platform

Middleware Architecture Project – SCS2314  
University of Colombo School of Computing

SwiftTrack is an event-driven middleware integration platform designed to orchestrate logistics operations between multiple heterogeneous enterprise systems. The platform integrates a Client Portal, Driver Application, and backend enterprise systems including CMS, ROS, and WMS through a reliable asynchronous middleware layer.

--------------------------------------------------

## System Overview

Modern logistics platforms rely on multiple backend enterprise systems that are often developed using different technologies and communication protocols. Direct integration between these systems can create several challenges such as tight coupling, limited scalability, reliability risks, and lack of visibility into order processing.

SwiftTrack Middleware solves this problem by introducing an event-driven integration layer that coordinates communication between systems.

The platform enables:

• Client order submission and tracking  
• Asynchronous order processing  
• Integration with heterogeneous backend systems  
• Driver delivery management  
• Real-time status updates  

--------------------------------------------------

## Architecture

### Conceptual Architecture

Client Portal  
→ API Gateway  
→ RabbitMQ Message Broker  
→ Worker Orchestrator  
→ CMS / ROS / WMS  
→ PostgreSQL Database  

The middleware acts as a central integration layer between client applications and enterprise systems.

### Implementation Architecture

The system is deployed using Docker Compose and consists of multiple containerized services.

Core Services:

Client Portal – Web interface for clients to submit and track orders  
Driver App – Application used by drivers to manage deliveries  
API Gateway – FastAPI service handling authentication, order intake, and notifications  
Worker – Background service responsible for orchestration logic  
RabbitMQ – Message broker enabling asynchronous communication  
PostgreSQL – Database storing orders and event logs  
CMS Mock – SOAP-based mock service  
ROS Mock – REST-based mock service  
WMS Mock – TCP-based mock service  

--------------------------------------------------

## Technology Stack

Frontend  
React (Client Portal)  
Driver Application  

Backend  
Python  
FastAPI  

Messaging  
RabbitMQ  

Database  
PostgreSQL  

Containerization  
Docker  
Docker Compose  

Integration Protocols

CMS – SOAP / XML  
ROS – REST / JSON  
WMS – TCP Messaging  

--------------------------------------------------

## Architectural Patterns

SwiftTrack uses several middleware architectural and integration patterns.

API Gateway Pattern  
Provides a unified entry point for client requests.

Event-Driven Architecture  
Orders are propagated as events through RabbitMQ enabling asynchronous processing.

Orchestration Pattern  
The worker coordinates interactions between CMS, ROS, and WMS.

Message Broker Pattern  
RabbitMQ decouples services and allows reliable asynchronous communication.

Retry Pattern  
Temporary failures trigger automatic retry attempts.

Dead Letter Queue Pattern  
Messages exceeding retry limits are redirected to a Dead Letter Queue.

Adapter Pattern  
Adapters convert requests between SOAP, REST, and TCP systems.

Outbox Pattern  
Ensures transactional consistency between database operations and message publication.

--------------------------------------------------

## Order Processing Flow

Client Portal  
→ Submit Order  
→ API Gateway  
→ Store Order in Database  
→ Publish Event to RabbitMQ  
→ Worker Consumes Event  
→ CMS Validation  
→ Route Optimization (ROS)  
→ Warehouse Allocation (WMS)  
→ Order Ready for Driver  
→ Driver Delivers Package  
→ Client Portal Updated  

Each stage of the pipeline is recorded in the system event log.

--------------------------------------------------

## Database Schema

SwiftTrack uses PostgreSQL for persistent storage.

Tables:

users – Stores user accounts  
orders – Stores order information  
order_events – Tracks the lifecycle of each order  
outbox – Stores events before publishing to RabbitMQ  

Example Event Lifecycle:

PROCESSING  
CMS_CALLING  
CMS_OK  
ROS_CALLING  
ROS_OK  
WMS_CALLING  
WMS_OK  
READY_FOR_DRIVER  
DELIVERED  

This event trail provides traceability and observability.

--------------------------------------------------

## Real-Time Tracking

SwiftTrack provides real-time updates using WebSocket communication between the client portal and the API Gateway.

Features include:

• Live order status updates  
• Delivery notifications  
• Driver delivery updates  

--------------------------------------------------

## Functional Capabilities

### Client Portal

Clients can:

• Log in to the platform  
• Submit delivery orders  
• Track order status  
• View delivery progress  
• Receive notifications  

### Driver Application

Drivers can:

• View assigned deliveries  
• Access optimized delivery routes  
• Mark packages as delivered or failed  
• Provide delivery confirmation  

### Order Processing

The middleware ensures:

• High-volume order handling  
• Asynchronous processing  
• Reliable event-driven communication  
• Fault tolerance during backend failures  

--------------------------------------------------

## Security Considerations

Authentication and Authorization  
JWT-based authentication  
Protected API endpoints  

Data Protection  
Password hashing  
Secure credential storage  

Transport Security  
HTTPS / WSS recommended for production  
Internal network isolation using Docker  

Input Validation  
Schema validation  
SQL injection prevention using parameterized queries  

Messaging Security  
Broker authentication  
Queue access restrictions  

--------------------------------------------------

## Reliability and Resilience

SwiftTrack incorporates several reliability mechanisms.

Retry Mechanism  
Temporary failures trigger controlled retry attempts.

Dead Letter Queue  
Messages exceeding retry thresholds are redirected for manual inspection.

Event Logging  
All order processing steps are recorded in the order_events table.

Fault Isolation  
Failures in one backend system do not crash the entire middleware workflow.

--------------------------------------------------

## Running the Project

Prerequisites:

Docker  
Docker Compose  
Git  

Clone the repository:

git clone <repository-url>  
cd SwiftLogistics_Middleware  

Start the system:

docker compose up -d  

View running containers:

docker compose ps  

View worker logs:

docker logs worker  

Stop the system:

docker compose down  

--------------------------------------------------

## Accessing Services

Client Portal  
http://localhost:3000  

API Gateway  
http://localhost:8000  

RabbitMQ Management  
http://localhost:15672  

--------------------------------------------------

## Project Structure

SwiftLogistics_Middleware  
api-gateway  
worker  
client-portal  
driver-app  
cms-soap-mock  
ros-rest-mock  
wms-tcp-mock  
docker-compose.yml  
README.md  

--------------------------------------------------

## Demo Flow

Typical demonstration scenario:

1. Client logs in and submits a delivery order  
2. API Gateway stores the order and publishes an event  
3. Worker consumes the event from RabbitMQ  
4. CMS validates the order  
5. ROS calculates the optimal route  
6. WMS allocates the package  
7. Order status becomes READY_FOR_DRIVER  
8. Driver marks the package delivered  
9. Client portal updates delivery status  

--------------------------------------------------

## Future Improvements

Production-grade monitoring and observability  
Advanced notification system  
Distributed tracing  
Automatic scaling of worker services  
Enhanced security and access control  

--------------------------------------------------

## Conclusion

SwiftTrack Middleware demonstrates how event-driven middleware architectures can integrate heterogeneous enterprise systems while ensuring reliability, scalability, and observability.

The platform successfully orchestrates logistics operations between client applications, driver systems, and backend enterprise services using asynchronous messaging and containerized microservices.
