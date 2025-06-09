from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from app import db
from models import LeaveApplication, LeaveType, LeaveBalance, User
from auth_simple import role_required, super_user_required

# Create leave management blueprint
leave_management_bp = Blueprint('leave_management', __name__, url_prefix='/leave')

# Employee Leave Management Routes

@leave_management_bp.route('/my-leave')
@login_required
def my_leave():
    """Employee's leave dashboard"""
    # Get current year leave balances
    current_year = datetime.now().year
    leave_balances = LeaveBalance.query.filter_by(
        user_id=current_user.id, 
        year=current_year
    ).all()
    
    # Get recent leave applications
    recent_applications = LeaveApplication.query.filter_by(
        user_id=current_user.id
    ).order_by(LeaveApplication.created_at.desc()).limit(5).all()
    
    # Get all leave types for balance display
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    # Create balance dictionary for easy lookup
    balance_dict = {lb.leave_type_id: lb for lb in leave_balances}
    
    return render_template('leave_management/my_leave.html',
                         leave_balances=leave_balances,
                         leave_types=leave_types,
                         recent_applications=recent_applications,
                         balance_dict=balance_dict,
                         datetime=datetime)

@leave_management_bp.route('/apply', methods=['GET', 'POST'])
@login_required
def apply_leave():
    """Apply for leave"""
    if request.method == 'POST':
        try:
            leave_type_id = request.form.get('leave_type_id', type=int)
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            reason = request.form.get('reason')
            is_hourly = request.form.get('is_hourly') == 'on'
            hours_requested = float(request.form.get('hours_requested', 0)) if is_hourly else None
            
            # Validation
            if not all([leave_type_id, start_date, end_date]):
                flash('Leave type, start date, and end date are required.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            if end_date < start_date:
                flash('End date must be after start date.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            if start_date <= date.today():
                flash('Leave applications must be for future dates.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            # Check for overlapping applications
            overlapping = LeaveApplication.query.filter(
                LeaveApplication.user_id == current_user.id,
                LeaveApplication.status.in_(['Pending', 'Approved']),
                or_(
                    and_(LeaveApplication.start_date <= start_date, LeaveApplication.end_date >= start_date),
                    and_(LeaveApplication.start_date <= end_date, LeaveApplication.end_date >= end_date),
                    and_(LeaveApplication.start_date >= start_date, LeaveApplication.end_date <= end_date)
                )
            ).first()
            
            if overlapping:
                flash('You already have a leave application for overlapping dates.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            # Check leave balance
            leave_type = LeaveType.query.get(leave_type_id)
            if not leave_type:
                flash('Invalid leave type selected.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            # Calculate hours needed
            if is_hourly and hours_requested:
                hours_needed = hours_requested
            else:
                days_requested = (end_date - start_date).days + 1
                hours_needed = days_requested * 8  # Assuming 8-hour workday
            
            # Check balance if leave type requires it
            current_year = datetime.now().year
            leave_balance = LeaveBalance.query.filter_by(
                user_id=current_user.id,
                leave_type_id=leave_type_id,
                year=current_year
            ).first()
            
            if leave_balance and leave_balance.balance < hours_needed:
                flash(f'Insufficient leave balance. You have {leave_balance.balance} hours available, but requested {hours_needed} hours.', 'danger')
                return redirect(url_for('leave_management.apply_leave'))
            
            # Create leave application
            application = LeaveApplication(
                user_id=current_user.id,
                leave_type_id=leave_type_id,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                is_hourly=is_hourly,
                hours_requested=hours_requested
            )
            
            db.session.add(application)
            db.session.commit()
            
            flash('Leave application submitted successfully!', 'success')
            return redirect(url_for('leave_management.my_applications'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting leave application: {str(e)}', 'danger')
    
    # Get active leave types
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    
    # Get current year leave balances
    current_year = datetime.now().year
    leave_balances = LeaveBalance.query.filter_by(
        user_id=current_user.id, 
        year=current_year
    ).all()
    
    balance_dict = {lb.leave_type_id: lb for lb in leave_balances}
    
    return render_template('leave_management/apply_leave.html',
                         leave_types=leave_types,
                         balance_dict=balance_dict,
                         datetime=datetime,
                         timedelta=timedelta)

@leave_management_bp.route('/my-applications')
@login_required
def my_applications():
    """View employee's leave application history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    status_filter = request.args.get('status')
    
    query = LeaveApplication.query.filter_by(user_id=current_user.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    applications = query.order_by(LeaveApplication.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('leave_management/my_applications.html',
                         applications=applications,
                         status_filter=status_filter)

@leave_management_bp.route('/applications/<int:application_id>/cancel', methods=['POST'])
@login_required
def cancel_application(application_id):
    """Cancel a leave application"""
    try:
        application = LeaveApplication.query.filter_by(
            id=application_id,
            user_id=current_user.id
        ).first_or_404()
        
        if not application.can_be_cancelled():
            flash('This application cannot be cancelled.', 'danger')
            return redirect(url_for('leave_management.my_applications'))
        
        application.status = 'Cancelled'
        db.session.commit()
        
        flash('Leave application cancelled successfully.', 'success')
        return redirect(url_for('leave_management.my_applications'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling application: {str(e)}', 'danger')
        return redirect(url_for('leave_management.my_applications'))

# Manager Leave Management Routes

@leave_management_bp.route('/team-applications')
@role_required('Manager', 'Admin', 'Super User')
def team_applications():
    """View team leave applications for approval"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    status_filter = request.args.get('status', 'Pending')
    user_filter = request.args.get('user_id', type=int)
    
    # Import get_managed_departments function
    from dashboard_management import get_managed_departments
    
    # Apply role-based filtering for department access
    is_super_user = current_user.has_role('Super User')
    is_manager = current_user.has_role('Manager')
    managed_dept_ids = get_managed_departments(current_user.id) if is_manager else []
    
    query = LeaveApplication.query
    
    # Apply department filtering based on user role
    if is_super_user:
        # Super Users see all applications
        pass
    elif is_manager and managed_dept_ids:
        # Managers see only applications from employees in departments they manage
        query = query.join(User, LeaveApplication.user_id == User.id).filter(
            User.department_id.in_(managed_dept_ids)
        )
    else:
        # Employees should not access this page, but if they do, show nothing
        query = query.filter(LeaveApplication.id == -1)  # No results
    
    # Filter by status
    if status_filter:
        query = query.filter(LeaveApplication.status == status_filter)
    
    # Filter by user
    if user_filter:
        query = query.filter(LeaveApplication.user_id == user_filter)
    
    applications = query.order_by(LeaveApplication.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get users for filter dropdown - also filtered by department access
    if is_super_user:
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
    elif is_manager and managed_dept_ids:
        users = User.query.filter(
            User.is_active == True,
            User.department_id.in_(managed_dept_ids)
        ).order_by(User.username).all()
    else:
        users = []
    
    return render_template('leave_management/team_applications.html',
                         applications=applications,
                         status_filter=status_filter,
                         user_filter=user_filter,
                         users=users)

@leave_management_bp.route('/applications/<int:application_id>/approve', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def approve_application(application_id):
    """Approve a leave application"""
    try:
        # Import get_managed_departments function
        from dashboard_management import get_managed_departments
        
        application = LeaveApplication.query.get_or_404(application_id)
        manager_comments = request.form.get('manager_comments', '')
        
        # Verify manager has access to this employee's application
        is_super_user = current_user.has_role('Super User')
        is_manager = current_user.has_role('Manager')
        
        if not is_super_user:
            if is_manager:
                managed_dept_ids = get_managed_departments(current_user.id)
                if not managed_dept_ids or application.user.department_id not in managed_dept_ids:
                    return jsonify({'success': False, 'message': 'Access denied: Cannot approve applications for employees outside your managed departments'})
            else:
                return jsonify({'success': False, 'message': 'Access denied: Insufficient permissions'})
        
        if application.status != 'Pending':
            return jsonify({'success': False, 'message': 'Application is not pending approval'})
        
        # Deduct from leave balance if approved
        current_year = datetime.now().year
        leave_balance = LeaveBalance.query.filter_by(
            user_id=application.user_id,
            leave_type_id=application.leave_type_id,
            year=current_year
        ).first()
        
        hours_to_deduct = application.total_hours()
        
        if leave_balance:
            if not leave_balance.deduct_usage(hours_to_deduct):
                return jsonify({'success': False, 'message': 'Insufficient leave balance'})
        
        application.status = 'Approved'
        application.manager_approved_id = current_user.id
        application.manager_comments = manager_comments
        application.approved_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Leave application approved successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error approving application: {str(e)}'})

@leave_management_bp.route('/applications/<int:application_id>/reject', methods=['POST'])
@role_required('Manager', 'Admin', 'Super User')
def reject_application(application_id):
    """Reject a leave application"""
    try:
        # Import get_managed_departments function
        from dashboard_management import get_managed_departments
        
        application = LeaveApplication.query.get_or_404(application_id)
        manager_comments = request.form.get('manager_comments', '')
        
        # Verify manager has access to this employee's application
        is_super_user = current_user.has_role('Super User')
        is_manager = current_user.has_role('Manager')
        
        if not is_super_user:
            if is_manager:
                managed_dept_ids = get_managed_departments(current_user.id)
                if not managed_dept_ids or application.user.department_id not in managed_dept_ids:
                    return jsonify({'success': False, 'message': 'Access denied: Cannot reject applications for employees outside your managed departments'})
            else:
                return jsonify({'success': False, 'message': 'Access denied: Insufficient permissions'})
        
        if application.status != 'Pending':
            return jsonify({'success': False, 'message': 'Application is not pending approval'})
        
        application.status = 'Rejected'
        application.manager_approved_id = current_user.id
        application.manager_comments = manager_comments
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Leave application rejected'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error rejecting application: {str(e)}'})

@leave_management_bp.route('/apply-for-employee', methods=['GET', 'POST'])
@role_required('Manager', 'Admin', 'Super User')
def apply_for_employee():
    """Manager applies leave on behalf of employee"""
    # Import get_managed_departments function
    from dashboard_management import get_managed_departments
    
    # Apply role-based filtering for department access
    is_super_user = current_user.has_role('Super User')
    is_manager = current_user.has_role('Manager')
    managed_dept_ids = get_managed_departments(current_user.id) if is_manager else []
    
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            leave_type_id = request.form.get('leave_type_id', type=int)
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            reason = request.form.get('reason')
            is_hourly = request.form.get('is_hourly') == 'on'
            hours_requested = float(request.form.get('hours_requested', 0)) if is_hourly else None
            auto_approve = request.form.get('auto_approve') == 'on'
            
            # Verify manager has access to this employee
            if not is_super_user:
                if is_manager:
                    selected_user = User.query.get(user_id)
                    if not selected_user or not managed_dept_ids or selected_user.department_id not in managed_dept_ids:
                        flash('Access denied: Cannot apply for employees outside your managed departments', 'danger')
                        return redirect(url_for('leave_management.apply_for_employee'))
                else:
                    flash('Access denied: Insufficient permissions', 'danger')
                    return redirect(url_for('leave_management.apply_for_employee'))
            
            # Create leave application
            application = LeaveApplication(
                user_id=user_id,
                leave_type_id=leave_type_id,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                is_hourly=is_hourly,
                hours_requested=hours_requested,
                status='Approved' if auto_approve else 'Pending',
                manager_approved_id=current_user.id if auto_approve else None,
                approved_at=datetime.utcnow() if auto_approve else None
            )
            
            db.session.add(application)
            
            # Deduct from balance if auto-approved
            if auto_approve:
                current_year = datetime.now().year
                leave_balance = LeaveBalance.query.filter_by(
                    user_id=user_id,
                    leave_type_id=leave_type_id,
                    year=current_year
                ).first()
                
                if leave_balance:
                    leave_balance.deduct_usage(application.total_hours())
            
            db.session.commit()
            
            status_msg = 'approved' if auto_approve else 'submitted for approval'
            flash(f'Leave application {status_msg} successfully!', 'success')
            return redirect(url_for('leave_management.team_applications'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating leave application: {str(e)}', 'danger')
    
    # Get data for form - filtered by department access
    if is_super_user:
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
    elif is_manager and managed_dept_ids:
        users = User.query.filter(
            User.is_active == True,
            User.department_id.in_(managed_dept_ids)
        ).order_by(User.username).all()
    else:
        users = []
    
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    
    return render_template('leave_management/apply_for_employee.html',
                         users=users,
                         leave_types=leave_types)

# Admin Leave Management Routes

@leave_management_bp.route('/admin/leave-types')
@role_required('Admin', 'Super User')
def manage_leave_types():
    """Manage leave types"""
    leave_types = LeaveType.query.order_by(LeaveType.name).all()
    return render_template('leave_management/manage_leave_types.html',
                         leave_types=leave_types)

@leave_management_bp.route('/admin/leave-types/create', methods=['GET', 'POST'])
@role_required('Admin', 'Super User')
def create_leave_type():
    """Create a new leave type"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            default_accrual_rate = float(request.form.get('default_accrual_rate', 0)) or None
            requires_approval = request.form.get('requires_approval') == 'on'
            max_consecutive_days = int(request.form.get('max_consecutive_days', 0)) or None
            
            if not name:
                flash('Leave type name is required.', 'danger')
                return render_template('leave_management/create_leave_type.html')
            
            # Check if leave type already exists
            if LeaveType.query.filter_by(name=name).first():
                flash('A leave type with this name already exists.', 'danger')
                return render_template('leave_management/create_leave_type.html')
            
            leave_type = LeaveType(
                name=name,
                description=description,
                default_accrual_rate=default_accrual_rate,
                requires_approval=requires_approval,
                max_consecutive_days=max_consecutive_days
            )
            
            db.session.add(leave_type)
            db.session.commit()
            
            flash(f'Leave type "{name}" created successfully!', 'success')
            return redirect(url_for('leave_management.manage_leave_types'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating leave type: {str(e)}', 'danger')
    
    return render_template('leave_management/create_leave_type.html')

@leave_management_bp.route('/admin/leave-types/<int:leave_type_id>')
@role_required('Admin', 'Super User')
def view_leave_type(leave_type_id):
    """View leave type details"""
    leave_type = LeaveType.query.get_or_404(leave_type_id)
    
    # Get usage statistics
    total_applications = LeaveApplication.query.filter_by(leave_type_id=leave_type_id).count()
    pending_applications = LeaveApplication.query.filter_by(
        leave_type_id=leave_type_id, 
        status='Pending'
    ).count()
    approved_applications = LeaveApplication.query.filter_by(
        leave_type_id=leave_type_id, 
        status='Approved'
    ).count()
    
    # Get recent applications for this leave type
    recent_applications = LeaveApplication.query.filter_by(
        leave_type_id=leave_type_id
    ).order_by(LeaveApplication.created_at.desc()).limit(10).all()
    
    return render_template('leave_management/view_leave_type.html',
                         leave_type=leave_type,
                         total_applications=total_applications,
                         pending_applications=pending_applications,
                         approved_applications=approved_applications,
                         recent_applications=recent_applications)

@leave_management_bp.route('/admin/leave-types/<int:leave_type_id>/edit', methods=['GET', 'POST'])
@role_required('Admin', 'Super User')
def edit_leave_type(leave_type_id):
    """Edit leave type"""
    leave_type = LeaveType.query.get_or_404(leave_type_id)
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            default_accrual_rate = float(request.form.get('default_accrual_rate', 0)) or None
            requires_approval = request.form.get('requires_approval') == 'on'
            max_consecutive_days = int(request.form.get('max_consecutive_days', 0)) or None
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Leave type name is required.', 'danger')
                return render_template('leave_management/edit_leave_type.html', leave_type=leave_type)
            
            # Check if name conflicts with another leave type
            existing_type = LeaveType.query.filter(
                LeaveType.name == name,
                LeaveType.id != leave_type_id
            ).first()
            
            if existing_type:
                flash('A leave type with this name already exists.', 'danger')
                return render_template('leave_management/edit_leave_type.html', leave_type=leave_type)
            
            # Update leave type
            leave_type.name = name
            leave_type.description = description
            leave_type.default_accrual_rate = default_accrual_rate
            leave_type.requires_approval = requires_approval
            leave_type.max_consecutive_days = max_consecutive_days
            leave_type.is_active = is_active
            leave_type.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Leave type "{name}" updated successfully!', 'success')
            return redirect(url_for('leave_management.view_leave_type', leave_type_id=leave_type_id))
            
        except ValueError as e:
            flash('Invalid numeric values provided.', 'danger')
            return render_template('leave_management/edit_leave_type.html', leave_type=leave_type)
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating leave type: {str(e)}', 'danger')
            return render_template('leave_management/edit_leave_type.html', leave_type=leave_type)
    
    return render_template('leave_management/edit_leave_type.html', leave_type=leave_type)

@leave_management_bp.route('/admin/leave-types/<int:leave_type_id>/toggle-status', methods=['POST'])
@role_required('Admin', 'Super User')
def toggle_leave_type_status(leave_type_id):
    """Toggle leave type active/inactive status"""
    try:
        leave_type = LeaveType.query.get_or_404(leave_type_id)
        
        # Check if there are pending applications before deactivating
        if leave_type.is_active:
            pending_count = LeaveApplication.query.filter_by(
                leave_type_id=leave_type_id,
                status='Pending'
            ).count()
            
            if pending_count > 0:
                flash(f'Cannot deactivate leave type with {pending_count} pending applications. Please process them first.', 'warning')
                return redirect(url_for('leave_management.view_leave_type', leave_type_id=leave_type_id))
        
        leave_type.is_active = not leave_type.is_active
        leave_type.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status = 'activated' if leave_type.is_active else 'deactivated'
        flash(f'Leave type "{leave_type.name}" {status} successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating leave type status: {str(e)}', 'danger')
    
    return redirect(url_for('leave_management.view_leave_type', leave_type_id=leave_type_id))

@leave_management_bp.route('/admin/leave-balances')
@role_required('Admin', 'Super User')
def manage_leave_balances():
    """Manage employee leave balances"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    user_filter = request.args.get('user_id', type=int)
    leave_type_filter = request.args.get('leave_type_id', type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    query = LeaveBalance.query.filter_by(year=year)
    
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    
    if leave_type_filter:
        query = query.filter_by(leave_type_id=leave_type_filter)
    
    balances = query.join(User).order_by(User.username).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get data for filters
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    
    return render_template('leave_management/manage_leave_balances.html',
                         balances=balances,
                         users=users,
                         leave_types=leave_types,
                         user_filter=user_filter,
                         leave_type_filter=leave_type_filter,
                         year=year,
                         datetime=datetime)

@leave_management_bp.route('/admin/leave-balances/<int:balance_id>/adjust', methods=['POST'])
@role_required('Admin', 'Super User')
def adjust_leave_balance(balance_id):
    """Adjust an employee's leave balance"""
    try:
        balance = LeaveBalance.query.get_or_404(balance_id)
        new_balance = float(request.form.get('new_balance'))
        reason = request.form.get('reason', 'Manual adjustment by admin')
        
        balance.adjust_balance(new_balance, reason)
        db.session.commit()
        
        flash(f'Leave balance adjusted successfully for {balance.employee.username}.', 'success')
        return redirect(url_for('leave_management.manage_leave_balances'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adjusting leave balance: {str(e)}', 'danger')
        return redirect(url_for('leave_management.manage_leave_balances'))

@leave_management_bp.route('/admin/accrual-run', methods=['POST'])
@role_required('Super User')
def run_accrual():
    """Run monthly leave accrual (stub implementation)"""
    try:
        # This is a placeholder for the accrual logic
        # In a real system, this would calculate and add accrued leave
        # based on employee start dates, leave policies, etc.
        
        accrual_date = datetime.now().date()
        current_year = datetime.now().year
        users_processed = 0
        
        # Get all active users
        users = User.query.filter_by(is_active=True).all()
        
        for user in users:
            # Get all leave types with accrual rates
            leave_types = LeaveType.query.filter(
                LeaveType.is_active == True,
                LeaveType.default_accrual_rate.isnot(None)
            ).all()
            
            for leave_type in leave_types:
                # Get or create leave balance for this year
                balance = LeaveBalance.query.filter_by(
                    user_id=user.id,
                    leave_type_id=leave_type.id,
                    year=current_year
                ).first()
                
                if not balance:
                    balance = LeaveBalance(
                        user_id=user.id,
                        leave_type_id=leave_type.id,
                        year=current_year
                    )
                    db.session.add(balance)
                
                # Check if accrual is due (monthly accrual)
                if (not balance.last_accrual_date or 
                    balance.last_accrual_date.month != accrual_date.month):
                    
                    # Add monthly accrual (assuming monthly rate)
                    monthly_accrual = leave_type.default_accrual_rate / 12
                    balance.add_accrual(monthly_accrual)
                    users_processed += 1
        
        db.session.commit()
        
        flash(f'Leave accrual completed successfully. Processed {users_processed} user records.', 'success')
        return redirect(url_for('leave_management.manage_leave_balances'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error running leave accrual: {str(e)}', 'danger')
        return redirect(url_for('leave_management.manage_leave_balances'))

# API Endpoints

@leave_management_bp.route('/api/leave-balance/<int:user_id>/<int:leave_type_id>')
@login_required
def api_leave_balance(user_id, leave_type_id):
    """API endpoint to get leave balance"""
    # Only allow users to see their own balance, or managers/admins to see others
    if (user_id != current_user.id and 
        not any(current_user.has_role(role) for role in ['Manager', 'Admin', 'Super User'])):
        return jsonify({'error': 'Unauthorized'}), 403
    
    current_year = datetime.now().year
    balance = LeaveBalance.query.filter_by(
        user_id=user_id,
        leave_type_id=leave_type_id,
        year=current_year
    ).first()
    
    if balance:
        return jsonify({
            'balance': balance.balance,
            'accrued_this_year': balance.accrued_this_year,
            'used_this_year': balance.used_this_year
        })
    else:
        return jsonify({
            'balance': 0,
            'accrued_this_year': 0,
            'used_this_year': 0
        })

@leave_management_bp.route('/api/check-overlap', methods=['POST'])
@login_required
def api_check_overlap():
    """API endpoint to check for leave application overlaps"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', current_user.id)
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
        exclude_id = data.get('exclude_id')  # For editing existing applications
        
        query = LeaveApplication.query.filter(
            LeaveApplication.user_id == user_id,
            LeaveApplication.status.in_(['Pending', 'Approved']),
            or_(
                and_(LeaveApplication.start_date <= start_date, LeaveApplication.end_date >= start_date),
                and_(LeaveApplication.start_date <= end_date, LeaveApplication.end_date >= end_date),
                and_(LeaveApplication.start_date >= start_date, LeaveApplication.end_date <= end_date)
            )
        )
        
        if exclude_id:
            query = query.filter(LeaveApplication.id != exclude_id)
        
        overlapping = query.all()
        
        return jsonify({
            'has_overlap': len(overlapping) > 0,
            'overlapping_applications': [{
                'id': app.id,
                'start_date': app.start_date.isoformat(),
                'end_date': app.end_date.isoformat(),
                'leave_type': app.leave_type.name,
                'status': app.status
            } for app in overlapping]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400