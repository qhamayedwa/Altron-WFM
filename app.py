import os
import logging
from flask import Flask, Blueprint, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from datetime import datetime

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
    
    # Register currency formatter for templates
    from currency_formatter import currency_filter
    app.jinja_env.filters['currency'] = currency_filter
    
    # Register timezone filters for templates
    from timezone_utils import datetime_filter, date_filter, time_filter
    app.jinja_env.filters['datetime'] = datetime_filter
    app.jinja_env.filters['date'] = date_filter
    app.jinja_env.filters['time'] = time_filter
    
    # Register hours filter for templates
    def hours_minutes_filter(value):
        """Convert decimal hours to hours and minutes format"""
        if not value:
            return "0h 0m"
        
        total_minutes = int(value * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
    
    app.jinja_env.filters['hours_minutes'] = hours_minutes_filter
    
    # Register department filter for templates
    def get_department_name(user):
        """Get department name from user, handling both legacy and hierarchical departments"""
        if hasattr(user, 'employee_department') and user.employee_department:
            return user.employee_department.name
        elif user.department:
            return user.department
        else:
            return 'Unassigned'
    
    app.jinja_env.filters['department_name'] = get_department_name
    
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
    from ai_scheduling import ai_scheduling_bp
    from organization_management import org_bp
    from employee_import import import_bp
    from debug_roles import debug_bp
    from dashboard_management import dashboard_bp
    from notifications import notifications_bp
    from pay_code_admin import pay_code_admin_bp
    from sage_vip_routes import sage_vip_bp
    from sage_vip_api import sage_vip_api_bp
    from sage_vip_config_api import sage_vip_config_api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(time_attendance_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(leave_management_bp)
    app.register_blueprint(pay_rules_bp)
    app.register_blueprint(pay_codes_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(automation_bp)
    app.register_blueprint(ai_scheduling_bp)
    app.register_blueprint(org_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(pay_code_admin_bp)
    app.register_blueprint(sage_vip_bp)
    app.register_blueprint(sage_vip_api_bp)
    app.register_blueprint(sage_vip_config_api_bp)

    
    # Register additional API routes without version prefix for frontend compatibility
    from api import api_bp as api_v1_bp
    api_compat_bp = Blueprint('api_compat', __name__, url_prefix='/api')
    
    # Add database status endpoint for frontend
    @api_compat_bp.route('/db-status', methods=['GET'])
    def api_database_status_compat():
        """Database status endpoint for frontend monitoring"""
        try:
            # Test database connection
            db.session.execute(db.text('SELECT 1'))
            
            # Get table counts for monitoring
            from models import User, TimeEntry, Schedule, LeaveApplication
            table_counts = {
                'users': User.query.count(),
                'time_entries': TimeEntry.query.count(),
                'schedules': Schedule.query.count(),
                'leave_applications': LeaveApplication.query.count()
            }
            
            return jsonify({
                'status': 'connected',
                'message': 'Database connection successful',
                'tables': table_counts,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            
        except Exception as e:
            logging.error(f"Database status check failed: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }), 500
    
    @api_compat_bp.route('/system-info', methods=['GET'])
    def api_system_info_compat():
        """System info endpoint for frontend compatibility"""
        return jsonify({
            'success': True,
            'data': {
                'app_name': 'WFM Time & Attendance',
                'version': '1.0.0',
                'status': 'connected'
            }
        })
    
    app.register_blueprint(api_compat_bp)
    
    # Register time tracking routes
    from time_tracking_routes import time_tracking_bp
    app.register_blueprint(time_tracking_bp, url_prefix='/time')
    
    # Register dashboard management routes
    from dashboard_management import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    
    # Register pulse survey routes
    from pulse_survey import pulse_survey_bp
    app.register_blueprint(pulse_survey_bp, url_prefix='/pulse')
    
    # Register tenant management routes
    from tenant_management import tenant_bp
    app.register_blueprint(tenant_bp, url_prefix='/tenant')
    
    # Register AI-powered routes
    from ai_routes import ai_bp
    app.register_blueprint(ai_bp)
    
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
            
            # Initialize notification system
            from notifications import init_notification_types
            init_notification_types()
            logging.info("Notification system initialized")
        except Exception as e:
            logging.error(f"Error creating database tables: {e}")
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
