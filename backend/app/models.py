from . import db
from datetime import datetime

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    # Using JSON field to natively interface with DB arrays
    items = db.Column(db.JSON, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    
    status = db.Column(db.String(20), default='PENDING')
    payment_status = db.Column(db.String(20), default='PENDING')
    inventory_status = db.Column(db.String(20), default='PENDING')
    
    retry_count = db.Column(db.Integer, default=0)
    last_retry_at = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=True) 
    
    # Optional Razorpay fields left out of mandatory rules according to user step
    razorpay_order_id = db.Column(db.String(255), nullable=True)
    razorpay_payment_id = db.Column(db.String(255), nullable=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)
    
    failure_reason = db.Column(db.Text, nullable=True)
    is_cancelled = db.Column(db.Boolean, default=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'items': self.items,
            'total_amount': self.total_amount,
            'currency': self.currency,
            'status': self.status,
            'payment_status': self.payment_status,
            'inventory_status': self.inventory_status,
            'retry_count': self.retry_count,
            'idempotency_key': self.idempotency_key,
            'is_cancelled': self.is_cancelled,
            'failure_reason': self.failure_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), unique=True, nullable=False)
    stock_quantity = db.Column(db.Integer, default=0, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderLog(db.Model):
    __tablename__ = 'order_logs'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    event = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
