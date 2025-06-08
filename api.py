"""
REST API Blueprint for Time & Attendance System
Provides JSON endpoints for mobile apps and external integrations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta, date
from sqlalchemy import and_, func, or_
import logging
import json

from app import db
from models import User, TimeEntry, Schedule, LeaveApplication, PayCode, PayRule, LeaveType, LeaveBalance, ShiftType, Role
from auth import role_required, super_user_required

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

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

def validate_date_range(start_date, end_date):
    """Validate date range parameters"""
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if start_date and end_date and start_date > end_date:
            return None, None, "Start date cannot be after end date"
        
        return start_date, end_date, None
    except ValueError:
        return None, None, "Invalid date format. Use YYYY-MM-DD"

# ====================
# TIME & ATTENDANCE APIs
# ====================

@api_bp.route('/time/clock-in', methods=['POST'])
@login_required
def api_clock_in():
    """Clock in API endpoint for mobile apps"""
    try:
        data = request.get_json() or {}
        
        # Check if user is already clocked in
        existing_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if existing_entry:
            return api_response(False, error={
                'code': 'ALREADY_CLOCKED_IN',
                'message': 'You are already clocked in'
            }, status_code=400)
        
        # Create new time entry
        time_entry = TimeEntry(
            user_id=current_user.id,
            clock_in_time=datetime.utcnow(),
            status='Open',
            notes=data.get('notes'),
            clock_in_latitude=data.get('location', {}).get('latitude'),
            clock_in_longitude=data.get('location', {}).get('longitude')
        )
        
        db.session.add(time_entry)
        db.session.commit()
        
        return api_response(True, data={
            'entry_id': time_entry.id,
            'clock_in_time': time_entry.clock_in_time.isoformat() + 'Z',
            'status': 'clocked_in'
        }, message='Successfully clocked in')
        
    except Exception as e:
        logging.error(f"Clock in API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to clock in'
        }, status_code=500)

@api_bp.route('/time/clock-out', methods=['POST'])
@login_required
def api_clock_out():
    """Clock out API endpoint for mobile apps"""
    try:
        data = request.get_json() or {}
        
        # Find active time entry
        time_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if not time_entry:
            return api_response(False, error={
                'code': 'NOT_CLOCKED_IN',
                'message': 'You are not currently clocked in'
            }, status_code=400)
        
        # Update time entry
        time_entry.clock_out_time = datetime.utcnow()
        time_entry.status = 'Closed'
        time_entry.clock_out_latitude = data.get('location', {}).get('latitude')
        time_entry.clock_out_longitude = data.get('location', {}).get('longitude')
        
        if data.get('notes'):
            time_entry.notes = (time_entry.notes or '') + '\n' + data.get('notes')
        
        db.session.commit()
        
        return api_response(True, data={
            'entry_id': time_entry.id,
            'clock_out_time': time_entry.clock_out_time.isoformat() + 'Z',
            'total_hours': round(time_entry.total_hours, 2),
            'status': 'clocked_out'
        }, message='Successfully clocked out')
        
    except Exception as e:
        logging.error(f"Clock out API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to clock out'
        }, status_code=500)

@api_bp.route('/time/current-status', methods=['GET'])
@login_required
def api_current_status():
    """Get current time tracking status"""
    try:
        # Check for active time entry
        active_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        # Get today's total hours
        today = date.today()
        today_entries = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                func.date(TimeEntry.clock_in_time) == today
            )
        ).all()
        
        today_hours = sum(entry.total_hours for entry in today_entries if entry.total_hours)
        
        status_data = {
            'is_clocked_in': active_entry is not None,
            'today_hours': round(today_hours, 2),
            'week_hours': 0,  # Calculate week hours
        }
        
        if active_entry:
            duration = datetime.utcnow() - active_entry.clock_in_time
            status_data.update({
                'entry_id': active_entry.id,
                'clock_in_time': active_entry.clock_in_time.isoformat() + 'Z',
                'current_duration': round(duration.total_seconds() / 3600, 2)
            })
        
        return api_response(True, data=status_data)
        
    except Exception as e:
        logging.error(f"Current status API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to get current status'
        }, status_code=500)

@api_bp.route('/time/entries', methods=['GET'])
@login_required
def api_time_entries():
    """Get time entries with pagination and filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        start_date, end_date, error = validate_date_range(start_date, end_date)
        if error:
            return api_response(False, error={'code': 'VALIDATION_ERROR', 'message': error}, status_code=400)
        
        # Build query
        query = TimeEntry.query.filter(TimeEntry.user_id == current_user.id)
        
        if start_date:
            query = query.filter(func.date(TimeEntry.clock_in_time) >= start_date)
        if end_date:
            query = query.filter(func.date(TimeEntry.clock_in_time) <= end_date)
        
        # Paginate results
        entries = query.order_by(TimeEntry.clock_in_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format response
        entries_data = []
        for entry in entries.items:
            entries_data.append({
                'id': entry.id,
                'date': entry.work_date.isoformat(),
                'clock_in_time': entry.clock_in_time.isoformat() + 'Z',
                'clock_out_time': entry.clock_out_time.isoformat() + 'Z' if entry.clock_out_time else None,
                'total_hours': round(entry.total_hours, 2) if entry.total_hours else 0,
                'break_minutes': entry.total_break_minutes or 0,
                'status': entry.status,
                'notes': entry.notes,
                'is_overtime': entry.is_overtime,
                'overtime_hours': round(entry.overtime_hours, 2) if entry.overtime_hours else 0
            })
        
        return api_response(True, data={
            'entries': entries_data,
            'pagination': {
                'page': entries.page,
                'pages': entries.pages,
                'per_page': entries.per_page,
                'total': entries.total,
                'has_next': entries.has_next,
                'has_prev': entries.has_prev
            }
        })
        
    except Exception as e:
        logging.error(f"Time entries API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve time entries'
        }, status_code=500)

# ====================
# SCHEDULE APIs
# ====================

@api_bp.route('/schedule/my-schedule', methods=['GET'])
@login_required
def api_my_schedule():
    """Get employee's schedule for specified period"""
    try:
        week_start = request.args.get('week')
        if week_start:
            week_start = datetime.strptime(week_start, '%Y-%m-%d').date()
        else:
            # Default to current week
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=6)
        
        # Get schedules for the week
        schedules = Schedule.query.filter(
            and_(
                Schedule.user_id == current_user.id,
                Schedule.date >= week_start,
                Schedule.date <= week_end
            )
        ).order_by(Schedule.date, Schedule.start_time).all()
        
        # Format schedule data
        schedule_data = []
        for schedule in schedules:
            schedule_data.append({
                'id': schedule.id,
                'date': schedule.date.isoformat(),
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'shift_type': schedule.shift_type.name if schedule.shift_type else None,
                'location': schedule.location,
                'notes': schedule.notes,
                'status': schedule.status,
                'duration_hours': schedule.duration_hours
            })
        
        return api_response(True, data={
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'schedules': schedule_data,
            'total_hours': sum(s.duration_hours for s in schedules if s.duration_hours)
        })
        
    except Exception as e:
        logging.error(f"My schedule API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve schedule'
        }, status_code=500)

# ====================
# LEAVE MANAGEMENT APIs
# ====================

@api_bp.route('/leave/my-applications', methods=['GET'])
@login_required
def api_my_leave_applications():
    """Get employee's leave applications"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        status = request.args.get('status')
        
        query = LeaveApplication.query.filter(LeaveApplication.user_id == current_user.id)
        
        if status:
            query = query.filter(LeaveApplication.status == status)
        
        applications = query.order_by(LeaveApplication.applied_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        applications_data = []
        for app in applications.items:
            applications_data.append({
                'id': app.id,
                'leave_type': app.leave_type.name if app.leave_type else None,
                'start_date': app.start_date.isoformat(),
                'end_date': app.end_date.isoformat(),
                'total_days': app.total_days,
                'reason': app.reason,
                'status': app.status,
                'applied_date': app.applied_date.isoformat(),
                'approved_date': app.approved_date.isoformat() if app.approved_date else None,
                'manager_comments': app.manager_comments
            })
        
        return api_response(True, data={
            'applications': applications_data,
            'pagination': {
                'page': applications.page,
                'pages': applications.pages,
                'total': applications.total
            }
        })
        
    except Exception as e:
        logging.error(f"Leave applications API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve leave applications'
        }, status_code=500)

@api_bp.route('/leave/balances', methods=['GET'])
@login_required
def api_leave_balances():
    """Get employee's leave balances"""
    try:
        balances = LeaveBalance.query.filter(LeaveBalance.user_id == current_user.id).all()
        
        balances_data = []
        for balance in balances:
            balances_data.append({
                'leave_type_id': balance.leave_type_id,
                'leave_type_name': balance.leave_type.name if balance.leave_type else None,
                'allocated_days': balance.allocated_days,
                'used_days': balance.used_days,
                'remaining_days': balance.remaining_days,
                'accrual_rate': balance.accrual_rate,
                'year': balance.year
            })
        
        return api_response(True, data={'balances': balances_data})
        
    except Exception as e:
        logging.error(f"Leave balances API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve leave balances'
        }, status_code=500)

@api_bp.route('/leave/apply', methods=['POST'])
@login_required
def api_apply_leave():
    """Apply for leave via API"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['leave_type_id', 'start_date', 'end_date', 'reason']
        for field in required_fields:
            if not data.get(field):
                return api_response(False, error={
                    'code': 'VALIDATION_ERROR',
                    'message': f'Missing required field: {field}'
                }, status_code=400)
        
        # Parse dates
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return api_response(False, error={
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status_code=400)
        
        if start_date > end_date:
            return api_response(False, error={
                'code': 'VALIDATION_ERROR',
                'message': 'Start date cannot be after end date'
            }, status_code=400)
        
        # Calculate total days
        total_days = (end_date - start_date).days + 1
        
        # Create leave application
        application = LeaveApplication(
            user_id=current_user.id,
            leave_type_id=data['leave_type_id'],
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=data['reason'],
            emergency_contact=data.get('emergency_contact'),
            applied_date=datetime.utcnow(),
            status='Pending'
        )
        
        db.session.add(application)
        db.session.commit()
        
        return api_response(True, data={
            'application_id': application.id,
            'status': application.status,
            'total_days': application.total_days
        }, message='Leave application submitted successfully')
        
    except Exception as e:
        logging.error(f"Apply leave API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to submit leave application'
        }, status_code=500)

# ====================
# USER PROFILE APIs
# ====================

@api_bp.route('/users/profile', methods=['GET'])
@login_required
def api_user_profile():
    """Get current user's profile"""
    try:
        profile_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'department': getattr(current_user, 'department', None),
            'is_active': current_user.is_active,
            'roles': [role.name for role in current_user.roles] if hasattr(current_user, 'roles') else [],
            'created_at': current_user.created_at.isoformat() + 'Z' if hasattr(current_user, 'created_at') and current_user.created_at else None
        }
        
        return api_response(True, data=profile_data)
        
    except Exception as e:
        logging.error(f"User profile API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve user profile'
        }, status_code=500)

# ====================
# MANAGER APIs
# ====================

@api_bp.route('/time/team-entries', methods=['GET'])
@login_required
@role_required(['Super User', 'Manager'])
def api_team_time_entries():
    """Get team time entries for managers"""
    try:
        date_filter = request.args.get('date', date.today().isoformat())
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        
        # Get team entries for the specified date
        entries = TimeEntry.query.filter(
            func.date(TimeEntry.clock_in_time) == target_date
        ).join(User).all()
        
        entries_data = []
        for entry in entries:
            entries_data.append({
                'id': entry.id,
                'employee': {
                    'id': entry.employee.id,
                    'name': f"{entry.employee.first_name} {entry.employee.last_name}",
                    'username': entry.employee.username,
                    'department': getattr(entry.employee, 'department', None)
                },
                'clock_in_time': entry.clock_in_time.isoformat() + 'Z',
                'clock_out_time': entry.clock_out_time.isoformat() + 'Z' if entry.clock_out_time else None,
                'total_hours': round(entry.total_hours, 2) if entry.total_hours else 0,
                'status': entry.status,
                'needs_approval': not entry.approved_by_manager_id,
                'is_overtime': entry.is_overtime
            })
        
        return api_response(True, data={
            'date': target_date.isoformat(),
            'entries': entries_data,
            'total_entries': len(entries_data)
        })
        
    except Exception as e:
        logging.error(f"Team entries API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve team entries'
        }, status_code=500)

# ====================
# SYSTEM INFO APIs
# ====================

@api_bp.route('/system/info', methods=['GET'])
def api_system_info():
    """Get system information for mobile apps"""
    return api_response(True, data={
        'app_name': 'Time & Attendance System',
        'version': '1.0.0',
        'api_version': 'v1',
        'features': {
            'time_tracking': True,
            'scheduling': True,
            'leave_management': True,
            'payroll': True,
            'geolocation': True,
            'offline_mode': False  # To be implemented
        },
        'supported_platforms': ['web', 'ios', 'android']
    })

@api_bp.route('/system-info', methods=['GET'])
def api_system_info_legacy():
    """Legacy system info endpoint for frontend compatibility"""
    return api_system_info()

# ====================
# DATABASE STATUS APIs
# ====================

@api_bp.route('/db-status', methods=['GET'])
def api_database_status():
    """Database status endpoint for frontend monitoring"""
    try:
        from app import db
        from models import User, TimeEntry, Schedule, LeaveApplication
        
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        
        # Get table counts for monitoring
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

@api_bp.route('/recent-time-entries', methods=['GET'])
@login_required
def api_recent_time_entries():
    """Get recent time entries for dashboard updates with proper employee data restrictions"""
    try:
        # Determine scope based on user role
        is_manager_or_admin = (
            hasattr(current_user, 'has_role') and 
            (current_user.has_role('Manager') or current_user.has_role('Admin') or current_user.has_role('Super User'))
        )
        
        # Base query for recent entries (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        
        if is_manager_or_admin:
            # Managers see all recent entries
            recent_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time >= week_ago
            ).order_by(TimeEntry.clock_in_time.desc()).limit(10).all()
        else:
            # Employees restricted to only their own entries
            recent_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == current_user.id,
                    TimeEntry.clock_in_time >= week_ago
                )
            ).order_by(TimeEntry.clock_in_time.desc()).limit(10).all()
        
        # Format entries for API response
        entries_data = []
        for entry in recent_entries:
            employee_name = f"{entry.employee.first_name or ''} {entry.employee.last_name or ''}".strip() or entry.employee.username
            
            entry_data = {
                'id': entry.id,
                'employee_name': employee_name,
                'employee_username': entry.employee.username,
                'date': entry.clock_in_time.strftime('%m/%d') if entry.clock_in_time else 'N/A',
                'clock_in_time': entry.clock_in_time.strftime('%H:%M') if entry.clock_in_time else 'N/A',
                'clock_out_time': entry.clock_out_time.strftime('%H:%M') if entry.clock_out_time else None,
                'total_hours': entry.total_hours or 0,
                'status': entry.status or 'Open'
            }
            entries_data.append(entry_data)
        
        return api_response(True, data={
            'entries': entries_data,
            'count': len(entries_data),
            'is_manager_view': is_manager_or_admin
        })
        
    except Exception as e:
        logging.error(f"Recent time entries API error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to fetch recent time entries'
        }, status_code=500)

# ====================
# USER MANAGEMENT APIs
# ====================

@api_bp.route('/users', methods=['GET'])
@login_required
def api_users():
    """Get users list for manager selection dropdowns"""
    try:
        # Get role filter from query parameters
        role_filter = request.args.get('role', '')
        search_term = request.args.get('search', '')
        
        # Build query
        query = User.query.filter(User.is_active == True)
        
        # Apply role filter if specified - for now, get all active users
        # TODO: Implement proper role filtering once role system is clarified
        if role_filter:
            # Skip role filtering for now - return all active users for manager selection
            pass
        
        # Apply search filter if specified
        if search_term:
            search_filter = f"%{search_term}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_filter),
                    User.email.ilike(search_filter),
                    User.first_name.ilike(search_filter),
                    User.last_name.ilike(search_filter)
                )
            )
        
        users = query.order_by(User.username).all()
        
        # Format user data for API response
        users_data = []
        for user in users:
            # Get primary role name or default
            primary_role = user.roles[0].name if user.roles else 'Employee'
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': getattr(user, 'first_name', ''),
                'last_name': getattr(user, 'last_name', ''),
                'phone': getattr(user, 'phone_number', '') or getattr(user, 'mobile_number', ''),
                'role': primary_role,
                'department': getattr(user, 'department', ''),
                'employee_id': getattr(user, 'employee_id', '')
            })
        
        return api_response(True, data={
            'users': users_data,
            'total': len(users_data)
        })
        
    except Exception as e:
        current_app.logger.error(f"API users error: {e}")
        return api_response(False, error={
            'code': 'API_ERROR',
            'message': 'Failed to fetch users'
        }, status_code=500)

# ====================
# DRILL-DOWN ANALYTICS APIs
# ====================

@api_bp.route('/drill-down/daily-attendance', methods=['GET'])
@login_required
def api_drill_down_daily_attendance():
    """Get detailed daily attendance data for drill-down"""
    date_str = request.args.get('date')
    if not date_str:
        return api_response(False, error={
            'code': 'MISSING_PARAMETER',
            'message': 'Date parameter required'
        }, status_code=400)
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get all time entries for the specific date
        time_entries = TimeEntry.query.filter(
            func.date(TimeEntry.clock_in_time) == target_date
        ).join(User).all()
        
        # Prepare detailed data
        entries_data = []
        for entry in time_entries:
            entries_data.append({
                'employee': f"{entry.user.first_name} {entry.user.last_name}",
                'employee_id': getattr(entry.user, 'employee_id', 'N/A'),
                'department': getattr(entry.user, 'department', 'Not Assigned') or 'Not Assigned',
                'clock_in': entry.clock_in_time.strftime('%H:%M') if entry.clock_in_time else 'N/A',
                'clock_out': entry.clock_out_time.strftime('%H:%M') if entry.clock_out_time else 'Still Active',
                'total_hours': round(entry.total_hours, 2) if entry.total_hours else 0,
                'status': 'Completed' if entry.clock_out_time else 'Active',
                'break_minutes': getattr(entry, 'total_break_minutes', 0) or 0
            })
        
        return api_response(True, data={
            'date': date_str,
            'total_entries': len(entries_data),
            'entries': entries_data,
            'summary': {
                'total_hours': sum(e['total_hours'] for e in entries_data),
                'active_employees': len([e for e in entries_data if e['status'] == 'Active']),
                'completed_shifts': len([e for e in entries_data if e['status'] == 'Completed'])
            }
        })
        
    except ValueError:
        return api_response(False, error={
            'code': 'INVALID_DATE_FORMAT',
            'message': 'Invalid date format. Use YYYY-MM-DD'
        }, status_code=400)
    except Exception as e:
        logging.error(f"Daily attendance drill-down error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve attendance data'
        }, status_code=500)

@api_bp.route('/drill-down/leave-status', methods=['GET'])
@login_required
def api_drill_down_leave_status():
    """Get detailed leave applications by status"""
    status = request.args.get('status')
    if not status:
        return api_response(False, error={
            'code': 'MISSING_PARAMETER',
            'message': 'Status parameter required'
        }, status_code=400)
    
    try:
        # Get leave applications by status
        leave_apps = LeaveApplication.query.filter(
            LeaveApplication.status == status
        ).join(User).all()
        
        applications_data = []
        for app in leave_apps:
            applications_data.append({
                'employee': f"{app.user.first_name} {app.user.last_name}",
                'employee_id': getattr(app.user, 'employee_id', 'N/A'),
                'department': getattr(app.user, 'department', 'Not Assigned') or 'Not Assigned',
                'leave_type': getattr(app, 'leave_type', 'Annual Leave'),
                'start_date': app.start_date.strftime('%Y-%m-%d'),
                'end_date': app.end_date.strftime('%Y-%m-%d'),
                'days_requested': (app.end_date - app.start_date).days + 1,
                'applied_date': getattr(app, 'applied_date', app.start_date).strftime('%Y-%m-%d'),
                'reason': getattr(app, 'reason', 'No reason provided') or 'No reason provided',
                'manager_notes': getattr(app, 'manager_notes', 'No notes') or 'No notes'
            })
        
        # Calculate summary statistics
        total_days = sum(app['days_requested'] for app in applications_data)
        leave_types = {}
        for app in applications_data:
            leave_type = app['leave_type']
            if leave_type not in leave_types:
                leave_types[leave_type] = 0
            leave_types[leave_type] += 1
        
        return api_response(True, data={
            'status': status,
            'total_applications': len(applications_data),
            'applications': applications_data,
            'summary': {
                'total_days_requested': total_days,
                'leave_type_breakdown': leave_types,
                'avg_days_per_application': round(total_days / len(applications_data), 1) if applications_data else 0
            }
        })
        
    except Exception as e:
        logging.error(f"Leave status drill-down error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve leave data'
        }, status_code=500)

@api_bp.route('/drill-down/hourly-patterns', methods=['GET'])
@login_required
def api_drill_down_hourly_patterns():
    """Get detailed hourly clock-in pattern data"""
    hour = request.args.get('hour')
    if not hour:
        return api_response(False, error={
            'code': 'MISSING_PARAMETER',
            'message': 'Hour parameter required'
        }, status_code=400)
    
    try:
        hour_int = int(hour)
        
        # Get time entries for the specific hour (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        time_entries = TimeEntry.query.filter(
            TimeEntry.clock_in_time >= thirty_days_ago,
            func.extract('hour', TimeEntry.clock_in_time) == hour_int
        ).join(User).all()
        
        entries_data = []
        frequency_by_employee = {}
        
        for entry in time_entries:
            employee_name = f"{entry.user.first_name} {entry.user.last_name}"
            entry_data = {
                'employee': employee_name,
                'employee_id': getattr(entry.user, 'employee_id', 'N/A'),
                'department': getattr(entry.user, 'department', 'Not Assigned') or 'Not Assigned',
                'date': entry.clock_in_time.strftime('%Y-%m-%d'),
                'exact_time': entry.clock_in_time.strftime('%H:%M:%S'),
                'day_of_week': entry.clock_in_time.strftime('%A')
            }
            entries_data.append(entry_data)
            
            # Count frequency per employee
            if employee_name not in frequency_by_employee:
                frequency_by_employee[employee_name] = 0
            frequency_by_employee[employee_name] += 1
        
        # Analyze patterns
        day_patterns = {}
        for entry in entries_data:
            day = entry['day_of_week']
            if day not in day_patterns:
                day_patterns[day] = 0
            day_patterns[day] += 1
        
        return api_response(True, data={
            'hour': f"{hour}:00",
            'period': "Last 30 days",
            'total_clock_ins': len(entries_data),
            'entries': entries_data,
            'patterns': {
                'employee_frequency': frequency_by_employee,
                'day_of_week_breakdown': day_patterns,
                'most_frequent_employee': max(frequency_by_employee.items(), key=lambda x: x[1]) if frequency_by_employee else None,
                'most_common_day': max(day_patterns.items(), key=lambda x: x[1]) if day_patterns else None
            }
        })
        
    except ValueError:
        return api_response(False, error={
            'code': 'INVALID_HOUR_FORMAT',
            'message': 'Invalid hour format. Use 0-23'
        }, status_code=400)
    except Exception as e:
        logging.error(f"Hourly patterns drill-down error: {e}")
        return api_response(False, error={
            'code': 'SERVER_ERROR',
            'message': 'Failed to retrieve pattern data'
        }, status_code=500)

# Error handlers
@api_bp.errorhandler(400)
def bad_request(error):
    return api_response(False, error={
        'code': 'BAD_REQUEST',
        'message': 'Invalid request'
    }, status_code=400)

@api_bp.errorhandler(401)
def unauthorized(error):
    return api_response(False, error={
        'code': 'AUTH_REQUIRED',
        'message': 'Authentication required'
    }, status_code=401)

@api_bp.errorhandler(403)
def forbidden(error):
    return api_response(False, error={
        'code': 'INSUFFICIENT_PERMISSIONS',
        'message': 'Insufficient permissions'
    }, status_code=403)

@api_bp.errorhandler(404)
def not_found(error):
    return api_response(False, error={
        'code': 'RESOURCE_NOT_FOUND',
        'message': 'Resource not found'
    }, status_code=404)

@api_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return api_response(False, error={
        'code': 'SERVER_ERROR',
        'message': 'Internal server error'
    }, status_code=500)