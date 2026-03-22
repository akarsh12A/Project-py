from celery import shared_task
from sqlalchemy import text
from .models import db, Order
from .services import log_order_event
import logging
import datetime
import random

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _refetch(order_id):
    """Always re-read from DB to get the freshest state."""
    return Order.query.get(order_id)

# ─── Main Task ────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_order_task(self, order_id):
    """
    Full order processing pipeline:
      1. Guard checks (cancelled, already terminal, max retries)
      2. PAYMENT SIMULATION  — 30% random failure, retried up to 3 times
      3. INVENTORY CHECK     — Atomic SQL; out-of-stock = permanent failure (no retry)
    """

    # ── 1. Fetch & guard ──────────────────────────────────────────────────────
    order = _refetch(order_id)
    if not order:
        logger.error(f"Worker: Order {order_id} not found.")
        return

    if order.is_cancelled:
        log_order_event(order_id, 'ORDER_CANCELLED', "Worker halted — order was cancelled")
        return

    if order.status in ('SUCCESS', 'FAILED', 'CANCELLED'):
        logger.info(f"Worker: Order {order_id} already terminal ({order.status}). Skipping.")
        return

    if order.retry_count >= 3:
        order.status = 'FAILED'
        order.payment_status = 'FAILED'
        order.failure_reason = "Max retries (3) exhausted"
        db.session.commit()
        log_order_event(order_id, 'ORDER_FAILED', "Max retries reached — giving up")
        return

    # ── 2. Mark PROCESSING ────────────────────────────────────────────────────
    if order.status == 'PENDING':
        order.status = 'PROCESSING'
        order.payment_status = 'PENDING'
        db.session.commit()

    log_order_event(order_id, 'PROCESSING_STARTED', f"Attempt {order.retry_count + 1}/3 started")

    # ── Cancel check ──────────────────────────────────────────────────────────
    order = _refetch(order_id)
    if order.is_cancelled:
        log_order_event(order_id, 'ORDER_CANCELLED', "Cancelled before payment step")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2: PAYMENT SIMULATION (30% failure rate)
    # ─────────────────────────────────────────────────────────────────────────
    if order.payment_status != 'SUCCESS':          # skip if already paid on a retry
        log_order_event(order_id, 'PAYMENT_STARTED', "Simulating payment gateway call")

        payment_failed = random.random() < 0.30    # 30% chance of failure

        if payment_failed:
            failure_reason = "Payment gateway declined (simulated)"
            order = _refetch(order_id)
            order.retry_count += 1
            order.last_retry_at = datetime.datetime.utcnow()
            order.failure_reason = failure_reason
            db.session.commit()

            log_order_event(order_id, 'PAYMENT_FAILED',
                            f"Attempt {order.retry_count}/3 — {failure_reason}")
            logger.warning(f"Worker: Order {order_id} payment failed (attempt {order.retry_count}/3)")

            # Retry the whole task
            try:
                raise self.retry(
                    exc=Exception(failure_reason),
                    countdown=5,
                    max_retries=3
                )
            except self.MaxRetriesExceededError:
                order = _refetch(order_id)
                order.status = 'FAILED'
                order.payment_status = 'FAILED'
                db.session.commit()
                log_order_event(order_id, 'ORDER_FAILED', "Payment failed after 3 retries")
                return

        # Payment succeeded
        order = _refetch(order_id)
        order.payment_status = 'SUCCESS'
        db.session.commit()
        log_order_event(order_id, 'PAYMENT_SUCCESS', "Payment gateway accepted")

    # ── Cancel check before inventory ─────────────────────────────────────────
    order = _refetch(order_id)
    if order.is_cancelled:
        log_order_event(order_id, 'ORDER_CANCELLED', "Cancelled after payment, before inventory")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 5: INVENTORY CHECK — Atomic SQL prevents race conditions / overselling
    # ─────────────────────────────────────────────────────────────────────────
    if order.inventory_status == 'RESERVED':
        # Already reserved on a previous attempt — skip straight to success
        order.status = 'SUCCESS'
        db.session.commit()
        log_order_event(order_id, 'ORDER_SUCCESS', "Resumed — inventory was already reserved")
        return

    try:
        log_order_event(order_id, 'INVENTORY_CHECK_STARTED', "Initiating atomic stock evaluation")

        items = order.items if isinstance(order.items, list) else []
        reserved_all = True
        failed_item = None

        if _refetch(order_id).is_cancelled:
            db.session.rollback(); return

        for item in items:
            item_name = item.get('item_name')
            qty       = item.get('qty', 1)

            sql = text(
                "UPDATE inventory "
                "SET stock_quantity = stock_quantity - :qty "
                "WHERE item_name = :name AND stock_quantity >= :qty"
            )
            result = db.session.execute(sql, {"qty": qty, "name": item_name})

            if result.rowcount == 0:
                reserved_all = False
                failed_item  = item_name
                break

        if reserved_all:
            if _refetch(order_id).is_cancelled:
                db.session.rollback()
                log_order_event(order_id, 'ORDER_CANCELLED', "Cancelled during inventory — rolled back")
                return

            order = _refetch(order_id)
            order.inventory_status = 'RESERVED'
            order.status           = 'SUCCESS'
            db.session.commit()
            log_order_event(order_id, 'INVENTORY_RESERVED', "All stock reserved atomically")
            log_order_event(order_id, 'ORDER_SUCCESS',       "Order completed successfully")
            logger.info(f"Worker: Order {order_id} → SUCCESS")

        else:
            db.session.rollback()
            order = _refetch(order_id)
            order.inventory_status = 'FAILED'
            order.status           = 'FAILED'
            order.failure_reason   = f"Out of stock: {failed_item}"
            db.session.commit()
            log_order_event(order_id, 'INVENTORY_FAILED', f"Out of stock: {failed_item}")
            log_order_event(order_id, 'ORDER_FAILED',     "Inventory check failed — no retry")
            logger.error(f"Worker: Order {order_id} → FAILED ({order.failure_reason})")

    except Exception as e:
        db.session.rollback()
        log_order_event(order_id, 'ORDER_FAILED', f"Unexpected exception: {str(e)}")
        logger.error(f"Worker: Order {order_id} exception: {str(e)}")

        order = _refetch(order_id)
        if order.is_cancelled:
            return

        order.retry_count    += 1
        order.last_retry_at   = datetime.datetime.utcnow()
        db.session.commit()

        raise self.retry(exc=e, countdown=5)
