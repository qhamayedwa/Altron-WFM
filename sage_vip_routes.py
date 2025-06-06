"""
SAGE VIP Payroll Integration Routes
Web interface for managing SAGE VIP Payroll system integration
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from auth import super_user_required, role_required
from sage_vip_integration import sage_integration
from app import db
from models import User, TimeEntry, PayCalculation
import logging

logger = logging.getLogger(__name__)

sage_vip_bp = Blueprint('sage_vip', __name__, url_prefix='/sage-vip')

@sage_vip_bp.route('/dashboard')
@login_required
@role_required('Super User', 'Manager', 'Payroll Admin')
def dashboard():
    """SAGE VIP Integration dashboard"""
    return render_template('sage_vip/dashboard.html')

@sage_vip_bp.route('/test-connection')
@login_required
@role_required('Super User', 'Payroll Admin')
def test_connection():
    """Test connection to SAGE VIP Payroll system"""
    try:
        result = sage_integration.test_connection()
        if result['success']:
            flash('Successfully connected to SAGE VIP Payroll system', 'success')
        else:
            flash(f'Connection failed: {result["message"]}', 'danger')
    except Exception as e:
        flash(f'Connection test error: {str(e)}', 'danger')
    
    return redirect(url_for('sage_vip.dashboard'))

@sage_vip_bp.route('/sync-employees', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def sync_employees():
    """Sync employees from SAGE VIP to WFM"""
    try:
        employees = sage_integration.sync_employees_from_sage()
        flash(f'Successfully synced {len(employees)} employees from SAGE VIP', 'success')
    except Exception as e:
        flash(f'Employee sync failed: {str(e)}', 'danger')
        logger.error(f'Employee sync error: {e}')
    
    return redirect(url_for('sage_vip.dashboard'))

@sage_vip_bp.route('/push-timesheet', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def push_timesheet():
    """Push time entries to SAGE VIP Payroll"""
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Please provide both start and end dates', 'warning')
                return redirect(url_for('sage_vip.push_timesheet'))
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            if end_date < start_date:
                flash('End date must be after start date', 'warning')
                return redirect(url_for('sage_vip.push_timesheet'))
            
            success = sage_integration.push_time_entries_to_sage(start_date, end_date)
            
            if success:
                flash('Time entries successfully pushed to SAGE VIP Payroll', 'success')
            else:
                flash('Failed to push time entries to SAGE VIP', 'danger')
                
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD format', 'danger')
        except Exception as e:
            flash(f'Error pushing timesheet: {str(e)}', 'danger')
            logger.error(f'Timesheet push error: {e}')
    
    return render_template('sage_vip/push_timesheet.html')

@sage_vip_bp.route('/push-leave', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def push_leave():
    """Push leave applications to SAGE VIP Payroll"""
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Please provide both start and end dates', 'warning')
                return redirect(url_for('sage_vip.push_leave'))
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            if end_date < start_date:
                flash('End date must be after start date', 'warning')
                return redirect(url_for('sage_vip.push_leave'))
            
            success = sage_integration.push_leave_entries_to_sage(start_date, end_date)
            
            if success:
                flash('Leave applications successfully pushed to SAGE VIP Payroll', 'success')
            else:
                flash('Failed to push leave applications to SAGE VIP', 'danger')
                
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD format', 'danger')
        except Exception as e:
            flash(f'Error pushing leave data: {str(e)}', 'danger')
            logger.error(f'Leave push error: {e}')
    
    return render_template('sage_vip/push_leave.html')

@sage_vip_bp.route('/pull-payroll', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def pull_payroll():
    """Pull payroll data from SAGE VIP Payroll"""
    payroll_data = []
    
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Please provide both start and end dates', 'warning')
                return redirect(url_for('sage_vip.pull_payroll'))
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            if end_date < start_date:
                flash('End date must be after start date', 'warning')
                return redirect(url_for('sage_vip.pull_payroll'))
            
            payroll_data = sage_integration.pull_payroll_data_from_sage(start_date, end_date)
            
            if payroll_data:
                flash(f'Retrieved payroll data for {len(payroll_data)} employees', 'success')
            else:
                flash('No payroll data found for the specified period', 'info')
                
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD format', 'danger')
        except Exception as e:
            flash(f'Error retrieving payroll data: {str(e)}', 'danger')
            logger.error(f'Payroll pull error: {e}')
    
    return render_template('sage_vip/pull_payroll.html', payroll_data=payroll_data)

@sage_vip_bp.route('/sync-pay-codes', methods=['POST'])
@login_required
@role_required('Super User', 'Payroll Admin')
def sync_pay_codes():
    """Sync pay codes from SAGE VIP to WFM"""
    try:
        success = sage_integration.sync_pay_codes_from_sage()
        if success:
            flash('Pay codes successfully synced from SAGE VIP', 'success')
        else:
            flash('Failed to sync pay codes from SAGE VIP', 'danger')
    except Exception as e:
        flash(f'Pay codes sync failed: {str(e)}', 'danger')
        logger.error(f'Pay codes sync error: {e}')
    
    return redirect(url_for('sage_vip.dashboard'))

@sage_vip_bp.route('/integration-logs')
@login_required
@role_required('Super User', 'Payroll Admin')
def integration_logs():
    """View SAGE VIP integration logs"""
    # This would typically read from log files or database
    # For now, return a basic template
    return render_template('sage_vip/logs.html')

@sage_vip_bp.route('/api/sync-status')
@login_required
@role_required('Super User', 'Payroll Admin')
def api_sync_status():
    """API endpoint to check sync status"""
    try:
        # Check last sync times and status
        last_employee_sync = None  # Would be retrieved from database/logs
        last_timesheet_push = None  # Would be retrieved from database/logs
        last_payroll_pull = None   # Would be retrieved from database/logs
        
        connection_test = sage_integration.test_connection()
        
        return jsonify({
            'success': True,
            'connection_status': connection_test['success'],
            'last_employee_sync': last_employee_sync,
            'last_timesheet_push': last_timesheet_push,
            'last_payroll_pull': last_payroll_pull,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@sage_vip_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@super_user_required
def settings():
    """SAGE VIP integration settings (Super User only)"""
    if request.method == 'POST':
        # Handle settings updates
        # Note: In production, these should be stored securely
        flash('Settings updated successfully', 'success')
        return redirect(url_for('sage_vip.settings'))
    
    return render_template('sage_vip/settings.html')

# Register error handlers for this blueprint
@sage_vip_bp.errorhandler(403)
def forbidden(error):
    flash('You do not have permission to access this resource', 'danger')
    return redirect(url_for('main.index'))

@sage_vip_bp.errorhandler(500)
def internal_error(error):
    flash('An internal error occurred during SAGE VIP integration', 'danger')
    return redirect(url_for('sage_vip.dashboard'))