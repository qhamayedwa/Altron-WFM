"""
Standardization Utilities for Time & Attendance System
Ensures consistent API responses, error handling, and data validation
"""

from flask import jsonify, request
from datetime import datetime
from functools import wraps
import logging
import traceback

class StandardizedResponse:
    """
    Standardized API response format for consistency
    Principle: STANDARDIZATION - Uniform response structure
    """
    
    @staticmethod
    def success(data=None, message=None, status_code=200, meta=None):
        """Standard success response format"""
        response = {
            'success': True,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': data or {}
        }
        
        if message:
            response['message'] = message
            
        if meta:
            response['meta'] = meta
            
        return jsonify(response), status_code
    
    @staticmethod
    def error(code, message, details=None, status_code=400, trace=None):
        """Standard error response format"""
        response = {
            'success': False,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'error': {
                'code': code,
                'message': message
            }
        }
        
        if details:
            response['error']['details'] = details
            
        if trace and logging.getLogger().isEnabledFor(logging.DEBUG):
            response['error']['trace'] = trace
            
        return jsonify(response), status_code
    
    @staticmethod
    def validation_error(field_errors, message="Validation failed"):
        """Standard validation error response"""
        return StandardizedResponse.error(
            code='VALIDATION_ERROR',
            message=message,
            details={'field_errors': field_errors},
            status_code=422
        )

class CentralizedErrorHandler:
    """
    Centralized error handling for all system components
    Principle: STANDARDIZATION - Consistent error processing
    """
    
    @staticmethod
    def handle_database_error(error):
        """Handle database-related errors"""
        logging.error(f"Database error: {str(error)}")
        
        # Check for common database issues
        error_str = str(error).lower()
        
        if 'unique constraint' in error_str:
            return StandardizedResponse.error(
                code='DUPLICATE_ENTRY',
                message='A record with this information already exists',
                status_code=409
            )
        elif 'foreign key constraint' in error_str:
            return StandardizedResponse.error(
                code='INVALID_REFERENCE',
                message='Referenced record does not exist',
                status_code=400
            )
        elif 'not null constraint' in error_str:
            return StandardizedResponse.error(
                code='MISSING_REQUIRED_FIELD',
                message='Required field cannot be empty',
                status_code=400
            )
        else:
            return StandardizedResponse.error(
                code='DATABASE_ERROR',
                message='Database operation failed',
                status_code=500
            )
    
    @staticmethod
    def handle_authentication_error():
        """Handle authentication failures"""
        return StandardizedResponse.error(
            code='AUTH_REQUIRED',
            message='Authentication required to access this resource',
            status_code=401
        )
    
    @staticmethod
    def handle_authorization_error(required_roles=None):
        """Handle authorization failures"""
        message = 'Insufficient permissions to access this resource'
        if required_roles:
            message += f'. Required roles: {", ".join(required_roles)}'
        
        return StandardizedResponse.error(
            code='INSUFFICIENT_PERMISSIONS',
            message=message,
            status_code=403
        )
    
    @staticmethod
    def handle_not_found_error(resource_type='Resource'):
        """Handle resource not found errors"""
        return StandardizedResponse.error(
            code='RESOURCE_NOT_FOUND',
            message=f'{resource_type} not found',
            status_code=404
        )
    
    @staticmethod
    def handle_system_error(error, context=None):
        """Handle unexpected system errors"""
        logging.error(f"System error in {context}: {str(error)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        return StandardizedResponse.error(
            code='SYSTEM_ERROR',
            message='An internal system error occurred',
            trace=traceback.format_exc() if logging.getLogger().isEnabledFor(logging.DEBUG) else None,
            status_code=500
        )

def standardized_endpoint(func):
    """
    Decorator to standardize endpoint responses and error handling
    Principle: STANDARDIZATION - Consistent endpoint behavior
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Execute the endpoint function
            result = func(*args, **kwargs)
            
            # If result is already a response, return it
            if hasattr(result, 'status_code'):
                return result
            
            # If result is a tuple (data, status_code), format as success
            if isinstance(result, tuple) and len(result) == 2:
                data, status_code = result
                return StandardizedResponse.success(data=data, status_code=status_code)
            
            # If result is just data, format as success with 200
            return StandardizedResponse.success(data=result)
            
        except ValueError as e:
            return CentralizedErrorHandler.handle_database_error(e)
        except PermissionError as e:
            return CentralizedErrorHandler.handle_authorization_error()
        except FileNotFoundError as e:
            return CentralizedErrorHandler.handle_not_found_error()
        except Exception as e:
            return CentralizedErrorHandler.handle_system_error(e, context=func.__name__)
    
    return wrapper

class DataValidator:
    """
    Centralized data validation for system consistency
    Principle: STANDARDIZATION - Uniform validation rules
    """
    
    @staticmethod
    def validate_required_fields(data, required_fields):
        """Validate that all required fields are present and not empty"""
        errors = {}
        
        for field in required_fields:
            if field not in data:
                errors[field] = 'This field is required'
            elif data[field] is None or str(data[field]).strip() == '':
                errors[field] = 'This field cannot be empty'
        
        return errors
    
    @staticmethod
    def validate_date_range(start_date, end_date, field_prefix=''):
        """Validate date range consistency"""
        errors = {}
        
        try:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if start_date > end_date:
                errors[f'{field_prefix}end_date'] = 'End date must be after start date'
                
        except ValueError:
            errors[f'{field_prefix}date_format'] = 'Invalid date format. Use YYYY-MM-DD'
        
        return errors
    
    @staticmethod
    def validate_time_entry(data):
        """Validate time entry data"""
        errors = {}
        
        # Check required fields
        required_errors = DataValidator.validate_required_fields(
            data, ['clock_in_time']
        )
        errors.update(required_errors)
        
        # Validate time logic
        if 'clock_in_time' in data and 'clock_out_time' in data:
            try:
                clock_in = datetime.fromisoformat(data['clock_in_time'].replace('Z', '+00:00'))
                clock_out = datetime.fromisoformat(data['clock_out_time'].replace('Z', '+00:00'))
                
                if clock_out <= clock_in:
                    errors['clock_out_time'] = 'Clock out time must be after clock in time'
                
                # Check for reasonable duration (not more than 24 hours)
                duration = clock_out - clock_in
                if duration.total_seconds() > 86400:  # 24 hours
                    errors['duration'] = 'Work duration cannot exceed 24 hours'
                    
            except ValueError:
                errors['time_format'] = 'Invalid time format'
        
        return errors
    
    @staticmethod
    def validate_leave_application(data):
        """Validate leave application data"""
        errors = {}
        
        # Check required fields
        required_errors = DataValidator.validate_required_fields(
            data, ['leave_type_id', 'start_date', 'end_date', 'reason']
        )
        errors.update(required_errors)
        
        # Validate date range
        if 'start_date' in data and 'end_date' in data:
            date_errors = DataValidator.validate_date_range(
                data['start_date'], data['end_date']
            )
            errors.update(date_errors)
        
        # Validate reason length
        if 'reason' in data and len(data['reason']) < 10:
            errors['reason'] = 'Reason must be at least 10 characters long'
        
        return errors
    
    @staticmethod
    def validate_schedule_data(data):
        """Validate schedule creation data"""
        errors = {}
        
        # Check required fields
        required_errors = DataValidator.validate_required_fields(
            data, ['user_id', 'date', 'start_time', 'end_time']
        )
        errors.update(required_errors)
        
        # Validate time range
        if 'start_time' in data and 'end_time' in data:
            try:
                start_time = datetime.strptime(data['start_time'], '%H:%M').time()
                end_time = datetime.strptime(data['end_time'], '%H:%M').time()
                
                if end_time <= start_time:
                    errors['end_time'] = 'End time must be after start time'
                    
            except ValueError:
                errors['time_format'] = 'Invalid time format. Use HH:MM'
        
        return errors

class SystemLogger:
    """
    Centralized logging for system-wide consistency
    Principle: STANDARDIZATION - Uniform logging format
    """
    
    def __init__(self, module_name):
        self.logger = logging.getLogger(module_name)
        self.module_name = module_name
    
    def log_user_action(self, user_id, action, resource_type, resource_id=None, details=None):
        """Log user actions for audit trail"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'module': self.module_name,
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None
        }
        
        if details:
            log_entry['details'] = details
        
        self.logger.info(f"User Action: {log_entry}")
        return log_entry
    
    def log_system_event(self, event_type, message, data=None):
        """Log system events"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'message': message,
            'module': self.module_name
        }
        
        if data:
            log_entry['data'] = data
        
        self.logger.info(f"System Event: {log_entry}")
        return log_entry
    
    def log_error(self, error, context=None, user_id=None):
        """Log errors with context"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(error),
            'context': context,
            'module': self.module_name,
            'user_id': user_id,
            'traceback': traceback.format_exc()
        }
        
        self.logger.error(f"Error: {log_entry}")
        return log_entry

def apply_standardization_to_blueprint(blueprint):
    """
    Apply standardization to all routes in a blueprint
    Principle: STANDARDIZATION - Consistent blueprint behavior
    """
    
    @blueprint.before_request
    def log_request():
        """Log all requests for audit trail"""
        if request.endpoint:
            SystemLogger(blueprint.name).log_system_event(
                'API_REQUEST',
                f"Request to {request.endpoint}",
                {
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr
                }
            )
    
    @blueprint.after_request
    def log_response(response):
        """Log all responses"""
        SystemLogger(blueprint.name).log_system_event(
            'API_RESPONSE',
            f"Response from {request.endpoint}",
            {
                'status_code': response.status_code,
                'content_type': response.content_type
            }
        )
        return response
    
    @blueprint.errorhandler(400)
    def handle_bad_request(error):
        return CentralizedErrorHandler.handle_database_error(error)
    
    @blueprint.errorhandler(401)
    def handle_unauthorized(error):
        return CentralizedErrorHandler.handle_authentication_error()
    
    @blueprint.errorhandler(403)
    def handle_forbidden(error):
        return CentralizedErrorHandler.handle_authorization_error()
    
    @blueprint.errorhandler(404)
    def handle_not_found(error):
        return CentralizedErrorHandler.handle_not_found_error()
    
    @blueprint.errorhandler(500)
    def handle_internal_error(error):
        return CentralizedErrorHandler.handle_system_error(error, blueprint.name)

# Configuration for system-wide standards
STANDARDIZATION_CONFIG = {
    'api_version': 'v1',
    'response_format': 'json',
    'date_format': '%Y-%m-%d',
    'datetime_format': '%Y-%m-%dT%H:%M:%SZ',
    'timezone': 'UTC',
    'pagination_default_size': 20,
    'pagination_max_size': 100,
    'cache_duration': 3600,  # 1 hour
    'rate_limit_per_minute': 100,
    'rate_limit_per_hour': 1000
}