"""
Pay Code Administration Module for WFM System
Provides comprehensive pay code management and configuration
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from app import db
from models import User, Department, PayCode
from auth_simple import role_required, super_user_required
from datetime import datetime, date

# Create pay code admin blueprint
pay_code_admin_bp = Blueprint('pay_code_admin', __name__, url_prefix='/admin/pay-codes')

@pay_code_admin_bp.route('/')
@role_required('Admin', 'Super User')
def pay_code_dashboard():
    """Pay code configuration dashboard"""
    
    # Get all pay codes with usage statistics
    pay_codes = db.session.query(
        PayCode,
        func.count(User.id).label('usage_count')
    ).outerjoin(
        User, User.pay_code == PayCode.code
    ).group_by(PayCode.id).order_by(PayCode.code).all()
    
    # Get employees without pay codes
    unassigned_employees = User.query.filter(
        User.is_active == True,
        User.pay_code.is_(None)
    ).count()
    
    # Get pay code usage statistics
    total_pay_codes = PayCode.query.count()
    active_pay_codes = PayCode.query.filter_by(is_active=True).count()
    
    return render_template('admin/pay_code_dashboard.html',
                         pay_codes=pay_codes,
                         unassigned_employees=unassigned_employees,
                         total_pay_codes=total_pay_codes,
                         active_pay_codes=active_pay_codes)

@pay_code_admin_bp.route('/create', methods=['GET', 'POST'])
@role_required('Admin', 'Super User')
def create_pay_code():
    """Create a new pay code"""
    
    if request.method == 'POST':
        try:
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            hourly_rate = request.form.get('hourly_rate')
            is_overtime = request.form.get('is_overtime') == 'on'
            overtime_multiplier = request.form.get('overtime_multiplier')
            
            # Validation
            if not code or not name:
                flash('Code and name are required.', 'danger')
                return render_template('admin/create_pay_code.html')
            
            # Check if pay code already exists
            if PayCode.query.filter_by(code=code).first():
                flash(f'Pay code "{code}" already exists.', 'danger')
                return render_template('admin/create_pay_code.html')
            
            # Create new pay code
            pay_code = PayCode(
                code=code,
                name=name,
                description=description,
                hourly_rate=float(hourly_rate) if hourly_rate else None,
                is_overtime=is_overtime,
                overtime_multiplier=float(overtime_multiplier) if overtime_multiplier else 1.5,
                created_by_id=current_user.id
            )
            
            db.session.add(pay_code)
            db.session.commit()
            
            flash(f'Pay code "{code}" created successfully!', 'success')
            return redirect(url_for('pay_code_admin.pay_code_dashboard'))
            
        except ValueError as e:
            flash('Invalid numeric value provided.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating pay code: {str(e)}', 'danger')
    
    return render_template('admin/create_pay_code.html')

@pay_code_admin_bp.route('/<int:pay_code_id>/edit', methods=['GET', 'POST'])
@role_required('Admin', 'Super User')
def edit_pay_code(pay_code_id):
    """Edit an existing pay code"""
    
    pay_code = PayCode.query.get_or_404(pay_code_id)
    
    if request.method == 'POST':
        try:
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            hourly_rate = request.form.get('hourly_rate')
            is_overtime = request.form.get('is_overtime') == 'on'
            overtime_multiplier = request.form.get('overtime_multiplier')
            is_active = request.form.get('is_active') == 'on'
            
            # Validation
            if not code or not name:
                flash('Code and name are required.', 'danger')
                return render_template('admin/edit_pay_code.html', pay_code=pay_code)
            
            # Check if another pay code with this code exists
            existing = PayCode.query.filter(
                PayCode.code == code,
                PayCode.id != pay_code_id
            ).first()
            
            if existing:
                flash(f'Pay code "{code}" already exists.', 'danger')
                return render_template('admin/edit_pay_code.html', pay_code=pay_code)
            
            # Update pay code
            pay_code.code = code
            pay_code.name = name
            pay_code.description = description
            pay_code.hourly_rate = float(hourly_rate) if hourly_rate else None
            pay_code.is_overtime = is_overtime
            pay_code.overtime_multiplier = float(overtime_multiplier) if overtime_multiplier else 1.5
            pay_code.is_active = is_active
            pay_code.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Pay code "{code}" updated successfully!', 'success')
            return redirect(url_for('pay_code_admin.pay_code_dashboard'))
            
        except ValueError as e:
            flash('Invalid numeric value provided.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating pay code: {str(e)}', 'danger')
    
    return render_template('admin/edit_pay_code.html', pay_code=pay_code)

@pay_code_admin_bp.route('/<int:pay_code_id>/delete', methods=['POST'])
@role_required('Admin', 'Super User')
def delete_pay_code(pay_code_id):
    """Delete a pay code"""
    
    try:
        pay_code = PayCode.query.get_or_404(pay_code_id)
        
        # Check if pay code is in use
        usage_count = User.query.filter_by(pay_code=pay_code.code).count()
        if usage_count > 0:
            flash(f'Cannot delete pay code "{pay_code.code}" because it is assigned to {usage_count} employee(s).', 'danger')
        else:
            db.session.delete(pay_code)
            db.session.commit()
            flash(f'Pay code "{pay_code.code}" deleted successfully!', 'success')
        
        return redirect(url_for('pay_code_admin.pay_code_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting pay code: {str(e)}', 'danger')
        return redirect(url_for('pay_code_admin.pay_code_dashboard'))

@pay_code_admin_bp.route('/assign')
@role_required('Admin', 'Super User')
def assign_pay_codes():
    """Bulk assign pay codes to employees"""
    
    # Get all active employees
    employees = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    # Get all active pay codes
    pay_codes = PayCode.query.filter_by(is_active=True).order_by(PayCode.code).all()
    
    # Get departments for filtering
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template('admin/assign_pay_codes.html',
                         employees=employees,
                         pay_codes=pay_codes,
                         departments=departments)

@pay_code_admin_bp.route('/assign/individual', methods=['POST'])
@role_required('Admin', 'Super User')
def assign_individual_pay_code():
    """Assign pay code to individual employee"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        pay_code_id = data.get('pay_code_id')
        
        if not employee_id or not pay_code_id:
            return jsonify({
                'success': False,
                'message': 'Employee ID and Pay Code ID are required'
            }), 400
        
        # Get employee and pay code
        employee = User.query.get(employee_id)
        pay_code = PayCode.query.get(pay_code_id)
        
        if not employee or not pay_code:
            return jsonify({
                'success': False,
                'message': 'Employee or Pay Code not found'
            }), 404
        
        # Check if already assigned
        if pay_code in employee.pay_codes:
            return jsonify({
                'success': False,
                'message': 'Pay code already assigned to this employee'
            }), 400
        
        # Assign pay code
        employee.pay_codes.append(pay_code)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Pay code {pay_code.code} assigned to {employee.username}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error assigning pay code: {str(e)}'
        }), 500

@pay_code_admin_bp.route('/assign/remove', methods=['POST'])
@role_required('Admin', 'Super User')
def remove_pay_code_assignment():
    """Remove pay code assignment from employee"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        pay_code_id = data.get('pay_code_id')
        
        if not employee_id or not pay_code_id:
            return jsonify({
                'success': False,
                'message': 'Employee ID and Pay Code ID are required'
            }), 400
        
        # Get employee and pay code
        employee = User.query.get(employee_id)
        pay_code = PayCode.query.get(pay_code_id)
        
        if not employee or not pay_code:
            return jsonify({
                'success': False,
                'message': 'Employee or Pay Code not found'
            }), 404
        
        # Check if assigned
        if pay_code not in employee.pay_codes:
            return jsonify({
                'success': False,
                'message': 'Pay code not assigned to this employee'
            }), 400
        
        # Remove pay code
        employee.pay_codes.remove(pay_code)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Pay code {pay_code.code} removed from {employee.username}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error removing pay code: {str(e)}'
        }), 500

@pay_code_admin_bp.route('/assign/bulk', methods=['POST'])
@role_required('Admin', 'Super User')
def bulk_assign_pay_codes():
    """Process bulk pay code assignments"""
    
    try:
        assignments = request.json.get('assignments', [])
        
        updated_count = 0
        for assignment in assignments:
            employee_id = assignment.get('employee_id')
            pay_code = assignment.get('pay_code')
            
            employee = User.query.get(employee_id)
            if employee:
                employee.pay_code = pay_code if pay_code else None
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated pay codes for {updated_count} employees.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating pay codes: {str(e)}'
        }), 500

@pay_code_admin_bp.route('/reports')
@role_required('Admin', 'Super User')
def pay_code_reports():
    """Pay code usage reports and analytics"""
    
    # Get pay code usage statistics
    usage_stats = db.session.query(
        User.pay_code,
        func.count(User.id).label('employee_count'),
        func.avg(User.hourly_rate).label('avg_hourly_rate')
    ).filter(
        User.is_active == True,
        User.pay_code.isnot(None)
    ).group_by(User.pay_code).order_by(desc('employee_count')).all()
    
    # Get department breakdown
    dept_stats = db.session.query(
        Department.name,
        User.pay_code,
        func.count(User.id).label('count')
    ).join(
        User, User.department_id == Department.id
    ).filter(
        User.is_active == True,
        User.pay_code.isnot(None)
    ).group_by(Department.name, User.pay_code).order_by(Department.name, User.pay_code).all()
    
    # Get unassigned employees by department
    unassigned_by_dept = db.session.query(
        Department.name,
        func.count(User.id).label('unassigned_count')
    ).join(
        User, User.department_id == Department.id
    ).filter(
        User.is_active == True,
        User.pay_code.is_(None)
    ).group_by(Department.name).order_by(Department.name).all()
    
    return render_template('admin/pay_code_reports.html',
                         usage_stats=usage_stats,
                         dept_stats=dept_stats,
                         unassigned_by_dept=unassigned_by_dept)