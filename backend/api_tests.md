# Backend API Testing Guide

This document outlines the API definitions and testing steps necessary to interact with the Python order processing system.

## 1. Create Order
**Endpoint**: `POST /api/orders`
```bash
curl -X POST http://127.0.0.1:5000/api/orders \
-H "Content-Type: application/json" \
-H "Idempotency-Key: testing12345" \
-d '{
    "user_id": "user_01",
    "items": [{"item_name": "pizza", "qty": 1}],
    "total_amount": 299.00
}'
```

## 2. Idempotency Check
When sending the **exact same** command above twice using the same `Idempotency-Key` header, the system safely recognizes the repeated key format and prevents generating an entirely new object in the DB. Instead, it natively outputs the previously allocated JSON database entity originally linked to that key. 
**Why?**: If the user's internet lags momentarily and they accidentally post the checkout form twice, their card and stock reservations should inherently be shielded from duplicate processing.

## 3. Cancel Order
**Endpoint**: `POST /api/orders/{id}/cancel`
```bash
curl -X POST http://127.0.0.1:5000/api/orders/1/cancel \
-H "Content-Type: application/json"
```

## 4. Fetch Order
**Endpoint**: `GET /api/orders/{id}`
```bash
curl -X GET http://127.0.0.1:5000/api/orders/1 \
-H "Content-Type: application/json"
```

--- 
## Concurrency Handling
When two distinct orders ask for "pizza", the worker checks backend inventory. Suppose only 1 stock exists.
Locally resolving stock (using ORM math like `order.stock - 1`) causes Race Conditions. If both workers open the database exactly at the same millisecond, they both perceive `stock = 1`, and both override stock to `0`. 
**Our System:** To explicitly stop this, `tasks.py` issues a raw SQL **Atomic UPDATE**: `UPDATE inventory SET stock_quantity = stock_quantity - 1 WHERE stock_quantity >= 1`.
MySQL implicitly locks the inventory row momentarily while editing it. Worker 1 will successfully edit the matrix string while Worker 2's request will silently update exactly 0 rows (since stock_quantity naturally fell to 0 already). The framework natively bounces Worker 2 over to the Rollback block, marking their process as `FAILED`.

## Retry Safety
Retry executions within Celery natively refer to the precise source-of-truth variable blocks inside of MySQL (`retry_count`). 
When retrieving the process, the task will automatically filter past execution errors and evaluate if `inventory_status == RESERVED`. If true, the system jumps ahead. Thus ensuring infinite safe retries.
