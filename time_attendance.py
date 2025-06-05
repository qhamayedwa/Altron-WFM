from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from app import db
from models import TimeEntry, User
from auth_simple import role_required, super_user_required

# Create time attendance blueprint
time_attendance_bp = Blueprint('time_attendance', __name__, url_prefix='/time')

# Employee Routes

@time_attendance_bp.route('/clock-in', methods=['POST'])
@login_required
def clock_in():
    """Employee clock-in endpoint"""
    try:
        # Check if user already has an open time entry
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if open_entry:
            return jsonify({
                'success': False,
                'message': 'You already have an open time entry. Please clock out first.'
            }), 400
        
        # Get GPS coordinates if provided
        latitude = request.json.get('latitude') if request.is_json else None
        longitude = request.json.get('longitude') if request.is_json else None
        notes = request.json.get('notes', '') if request.is_json else ''
        
        # Create new time entry
        time_entry = TimeEntry()
        time_entry.user_id = current_user.id
        time_entry.clock_in_time = datetime.utcnow()
        time_entry.status = 'Open'
        time_entry.notes = notes
        time_entry.clock_in_latitude = latitude
        time_entry.clock_in_longitude = longitude
        
        db.session.add(time_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Successfully clocked in',
            'time_entry_id': time_entry.id,
            'clock_in_time': time_entry.clock_in_time.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error clocking in: {str(e)}'
        }), 500

@time_attendance_bp.route('/clock-out', methods=['POST'])
@login_required
def clock_out():
    """Employee clock-out endpoint"""
    try:
        # Find the open time entry for the user
        open_entry = TimeEntry.query.filter_by(
            user_id=current_user.id,
            status='Open'
        ).first()
        
        if not open_entry:
            return jsonify({
                'success': False,
                'message': 'No open time entry found. Please clock in first.'
            }), 400
        
        # Get GPS coordinates if provided
        latitude = request.json.get('latitude') if request.is_json else None
        longitude = request.json.get('longitude') if request.is_json else None
        notes = request.json.get('notes', '') if request.is_json else ''
        
        # Update time entry
        open_entry.clock_out_time = datetime.utcnow()
        open_entry.status = 'Closed'
        open_entry.clock_out_latitude = latitude
        open_entry.clock_out_longitude = longitude
        if notes:
            open_entry.notes = (open_entry.notes or '') + f" | Clock-out notes: {notes}"
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Successfully clocked out',
            'time_entry_id': open_entry.id,
            'clock_out_time': open_entry.clock_out_time.isoformat(),
            'total_hours': open_entry.total_hours
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error clocking out: {str(e)}'
        }), 500

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
    
    return render_template('time_attendance/my_timecard.html',
                         time_entries=time_entries,
                         total_hours=total_hours,
                         total_overtime=total_overtime,
                         start_date=start_date,
                         end_date=end_date)

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
    """View team members' time cards"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    user_id = request.args.get('user_id', type=int)
    
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = TimeEntry.query
    
    # Filter by user if specified
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by date range
    if start_date:
        query = query.filter(TimeEntry.clock_in_time >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(TimeEntry.clock_in_time <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    time_entries = query.order_by(TimeEntry.clock_in_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all users for filter dropdown
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    return render_template('time_attendance/team_timecard.html',
                         time_entries=time_entries,
                         users=users,
                         selected_user_id=user_id,
                         start_date=start_date,
                         end_date=end_date)

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
        # Summary report by user
        report_data = db.session.query(
            User.username,
            func.count(TimeEntry.id).label('total_entries'),
            func.sum(func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) / 3600).label('total_hours'),
            func.sum(func.case(
                [(func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) / 3600 > 8, 
                 func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) / 3600 - 8)],
                else_=0
            )).label('overtime_hours')
        ).join(TimeEntry).filter(
            and_(
                TimeEntry.clock_in_time >= datetime.strptime(start_date, '%Y-%m-%d'),
                TimeEntry.clock_in_time <= datetime.strptime(end_date, '%Y-%m-%d'),
                TimeEntry.clock_out_time.isnot(None)
            )
        ).group_by(User.username).all()
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