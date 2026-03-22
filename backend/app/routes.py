from flask import Blueprint, request, jsonify
from .models import Order
from .services import create_order, cancel_order
import logging

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/orders', methods=['POST'])
def handle_create_order():
    data = request.json
    idempotency_key = request.headers.get('Idempotency-Key')
    
    if not idempotency_key:
        return jsonify({"error": "Idempotency-Key header is required"}), 400
        
    items = data.get('items')
    currency = data.get('currency', 'INR')
    user_id = data.get('user_id') or None  # INT column — must be None or a real integer

    if not items or not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "'items' is required and must be a non-empty list"}), 400

    try:
        order = create_order(user_id, items, currency, idempotency_key)
        return jsonify({
            "order_id": order.id,
            "total_amount": float(order.total_amount),
            "status": order.status,
            "payment_status": order.payment_status,
            "inventory_status": order.inventory_status
        }), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 422
    except Exception as e:
        logger.error(f"Route create_order failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/orders', methods=['GET'])
def list_orders():
    # Basic pagination logic built-in natively
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = Order.query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "orders": [o.to_dict() for o in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200

@api_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    return jsonify(order.to_dict()), 200

@api_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
def handle_cancel_order(order_id):
    success, message = cancel_order(order_id)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 400
