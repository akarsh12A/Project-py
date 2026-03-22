from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from celery import Celery
from .config import Config

db = SQLAlchemy()

def create_celery_app(app=None):
    app = app or create_app()
    celery = Celery(
        app.import_name,
        broker=app.config.get('broker_url'),
        backend=app.config.get('result_backend'),
        include=['app.tasks']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Re-initialize the logging standard
    Config.setup_logging()

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints safely here (lazy import to wait for db)
    with app.app_context():
        from .routes import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')

    return app
