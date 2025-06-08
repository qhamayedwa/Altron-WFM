from datetime import datetime, date, timedelta, time
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from app import db
from models import Schedule, ShiftType, User
from auth_simple import role_required, super_user_required

# Create scheduling blueprint
scheduling_bp = Blueprint('scheduling', __name__, url_prefix='/schedule')

# Shift Type Management Routes

@scheduling_bp.route('/shift-types')
@role_required('Manager', 'Admin', 'Super User')
def shift_types():
    """View and manage shift types"""
    shift_types = ShiftType.query.filter_by(is_active=True).order_by(ShiftType.name).all()
    return render_template('scheduling/shift_types.html', shift_types=shift_types)

@scheduling_bp.route('/shift-types/create', methods=['GET', 'POST'])
@role_required('Manager', 'Admin', 'Super User')
def create_shift_type():
    """Create a new shift type"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            default_start_time = request.form.get('default_start_time')
            default_end_time = request.form.get('default_end_time')
            
            if not all([name, default_start_time, default_end_time]):
                flash('Name, start time, and end time are required.', 'danger')
                return render_template('scheduling/create_shift_type.html')
            
            # Check if shift type already exists
            if ShiftType.query.filter_by(name=name).first():
                flash('A shift type with this name already exists.', 'danger')
                return render_template('scheduling/create_shift_type.html')
            
            # Parse time strings
            start_time = datetime.strptime(default_start_time, '%H:%M').time()
            end_time = datetime.strptime(default_end_time, '%H:%M').time()
            
            shift_type = ShiftType(
                name=name,
                description=description,
                default_start_time=start_time,
                default_end_time=end_time
            )
            
            db.session.add(shift_type)
            db.session.commit()
            
            flash(f'Shift type "{name}" created successfully!', 'success')
            return redirect(url_for('scheduling.shift_types'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating shift type: {str(e)}', 'danger')
    
    return render_template('scheduling/create_shift_type.html')

@scheduling_bp.route('/shift-types/<int:shift_type_id>/edit', methods=['GET', 'POST'])
@role_required('Manager', 'Admin', 'Super User')
def edit_shift_type(shift_type_id):
    """Edit an existing shift type"""
    shift_type = ShiftType.query.get_or_404(shift_type_id)
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            default_start_time = request.form.get('default_start_time')
            default_end_time = request.form.get('default_end_time')
            is_active = request.form.get('is_active') == 'on'
            
            if not all([name, default_start_time, default_end_time]):
                flash('Name, start time, and end time are required.', 'danger')
                return render_template('scheduling/edit_shift_type.html', shift_type=shift_type)
            
            # Check if another shift type with this name exists
            existing = ShiftType.query.filter(
                ShiftType.name == name,
                ShiftType.id != shift_type_id
            ).first()
            
            if existing:
                flash('A shift type with this name already exists.', 'danger')
                return render_template('scheduling/edit_shift_type.html', shift_type=shift_type)
            
            # Parse time strings
            start_time = datetime.strptime(default_start_time, '%H:%M').time()
            end_time = datetime.strptime(default_end_time, '%H:%M').time()
            
            shift_type.name = name
            shift_type.description = description
            shift_type.default_start_time = start_time
            shift_type.default_end_time = end_time
            shift_type.is_active = is_active
            
            db.session.commit()
            
            flash(f'Shift type "{name}" updated successfully!', 'success')
            return redirect(url_for('scheduling.shift_types'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating shift type: {str(e)}', 'danger')
    
    return render_template('scheduling/edit_shift_type.html', shift_type=shift_type)

@scheduling_bp.route('/shift-types/<int:shift_type_id>/delete', methods=['POST'])
@role_required('Admin', 'Super User')
def delete_shift_type(shift_type_id):
    """Delete a shift type"""
    try:
        shift_type = ShiftType.query.get_or_404(shift_type_id)
        
        # Check if shift type is in use
        schedules_count = Schedule.query.filter_by(shift_type_id=shift_type_id).count()
        if schedules_count > 0:
            flash(f'Cannot delete shift type "{shift_type.name}" because it is used in {schedules_count} schedule(s).', 'danger')
        else:
            db.session.delete(shift_type)
            db.session.commit()
            flash(f'Shift type "{shift_type.name}" deleted successfully!', 'success')
        
        return redirect(url_for('scheduling.shift_types'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting shift type: {str(e)}', 'danger')
        return redirect(url_for('scheduling.shift_types'))

# Schedule Management Routes

@scheduling_bp.route('/schedules')
@role_required('Manager', 'Admin', 'Super User')
def manage_schedules():
    """View and manage employee schedules"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    user_id = request.args.get('user_id', type=int)
    shift_type_id = request.args.get('shift_type_id', type=int)
    
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to current week if no dates provided
    if not start_date and not end_date:
        today = date.today()
        start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=6-today.weekday())).strftime('%Y-%m-%d')
    
    # Apply department filtering for managers
    is_super_user = current_user.has_role('Super User')
    is_manager = current_user.has_role('Manager')
    user_department_id = getattr(current_user, 'department_id', None)
    
    query = Schedule.query
    
    # Apply department filtering to schedules for managers
    if is_manager and user_department_id and not is_super_user:
        query = query.join(User).filter(User.department_id == user_department_id)
    
    # Filter by user if specified
    if user_id:
        query = query.filter(Schedule.user_id == user_id)
    
    # Filter by shift type if specified
    if shift_type_id:
        query = query.filter_by(shift_type_id=shift_type_id)
    
    # Filter by date range
    if start_date:
        query = query.filter(Schedule.start_time >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Schedule.start_time <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    
    schedules = query.order_by(Schedule.start_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Apply department filtering to users list for managers
    if is_super_user:
        # Super Users see all active users
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
    elif is_manager and user_department_id:
        # Managers see only users in their department
        users = User.query.filter_by(is_active=True, department_id=user_department_id).order_by(User.username).all()
    else:
        # Regular employees see only themselves
        users = [current_user] if current_user.is_active else []
    shift_types = ShiftType.query.filter_by(is_active=True).order_by(ShiftType.name).all()
    
    return render_template('scheduling/manage_schedules.html',
                         schedules=schedules,
                         users=users,
                         shift_types=shift_types,
                         selected_user_id=user_id,
                         selected_shift_type_id=shift_type_id,
                         start_date=start_date,
                         end_date=end_date)

@scheduling_bp.route('/schedules/create', methods=['GET', 'POST'])
@role_required('Manager', 'Admin', 'Super User')
def create_schedule():
    """Create a new schedule"""
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            shift_type_id = request.form.get('shift_type_id', type=int) or None
            start_datetime = request.form.get('start_datetime')
            end_datetime = request.form.get('end_datetime')
            notes = request.form.get('notes')
            
            if not all([user_id, start_datetime, end_datetime]):
                flash('Employee, start time, and end time are required.', 'danger')
                return redirect(url_for('scheduling.create_schedule'))
            
            # Parse datetime strings
            start_time = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            
            if end_time <= start_time:
                flash('End time must be after start time.', 'danger')
                return redirect(url_for('scheduling.create_schedule'))
            
            # Check for scheduling conflicts
            conflicts = Schedule.query.filter(
                Schedule.user_id == user_id,
                Schedule.status.in_(['Scheduled', 'Confirmed']),
                or_(
                    and_(Schedule.start_time <= start_time, Schedule.end_time > start_time),
                    and_(Schedule.start_time < end_time, Schedule.end_time >= end_time),
                    and_(Schedule.start_time >= start_time, Schedule.end_time <= end_time)
                )
            ).first()
            
            if conflicts:
                flash('This schedule conflicts with an existing schedule.', 'danger')
                return redirect(url_for('scheduling.create_schedule'))
            
            schedule = Schedule(
                user_id=user_id,
                shift_type_id=shift_type_id,
                start_time=start_time,
                end_time=end_time,
                assigned_by_manager_id=current_user.id,
                notes=notes
            )
            
            db.session.add(schedule)
            db.session.commit()
            
            # Trigger notification (stub for now)
            _trigger_schedule_notification(schedule, 'created')
            
            flash('Schedule created successfully!', 'success')
            return redirect(url_for('scheduling.manage_schedules'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating schedule: {str(e)}', 'danger')
    
    # Apply department filtering for users list
    is_super_user = current_user.has_role('Super User')
    is_manager = current_user.has_role('Manager')
    user_department_id = getattr(current_user, 'department_id', None)
    
    if is_super_user:
        # Super Users see all active users
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
    elif is_manager and user_department_id:
        # Managers see only users in their department
        users = User.query.filter_by(is_active=True, department_id=user_department_id).order_by(User.username).all()
    else:
        # Regular employees see only themselves
        users = [current_user] if current_user.is_active else []
        
    shift_types = ShiftType.query.filter_by(is_active=True).order_by(ShiftType.name).all()
    
    return render_template('scheduling/create_schedule.html', 
                         users=users, 
                         shift_types=shift_types)

@scheduling_bp.route('/schedules/<int:schedule_id>/edit', methods=['GET', 'POST'])
@role_required('Manager', 'Admin', 'Super User')
def edit_schedule(schedule_id):
    """Edit an existing schedule"""
    schedule = Schedule.query.get_or_404(schedule_id)
    
    if request.method == 'POST':
        try:
            shift_type_id = request.form.get('shift_type_id', type=int) or None
            start_datetime = request.form.get('start_datetime')
            end_datetime = request.form.get('end_datetime')
            notes = request.form.get('notes')
            status = request.form.get('status')
            
            if not all([start_datetime, end_datetime]):
                flash('Start time and end time are required.', 'danger')
                return render_template('scheduling/edit_schedule.html', schedule=schedule)
            
            # Parse datetime strings
            start_time = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            
            if end_time <= start_time:
                flash('End time must be after start time.', 'danger')
                return render_template('scheduling/edit_schedule.html', schedule=schedule)
            
            # Check for scheduling conflicts (excluding current schedule)
            conflicts = Schedule.query.filter(
                Schedule.user_id == schedule.user_id,
                Schedule.id != schedule_id,
                Schedule.status.in_(['Scheduled', 'Confirmed']),
                or_(
                    and_(Schedule.start_time <= start_time, Schedule.end_time > start_time),
                    and_(Schedule.start_time < end_time, Schedule.end_time >= end_time),
                    and_(Schedule.start_time >= start_time, Schedule.end_time <= end_time)
                )
            ).first()
            
            if conflicts:
                flash('This schedule conflicts with an existing schedule.', 'danger')
                return render_template('scheduling/edit_schedule.html', schedule=schedule)
            
            schedule.shift_type_id = shift_type_id
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.notes = notes
            schedule.status = status
            
            db.session.commit()
            
            # Trigger notification (stub for now)
            _trigger_schedule_notification(schedule, 'updated')
            
            flash('Schedule updated successfully!', 'success')
            return redirect(url_for('scheduling.manage_schedules'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating schedule: {str(e)}', 'danger')
    
    shift_types = ShiftType.query.filter_by(is_active=True).order_by(ShiftType.name).all()
    return render_template('scheduling/edit_schedule.html', 
                         schedule=schedule, 
                         shift_types=shift_types)

@scheduling_bp.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def delete_schedule(schedule_id):
    """Delete a schedule"""
    try:
        schedule = Schedule.query.get_or_404(schedule_id)
        
        # Trigger notification (stub for now)
        _trigger_schedule_notification(schedule, 'deleted')
        
        db.session.delete(schedule)
        db.session.commit()
        
        flash('Schedule deleted successfully!', 'success')
        return redirect(url_for('scheduling.manage_schedules'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting schedule: {str(e)}', 'danger')
        return redirect(url_for('scheduling.manage_schedules'))

# Employee Schedule View

@scheduling_bp.route('/my-schedule')
@login_required
def my_schedule():
    """View employee's own schedule"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Default to current and next week if no dates provided
    if not start_date and not end_date:
        today = date.today()
        start_date = today.strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=14)).strftime('%Y-%m-%d')
    
    query = Schedule.query.filter_by(user_id=current_user.id)
    
    # Filter by date range
    if start_date:
        query = query.filter(Schedule.start_time >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Schedule.start_time <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    
    schedules = query.order_by(Schedule.start_time.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total hours for the current page
    total_hours = sum(schedule.duration_hours() for schedule in schedules.items)
    
    return render_template('scheduling/my_schedule.html',
                         schedules=schedules,
                         total_hours=total_hours,
                         start_date=start_date,
                         end_date=end_date)

# API Endpoints

@scheduling_bp.route('/api/shift-types', methods=['GET'])
@role_required('Manager', 'Admin', 'Super User')
def api_shift_types():
    """API endpoint to get shift types"""
    shift_types = ShiftType.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': st.id,
        'name': st.name,
        'default_start_time': st.default_start_time.strftime('%H:%M'),
        'default_end_time': st.default_end_time.strftime('%H:%M'),
        'duration_hours': st.duration_hours()
    } for st in shift_types])

@scheduling_bp.route('/api/schedule-conflicts', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def api_check_schedule_conflicts():
    """API endpoint to check for schedule conflicts"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_time = datetime.fromisoformat(data.get('start_time'))
        end_time = datetime.fromisoformat(data.get('end_time'))
        exclude_schedule_id = data.get('exclude_schedule_id')
        
        query = Schedule.query.filter(
            Schedule.user_id == user_id,
            Schedule.status.in_(['Scheduled', 'Confirmed']),
            or_(
                and_(Schedule.start_time <= start_time, Schedule.end_time > start_time),
                and_(Schedule.start_time < end_time, Schedule.end_time >= end_time),
                and_(Schedule.start_time >= start_time, Schedule.end_time <= end_time)
            )
        )
        
        if exclude_schedule_id:
            query = query.filter(Schedule.id != exclude_schedule_id)
        
        conflicts = query.all()
        
        return jsonify({
            'has_conflicts': len(conflicts) > 0,
            'conflicts': [{
                'id': s.id,
                'start_time': s.start_time.isoformat(),
                'end_time': s.end_time.isoformat(),
                'shift_type': s.shift_type.name if s.shift_type else 'Custom'
            } for s in conflicts]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Helper Functions

def _trigger_schedule_notification(schedule, action):
    """Trigger notification for schedule changes (stub implementation)"""
    # This is a placeholder for future notification system integration
    # Could send emails, SMS, push notifications, etc.
    print(f"Schedule {action}: {schedule.employee.username} - {schedule.start_time}")
    pass