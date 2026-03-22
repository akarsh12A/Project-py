import os
from dotenv import load_dotenv
from sqlalchemy.engine.url import URL

# Load variables from .env file
load_dotenv()

class Config:
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'order_system')
    
    # Requirement 2: Construct SQLAlchemy URI using pymysql
    # We use URL.create to safely escape any special characters (like '@') in the password!
    SQLALCHEMY_DATABASE_URI = URL.create(
        drivername="mysql+pymysql",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        database=DB_NAME
    ).render_as_string(hide_password=False)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Modern Celery 5+ config keys (removes CDeprecationWarning)
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    broker_connection_retry_on_startup = True
    
    @staticmethod
    def setup_logging():
        import logging
        from pythonjsonlogger import jsonlogger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logHandler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
