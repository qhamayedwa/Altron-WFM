from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func, case
from app import db
from models import TimeEntry, User, Department
from auth_simple import role_required, super_user_required
from timezone_utils import get_current_time, localize_datetime

def get_managed_departments(user_id):
    """Get list of department IDs that a manager oversees"""
    managed_depts = db.session.query(Department.id).filter(
        or_(Department.manager_id == user_id, Department.deputy_manager_id == user_id)
    ).all()
    return [dept.id for dept in managed_depts]

# Create time attendance blueprint
time_attendance_bp = Blueprint('time_attendance', __name__, url_prefix='/time')

# Employee Routes

@time_attendance_bp.route('/clock-in', methods=['POST'])
@login_required
def clock_in():
    """Employee clock-in endpoint"""
    # Handle both JSON and form requests properly
    json_data = {}
    if request.is_json and request.content_length and request.content_length > 0:
        try:
            json_data = request.get_json() or {}
        except Exception:
            json_data = {}
    
    try:
        # Check if user already has an open time entry
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if open_entry:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'You already have an open time entry. Please clock out first.'
                }), 400
            else:
                flash('You already have an open time entry. Please clock out first.', 'warning')
                # Check if request came from timecard page
                if request.referrer and 'timecard' in request.referrer:
                    return redirect(url_for('time_attendance.my_timecard'))
                return redirect(url_for('main.index'))
        
        # Get GPS coordinates if provided  
        latitude = json_data.get('latitude') if request.is_json else None
        longitude = json_data.get('longitude') if request.is_json else None
        notes = json_data.get('notes', '') if request.is_json else ''
        
        # Create new time entry
        time_entry = TimeEntry()
        time_entry.user_id = current_user.id
        time_entry.clock_in_time = get_current_time()
        time_entry.status = 'Open'
        time_entry.notes = notes
        time_entry.clock_in_latitude = latitude
        time_entry.clock_in_longitude = longitude
        
        db.session.add(time_entry)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Successfully clocked in',
                'time_entry_id': time_entry.id,
                'clock_in_time': time_entry.clock_in_time.isoformat()
            })
        else:
            flash('Successfully clocked in!', 'success')
            # Check if request came from timecard page
            if request.referrer and 'timecard' in request.referrer:
                return redirect(url_for('time_attendance.my_timecard'))
            return redirect(url_for('main.index'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': f'Error clocking in: {str(e)}'
            }), 500
        else:
            flash(f'Error clocking in: {str(e)}', 'danger')
            # Check if request came from timecard page
            if request.referrer and 'timecard' in request.referrer:
                return redirect(url_for('time_attendance.my_timecard'))
            return redirect(url_for('main.index'))

@time_attendance_bp.route('/clock-out', methods=['POST'])
@login_required
def clock_out():
    """Employee clock-out endpoint"""
    try:
        # Handle both JSON and form requests properly
        json_data = {}
        if request.is_json and request.content_length and request.content_length > 0:
            try:
                json_data = request.get_json() or {}
            except Exception:
                json_data = {}
        # Find the open time entry for the user
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if not open_entry:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'No open time entry found. Please clock in first.'
                }), 400
            else:
                flash('No open time entry found. Please clock in first.', 'warning')
                # Check if request came from timecard page
                if request.referrer and 'timecard' in request.referrer:
                    return redirect(url_for('time_attendance.my_timecard'))
                return redirect(url_for('main.index'))
        
        # Get GPS coordinates if provided
        latitude = json_data.get('latitude') if request.is_json else None
        longitude = json_data.get('longitude') if request.is_json else None
        notes = json_data.get('notes', '') if request.is_json else ''
        
        # Update time entry
        open_entry.clock_out_time = get_current_time()
        open_entry.status = 'Closed'
        open_entry.clock_out_latitude = latitude
        open_entry.clock_out_longitude = longitude
        if notes:
            open_entry.notes = (open_entry.notes or '') + f" | Clock-out notes: {notes}"
        
        db.session.commit()
        
        # Calculate duration for display
        duration = open_entry.clock_out_time - open_entry.clock_in_time
        total_hours = duration.total_seconds() / 3600
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Successfully clocked out',
                'time_entry_id': open_entry.id,
                'clock_out_time': open_entry.clock_out_time.isoformat(),
                'total_hours': round(total_hours, 2)
            })
        else:
            flash(f'Successfully clocked out! Total time: {total_hours:.2f} hours', 'success')
            # Check if request came from timecard page
            if request.referrer and 'timecard' in request.referrer:
                return redirect(url_for('time_attendance.my_timecard'))
            return redirect(url_for('main.index'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': f'Error clocking out: {str(e)}'
            }), 500
        else:
            flash(f'Error clocking out: {str(e)}', 'danger')
            # Check if request came from timecard page
            if request.referrer and 'timecard' in request.referrer:
                return redirect(url_for('time_attendance.my_timecard'))
            return redirect(url_for('main.index'))

@time_attendance_bp.route('/start-break', methods=['POST'])
@login_required
def start_break():
    """Start break time"""
    try:
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if not open_entry:
            return jsonify({
                'success': False,
                'message': 'No open time entry found.'
            }), 400
        
        if open_entry.break_start_time and not open_entry.break_end_time:
            return jsonify({
                'success': False,
                'message': 'Break already in progress.'
            }), 400
        
        open_entry.break_start_time = datetime.utcnow()
        open_entry.break_end_time = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Break started',
            'break_start_time': open_entry.break_start_time.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error starting break: {str(e)}'
        }), 500

@time_attendance_bp.route('/end-break', methods=['POST'])
@login_required
def end_break():
    """End break time"""
    try:
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if not open_entry or not open_entry.break_start_time:
            return jsonify({
                'success': False,
                'message': 'No active break found.'
            }), 400
        
        open_entry.break_end_time = datetime.utcnow()
        
        # Calculate break duration in minutes
        break_duration = (open_entry.break_end_time - open_entry.break_start_time).total_seconds() / 60
        open_entry.total_break_minutes += int(break_duration)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Break ended',
            'break_end_time': open_entry.break_end_time.isoformat(),
            'break_duration_minutes': int(break_duration)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error ending break: {str(e)}'
        }), 500

@time_attendance_bp.route('/status', methods=['GET'])
@login_required
def get_status():
    """Get current clock-in status for the user"""
    try:
        # Find current open time entry
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        status_data = {
            'is_clocked_in': open_entry is not None,
            'clock_in_time': None,
            'current_duration': 0
        }
        
        if open_entry:
            status_data.update({
                'clock_in_time': open_entry.clock_in_time.isoformat(),
                'entry_id': open_entry.id
            })
            
            # Calculate current duration
            duration = get_current_time() - open_entry.clock_in_time
            status_data['current_duration'] = duration.total_seconds() / 3600
        
        return jsonify({
            'success': True,
            'data': status_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting status: {str(e)}'
        }), 500

@time_attendance_bp.route('/my-timecard')
@login_required
def my_timecard():
    """View employee's own time cards"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = TimeEntry.query.filter_by(user_id=current_user.id)
    
    if start_date:
        query = query.filter(TimeEntry.clock_in_time >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(TimeEntry.clock_in_time <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    time_entries = query.order_by(TimeEntry.clock_in_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate totals
    total_hours = sum(entry.total_hours for entry in time_entries.items)
    total_overtime = sum(entry.overtime_hours for entry in time_entries.items)
    
    # Get current clock status
    open_entry = TimeEntry.query.filter_by(
        user_id=current_user.id,
        status='Open'
    ).first()
    
    current_status = None
    if open_entry:
        current_status = {
            'status': 'clocked_in',
            'clock_in_time': open_entry.clock_in_time,
            'on_break': open_entry.break_start_time and not open_entry.break_end_time
        }
    else:
        current_status = {
            'status': 'clocked_out'
        }
    
    return render_template('time_attendance/my_timecard.html',
                         time_entries=time_entries,
                         total_hours=total_hours,
                         total_overtime=total_overtime,
                         start_date=start_date,
                         end_date=end_date,
                         current_status=current_status)

@time_attendance_bp.route('/status')
@login_required
def current_status():
    """Get current clock status"""
    open_entry = TimeEntry.query.filter_by(
        user_id=current_user.id,
        status='Open'
    ).first()
    
    if not open_entry:
        return jsonify({
            'status': 'clocked_out',
            'message': 'Not currently clocked in'
        })
    
    # Check if on break
    on_break = open_entry.break_start_time and not open_entry.break_end_time
    
    return jsonify({
        'status': 'clocked_in',
        'time_entry_id': open_entry.id,
        'clock_in_time': open_entry.clock_in_time.isoformat(),
        'on_break': on_break,
        'break_start_time': open_entry.break_start_time.isoformat() if open_entry.break_start_time else None
    })

# Manager Routes

@time_attendance_bp.route('/team-timecard')
@role_required('Manager', 'Admin', 'Super User')
def team_timecard():
    """Enhanced team time card management with comprehensive search and filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Enhanced filter parameters
    user_id = request.args.get('user_id', type=int)
    role_filter = request.args.get('role')
    department_filter = request.args.get('department', type=int)
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '').strip()
    
    # Date range filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Quick filters
    quick_filter = request.args.get('quick_filter')
    if quick_filter == 'today':
        start_date = date.today().strftime('%Y-%m-%d')
        end_date = start_date
    elif quick_filter == 'this_week':
        today = date.today()
        start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=6-today.weekday())).strftime('%Y-%m-%d')
    elif quick_filter == 'this_month':
        today = date.today()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # Build base query with joins
    from sqlalchemy.orm import joinedload
    from models import Role, Department
    
    query = TimeEntry.query.options(
        joinedload(TimeEntry.employee).joinedload(User.roles),
        joinedload(TimeEntry.employee).joinedload(User.employee_department)
    ).join(User, TimeEntry.user_id == User.id)
    
    # Apply department-based access control for managers
    if current_user.has_role('Manager') and not current_user.has_role('Super User'):
        # Get departments this manager can access
        from dashboard_management import get_managed_departments
        managed_dept_ids = get_managed_departments(current_user.id)
        
        if managed_dept_ids:
            # Manager can see entries from their managed departments
            query = query.filter(User.department_id.in_(managed_dept_ids))
        else:
            # Manager with no departments sees only their own entries
            query = query.filter(TimeEntry.user_id == current_user.id)
    
    # Apply filters
    if user_id:
        query = query.filter(TimeEntry.user_id == user_id)
    
    if role_filter:
        query = query.join(User.roles).filter(Role.name == role_filter)
    
    if department_filter:
        query = query.filter(User.department_id == department_filter)
    
    if status_filter:
        query = query.filter(TimeEntry.status == status_filter)
    
    # Search functionality
    if search_query:
        search_terms = search_query.split()
        for term in search_terms:
            query = query.filter(
                or_(
                    User.username.ilike(f'%{term}%'),
                    User.first_name.ilike(f'%{term}%'),
                    User.last_name.ilike(f'%{term}%'),
                    User.email.ilike(f'%{term}%'),
                    TimeEntry.notes.ilike(f'%{term}%')
                )
            )
    
    # Date range filtering
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(TimeEntry.clock_in_time >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(TimeEntry.clock_in_time < end_dt)
        except ValueError:
            pass
    
    # Get total count for statistics
    total_entries = query.count()
    
    # Paginate results
    time_entries = query.order_by(TimeEntry.clock_in_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get filter options based on access rights
    if current_user.has_role('Manager') and not current_user.has_role('Super User'):
        # Managers see limited scope
        from dashboard_management import get_managed_departments
        managed_dept_ids = get_managed_departments(current_user.id)
        
        if managed_dept_ids:
            users = User.query.filter(
                User.is_active == True,
                User.department_id.in_(managed_dept_ids)
            ).order_by(User.username).all()
            
            departments = Department.query.filter(
                Department.id.in_(managed_dept_ids)
            ).order_by(Department.name).all()
        else:
            users = [current_user]
            departments = []
    else:
        # Super Users and Admins see all
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
        departments = Department.query.order_by(Department.name).all()
    
    # Get all roles for filtering
    roles = Role.query.order_by(Role.name).all()
    
    # Calculate summary statistics
    summary_stats = {
        'total_entries': total_entries,
        'total_hours': 0,
        'avg_hours_per_day': 0,
        'overtime_hours': 0
    }
    
    # Calculate statistics from current query results
    if time_entries.items:
        total_hours = sum(entry.total_hours for entry in time_entries.items if entry.total_hours)
        summary_stats['total_hours'] = round(total_hours, 2)
        summary_stats['avg_hours_per_day'] = round(total_hours / len(time_entries.items), 2) if time_entries.items else 0
        summary_stats['overtime_hours'] = round(sum(entry.overtime_hours for entry in time_entries.items), 2)
    
    return render_template('time_attendance/team_timecard.html',
                         time_entries=time_entries,
                         users=users,
                         roles=roles,
                         departments=departments,
                         summary_stats=summary_stats,
                         selected_user_id=user_id,
                         selected_role=role_filter,
                         selected_department=department_filter,
                         selected_status=status_filter,
                         search_query=search_query,
                         start_date=start_date,
                         end_date=end_date,
                         quick_filter=quick_filter,
                         per_page=per_page)

@time_attendance_bp.route('/team-calendar')
@role_required('Manager', 'Admin', 'Super User')
def team_calendar():
    """View team time cards in calendar format"""
    # Get week start date from query params or default to current week
    week_start_param = request.args.get('week_start')
    department_filter = request.args.get('department')
    
    if week_start_param:
        try:
            week_start = datetime.strptime(week_start_param, '%Y-%m-%d').date()
        except ValueError:
            week_start = date.today()
    else:
        week_start = date.today()
    
    # Calculate start of week (Monday)
    days_since_monday = week_start.weekday()
    week_start = week_start - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    # Generate date range for the week
    week_dates = []
    current_date = week_start
    while current_date <= week_end:
        week_dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Get all active users with department filtering
    users_query = User.query.filter_by(is_active=True)
    if department_filter:
        # Handle both hierarchical departments and legacy department fields
        if '(' in department_filter and ')' in department_filter:
            # Extract department name from "Department Name (Site Name)" format
            dept_name = department_filter.split(' (')[0]
            users_query = users_query.filter(
                or_(
                    User.department == department_filter,
                    User.department == dept_name
                )
            )
        else:
            # Direct department name match
            users_query = users_query.filter_by(department=department_filter)
    users = users_query.order_by(User.username).all()
    
    # Get time entries for the week
    time_entries = TimeEntry.query.filter(
        and_(
            TimeEntry.clock_in_time >= datetime.combine(week_start, datetime.min.time()),
            TimeEntry.clock_in_time <= datetime.combine(week_end, datetime.max.time())
        )
    ).all()
    
    # Organize time entries by user and date
    calendar_data = {}
    for user in users:
        calendar_data[user.id] = {
            'user': user,
            'entries': {},
            'weekly_total': 0,
            'overtime_hours': 0
        }
        
        # Initialize empty entries for each day
        for date_obj in week_dates:
            calendar_data[user.id]['entries'][date_obj] = []
    
    # Populate actual time entries and calculate totals
    for entry in time_entries:
        if entry.user_id in calendar_data:
            entry_date = entry.clock_in_time.date()
            if entry_date in calendar_data[entry.user_id]['entries']:
                calendar_data[entry.user_id]['entries'][entry_date].append(entry)
                
                # Add to weekly total
                if entry.total_hours:
                    calendar_data[entry.user_id]['weekly_total'] += entry.total_hours
                    
                    # Calculate overtime (assuming 40 hour standard week)
                    if calendar_data[entry.user_id]['weekly_total'] > 40:
                        calendar_data[entry.user_id]['overtime_hours'] = calendar_data[entry.user_id]['weekly_total'] - 40
    
    # Get available departments for filter - using hierarchical Department model
    from models import Department
    departments = Department.query.filter(Department.is_active == True).all()
    department_list = [(dept.name, f"{dept.name} ({dept.site.name})") for dept in departments]
    
    # Also include legacy departments for backwards compatibility
    legacy_departments = db.session.query(User.department).filter(
        User.department.isnot(None),
        User.is_active == True
    ).distinct().all()
    legacy_dept_names = [dept[0] for dept in legacy_departments if dept[0]]
    
    # Combine both lists
    all_departments = []
    for dept_name, dept_display in department_list:
        all_departments.append(dept_display)
    for legacy_dept in legacy_dept_names:
        if legacy_dept not in [d[0] for d in department_list]:
            all_departments.append(legacy_dept)
    
    departments = sorted(all_departments)
    
    # Calculate navigation dates
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    
    return render_template('time_attendance/team_calendar.html',
                         calendar_data=calendar_data,
                         week_dates=week_dates,
                         week_start=week_start,
                         week_end=week_end,
                         prev_week=prev_week,
                         next_week=next_week,
                         departments=departments,
                         selected_department=department_filter)

@time_attendance_bp.route('/approve-entry/<int:entry_id>', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def approve_time_entry(entry_id):
    """Approve a time entry"""
    try:
        time_entry = TimeEntry.query.get_or_404(entry_id)
        
        if not time_entry.can_be_approved_by(current_user):
            return jsonify({
                'success': False,
                'message': 'You do not have permission to approve this entry.'
            }), 403
        
        time_entry.approved_by_manager_id = current_user.id
        time_entry.status = 'Closed'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Time entry approved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error approving entry: {str(e)}'
        }), 500

@time_attendance_bp.route('/approve-overtime/<int:entry_id>', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def approve_overtime(entry_id):
    """Approve overtime for a time entry"""
    try:
        time_entry = TimeEntry.query.get_or_404(entry_id)
        
        if not time_entry.can_be_approved_by(current_user):
            return jsonify({
                'success': False,
                'message': 'You do not have permission to approve overtime for this entry.'
            }), 403
        
        time_entry.is_overtime_approved = True
        time_entry.approved_by_manager_id = current_user.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Overtime approved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error approving overtime: {str(e)}'
        }), 500

@time_attendance_bp.route('/exceptions')
@role_required('Manager', 'Admin', 'Super User')
def time_exceptions():
    """View time card exceptions that need approval"""
    # Find entries with exceptions (missed clock-out, long shifts, etc.)
    exceptions = TimeEntry.query.filter(
        or_(
            TimeEntry.status == 'Exception',
            and_(TimeEntry.status == 'Open', 
                 TimeEntry.clock_in_time < datetime.utcnow() - timedelta(hours=12)),
            and_(TimeEntry.clock_out_time.isnot(None),
                 func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) > 10 * 3600)  # >10 hours
        )
    ).order_by(TimeEntry.clock_in_time.desc()).all()
    
    return render_template('time_attendance/exceptions.html', exceptions=exceptions)

# Admin/Super User Routes

@time_attendance_bp.route('/manual-entry', methods=['GET', 'POST'])
@super_user_required
def manual_entry():
    """Manual time entry for admins"""
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            clock_in_str = request.form.get('clock_in_time')
            clock_out_str = request.form.get('clock_out_time')
            notes = request.form.get('notes', '')
            
            clock_in_time = datetime.strptime(clock_in_str, '%Y-%m-%dT%H:%M')
            clock_out_time = datetime.strptime(clock_out_str, '%Y-%m-%dT%H:%M') if clock_out_str else None
            
            time_entry = TimeEntry()
            time_entry.user_id = user_id
            time_entry.clock_in_time = clock_in_time
            time_entry.clock_out_time = clock_out_time
            time_entry.status = 'Closed' if clock_out_time else 'Open'
            time_entry.notes = notes
            time_entry.approved_by_manager_id = current_user.id
            
            db.session.add(time_entry)
            db.session.commit()
            
            flash('Manual time entry created successfully', 'success')
            return redirect(url_for('time_attendance.admin_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating manual entry: {str(e)}', 'danger')
    
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    return render_template('time_attendance/manual_entry.html', users=users)

@time_attendance_bp.route('/admin')
@super_user_required
def admin_dashboard():
    """Admin dashboard for time attendance"""
    # Get summary statistics
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    
    stats = {
        'total_entries_today': TimeEntry.query.filter(
            func.date(TimeEntry.clock_in_time) == today
        ).count(),
        'open_entries': TimeEntry.query.filter_by(status='Open').count(),
        'exceptions_count': TimeEntry.query.filter_by(status='Exception').count(),
        'week_total_hours': db.session.query(
            func.sum(func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) / 3600)
        ).filter(
            and_(
                TimeEntry.clock_in_time >= week_start,
                TimeEntry.clock_out_time.isnot(None)
            )
        ).scalar() or 0
    }
    
    # Recent entries
    recent_entries = TimeEntry.query.order_by(
        TimeEntry.created_at.desc()
    ).limit(10).all()
    
    return render_template('time_attendance/admin_dashboard.html', 
                         stats=stats, 
                         recent_entries=recent_entries)

@time_attendance_bp.route('/import-data', methods=['GET', 'POST'])
@super_user_required
def import_clock_data():
    """Import clock data endpoint (stub for future implementation)"""
    if request.method == 'POST':
        # Placeholder for import functionality
        # This would handle CSV/Excel imports, external system integrations, etc.
        flash('Import functionality will be implemented in future updates', 'info')
        return redirect(url_for('time_attendance.admin_dashboard'))
    
    return render_template('time_attendance/import_data.html')

@time_attendance_bp.route('/reports')
@role_required('Manager', 'Admin', 'Super User')
def reports():
    """Time attendance reports"""
    report_type = request.args.get('type', 'summary')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = date.today().strftime('%Y-%m-%d')
    
    query = TimeEntry.query.filter(
        and_(
            TimeEntry.clock_in_time >= datetime.strptime(start_date, '%Y-%m-%d'),
            TimeEntry.clock_in_time <= datetime.strptime(end_date, '%Y-%m-%d')
        )
    )
    
    if report_type == 'summary':
        # Apply department filtering for managers
        is_super_user = current_user.has_role('Super User')
        is_manager = current_user.has_role('Manager')
        managed_dept_ids = get_managed_departments(current_user.id) if is_manager else []
        
        # Build base query with date filters
        base_query = TimeEntry.query.filter(
            and_(
                TimeEntry.clock_in_time >= datetime.strptime(start_date, '%Y-%m-%d'),
                TimeEntry.clock_in_time <= datetime.strptime(end_date, '%Y-%m-%d'),
                TimeEntry.clock_out_time.isnot(None)
            )
        )
        
        # Apply department filtering for managers
        if is_manager and managed_dept_ids and not is_super_user:
            entries_query = base_query.join(User, TimeEntry.user_id == User.id).filter(User.department_id.in_(managed_dept_ids)).all()
        else:
            entries_query = base_query.all()
        
        # Calculate summary data in Python
        user_data = {}
        for entry in entries_query:
            user = User.query.get(entry.user_id)
            if not user:
                continue
            
            # Additional security check for managers
            if is_manager and managed_dept_ids and not is_super_user:
                if user.department_id not in managed_dept_ids:
                    continue
                
            username = user.username
            if username not in user_data:
                user_data[username] = {
                    'username': username,
                    'total_entries': 0,
                    'total_hours': 0.0,
                    'overtime_hours': 0.0
                }
            
            user_data[username]['total_entries'] += 1
            user_data[username]['total_hours'] += entry.total_hours or 0
            user_data[username]['overtime_hours'] += entry.overtime_hours or 0
        
        report_data = list(user_data.values())
    else:
        report_data = query.all()
    
    return render_template('time_attendance/reports.html',
                         report_data=report_data,
                         report_type=report_type,
                         start_date=start_date,
                         end_date=end_date)

# API Endpoints for Mobile/AJAX

@time_attendance_bp.route('/api/punch-status')
@login_required
def api_punch_status():
    """API endpoint to get current punch status"""
    return current_status()

@time_attendance_bp.route('/api/quick-punch', methods=['POST'])
@login_required
def api_quick_punch():
    """API endpoint for quick punch in/out"""
    try:
        action = request.json.get('action')  # 'clock_in' or 'clock_out'
        
        if action == 'clock_in':
            return clock_in()
        elif action == 'clock_out':
            return clock_out()
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid action. Use "clock_in" or "clock_out"'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing punch: {str(e)}'
        }), 500

@time_attendance_bp.route('/employee-timecards')
@role_required('Manager', 'Admin', 'Super User')
def employee_timecards():
    """Comprehensive employee time card management interface"""
    from models import User, Schedule, TimeEntry, LeaveApplication
    from organization_management import get_managed_departments
    from datetime import datetime, date, timedelta
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    user_id = request.args.get('user_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to current week if no dates provided
    if not start_date and not end_date:
        today = date.today()
        start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=6-today.weekday())).strftime('%Y-%m-%d')
    
    # Convert string dates to date objects for queries
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    
    # Apply role-based filtering
    is_super_user = current_user.has_role('Super User')
    is_manager = current_user.has_role('Manager')
    managed_dept_ids = get_managed_departments(current_user.id) if is_manager else []
    
    # Get users based on permissions
    users_query = User.query.filter_by(is_active=True)
    
    if is_super_user:
        # Super Users see all active users
        users = users_query.order_by(User.username).all()
    elif is_manager and managed_dept_ids:
        # Managers see only users in departments they manage
        users = users_query.filter(User.department_id.in_(managed_dept_ids)).order_by(User.username).all()
    else:
        # Regular employees see only themselves
        users = [current_user] if current_user.is_active else []
    
    # If specific user selected, filter to that user
    if user_id:
        users = [user for user in users if user.id == user_id]
    
    # Build comprehensive time card data
    timecard_data = []
    
    for user in users:
        if start_date_obj and end_date_obj:
            # Generate date range for the period
            current_date = start_date_obj
            while current_date <= end_date_obj:
                # Get schedule for this date
                schedule = Schedule.query.filter(
                    Schedule.user_id == user.id,
                    func.date(Schedule.start_time) == current_date
                ).first()
                
                # Get time entries for this date
                time_entries = TimeEntry.query.filter(
                    TimeEntry.user_id == user.id,
                    func.date(TimeEntry.clock_in_time) == current_date
                ).all()
                
                # Get leave applications for this date
                leave_app = LeaveApplication.query.filter(
                    LeaveApplication.user_id == user.id,
                    LeaveApplication.start_date <= current_date,
                    LeaveApplication.end_date >= current_date,
                    LeaveApplication.status == 'Approved'
                ).first()
                
                # Calculate total hours worked
                total_hours = 0
                clock_in_time = None
                clock_out_time = None
                
                if time_entries:
                    for entry in time_entries:
                        if entry.clock_in_time and entry.clock_out_time:
                            hours = entry.total_hours
                            total_hours += hours
                            
                            # Get first clock in and last clock out
                            if not clock_in_time or entry.clock_in_time < clock_in_time:
                                clock_in_time = entry.clock_in_time
                            if not clock_out_time or entry.clock_out_time > clock_out_time:
                                clock_out_time = entry.clock_out_time
                
                # Calculate amount earned (if hourly rate available)
                amount_earned = 0
                if user.hourly_rate and total_hours > 0:
                    amount_earned = total_hours * user.hourly_rate
                
                timecard_data.append({
                    'user': user,
                    'date': current_date,
                    'schedule': schedule,
                    'absence': leave_app,
                    'clock_in': clock_in_time,
                    'clock_out': clock_out_time,
                    'total_hours': round(total_hours, 2),
                    'amount_earned': round(amount_earned, 2),
                    'time_entries': time_entries
                })
                
                current_date += timedelta(days=1)
    
    # Pagination for timecard data
    total_records = len(timecard_data)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_data = timecard_data[start_index:end_index]
    
    # Create pagination object
    class PaginationHelper:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    pagination = PaginationHelper(page, per_page, total_records, paginated_data)
    
    # Get all users for dropdown (not filtered by selection)
    all_users = User.query.filter_by(is_active=True)
    if is_manager and managed_dept_ids and not is_super_user:
        all_users = all_users.filter(User.department_id.in_(managed_dept_ids))
    all_users = all_users.order_by(User.username).all()
    
    return render_template('time_attendance/employee_timecards.html',
                         timecard_data=pagination,
                         users=all_users,
                         selected_user_id=user_id,
                         start_date=start_date,
                         end_date=end_date)