import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
migrate = Migrate()

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Set secret key from environment
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    
    # Configure for proxy (needed for url_for to generate with https)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize Flask-Login
    from auth_simple import init_login_manager
    init_login_manager(app)
    
    # Register blueprints/routes
    from routes import main_bp
    from auth_simple import auth_bp
    from time_attendance import time_attendance_bp
    from scheduling import scheduling_bp
    from leave_management import leave_management_bp
    from pay_rules import pay_rules_bp
    from pay_codes import pay_codes_bp
    from payroll import payroll_bp
    from api import api_bp
    from automation_engine import automation_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(time_attendance_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(leave_management_bp)
    app.register_blueprint(pay_rules_bp)
    app.register_blueprint(pay_codes_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(automation_bp, url_prefix='/automation')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('error.html', 
                             error_code=404, 
                             error_message="Page not found"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('error.html', 
                             error_code=500, 
                             error_message="Internal server error"), 500
    
    # Register CLI commands
    from cli_commands import register_commands
    register_commands(app)
    
    # Create database tables
    with app.app_context():
        # Import models to ensure tables are created
        import models  # noqa: F401
        
        try:
            db.create_all()
            logging.info("Database tables created successfully")
        except Exception as e:
            logging.error(f"Error creating database tables: {e}")
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
