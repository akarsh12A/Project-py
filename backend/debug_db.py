import traceback
from app import create_app, db
from app.models import Order

app = create_app()

with app.app_context():
    try:
        sample = Order(
            items='[{"item": "pizza"}]',
            total_amount=299.00,
            status="TEST"
        )
        db.session.add(sample)
        db.session.commit()
        print("SUCCESS")
    except Exception as e:
        with open("clean_error.txt", "w") as f:
            f.write(traceback.format_exc())
        print("FAILED, check clean_error.txt")
