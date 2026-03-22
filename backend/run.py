from app import create_app, db, create_celery_app
from app.models import Order
from sqlalchemy.exc import OperationalError, ProgrammingError
import sys

app = create_app()
celery_app = create_celery_app(app)

def test_database_connection():
    with app.app_context():
        try:
            print("Attempting to connect to the database...")
            db.create_all()
            print("Successfully connected to the database and created all tables.")

        except OperationalError as e:
            print("\n[!] Database Connection Error!")
            print("Please check your DB_USER, DB_PASSWORD, and DB_HOST in the .env file.")
            sys.exit(1)
        except ProgrammingError as e:
            print("\n[!] Database Configuration/Syntax Error!")
            sys.exit(1)
        except Exception as e:
            print(f"\n[!] Unexpected Error: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    # Add flag flexibility: python run.py testdb runs the test.
    # python run.py boots the actual API server needed for concurrency tests!
    if len(sys.argv) > 1 and sys.argv[1] == "testdb":
        print("Initializing DB Connection Test Protocol...")
        test_database_connection()
    else:
        print("Booting Order Processing Backend API on Port 5000...")
        # Make sure to run in multithreaded mode to handle concurrency requests!
        app.run(debug=True, port=5000, threaded=True)
