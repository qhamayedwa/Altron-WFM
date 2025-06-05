from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from app import db
from models import PayCode, TimeEntry, User, LeaveType, LeaveBalance
from auth_simple import super_user_required
import json

# Create pay codes blueprint
pay_codes_bp = Blueprint('pay_codes', __name__, url_prefix='/pay-codes')

@pay_codes_bp.route('/')
@super_user_required
def manage_pay_codes():
    """Manage pay codes dashboard"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    code_type = request.args.get('type')
    status_filter = request.args.get('status')
    
    query = PayCode.query
    
    if code_type == 'absence':
        query = query.filter_by(is_absence_code=True)
    elif code_type == 'payroll':
        query = query.filter_by(is_absence_code=False)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    pay_codes = query.order_by(PayCode.code.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('pay_codes/manage_codes.html',
                         pay_codes=pay_codes,
                         code_type=code_type,
                         status_filter=status_filter)

@pay_codes_bp.route('/create', methods=['GET', 'POST'])
@super_user_required
def create_pay_code():
    """Create a new pay code"""
    if request.method == 'POST':
        try:
            code = request.form.get('code', '').upper().strip()
            description = request.form.get('description', '').strip()
            is_absence_code = request.form.get('is_absence_code') == 'on'
            
            if not code or not description:
                flash('Code and description are required.', 'danger')
                return render_template('pay_codes/create_code.html')
            
            # Check if code already exists
            if PayCode.query.filter_by(code=code).first():
                flash(f'Pay code "{code}" already exists.', 'danger')
                return render_template('pay_codes/create_code.html')
            
            # Build configuration
            configuration = {}
            
            # Pay rate factor
            pay_rate_factor = request.form.get('pay_rate_factor')
            if pay_rate_factor:
                configuration['pay_rate_factor'] = float(pay_rate_factor)
            
            # Absence-specific settings
            if is_absence_code:
                configuration['is_paid'] = request.form.get('is_paid') == 'on'
                configuration['requires_approval'] = request.form.get('requires_approval') == 'on'
                configuration['deducts_from_balance'] = request.form.get('deducts_from_balance') == 'on'
                
                # Max hours per day
                max_hours_per_day = request.form.get('max_hours_per_day')
                if max_hours_per_day:
                    configuration['max_hours_per_day'] = float(max_hours_per_day)
                
                # Max consecutive days
                max_consecutive_days = request.form.get('max_consecutive_days')
                if max_consecutive_days:
                    configuration['max_consecutive_days'] = int(max_consecutive_days)
                
                # Linked leave type
                leave_type_id = request.form.get('leave_type_id')
                if leave_type_id:
                    configuration['leave_type_id'] = int(leave_type_id)
            
            pay_code = PayCode(
                code=code,
                description=description,
                is_absence_code=is_absence_code,
                created_by_id=current_user.id
            )
            
            pay_code.set_configuration(configuration)
            
            db.session.add(pay_code)
            db.session.commit()
            
            flash(f'Pay code "{code}" created successfully!', 'success')
            return redirect(url_for('pay_codes.manage_pay_codes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating pay code: {str(e)}', 'danger')
    
    # Get leave types for linking
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    
    return render_template('pay_codes/create_code.html', leave_types=leave_types)

@pay_codes_bp.route('/<int:code_id>')
@super_user_required
def view_pay_code(code_id):
    """View pay code details"""
    pay_code = PayCode.query.get_or_404(code_id)
    
    # Get usage statistics
    time_entries_count = TimeEntry.query.filter_by(absence_pay_code_id=code_id).count()
    
    # Get recent usage
    recent_entries = TimeEntry.query.filter_by(absence_pay_code_id=code_id).order_by(
        TimeEntry.created_at.desc()
    ).limit(10).all()
    
    return render_template('pay_codes/view_code.html',
                         pay_code=pay_code,
                         time_entries_count=time_entries_count,
                         recent_entries=recent_entries)

@pay_codes_bp.route('/<int:code_id>/edit', methods=['GET', 'POST'])
@super_user_required
def edit_pay_code(code_id):
    """Edit an existing pay code"""
    pay_code = PayCode.query.get_or_404(code_id)
    
    if request.method == 'POST':
        try:
            pay_code.description = request.form.get('description', '').strip()
            pay_code.is_active = request.form.get('is_active') == 'on'
            
            # Build configuration
            configuration = {}
            
            # Pay rate factor
            pay_rate_factor = request.form.get('pay_rate_factor')
            if pay_rate_factor:
                configuration['pay_rate_factor'] = float(pay_rate_factor)
            
            # Absence-specific settings
            if pay_code.is_absence_code:
                configuration['is_paid'] = request.form.get('is_paid') == 'on'
                configuration['requires_approval'] = request.form.get('requires_approval') == 'on'
                configuration['deducts_from_balance'] = request.form.get('deducts_from_balance') == 'on'
                
                # Max hours per day
                max_hours_per_day = request.form.get('max_hours_per_day')
                if max_hours_per_day:
                    configuration['max_hours_per_day'] = float(max_hours_per_day)
                
                # Max consecutive days
                max_consecutive_days = request.form.get('max_consecutive_days')
                if max_consecutive_days:
                    configuration['max_consecutive_days'] = int(max_consecutive_days)
                
                # Linked leave type
                leave_type_id = request.form.get('leave_type_id')
                if leave_type_id:
                    configuration['leave_type_id'] = int(leave_type_id)
            
            pay_code.set_configuration(configuration)
            pay_code.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Pay code "{pay_code.code}" updated successfully!', 'success')
            return redirect(url_for('pay_codes.view_pay_code', code_id=code_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating pay code: {str(e)}', 'danger')
    
    # Get leave types for linking
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    
    return render_template('pay_codes/edit_code.html',
                         pay_code=pay_code,
                         leave_types=leave_types)

@pay_codes_bp.route('/<int:code_id>/delete', methods=['POST'])
@super_user_required
def delete_pay_code(code_id):
    """Delete a pay code (Super User only)"""
    try:
        pay_code = PayCode.query.get_or_404(code_id)
        
        # Check if code is used in any time entries
        entries_using_code = TimeEntry.query.filter_by(absence_pay_code_id=code_id).count()
        
        if entries_using_code > 0:
            flash(f'Cannot delete pay code "{pay_code.code}" - it is used in {entries_using_code} time entries. Consider deactivating instead.', 'danger')
            return redirect(url_for('pay_codes.view_pay_code', code_id=code_id))
        
        code_name = pay_code.code
        db.session.delete(pay_code)
        db.session.commit()
        
        flash(f'Pay code "{code_name}" deleted successfully!', 'success')
        return redirect(url_for('pay_codes.manage_pay_codes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting pay code: {str(e)}', 'danger')
        return redirect(url_for('pay_codes.manage_pay_codes'))

@pay_codes_bp.route('/absences')
@login_required
def manage_absences():
    """Manage employee absences"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    employee_filter = request.args.get('employee_id', type=int)
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    
    query = TimeEntry.query.filter(TimeEntry.absence_pay_code_id.isnot(None))
    
    # Apply filters
    if employee_filter:
        query = query.filter_by(user_id=employee_filter)
    
    if status_filter:
        if status_filter == 'pending':
            query = query.filter(TimeEntry.absence_approved_at.is_(None))
        elif status_filter == 'approved':
            query = query.filter(TimeEntry.absence_approved_at.isnot(None))
    
    if date_filter:
        filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        query = query.filter(func.date(TimeEntry.clock_in_time) == filter_date)
    
    # Managers can only see their team's absences (unless Super User/Admin)
    if not (current_user.has_role('Super User') or current_user.has_role('Admin')):
        # Add team filtering logic here if needed
        pass
    
    absences = query.order_by(TimeEntry.clock_in_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get employees for filter
    employees = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    return render_template('pay_codes/manage_absences.html',
                         absences=absences,
                         employees=employees,
                         employee_filter=employee_filter,
                         status_filter=status_filter,
                         date_filter=date_filter)

@pay_codes_bp.route('/absence/<int:entry_id>/approve', methods=['POST'])
@login_required
def approve_absence(entry_id):
    """Approve an absence entry"""
    try:
        time_entry = TimeEntry.query.get_or_404(entry_id)
        
        # Check if already approved
        if time_entry.absence_approved_at:
            flash('This absence has already been approved.', 'warning')
            return redirect(url_for('pay_codes.manage_absences'))
        
        # Basic permission check - Super Users can approve all
        if not current_user.has_role('Super User'):
            flash('You do not have permission to approve this absence.', 'danger')
            return redirect(url_for('pay_codes.manage_absences'))
        
        time_entry.absence_approved_by_id = current_user.id
        time_entry.absence_approved_at = datetime.utcnow()
        
        # If this is a paid absence that deducts from balance, handle the deduction
        if time_entry.absence_pay_code_id:
            pay_code = PayCode.query.get(time_entry.absence_pay_code_id)
            if pay_code and pay_code.deducts_from_leave_balance():
                leave_type_id = pay_code.get_linked_leave_type_id()
                if leave_type_id:
                    # Deduct from leave balance
                    hours_to_deduct = time_entry.total_hours
                    year = time_entry.clock_in_time.year
                    
                    leave_balance = LeaveBalance.query.filter_by(
                        user_id=time_entry.user_id,
                        leave_type_id=leave_type_id,
                        year=year
                    ).first()
                    
                    if leave_balance:
                        leave_balance.deduct_usage(hours_to_deduct)
        
        db.session.commit()
        
        flash(f'Absence approved for {time_entry.employee.username}.', 'success')
        return redirect(url_for('pay_codes.manage_absences'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving absence: {str(e)}', 'danger')
        return redirect(url_for('pay_codes.manage_absences'))

@pay_codes_bp.route('/absence/log', methods=['GET', 'POST'])
@login_required
def log_absence():
    """Log absence for an employee"""
    if request.method == 'POST':
        try:
            employee_id = int(request.form.get('employee_id'))
            absence_date = datetime.strptime(request.form.get('absence_date'), '%Y-%m-%d').date()
            pay_code_id = int(request.form.get('pay_code_id'))
            absence_reason = request.form.get('absence_reason', '').strip()
            hours = float(request.form.get('hours', 8.0))
            
            # Validate pay code is an absence code
            pay_code = PayCode.query.get_or_404(pay_code_id)
            if not pay_code.is_absence_code:
                flash('Selected pay code is not an absence code.', 'danger')
                return render_template('pay_codes/log_absence.html')
            
            # Check if entry already exists for this date
            existing_entry = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == employee_id,
                    func.date(TimeEntry.clock_in_time) == absence_date
                )
            ).first()
            
            if existing_entry:
                flash(f'Time entry already exists for {absence_date}. Edit existing entry instead.', 'warning')
                return render_template('pay_codes/log_absence.html')
            
            # Create absence time entry
            start_time = datetime.combine(absence_date, datetime.min.time().replace(hour=9))
            end_time = start_time + timedelta(hours=hours)
            
            time_entry = TimeEntry(
                user_id=employee_id,
                clock_in_time=start_time,
                clock_out_time=end_time,
                status='Closed',
                notes=f'Absence logged by manager: {absence_reason}',
                absence_pay_code_id=pay_code_id,
                absence_reason=absence_reason,
                approved_by_manager_id=current_user.id
            )
            
            # Auto-approve if pay code doesn't require approval
            if not pay_code.requires_approval():
                time_entry.absence_approved_by_id = current_user.id
                time_entry.absence_approved_at = datetime.utcnow()
            
            db.session.add(time_entry)
            db.session.commit()
            
            flash(f'Absence logged successfully for {time_entry.employee.username}.', 'success')
            return redirect(url_for('pay_codes.manage_absences'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error logging absence: {str(e)}', 'danger')
    
    # Get data for form
    employees = User.query.filter_by(is_active=True).order_by(User.username).all()
    absence_codes = PayCode.query.filter_by(is_absence_code=True, is_active=True).order_by(PayCode.code).all()
    
    return render_template('pay_codes/log_absence.html',
                         employees=employees,
                         absence_codes=absence_codes)

@pay_codes_bp.route('/initialize-defaults', methods=['POST'])
@super_user_required
def initialize_default_codes():
    """Initialize system with default pay codes"""
    try:
        default_codes = PayCode.get_default_codes()
        created_count = 0
        
        for code_data in default_codes:
            # Check if code already exists
            if not PayCode.query.filter_by(code=code_data['code']).first():
                pay_code = PayCode(
                    code=code_data['code'],
                    description=code_data['description'],
                    is_absence_code=code_data['is_absence_code'],
                    created_by_id=current_user.id
                )
                
                pay_code.set_configuration(code_data['configuration'])
                db.session.add(pay_code)
                created_count += 1
        
        db.session.commit()
        
        if created_count > 0:
            flash(f'Successfully created {created_count} default pay codes.', 'success')
        else:
            flash('All default pay codes already exist.', 'info')
        
        return redirect(url_for('pay_codes.manage_pay_codes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error initializing default codes: {str(e)}', 'danger')
        return redirect(url_for('pay_codes.manage_pay_codes'))

# API Endpoints

@pay_codes_bp.route('/api/codes/<int:code_id>/toggle', methods=['POST'])
@super_user_required
def api_toggle_code(code_id):
    """Toggle pay code active status"""
    try:
        pay_code = PayCode.query.get_or_404(code_id)
        pay_code.is_active = not pay_code.is_active
        pay_code.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_active': pay_code.is_active,
            'message': f'Pay code "{pay_code.code}" {"activated" if pay_code.is_active else "deactivated"}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@pay_codes_bp.route('/api/codes/absence', methods=['GET'])
@login_required
def api_get_absence_codes():
    """Get active absence codes for dropdowns"""
    absence_codes = PayCode.query.filter_by(
        is_absence_code=True,
        is_active=True
    ).order_by(PayCode.code).all()
    
    return jsonify([{
        'id': code.id,
        'code': code.code,
        'description': code.description,
        'is_paid': code.is_paid_absence(),
        'requires_approval': code.requires_approval(),
        'max_hours_per_day': code.max_hours_per_day(),
        'max_consecutive_days': code.max_consecutive_days()
    } for code in absence_codes])

@pay_codes_bp.route('/api/validate-absence', methods=['POST'])
@login_required
def api_validate_absence():
    """Validate absence request against pay code rules"""
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        pay_code_id = data.get('pay_code_id')
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        hours = float(data.get('hours', 8.0))
        
        pay_code = PayCode.query.get(pay_code_id)
        if not pay_code or not pay_code.is_absence_code:
            return jsonify({'valid': False, 'errors': ['Invalid absence code']})
        
        errors = []
        
        # Check max hours per day
        max_hours = pay_code.max_hours_per_day()
        if max_hours and hours > max_hours:
            errors.append(f'Maximum {max_hours} hours allowed per day for {pay_code.code}')
        
        # Check if deducts from balance and validate balance
        if pay_code.deducts_from_leave_balance():
            leave_type_id = pay_code.get_linked_leave_type_id()
            if leave_type_id:
                year = start_date.year
                leave_balance = LeaveBalance.query.filter_by(
                    user_id=employee_id,
                    leave_type_id=leave_type_id,
                    year=year
                ).first()
                
                if not leave_balance or leave_balance.balance < hours:
                    available = leave_balance.balance if leave_balance else 0
                    errors.append(f'Insufficient leave balance. Available: {available} hours')
        
        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': []
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'errors': [str(e)]})

@pay_codes_bp.route('/api/employee/<int:employee_id>/absence-history', methods=['GET'])
@login_required
def api_get_employee_absence_history(employee_id):
    """Get employee's recent absence history"""
    try:
        # Get last 30 days of absences
        start_date = datetime.now() - timedelta(days=30)
        
        absences = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == employee_id,
                TimeEntry.absence_pay_code_id.isnot(None),
                TimeEntry.clock_in_time >= start_date
            )
        ).order_by(TimeEntry.clock_in_time.desc()).all()
        
        return jsonify([{
            'date': absence.work_date().isoformat(),
            'pay_code': absence.absence_pay_code.code if absence.absence_pay_code else None,
            'hours': absence.total_hours,
            'reason': absence.absence_reason,
            'approved': absence.absence_approved_at is not None,
            'approved_by': absence.absence_approved_by.username if absence.absence_approved_by else None
        } for absence in absences])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400