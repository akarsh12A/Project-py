# Backend Architecture Documentation

## 1. Concurrency (Atomic Inventory Updates)
To prevent overselling when multiple orders are placed simultaneously, we use a single atomic `UPDATE` query rather than resolving stock locally (`SELECT`, `compare`, `UPDATE`).
```sql
UPDATE inventory 
SET stock_quantity = stock_quantity - qt 
WHERE item_name = itemName AND stock_quantity >= qt;
```
If `rowcount == 0`, it means either the item doesn't exist or `stock_quantity` is insufficient. At this point, the entire session transaction is rolled back. This strategy ensures strict safe concurrency.

## 2. Idempotency Implementation
Idempotency ensures that identical requests don't duplicate effects. 
- **Order Creation (`POST /orders`)**: The API enforces an `Idempotency-Key` header. We query `Order.query.filter_by(idempotency_key=key).first()`. If found, we instantly return the existing record instead of creating a new Razorpay order.
- **Webhook Handling**: Razorpay webhook POST events are processed securely by checking the `razorpay_payment_id`. If `Order.query.filter_by(razorpay_payment_id=payment_id).first()` already exists, we skip it to prevent processing duplicate webhook calls.

## 3. Failure Recovery Mechanisms
The system recovers from failures naturally using **state tracking values** strictly residing in the Database (`payment_status`, `inventory_status`, `status`, `retry_count`). 
- **Restarting worker crash**: If the Celery worker crashes in the middle of a task, when it boots up and receives a message, it inspects whether `order.inventory_status == 'RESERVED'`. It will seamlessly skip components of the system that are already resolved safely.
- **Retries**: Retries max at 3 times, enforcing delays. We use the database state (`retry_count`) to track attempts because Redis data might be volatile and in-memory variables die when workers crash.

## 4. Cancellation Protocol
Users can request `POST /orders/<id>/cancel`. If `order.status == 'SUCCESS'`, the backend strictly denies the request. If it proceeds, it sets `is_cancelled = True`.
**Worker Interference**: The Celery worker's first check triggers an exit block if it detects `order.is_cancelled`.
