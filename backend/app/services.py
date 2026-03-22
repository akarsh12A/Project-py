import logging
import datetime
from sqlalchemy.orm import Session
from .models import db, Order, OrderLog, Inventory

logger = logging.getLogger(__name__)

def log_order_event(order_id, event_type, message=None):
    try:
        with Session(db.engine) as session:
            log_entry = OrderLog(order_id=order_id, event=event_type, message=message)
            session.add(log_entry)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to save log: {e}")

def create_order(user_id, items, currency, idempotency_key):
    # Idempotency Check
    existing_order = Order.query.filter_by(idempotency_key=idempotency_key).first()
    if existing_order:
        logger.info(f"Idempotent fetch: Order already exists for key {idempotency_key}")
        return existing_order

    # --- SECURE PRICE CALCULATION FROM DATABASE ---
    calculated_total = 0.0
    validated_items = []

    for item in items:
        item_name = item.get('item_name')
        qty = item.get('qty', 0)

        if not item_name:
            raise ValueError("Each item must have an item_name.")
        if qty <= 0:
            raise ValueError(f"Quantity for '{item_name}' must be greater than 0.")

        inv = Inventory.query.filter_by(item_name=item_name).first()
        if not inv:
            raise ValueError(f"Invalid item: '{item_name}' not found in inventory.")
        if inv.price is None:
            raise ValueError(f"Price not configured for item: '{item_name}'.")

        item_total = float(inv.price) * qty
        calculated_total += item_total
        validated_items.append({"item_name": item_name, "qty": qty, "unit_price": float(inv.price)})

    new_order = Order(
        user_id=user_id,
        items=validated_items,
        total_amount=round(calculated_total, 2),
        currency=currency,
        idempotency_key=idempotency_key,
        status='PENDING',
        payment_status='SUCCESS',
        inventory_status='PENDING'
    )
    db.session.add(new_order)
    db.session.commit()

    logger.info(f"Order created: ID {new_order.id} | Total: {new_order.total_amount} {currency}")
    log_order_event(new_order.id, 'ORDER_CREATED', f"Order created with calculated total: {new_order.total_amount}")

    # Trigger Celery Worker
    from .tasks import process_order_task
    process_order_task.delay(new_order.id)

    return new_order

def cancel_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return False, "Order not found"
        
    if order.status == 'SUCCESS':
        return False, "Cannot cancel a SUCCESS order"
        
    if order.is_cancelled:
        return True, "Order is already cancelled" # Idempotent cancellation
        
    order.is_cancelled = True
    order.status = 'CANCELLED'
    order.cancelled_at = datetime.datetime.utcnow()
    db.session.commit()
    logger.info(f"Order {order.id} cancelled successfully", extra={"order_id": order.id})
    log_order_event(order.id, 'ORDER_CANCELLED', "Order was cancelled by user")
    return True, "Order cancelled"
