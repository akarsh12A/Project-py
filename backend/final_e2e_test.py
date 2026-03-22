import requests
import uuid
import time
import sys

BASE_URL = "http://127.0.0.1:5000/api"

def test_final_workflow():
    print("=============================================")
    print("      FINAL START-TO-FINISH E2E TEST         ")
    print("=============================================\n")
    
    payload = {
        "items": [
            {"item_name": "burger", "qty": 2},
            {"item_name": "fries", "qty": 1},
            {"item_name": "coke", "qty": 3}
        ],
        "total_amount": 750.00,
        "currency": "INR",
        "user_id": 101
    }
    
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    
    print(f"[>] Submitting Order: {payload['items']}")
    
    try:
        response = requests.post(f"{BASE_URL}/orders", json=payload, headers=headers)
        if response.status_code != 200:
            print(f"[!] FAILED: {response.text}")
            sys.exit(1)
            
        data = response.json()
        order_id = data['order_id']
        print(f"[+] Order Created Successfully in Web Node: ID {order_id}")
        
    except Exception as e:
        print(f"[!] API Network Error: {str(e)}")
        sys.exit(1)

    print("\n[.] Waiting 3.5 seconds for Celery Background Worker to deeply compute atomic blocks...")
    time.sleep(3.5)

    # Now natively query using the internal database ORM context!
    from app import create_app, db
    from app.models import Order, Inventory, OrderLog
    
    app = create_app()
    with app.app_context():
        print("\n---------------------------------------------")
        print(" 1. MASTER ORDER STATUS                      ")
        print("---------------------------------------------")
        order = Order.query.get(order_id)
        if order:
            print(f"Order ID: {order.id} \nTotal Overall Status: {order.status} \nStrict Inventory Status: {order.inventory_status}")
            
        print("\n---------------------------------------------")
        print(" 2. INVENTORY DATABASE STATUS                ")
        print("---------------------------------------------")
        for item in ['burger', 'fries', 'coke', 'pizza']:
            inv = Inventory.query.filter_by(item_name=item).first()
            if inv:
                print(f"Item: {inv.item_name} | Stock Remaining: {inv.stock_quantity}")
                
        print("\n---------------------------------------------")
        print(" 3. OBSERVABILITY ORDER LIFECYCLE LOGS       ")
        print("---------------------------------------------")
        logs = OrderLog.query.filter_by(order_id=order_id).order_by(OrderLog.created_at.asc()).all()
        for i, log in enumerate(logs):
            print(f"Step {i+1}: [{log.event}] -> {log.message}")
            
if __name__ == "__main__":
    test_final_workflow()
