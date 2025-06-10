"""
SAGE VIP Payroll Integration API
Comprehensive REST API endpoints for SAGE VIP Payroll system integration
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta, date
from sqlalchemy import and_, func, or_
import logging
import json
from typing import Dict, List, Optional, Any

from app import db
from models import User, TimeEntry, LeaveApplication, PayCode, Department, PayCalculation
from auth import role_required, super_user_required
from sage_vip_integration import SAGEVIPIntegration
from currency_formatter import format_currency

# Create SAGE VIP API blueprint
sage_vip_api_bp = Blueprint('sage_vip_api', __name__, url_prefix='/api/v1/sage-vip')

# Initialize SAGE VIP integration
sage_integration = SAGEVIPIntegration()

logger = logging.getLogger(__name__)

def api_response(success=True, data=None, message=None, error=None, status_code=200):
    """Standard API response format for SAGE VIP integration"""
    response = {
        'success': success,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'integration': 'SAGE_VIP'
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
# CONNECTION & STATUS APIs
# ====================

@sage_vip_api_bp.route('/status', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def get_connection_status():
    """Get SAGE VIP integration connection status"""
    try:
        status = sage_integration.test_connection()
        
        return api_response(True, data={
            'connection_status': 'connected' if status['success'] else 'disconnected',
            'last_tested': datetime.utcnow().isoformat() + 'Z',
            'sage_version': status.get('version', 'unknown'),
            'company_database': sage_integration.company_db,
            'endpoints_available': list(sage_integration.endpoints.keys())
        })
        
    except Exception as e:
        logger.error(f"SAGE VIP status check error: {e}")
        return api_response(False, error={
            'code': 'CONNECTION_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/test-connection', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def test_connection():
    """Test connection to SAGE VIP Payroll system"""
    try:
        result = sage_integration.test_connection()
        
        if result['success']:
            return api_response(True, data={
                'connection_test': 'successful',
                'response_time_ms': result.get('response_time', 0),
                'sage_info': result.get('system_info', {})
            }, message='Successfully connected to SAGE VIP Payroll system')
        else:
            return api_response(False, error={
                'code': 'CONNECTION_FAILED',
                'message': result.get('message', 'Connection test failed')
            }, status_code=503)
            
    except Exception as e:
        logger.error(f"SAGE VIP connection test error: {e}")
        return api_response(False, error={
            'code': 'TEST_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# EMPLOYEE SYNC APIs
# ====================

@sage_vip_api_bp.route('/employees/sync-from-sage', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def sync_employees_from_sage():
    """Sync employees from SAGE VIP to WFM system"""
    try:
        data = request.get_json() or {}
        force_update = data.get('force_update', False)
        department_filter = data.get('department_filter')
        
        employees = sage_integration.sync_employees_from_sage(
            force_update=force_update,
            department_filter=department_filter
        )
        
        sync_stats = {
            'total_processed': len(employees),
            'new_employees': sum(1 for emp in employees if emp.get('is_new')),
            'updated_employees': sum(1 for emp in employees if emp.get('is_updated')),
            'skipped_employees': sum(1 for emp in employees if emp.get('is_skipped'))
        }
        
        return api_response(True, data={
            'sync_results': employees,
            'statistics': sync_stats,
            'sync_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=f'Successfully synced {len(employees)} employees from SAGE VIP')
        
    except Exception as e:
        logger.error(f"Employee sync from SAGE error: {e}")
        return api_response(False, error={
            'code': 'SYNC_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/employees/push-to-sage', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def push_employees_to_sage():
    """Push employee updates from WFM to SAGE VIP"""
    try:
        data = request.get_json() or {}
        employee_ids = data.get('employee_ids', [])
        push_all = data.get('push_all', False)
        
        if not push_all and not employee_ids:
            return api_response(False, error={
                'code': 'MISSING_PARAMETERS',
                'message': 'Either employee_ids or push_all must be specified'
            }, status_code=400)
        
        if push_all:
            employees = User.query.filter_by(is_active=True).all()
        else:
            employees = User.query.filter(User.id.in_(employee_ids)).all()
        
        results = sage_integration.push_employees_to_sage(employees)
        
        return api_response(True, data={
            'push_results': results,
            'total_pushed': len(results),
            'push_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=f'Successfully pushed {len(results)} employees to SAGE VIP')
        
    except Exception as e:
        logger.error(f"Employee push to SAGE error: {e}")
        return api_response(False, error={
            'code': 'PUSH_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# TIME ENTRY APIs
# ====================

@sage_vip_api_bp.route('/timesheet/push', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def push_timesheet_to_sage():
    """Push time entries from WFM to SAGE VIP Payroll"""
    try:
        data = request.get_json() or {}
        
        # Parse date parameters
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        employee_ids = data.get('employee_ids', [])
        department_ids = data.get('department_ids', [])
        
        if not start_date_str or not end_date_str:
            return api_response(False, error={
                'code': 'MISSING_DATES',
                'message': 'Both start_date and end_date are required'
            }, status_code=400)
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return api_response(False, error={
                'code': 'INVALID_DATE_FORMAT',
                'message': 'Date format must be YYYY-MM-DD'
            }, status_code=400)
        
        if end_date < start_date:
            return api_response(False, error={
                'code': 'INVALID_DATE_RANGE',
                'message': 'End date must be after start date'
            }, status_code=400)
        
        # Build query for time entries
        query = TimeEntry.query.filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                TimeEntry.status == 'Closed'
            )
        )
        
        # Apply filters
        if employee_ids:
            query = query.filter(TimeEntry.user_id.in_(employee_ids))
        
        if department_ids:
            query = query.join(User).filter(User.department_id.in_(department_ids))
        
        time_entries = query.all()
        
        if not time_entries:
            return api_response(True, data={
                'push_results': [],
                'total_entries': 0,
                'message': 'No time entries found for the specified criteria'
            })
        
        # Push to SAGE VIP
        results = sage_integration.push_time_entries_to_sage(time_entries)
        
        push_stats = {
            'total_entries': len(time_entries),
            'successful_pushes': sum(1 for r in results if r.get('success')),
            'failed_pushes': sum(1 for r in results if not r.get('success')),
            'total_hours': sum(entry.total_hours for entry in time_entries),
            'total_regular_hours': sum(entry.regular_hours for entry in time_entries),
            'total_overtime_hours': sum(entry.overtime_hours for entry in time_entries)
        }
        
        return api_response(True, data={
            'push_results': results,
            'statistics': push_stats,
            'date_range': {
                'start_date': start_date_str,
                'end_date': end_date_str
            },
            'push_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=f'Successfully processed {len(time_entries)} time entries')
        
    except Exception as e:
        logger.error(f"Timesheet push to SAGE error: {e}")
        return api_response(False, error={
            'code': 'TIMESHEET_PUSH_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/timesheet/validate', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def validate_timesheet_data():
    """Validate time entry data before pushing to SAGE VIP"""
    try:
        data = request.get_json() or {}
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        if not start_date_str or not end_date_str:
            return api_response(False, error={
                'code': 'MISSING_DATES',
                'message': 'Both start_date and end_date are required'
            }, status_code=400)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Get time entries for validation
        time_entries = TimeEntry.query.filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                TimeEntry.status == 'Closed'
            )
        ).all()
        
        validation_results = sage_integration.validate_time_entries(time_entries)
        
        return api_response(True, data={
            'validation_results': validation_results,
            'total_entries_checked': len(time_entries),
            'validation_timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except Exception as e:
        logger.error(f"Timesheet validation error: {e}")
        return api_response(False, error={
            'code': 'VALIDATION_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# LEAVE MANAGEMENT APIs
# ====================

@sage_vip_api_bp.route('/leave/push', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def push_leave_to_sage():
    """Push leave applications from WFM to SAGE VIP"""
    try:
        data = request.get_json() or {}
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        status_filter = data.get('status', 'Approved')
        
        if not start_date_str or not end_date_str:
            return api_response(False, error={
                'code': 'MISSING_DATES',
                'message': 'Both start_date and end_date are required'
            }, status_code=400)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get approved leave applications
        leave_applications = LeaveApplication.query.filter(
            and_(
                LeaveApplication.start_date >= start_date,
                LeaveApplication.end_date <= end_date,
                LeaveApplication.status == status_filter
            )
        ).all()
        
        if not leave_applications:
            return api_response(True, data={
                'push_results': [],
                'total_applications': 0,
                'message': f'No {status_filter.lower()} leave applications found'
            })
        
        results = sage_integration.push_leave_applications_to_sage(leave_applications)
        
        leave_stats = {
            'total_applications': len(leave_applications),
            'successful_pushes': sum(1 for r in results if r.get('success')),
            'failed_pushes': sum(1 for r in results if not r.get('success')),
            'total_days': sum(app.total_hours() / 8 for app in leave_applications)
        }
        
        return api_response(True, data={
            'push_results': results,
            'statistics': leave_stats,
            'push_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=f'Successfully processed {len(leave_applications)} leave applications')
        
    except Exception as e:
        logger.error(f"Leave push to SAGE error: {e}")
        return api_response(False, error={
            'code': 'LEAVE_PUSH_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# PAYROLL CALCULATION APIs
# ====================

@sage_vip_api_bp.route('/payroll/calculate', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def calculate_payroll_for_sage():
    """Calculate payroll data for SAGE VIP integration"""
    try:
        data = request.get_json() or {}
        pay_period_start = data.get('pay_period_start')
        pay_period_end = data.get('pay_period_end')
        employee_ids = data.get('employee_ids', [])
        
        if not pay_period_start or not pay_period_end:
            return api_response(False, error={
                'code': 'MISSING_PAY_PERIOD',
                'message': 'Both pay_period_start and pay_period_end are required'
            }, status_code=400)
        
        start_date = datetime.strptime(pay_period_start, '%Y-%m-%d').date()
        end_date = datetime.strptime(pay_period_end, '%Y-%m-%d').date()
        
        # Calculate payroll for specified period
        payroll_calculations = sage_integration.calculate_payroll_for_period(
            start_date, end_date, employee_ids
        )
        
        # Calculate totals
        total_gross_pay = sum(calc.get('gross_pay', 0) for calc in payroll_calculations)
        total_regular_hours = sum(calc.get('regular_hours', 0) for calc in payroll_calculations)
        total_overtime_hours = sum(calc.get('overtime_hours', 0) for calc in payroll_calculations)
        
        return api_response(True, data={
            'payroll_calculations': payroll_calculations,
            'summary': {
                'pay_period_start': pay_period_start,
                'pay_period_end': pay_period_end,
                'total_employees': len(payroll_calculations),
                'total_gross_pay': format_currency(total_gross_pay),
                'total_regular_hours': round(total_regular_hours, 2),
                'total_overtime_hours': round(total_overtime_hours, 2)
            },
            'calculation_timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except Exception as e:
        logger.error(f"Payroll calculation error: {e}")
        return api_response(False, error={
            'code': 'PAYROLL_CALCULATION_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/payroll/push', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def push_payroll_to_sage():
    """Push calculated payroll data to SAGE VIP"""
    try:
        data = request.get_json() or {}
        payroll_data = data.get('payroll_data', [])
        
        if not payroll_data:
            return api_response(False, error={
                'code': 'MISSING_PAYROLL_DATA',
                'message': 'Payroll data is required'
            }, status_code=400)
        
        results = sage_integration.push_payroll_data_to_sage(payroll_data)
        
        push_stats = {
            'total_records': len(payroll_data),
            'successful_pushes': sum(1 for r in results if r.get('success')),
            'failed_pushes': sum(1 for r in results if not r.get('success')),
            'total_amount': sum(record.get('gross_pay', 0) for record in payroll_data)
        }
        
        return api_response(True, data={
            'push_results': results,
            'statistics': push_stats,
            'total_amount_pushed': format_currency(push_stats['total_amount']),
            'push_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=f'Successfully pushed {push_stats["successful_pushes"]} payroll records')
        
    except Exception as e:
        logger.error(f"Payroll push to SAGE error: {e}")
        return api_response(False, error={
            'code': 'PAYROLL_PUSH_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# DEPARTMENT & PAY CODE SYNC APIs
# ====================

@sage_vip_api_bp.route('/departments/sync', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def sync_departments_with_sage():
    """Sync departments between WFM and SAGE VIP"""
    try:
        data = request.get_json() or {}
        sync_direction = data.get('direction', 'from_sage')  # 'from_sage' or 'to_sage'
        
        if sync_direction == 'from_sage':
            results = sage_integration.sync_departments_from_sage()
            message = f'Successfully synced {len(results)} departments from SAGE VIP'
        else:
            departments = Department.query.filter_by(is_active=True).all()
            results = sage_integration.push_departments_to_sage(departments)
            message = f'Successfully pushed {len(results)} departments to SAGE VIP'
        
        return api_response(True, data={
            'sync_results': results,
            'sync_direction': sync_direction,
            'sync_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=message)
        
    except Exception as e:
        logger.error(f"Department sync error: {e}")
        return api_response(False, error={
            'code': 'DEPARTMENT_SYNC_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/pay-codes/sync', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def sync_pay_codes_with_sage():
    """Sync pay codes between WFM and SAGE VIP"""
    try:
        data = request.get_json() or {}
        sync_direction = data.get('direction', 'from_sage')
        
        if sync_direction == 'from_sage':
            results = sage_integration.sync_pay_codes_from_sage()
            message = f'Successfully synced {len(results)} pay codes from SAGE VIP'
        else:
            pay_codes = PayCode.query.filter_by(is_active=True).all()
            results = sage_integration.push_pay_codes_to_sage(pay_codes)
            message = f'Successfully pushed {len(results)} pay codes to SAGE VIP'
        
        return api_response(True, data={
            'sync_results': results,
            'sync_direction': sync_direction,
            'sync_timestamp': datetime.utcnow().isoformat() + 'Z'
        }, message=message)
        
    except Exception as e:
        logger.error(f"Pay code sync error: {e}")
        return api_response(False, error={
            'code': 'PAY_CODE_SYNC_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# REPORTING & AUDIT APIs
# ====================

@sage_vip_api_bp.route('/audit/sync-history', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def get_sync_audit_history():
    """Get SAGE VIP integration audit history"""
    try:
        # Get query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        sync_type = request.args.get('sync_type')  # 'employees', 'timesheet', 'leave', 'payroll'
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Build audit query (would need SageVipAuditLog model)
        audit_records = sage_integration.get_audit_history(
            start_date=start_date_str,
            end_date=end_date_str,
            sync_type=sync_type,
            page=page,
            per_page=per_page
        )
        
        return api_response(True, data={
            'audit_records': audit_records,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_records': len(audit_records)
            }
        })
        
    except Exception as e:
        logger.error(f"Audit history error: {e}")
        return api_response(False, error={
            'code': 'AUDIT_ERROR',
            'message': str(e)
        }, status_code=500)

@sage_vip_api_bp.route('/reports/integration-summary', methods=['GET'])
@login_required
@role_required('Super User', 'Payroll Admin', 'Manager')
def get_integration_summary():
    """Get SAGE VIP integration summary report"""
    try:
        # Get query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to current month
            today = date.today()
            start_date = today.replace(day=1)
            end_date = today
        
        summary = sage_integration.generate_integration_summary(start_date, end_date)
        
        return api_response(True, data={
            'integration_summary': summary,
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        })
        
    except Exception as e:
        logger.error(f"Integration summary error: {e}")
        return api_response(False, error={
            'code': 'SUMMARY_ERROR',
            'message': str(e)
        }, status_code=500)

# ====================
# ERROR HANDLERS
# ====================

@sage_vip_api_bp.errorhandler(400)
def bad_request(error):
    return api_response(False, error={
        'code': 'BAD_REQUEST',
        'message': 'Invalid request parameters'
    }, status_code=400)

@sage_vip_api_bp.errorhandler(401)
def unauthorized(error):
    return api_response(False, error={
        'code': 'UNAUTHORIZED',
        'message': 'Authentication required'
    }, status_code=401)

@sage_vip_api_bp.errorhandler(403)
def forbidden(error):
    return api_response(False, error={
        'code': 'FORBIDDEN',
        'message': 'Insufficient permissions for SAGE VIP operations'
    }, status_code=403)

@sage_vip_api_bp.errorhandler(500)
def internal_error(error):
    return api_response(False, error={
        'code': 'INTERNAL_ERROR',
        'message': 'SAGE VIP integration server error'
    }, status_code=500)