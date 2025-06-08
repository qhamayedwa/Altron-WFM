"""
Automation Engine for Time & Attendance System
Implements automated workflows for leave accrual, notifications, and system maintenance
"""

from flask import Blueprint, current_app
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, func, or_
import logging
from app import db
from models import (
    User, LeaveBalance, LeaveType, LeaveApplication, 
    TimeEntry, Schedule, PayCalculation
)

automation_bp = Blueprint('automation', __name__, url_prefix='/automation')

class AutomationEngine:
    """Central automation engine for system-wide automated tasks"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def run_monthly_leave_accrual(self, target_month=None, target_year=None):
        """
        Automated monthly leave accrual for all active employees
        Principle: AUTOMATION - Eliminates manual leave balance calculations
        """
        if not target_month:
            target_month = datetime.now().month
        if not target_year:
            target_year = datetime.now().year
            
        results = {
            'processed_employees': 0,
            'total_accruals': 0,
            'errors': [],
            'debug_log': []
        }
        
        try:
            # Get all active employees
            active_employees = User.query.filter_by(is_active=True).all()
            
            for employee in active_employees:
                try:
                    employee_accruals = self._process_employee_accrual(
                        employee, target_month, target_year
                    )
                    results['processed_employees'] += 1
                    results['total_accruals'] += employee_accruals
                    
                    results['debug_log'].append(
                        f"Employee {employee.username}: {employee_accruals} days accrued"
                    )
                    
                except Exception as e:
                    error_msg = f"Error processing accrual for {employee.username}: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            # Log automation completion
            self.logger.info(
                f"Monthly accrual completed: {results['processed_employees']} employees, "
                f"{results['total_accruals']} total days accrued"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Monthly accrual automation failed: {str(e)}")
            results['errors'].append(f"System error: {str(e)}")
            return results
    
    def _process_employee_accrual(self, employee, month, year):
        """Process leave accrual for a single employee"""
        total_accrued = 0
        
        # Get all leave types for accrual
        leave_types = LeaveType.query.filter_by(is_active=True).all()
        
        for leave_type in leave_types:
            # Skip if no accrual rate defined
            if not leave_type.accrual_rate or leave_type.accrual_rate <= 0:
                continue
            
            # Get or create leave balance for this year
            leave_balance = LeaveBalance.query.filter(
                and_(
                    LeaveBalance.user_id == employee.id,
                    LeaveBalance.leave_type_id == leave_type.id,
                    LeaveBalance.year == year
                )
            ).first()
            
            if not leave_balance:
                # Create new balance record
                leave_balance = LeaveBalance(
                    user_id=employee.id,
                    leave_type_id=leave_type.id,
                    year=year,
                    allocated_days=0,
                    used_days=0,
                    accrual_rate=leave_type.accrual_rate
                )
                db.session.add(leave_balance)
            
            # Calculate accrual amount
            monthly_accrual = leave_type.accrual_rate
            
            # Apply accrual
            leave_balance.allocated_days += monthly_accrual
            total_accrued += monthly_accrual
            
            # Ensure doesn't exceed maximum
            if leave_type.max_days_per_year:
                leave_balance.allocated_days = min(
                    leave_balance.allocated_days, 
                    leave_type.max_days_per_year
                )
        
        db.session.commit()
        return total_accrued
    
    def run_automated_notifications(self):
        """
        Send automated notifications for various system events
        Principle: USER EMPOWERMENT - Proactive communication
        """
        notifications_sent = {
            'leave_reminders': 0,
            'schedule_alerts': 0,
            'approval_pending': 0,
            'system_alerts': 0
        }
        
        try:
            # Leave expiration reminders
            notifications_sent['leave_reminders'] = self._send_leave_expiration_reminders()
            
            # Schedule change notifications
            notifications_sent['schedule_alerts'] = self._send_schedule_notifications()
            
            # Pending approval reminders for managers
            notifications_sent['approval_pending'] = self._send_approval_reminders()
            
            # System maintenance alerts
            notifications_sent['system_alerts'] = self._send_system_alerts()
            
            self.logger.info(f"Automated notifications completed: {notifications_sent}")
            return notifications_sent
            
        except Exception as e:
            self.logger.error(f"Notification automation failed: {str(e)}")
            return notifications_sent
    
    def _send_leave_expiration_reminders(self):
        """Send reminders for leave balances expiring soon"""
        # Get leave balances expiring in next 30 days
        current_year = datetime.now().year
        expiring_balances = LeaveBalance.query.filter(
            and_(
                LeaveBalance.year == current_year,
                LeaveBalance.remaining_days > 0
            )
        ).all()
        
        reminders_sent = 0
        for balance in expiring_balances:
            # Create notification record (would integrate with email/SMS service)
            notification = {
                'user_id': balance.user_id,
                'type': 'leave_expiration_reminder',
                'message': f"You have {balance.remaining_days} {balance.leave_type.name} days expiring on Dec 31",
                'priority': 'medium',
                'created_at': datetime.utcnow()
            }
            # Store notification for future email/SMS processing
            self._queue_notification(notification)
            reminders_sent += 1
        
        return reminders_sent
    
    def _send_schedule_notifications(self):
        """Send notifications for upcoming schedule changes"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Get schedules for tomorrow
        upcoming_schedules = Schedule.query.filter(
            Schedule.date == tomorrow
        ).all()
        
        notifications_sent = 0
        for schedule in upcoming_schedules:
            notification = {
                'user_id': schedule.user_id,
                'type': 'schedule_reminder',
                'message': f"Reminder: You have a {schedule.shift_type.name} shift tomorrow from {schedule.start_time} to {schedule.end_time}",
                'priority': 'low',
                'created_at': datetime.utcnow()
            }
            self._queue_notification(notification)
            notifications_sent += 1
        
        return notifications_sent
    
    def _send_approval_reminders(self):
        """Send reminders to managers about pending approvals"""
        # Get pending leave applications
        pending_applications = LeaveApplication.query.filter_by(status='Pending').all()
        
        # Group by manager (simplified - would use proper manager hierarchy)
        manager_notifications = {}
        
        for application in pending_applications:
            # For now, send to Super Users and Managers
            managers = User.query.join(User.roles).filter(
                or_(
                    User.roles.any(name='Super User'),
                    User.roles.any(name='Manager')
                )
            ).all()
            
            for manager in managers:
                if manager.id not in manager_notifications:
                    manager_notifications[manager.id] = []
                
                manager_notifications[manager.id].append(application)
        
        notifications_sent = 0
        for manager_id, applications in manager_notifications.items():
            notification = {
                'user_id': manager_id,
                'type': 'approval_reminder',
                'message': f"You have {len(applications)} pending leave applications requiring approval",
                'priority': 'high',
                'created_at': datetime.utcnow()
            }
            self._queue_notification(notification)
            notifications_sent += 1
        
        return notifications_sent
    
    def _send_system_alerts(self):
        """Send system maintenance and status alerts"""
        # Check for system issues that need attention
        alerts_sent = 0
        
        # Check for employees without recent time entries
        week_ago = datetime.now() - timedelta(days=7)
        inactive_employees = User.query.filter(
            and_(
                User.is_active == True,
                ~User.time_entries.any(TimeEntry.clock_in_time >= week_ago)
            )
        ).all()
        
        if len(inactive_employees) > 5:  # Threshold for alert
            # Send alert to administrators
            admins = User.query.join(User.roles).filter(
                User.roles.any(name='Super User')
            ).all()
            
            for admin in admins:
                notification = {
                    'user_id': admin.id,
                    'type': 'system_alert',
                    'message': f"System Alert: {len(inactive_employees)} employees have not logged time in the past week",
                    'priority': 'high',
                    'created_at': datetime.utcnow()
                }
                self._queue_notification(notification)
                alerts_sent += 1
        
        return alerts_sent
    
    def _queue_notification(self, notification):
        """Queue notification for processing (would integrate with email/SMS service)"""
        # This would integrate with actual notification service
        # For now, log the notification
        self.logger.info(f"Queued notification: {notification['type']} for user {notification['user_id']}")
        
        # Could store in notification table for web dashboard
        # Could integrate with email service, SMS, push notifications
        pass
    
    def run_automated_payroll_calculations(self, pay_period_start=None, pay_period_end=None):
        """
        Automated payroll calculation for all employees
        Principle: AUTOMATION - Eliminates manual payroll processing
        """
        if not pay_period_start:
            # Default to current month
            today = date.today()
            pay_period_start = today.replace(day=1)
        
        if not pay_period_end:
            # End of current month
            next_month = pay_period_start + relativedelta(months=1)
            pay_period_end = next_month - timedelta(days=1)
        
        results = {
            'processed_employees': 0,
            'total_calculations': 0,
            'errors': [],
            'summary': {}
        }
        
        try:
            active_employees = User.query.filter_by(is_active=True).all()
            
            for employee in active_employees:
                try:
                    calculation = self._calculate_employee_payroll(
                        employee, pay_period_start, pay_period_end
                    )
                    
                    if calculation:
                        results['processed_employees'] += 1
                        results['total_calculations'] += 1
                        
                except Exception as e:
                    error_msg = f"Payroll calculation error for {employee.username}: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            # Generate summary statistics
            results['summary'] = self._generate_payroll_summary(pay_period_start, pay_period_end)
            
            self.logger.info(f"Automated payroll completed: {results['processed_employees']} employees processed")
            return results
            
        except Exception as e:
            self.logger.error(f"Automated payroll failed: {str(e)}")
            results['errors'].append(f"System error: {str(e)}")
            return results
    
    def _calculate_employee_payroll(self, employee, period_start, period_end):
        """Calculate payroll for a single employee"""
        # Get time entries for the period
        time_entries = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == employee.id,
                func.date(TimeEntry.clock_in_time) >= period_start,
                func.date(TimeEntry.clock_in_time) <= period_end,
                TimeEntry.clock_out_time.isnot(None)
            )
        ).all()
        
        if not time_entries:
            return None
        
        # Calculate totals
        total_hours = sum(entry.total_hours for entry in time_entries if entry.total_hours)
        regular_hours = min(total_hours, 40)  # Standard work week
        overtime_hours = max(0, total_hours - 40)
        
        # Create or update payroll calculation record
        existing_calc = PayCalculation.query.filter(
            and_(
                PayCalculation.user_id == employee.id,
                PayCalculation.pay_period_start == period_start,
                PayCalculation.pay_period_end == period_end
            )
        ).first()
        
        if existing_calc:
            calculation = existing_calc
        else:
            calculation = PayCalculation(
                user_id=employee.id,
                pay_period_start=period_start,
                pay_period_end=period_end
            )
            db.session.add(calculation)
        
        # Update calculation values
        calculation.total_hours = total_hours
        calculation.regular_hours = regular_hours
        calculation.overtime_hours = overtime_hours
        calculation.calculated_at = datetime.utcnow()
        
        # Set pay components (would integrate with pay rules engine)
        pay_components = {
            'regular_pay': regular_hours * 25.00,  # Base rate
            'overtime_pay': overtime_hours * 37.50,  # 1.5x rate
            'total_gross': (regular_hours * 25.00) + (overtime_hours * 37.50)
        }
        calculation.set_pay_components(pay_components)
        
        db.session.commit()
        return calculation
    
    def _generate_payroll_summary(self, period_start, period_end):
        """Generate summary statistics for payroll period"""
        calculations = PayCalculation.query.filter(
            and_(
                PayCalculation.pay_period_start == period_start,
                PayCalculation.pay_period_end == period_end
            )
        ).all()
        
        if not calculations:
            return {}
        
        total_employees = len(calculations)
        total_hours = sum(calc.total_hours for calc in calculations if calc.total_hours)
        total_overtime = sum(calc.overtime_hours for calc in calculations if calc.overtime_hours)
        
        return {
            'total_employees': total_employees,
            'total_hours': round(total_hours, 2),
            'total_overtime_hours': round(total_overtime, 2),
            'average_hours_per_employee': round(total_hours / total_employees, 2) if total_employees else 0,
            'overtime_percentage': round((total_overtime / total_hours) * 100, 2) if total_hours else 0
        }

# Automation routes for manual triggering and monitoring

@automation_bp.route('/dashboard')
def workflow_dashboard():
    """Workflow configuration dashboard for Super Users"""
    from flask_login import login_required
    from auth_simple import super_user_required
    from flask import render_template
    
    @login_required
    @super_user_required
    def _dashboard():
        # Get workflow status and statistics
        engine = AutomationEngine()
        
        # Get recent automation history
        recent_history = []
        
        # Calculate workflow statistics
        workflow_stats = {
            'total_employees': User.query.filter_by(is_active=True).count(),
            'pending_leave_applications': LeaveApplication.query.filter_by(status='Pending').count(),
            'open_time_entries': TimeEntry.query.filter_by(status='Open').count(),
            'active_workflows': 3  # Leave Accrual, Notifications, Payroll
        }
        
        # Define available workflows
        workflows = [
            {
                'id': 'leave_accrual',
                'name': 'Monthly Leave Accrual',
                'description': 'Automatically calculate and update employee leave balances',
                'schedule': 'Monthly (1st day)',
                'last_run': 'Not run yet',
                'status': 'Ready',
                'enabled': True
            },
            {
                'id': 'notifications',
                'name': 'Automated Notifications',
                'description': 'Send leave expiration alerts and approval reminders',
                'schedule': 'Daily (9:00 AM)',
                'last_run': 'Not run yet',
                'status': 'Ready',
                'enabled': True
            },
            {
                'id': 'payroll',
                'name': 'Payroll Processing',
                'description': 'Calculate payroll with overtime and exception detection',
                'schedule': 'Weekly (Fridays)',
                'last_run': 'Not run yet',
                'status': 'Ready',
                'enabled': True
            }
        ]
        
        return render_template('automation/dashboard.html',
                             workflows=workflows,
                             workflow_stats=workflow_stats,
                             recent_history=recent_history)
    
    return _dashboard()

@automation_bp.route('/run-accrual', methods=['POST'])
def manual_accrual():
    """Manual trigger for leave accrual (Super User only)"""
    from flask_login import login_required
    from auth import super_user_required
    
    @login_required
    @super_user_required
    def _run_accrual():
        engine = AutomationEngine()
        results = engine.run_monthly_leave_accrual()
        
        from flask import jsonify
        return jsonify({
            'success': True,
            'data': results,
            'message': f"Accrual completed for {results['processed_employees']} employees"
        })
    
    return _run_accrual()

@automation_bp.route('/run-notifications', methods=['POST'])
def manual_notifications():
    """Manual trigger for notifications (Super User only)"""
    from flask_login import login_required
    from auth import super_user_required
    
    @login_required
    @super_user_required
    def _run_notifications():
        engine = AutomationEngine()
        results = engine.run_automated_notifications()
        
        from flask import jsonify
        return jsonify({
            'success': True,
            'data': results,
            'message': "Automated notifications completed"
        })
    
    return _run_notifications()

@automation_bp.route('/run-payroll', methods=['POST'])
def manual_payroll():
    """Manual trigger for payroll calculations (Super User only)"""
    from flask_login import login_required
    from auth import super_user_required
    
    @login_required
    @super_user_required
    def _run_payroll():
        engine = AutomationEngine()
        results = engine.run_automated_payroll_calculations()
        
        from flask import jsonify
        return jsonify({
            'success': True,
            'data': results,
            'message': f"Payroll calculated for {results['processed_employees']} employees"
        })
    
    return _run_payroll()

# Scheduled automation (would integrate with task scheduler like Celery)
def schedule_automation_tasks():
    """Schedule all automation tasks (called from app initialization)"""
    # This would integrate with Celery, APScheduler, or similar
    # For now, provides framework for scheduling
    
    automation_schedule = {
        'monthly_accrual': {
            'function': AutomationEngine().run_monthly_leave_accrual,
            'schedule': 'monthly',  # First day of each month
            'enabled': True
        },
        'daily_notifications': {
            'function': AutomationEngine().run_automated_notifications,
            'schedule': 'daily',  # Every day at 9 AM
            'enabled': True
        },
        'weekly_payroll': {
            'function': AutomationEngine().run_automated_payroll_calculations,
            'schedule': 'weekly',  # Every Friday
            'enabled': True
        }
    }
    
    logging.info("Automation scheduler initialized with tasks: " + str(list(automation_schedule.keys())))
    return automation_schedule