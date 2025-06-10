"""
SAGE VIP Configuration API
Manages SAGE VIP integration settings, credentials, and configuration
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import os
import json
import logging
from typing import Dict, Any

from app import db
from models import User
from auth import super_user_required, role_required
from sage_vip_integration import SAGEVIPIntegration

# Create SAGE VIP Config API blueprint
sage_vip_config_api_bp = Blueprint('sage_vip_config_api', __name__, url_prefix='/api/v1/sage-vip/config')

logger = logging.getLogger(__name__)

def api_response(success=True, data=None, message=None, error=None, status_code=200):
    """Standard API response format"""
    response = {
        'success': success,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    if success:
        response['data'] = data or {}
        if message:
            response['message'] = message
    else:
        response['error'] = error or {'code': 'UNKNOWN_ERROR', 'message': 'An error occurred'}
        if message:
            response['error']['message'] = message
    
    return jsonify(response), status_code

# ====================
# CONFIGURATION MANAGEMENT
# ====================

@sage_vip_config_api_bp.route('/settings', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin')
def get_sage_settings():
    """Get current SAGE VIP integration settings (without sensitive data)"""
    try:
        settings = {
            'base_url': os.environ.get('SAGE_VIP_BASE_URL', ''),
            'company_db': os.environ.get('SAGE_VIP_COMPANY_DB', ''),
            'username': os.environ.get('SAGE_VIP_USERNAME', ''),
            'api_key_configured': bool(os.environ.get('SAGE_VIP_API_KEY')),
            'password_configured': bool(os.environ.get('SAGE_VIP_PASSWORD')),
            'integration_enabled': bool(os.environ.get('SAGE_VIP_ENABLED', 'false').lower() == 'true'),
            'sync_frequency': os.environ.get('SAGE_VIP_SYNC_FREQUENCY', 'daily'),
            'auto_sync_enabled': bool(os.environ.get('SAGE_VIP_AUTO_SYNC', 'false').lower() == 'true'),
            'last_sync_timestamp': os.environ.get('SAGE_VIP_LAST_SYNC'),
            'timeout_seconds': int(os.environ.get('SAGE_VIP_TIMEOUT', '30')),
            'retry_attempts': int(os.environ.get('SAGE_VIP_RETRY_ATTEMPTS', '3')),
            'batch_size': int(os.environ.get('SAGE_VIP_BATCH_SIZE', '100'))
        }
        
        return api_response(True, data={
            'sage_vip_settings': settings,
            'configuration_status': 'configured' if settings['api_key_configured'] else 'incomplete'
        })
        
    except Exception as e:
        logger.error(f"Get SAGE settings error: {e}")
        return api_response(False, error={
            'code': 'SETTINGS_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_config_api_bp.route('/settings', methods=['PUT'])
@login_required
@super_user_required
def update_sage_settings():
    """Update SAGE VIP integration settings"""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['base_url', 'company_db', 'username']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return api_response(False, error={
                'code': 'MISSING_REQUIRED_FIELDS',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status_code=400)
        
        # Update environment variables (in production, these would be managed differently)
        settings_updated = []
        
        # Basic connection settings
        if data.get('base_url'):
            os.environ['SAGE_VIP_BASE_URL'] = data['base_url']
            settings_updated.append('base_url')
            
        if data.get('company_db'):
            os.environ['SAGE_VIP_COMPANY_DB'] = data['company_db']
            settings_updated.append('company_db')
            
        if data.get('username'):
            os.environ['SAGE_VIP_USERNAME'] = data['username']
            settings_updated.append('username')
            
        # Optional settings
        if 'sync_frequency' in data:
            os.environ['SAGE_VIP_SYNC_FREQUENCY'] = data['sync_frequency']
            settings_updated.append('sync_frequency')
            
        if 'auto_sync_enabled' in data:
            os.environ['SAGE_VIP_AUTO_SYNC'] = str(data['auto_sync_enabled']).lower()
            settings_updated.append('auto_sync_enabled')
            
        if 'integration_enabled' in data:
            os.environ['SAGE_VIP_ENABLED'] = str(data['integration_enabled']).lower()
            settings_updated.append('integration_enabled')
            
        if 'timeout_seconds' in data:
            os.environ['SAGE_VIP_TIMEOUT'] = str(data['timeout_seconds'])
            settings_updated.append('timeout_seconds')
            
        if 'retry_attempts' in data:
            os.environ['SAGE_VIP_RETRY_ATTEMPTS'] = str(data['retry_attempts'])
            settings_updated.append('retry_attempts')
            
        if 'batch_size' in data:
            os.environ['SAGE_VIP_BATCH_SIZE'] = str(data['batch_size'])
            settings_updated.append('batch_size')
        
        return api_response(True, data={
            'settings_updated': settings_updated,
            'total_updated': len(settings_updated)
        }, message='SAGE VIP settings updated successfully')
        
    except Exception as e:
        logger.error(f"Update SAGE settings error: {e}")
        return api_response(False, error={
            'code': 'UPDATE_SETTINGS_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_config_api_bp.route('/credentials', methods=['PUT'])
@login_required
@super_user_required
def update_sage_credentials():
    """Update SAGE VIP authentication credentials"""
    try:
        data = request.get_json() or {}
        
        credentials_updated = []
        
        if data.get('api_key'):
            os.environ['SAGE_VIP_API_KEY'] = data['api_key']
            credentials_updated.append('api_key')
            
        if data.get('password'):
            os.environ['SAGE_VIP_PASSWORD'] = data['password']
            credentials_updated.append('password')
        
        if not credentials_updated:
            return api_response(False, error={
                'code': 'NO_CREDENTIALS_PROVIDED',
                'message': 'No credentials provided for update'
            }, status_code=400)
        
        # Test connection with new credentials
        try:
            sage_integration = SAGEVIPIntegration()
            test_result = sage_integration.test_connection()
            
            connection_status = 'success' if test_result.get('success') else 'failed'
            
        except Exception as e:
            connection_status = 'error'
            logger.warning(f"Credential test failed: {e}")
        
        return api_response(True, data={
            'credentials_updated': credentials_updated,
            'connection_test': connection_status,
            'test_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message='SAGE VIP credentials updated successfully')
        
    except Exception as e:
        logger.error(f"Update SAGE credentials error: {e}")
        return api_response(False, error={
            'code': 'UPDATE_CREDENTIALS_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# MAPPING CONFIGURATION
# ====================

@sage_vip_config_api_bp.route('/mappings/employees', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin')
def get_employee_field_mappings():
    """Get employee field mappings between WFM and SAGE VIP"""
    try:
        # Default field mappings
        mappings = {
            'wfm_to_sage': {
                'employee_id': 'EmployeeID',
                'username': 'EmployeeNumber',
                'first_name': 'FirstName',
                'last_name': 'LastName',
                'email': 'EmailAddress',
                'department_id': 'DepartmentCode',
                'hire_date': 'HireDate',
                'is_active': 'Active',
                'hourly_rate': 'HourlyRate'
            },
            'sage_to_wfm': {
                'EmployeeID': 'sage_employee_id',
                'EmployeeNumber': 'username',
                'FirstName': 'first_name',
                'LastName': 'last_name',
                'EmailAddress': 'email',
                'DepartmentCode': 'department_code',
                'HireDate': 'hire_date',
                'Active': 'is_active',
                'HourlyRate': 'hourly_rate'
            }
        }
        
        return api_response(True, data={
            'employee_mappings': mappings,
            'mapping_type': 'employee_fields'
        })
        
    except Exception as e:
        logger.error(f"Get employee mappings error: {e}")
        return api_response(False, error={
            'code': 'MAPPING_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_config_api_bp.route('/mappings/pay-codes', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin')
def get_pay_code_mappings():
    """Get pay code mappings between WFM and SAGE VIP"""
    try:
        # Default pay code mappings
        mappings = {
            'wfm_to_sage': {
                'REG': 'REGULAR',
                'OT': 'OVERTIME',
                'DT': 'DOUBLETIME',
                'SICK': 'SICK_LEAVE',
                'VAC': 'VACATION',
                'HOL': 'HOLIDAY'
            },
            'sage_to_wfm': {
                'REGULAR': 'REG',
                'OVERTIME': 'OT',
                'DOUBLETIME': 'DT',
                'SICK_LEAVE': 'SICK',
                'VACATION': 'VAC',
                'HOLIDAY': 'HOL'
            }
        }
        
        return api_response(True, data={
            'pay_code_mappings': mappings,
            'mapping_type': 'pay_codes'
        })
        
    except Exception as e:
        logger.error(f"Get pay code mappings error: {e}")
        return api_response(False, error={
            'code': 'MAPPING_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_config_api_bp.route('/mappings/departments', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin')
def get_department_mappings():
    """Get department mappings between WFM and SAGE VIP"""
    try:
        # Default department mappings
        mappings = {
            'wfm_to_sage': {
                'Human Resources': 'HR',
                'Information Technology': 'IT',
                'Finance': 'FIN',
                'Production': 'PROD',
                'Quality Control': 'QC',
                'Sales': 'SALES',
                'Warehouse Operations': 'WAREHOUSE'
            },
            'sage_to_wfm': {
                'HR': 'Human Resources',
                'IT': 'Information Technology',
                'FIN': 'Finance',
                'PROD': 'Production',
                'QC': 'Quality Control',
                'SALES': 'Sales',
                'WAREHOUSE': 'Warehouse Operations'
            }
        }
        
        return api_response(True, data={
            'department_mappings': mappings,
            'mapping_type': 'departments'
        })
        
    except Exception as e:
        logger.error(f"Get department mappings error: {e}")
        return api_response(False, error={
            'code': 'MAPPING_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# SYNC CONFIGURATION
# ====================

@sage_vip_config_api_bp.route('/sync/schedule', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin')
def get_sync_schedule():
    """Get current sync schedule configuration"""
    try:
        schedule_config = {
            'auto_sync_enabled': os.environ.get('SAGE_VIP_AUTO_SYNC', 'false').lower() == 'true',
            'sync_frequency': os.environ.get('SAGE_VIP_SYNC_FREQUENCY', 'daily'),
            'sync_time': os.environ.get('SAGE_VIP_SYNC_TIME', '02:00'),
            'last_sync': os.environ.get('SAGE_VIP_LAST_SYNC'),
            'next_sync': os.environ.get('SAGE_VIP_NEXT_SYNC'),
            'sync_types': {
                'employees': os.environ.get('SAGE_VIP_SYNC_EMPLOYEES', 'true').lower() == 'true',
                'timesheet': os.environ.get('SAGE_VIP_SYNC_TIMESHEET', 'true').lower() == 'true',
                'leave': os.environ.get('SAGE_VIP_SYNC_LEAVE', 'true').lower() == 'true',
                'departments': os.environ.get('SAGE_VIP_SYNC_DEPARTMENTS', 'false').lower() == 'true',
                'pay_codes': os.environ.get('SAGE_VIP_SYNC_PAY_CODES', 'false').lower() == 'true'
            },
            'retry_config': {
                'max_retries': int(os.environ.get('SAGE_VIP_RETRY_ATTEMPTS', '3')),
                'retry_delay': int(os.environ.get('SAGE_VIP_RETRY_DELAY', '60')),
                'exponential_backoff': os.environ.get('SAGE_VIP_EXPONENTIAL_BACKOFF', 'true').lower() == 'true'
            }
        }
        
        return api_response(True, data={
            'sync_schedule': schedule_config
        })
        
    except Exception as e:
        logger.error(f"Get sync schedule error: {e}")
        return api_response(False, error={
            'code': 'SYNC_SCHEDULE_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_config_api_bp.route('/sync/schedule', methods=['PUT'])
@login_required
@super_user_required
def update_sync_schedule():
    """Update sync schedule configuration"""
    try:
        data = request.get_json() or {}
        
        settings_updated = []
        
        # Update basic sync settings
        if 'auto_sync_enabled' in data:
            os.environ['SAGE_VIP_AUTO_SYNC'] = str(data['auto_sync_enabled']).lower()
            settings_updated.append('auto_sync_enabled')
            
        if data.get('sync_frequency'):
            valid_frequencies = ['hourly', 'daily', 'weekly', 'monthly']
            if data['sync_frequency'] in valid_frequencies:
                os.environ['SAGE_VIP_SYNC_FREQUENCY'] = data['sync_frequency']
                settings_updated.append('sync_frequency')
            else:
                return api_response(False, error={
                    'code': 'INVALID_FREQUENCY',
                    'message': f'Invalid sync frequency. Must be one of: {", ".join(valid_frequencies)}'
                }, status_code=400)
                
        if data.get('sync_time'):
            os.environ['SAGE_VIP_SYNC_TIME'] = data['sync_time']
            settings_updated.append('sync_time')
        
        # Update sync type settings
        sync_types = data.get('sync_types', {})
        for sync_type, enabled in sync_types.items():
            env_key = f'SAGE_VIP_SYNC_{sync_type.upper()}'
            os.environ[env_key] = str(enabled).lower()
            settings_updated.append(f'sync_types.{sync_type}')
        
        # Update retry configuration
        retry_config = data.get('retry_config', {})
        if 'max_retries' in retry_config:
            os.environ['SAGE_VIP_RETRY_ATTEMPTS'] = str(retry_config['max_retries'])
            settings_updated.append('retry_config.max_retries')
            
        if 'retry_delay' in retry_config:
            os.environ['SAGE_VIP_RETRY_DELAY'] = str(retry_config['retry_delay'])
            settings_updated.append('retry_config.retry_delay')
            
        if 'exponential_backoff' in retry_config:
            os.environ['SAGE_VIP_EXPONENTIAL_BACKOFF'] = str(retry_config['exponential_backoff']).lower()
            settings_updated.append('retry_config.exponential_backoff')
        
        return api_response(True, data={
            'settings_updated': settings_updated,
            'total_updated': len(settings_updated)
        }, message='Sync schedule updated successfully')
        
    except Exception as e:
        logger.error(f"Update sync schedule error: {e}")
        return api_response(False, error={
            'code': 'UPDATE_SYNC_SCHEDULE_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# HEALTH CHECK & MONITORING
# ====================

@sage_vip_config_api_bp.route('/health', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def get_integration_health():
    """Get SAGE VIP integration health status"""
    try:
        sage_integration = SAGEVIPIntegration()
        
        # Test basic connectivity
        connection_test = sage_integration.test_connection()
        
        # Get configuration status
        config_complete = all([
            os.environ.get('SAGE_VIP_BASE_URL'),
            os.environ.get('SAGE_VIP_API_KEY'),
            os.environ.get('SAGE_VIP_USERNAME'),
            os.environ.get('SAGE_VIP_PASSWORD'),
            os.environ.get('SAGE_VIP_COMPANY_DB')
        ])
        
        health_status = {
            'overall_status': 'healthy' if connection_test.get('success') and config_complete else 'unhealthy',
            'connection_status': 'connected' if connection_test.get('success') else 'disconnected',
            'configuration_status': 'complete' if config_complete else 'incomplete',
            'last_sync': os.environ.get('SAGE_VIP_LAST_SYNC'),
            'integration_enabled': os.environ.get('SAGE_VIP_ENABLED', 'false').lower() == 'true',
            'auto_sync_enabled': os.environ.get('SAGE_VIP_AUTO_SYNC', 'false').lower() == 'true',
            'health_check_timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Add detailed status for each component
        health_status['components'] = {
            'authentication': 'ok' if connection_test.get('success') else 'error',
            'api_endpoints': 'ok' if connection_test.get('success') else 'unknown',
            'database_connection': 'ok' if config_complete else 'error',
            'field_mappings': 'ok',  # Assuming mappings are configured
            'sync_scheduler': 'ok' if health_status['auto_sync_enabled'] else 'disabled'
        }
        
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        
        return api_response(True, data={
            'integration_health': health_status
        }, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Integration health check error: {e}")
        return api_response(False, error={
            'code': 'HEALTH_CHECK_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# ERROR HANDLERS
# ====================

@sage_vip_config_api_bp.errorhandler(400)
def bad_request(error):
    return api_response(False, error={
        'code': 'BAD_REQUEST',
        'message': 'Invalid configuration request'
    }, status_code=400)

@sage_vip_config_api_bp.errorhandler(403)
def forbidden(error):
    return api_response(False, error={
        'code': 'FORBIDDEN',
        'message': 'Insufficient permissions for SAGE VIP configuration'
    }, status_code=403)