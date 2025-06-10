"""
Payroll Processing and Reporting Blueprint
Handles payroll preparation, processing, and advanced reporting functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, current_app
from flask_login import login_required, current_user
from app import db
from models import User, TimeEntry, PayCode, PayRule, LeaveApplication, Schedule
from auth import role_required, super_user_required
# Import will be handled when PayrollEngine is available
# from pay_rule_engine_service import PayrollEngine
from datetime import datetime, timedelta
from sqlalchemy import and_, func, or_
import logging
import csv
import io
import json

# Create blueprint for payroll routes
payroll_bp = Blueprint('payroll', __name__, url_prefix='/payroll')

@payroll_bp.route('/processing')
@login_required
@role_required('Super User')
def payroll_processing():
    """Payroll Processing Screen for Super Users"""
    try:
        # Get processing parameters from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        employee_filter = request.args.get('employee_filter')
        
        # Default to current pay period if no dates provided
        if not start_date or not end_date:
            today = datetime.now().date()
            # Assume bi-weekly pay periods starting from first of month
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get all employees for the dropdown (users who are not Super Users)
        all_employees = User.query.order_by(User.username).all()
        # Filter out Super Users and inactive users from dropdown
        all_employees = [emp for emp in all_employees if emp.is_active and not emp.has_role('Super User')]
        
        # Build query for employees with time entries in the period
        employees_query = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        )
        
        # Apply employee filter if specified
        if employee_filter:
            employees_query = employees_query.filter(User.id == employee_filter)
        
        employees_with_entries = employees_query.distinct().all()
        
        # Process payroll data for each employee
        payroll_data = []
        for employee in employees_with_entries:
            try:
                # Calculate pay using simplified logic (payroll engine integration can be added later)
                pay_calculation = None
                
                # Get employee time entries for detailed breakdown
                time_entries = TimeEntry.query.filter(
                    and_(
                        TimeEntry.user_id == employee.id,
                        TimeEntry.clock_in_time >= start_date,
                        TimeEntry.clock_in_time <= end_date + timedelta(days=1)
                    )
                ).all()
                
                # Breakdown by pay codes
                pay_code_breakdown = {}
                for entry in time_entries:
                    if entry.pay_code_id:
                        pay_code = PayCode.query.get(entry.pay_code_id)
                        code_name = pay_code.code if pay_code else 'REGULAR'
                    else:
                        code_name = 'REGULAR'
                    
                    # Calculate hours for this entry
                    if entry.clock_in_time and entry.clock_out_time:
                        hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                    else:
                        hours = 8.0  # Default 8 hours if times not set
                    
                    if code_name not in pay_code_breakdown:
                        # Get actual pay code rate from database
                        pay_code = PayCode.query.filter_by(code=code_name, is_active=True).first()
                        base_rate = 150.0  # Base rate in ZAR
                        
                        # Calculate rate based on pay code factor
                        if pay_code and pay_code.configuration:
                            try:
                                import json
                                config = json.loads(pay_code.configuration)
                                pay_rate_factor = config.get('pay_rate_factor', 1.0)
                                actual_rate = base_rate * pay_rate_factor
                            except:
                                actual_rate = base_rate
                        else:
                            actual_rate = base_rate
                        
                        pay_code_breakdown[code_name] = {
                            'hours': 0,
                            'rate': actual_rate,
                            'amount': 0
                        }
                    
                    pay_code_breakdown[code_name]['hours'] += hours
                    pay_code_breakdown[code_name]['amount'] = pay_code_breakdown[code_name]['hours'] * pay_code_breakdown[code_name]['rate']
                
                # Calculate gross pay from pay code breakdown amounts
                calculated_gross_pay = sum([breakdown['amount'] for breakdown in pay_code_breakdown.values()])
                
                # Calculate overtime breakdown for reporting (based on total hours)
                total_hours = sum([breakdown['hours'] for breakdown in pay_code_breakdown.values()])
                
                # If all hours are REGULAR pay code, apply automatic overtime calculation
                if len(pay_code_breakdown) == 1 and 'REGULAR' in pay_code_breakdown:
                    regular_hours = min(total_hours, 40)
                    ot_15_hours = max(0, min(total_hours - 40, 8))  # First 8 hours over 40
                    ot_20_hours = max(0, total_hours - 48)  # Hours over 48
                    
                    base_rate = 150.0  # Base hourly rate in ZAR
                    overtime_15_rate = base_rate * 1.5  # Time and a half
                    overtime_20_rate = base_rate * 2.0  # Double time
                    
                    # Recalculate with proper overtime rates
                    regular_pay = regular_hours * base_rate
                    ot_15_pay = ot_15_hours * overtime_15_rate
                    ot_20_pay = ot_20_hours * overtime_20_rate
                    calculated_gross_pay = regular_pay + ot_15_pay + ot_20_pay
                else:
                    # Use individual pay code calculations
                    regular_hours = pay_code_breakdown.get('REGULAR', {}).get('hours', 0)
                    ot_15_hours = pay_code_breakdown.get('OVERTIME', {}).get('hours', 0)
                    ot_20_hours = pay_code_breakdown.get('DT', {}).get('hours', 0)
                    # Keep the calculated gross pay from individual pay codes
                    calculated_gross_pay = sum([breakdown['amount'] for breakdown in pay_code_breakdown.values()])
                
                employee_payroll = {
                    'employee_id': employee.id,
                    'employee_name': f"{employee.first_name} {employee.last_name}" if employee.first_name else employee.username,
                    'username': employee.username,
                    'email': employee.email,
                    'regular_hours': regular_hours,
                    'ot_15_hours': ot_15_hours,
                    'ot_20_hours': ot_20_hours,
                    'total_hours': total_hours,
                    'pay_code_breakdown': pay_code_breakdown,
                    'gross_pay': pay_calculation.get('gross_pay', calculated_gross_pay) if pay_calculation else calculated_gross_pay,
                    'net_pay': pay_calculation.get('net_pay', calculated_gross_pay * (1 - current_app.config['PAYROLL_DEDUCTION_RATE'])) if pay_calculation else calculated_gross_pay * (1 - current_app.config['PAYROLL_DEDUCTION_RATE']),
                    'deductions': pay_calculation.get('deductions', calculated_gross_pay * current_app.config['PAYROLL_DEDUCTION_RATE']) if pay_calculation else calculated_gross_pay * current_app.config['PAYROLL_DEDUCTION_RATE']
                }
                
                payroll_data.append(employee_payroll)
                
            except Exception as e:
                logging.error(f"Error processing payroll for employee {employee.id}: {e}")
                continue
        
        # Get available pay codes for filtering
        available_pay_codes = PayCode.query.filter_by(is_active=True).all()
        
        return render_template('payroll/processing.html',
                             payroll_data=payroll_data,
                             start_date=start_date,
                             end_date=end_date,
                             employees=all_employees,
                             selected_employee_id=employee_filter,
                             available_pay_codes=available_pay_codes)
        
    except Exception as e:
        logging.error(f"Error in payroll processing: {e}")
        flash("An error occurred while processing payroll data.", "error")
        return redirect(url_for('main.index'))

@payroll_bp.route('/export-payroll')
@login_required
@role_required('Super User')
def export_payroll():
    """Export processed payroll data to CSV"""
    try:
        # Get parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        employee_filter = request.args.get('employee_filter')
        include_codes = request.args.getlist('include_codes')
        exclude_codes = request.args.getlist('exclude_codes')
        
        if not start_date or not end_date:
            flash("Start and end dates are required for export.", "error")
            return redirect(url_for('payroll.payroll_processing'))
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Build query for employees with time entries in the period
        employees_query = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        )
        
        # Apply employee filter if specified
        if employee_filter:
            employees_query = employees_query.filter(User.id == employee_filter)
        
        employees_with_entries = employees_query.distinct().all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        header = [
            'Employee ID', 'Employee Name', 'Username', 'Email',
            'Regular Hours', 'OT 1.5x Hours', 'OT 2.0x Hours', 'Total Hours',
            'Regular Pay', 'OT 1.5x Pay', 'OT 2.0x Pay', 'Gross Pay', 'Deductions', 'Net Pay'
        ]
        
        # Add pay code columns if specified
        if include_codes:
            for code in include_codes:
                header.extend([f'{code} Hours', f'{code} Amount'])
        
        writer.writerow(header)
        
        # Process each employee
        for employee in employees_with_entries:
            time_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == employee.id,
                    TimeEntry.clock_in_time >= start_date,
                    TimeEntry.clock_in_time <= end_date + timedelta(days=1)
                )
            ).all()
            
            # Calculate totals
            total_hours = 0
            pay_code_data = {}
            
            for entry in time_entries:
                if entry.clock_in_time and entry.clock_out_time:
                    hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                else:
                    hours = 8.0
                
                total_hours += hours
                
                # Track by pay code
                if entry.pay_code_id:
                    pay_code = PayCode.query.get(entry.pay_code_id)
                    code_name = pay_code.code if pay_code else 'REGULAR'
                else:
                    code_name = 'REGULAR'
                
                if code_name not in pay_code_data:
                    # Get actual pay code rate from database
                    pay_code = PayCode.query.filter_by(code=code_name, is_active=True).first()
                    base_rate = 150.0  # Base rate in ZAR
                    
                    # Calculate rate based on pay code factor
                    if pay_code and pay_code.configuration:
                        try:
                            import json
                            config = json.loads(pay_code.configuration)
                            pay_rate_factor = config.get('pay_rate_factor', 1.0)
                            actual_rate = base_rate * pay_rate_factor
                        except:
                            actual_rate = base_rate
                    else:
                        actual_rate = base_rate
                    
                    pay_code_data[code_name] = {'hours': 0, 'amount': 0, 'rate': actual_rate}
                
                pay_code_data[code_name]['hours'] += hours
                pay_code_data[code_name]['amount'] += hours * pay_code_data[code_name]['rate']
            
            # Calculate breakdown for display
            regular_hours = pay_code_data.get('REGULAR', {}).get('hours', 0)
            ot_15_hours = pay_code_data.get('OVERTIME', {}).get('hours', 0)
            ot_20_hours = pay_code_data.get('DT', {}).get('hours', 0)
            
            # If all hours are REGULAR, apply automatic overtime calculation
            if len(pay_code_data) == 1 and 'REGULAR' in pay_code_data:
                regular_hours = min(total_hours, 40)
                ot_15_hours = max(0, min(total_hours - 40, 8))
                ot_20_hours = max(0, total_hours - 48)
                
                base_rate = 150.0
                regular_pay = regular_hours * base_rate
                ot_15_pay = ot_15_hours * (base_rate * 1.5)
                ot_20_pay = ot_20_hours * (base_rate * 2.0)
                gross_pay = regular_pay + ot_15_pay + ot_20_pay
            else:
                # Use pay code calculations
                regular_pay = pay_code_data.get('REGULAR', {}).get('amount', 0)
                ot_15_pay = pay_code_data.get('OVERTIME', {}).get('amount', 0)
                ot_20_pay = pay_code_data.get('DT', {}).get('amount', 0)
                gross_pay = sum([data['amount'] for data in pay_code_data.values()])
            
            deductions = gross_pay * current_app.config['PAYROLL_DEDUCTION_RATE']
            net_pay = gross_pay - deductions
            
            # Build row data
            row = [
                employee.id,
                f"{employee.first_name} {employee.last_name}" if employee.first_name else employee.username,
                employee.username,
                employee.email,
                round(regular_hours, 2),
                round(ot_15_hours, 2),
                round(ot_20_hours, 2),
                round(total_hours, 2),
                f"${regular_pay:.2f}",
                f"${ot_15_pay:.2f}",
                f"${ot_20_pay:.2f}",
                f"${gross_pay:.2f}",
                f"${deductions:.2f}",
                f"${net_pay:.2f}"
            ]
            
            # Add pay code data if requested
            if include_codes:
                for code in include_codes:
                    if code in pay_code_data:
                        row.extend([
                            round(pay_code_data[code]['hours'], 2),
                            f"R{pay_code_data[code]['amount']:.2f}"
                        ])
                    else:
                        row.extend([0, "R0.00"])
            
            writer.writerow(row)
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=payroll_export_{start_date}_{end_date}.csv'
        
        return response
        
    except Exception as e:
        logging.error(f"Error exporting payroll: {e}")
        flash("Error generating payroll export.", "error")
        return redirect(url_for('payroll.payroll_processing'))

@payroll_bp.route('/reports/time-summary')
@login_required
@super_user_required
def time_summary_report():
    """Time worked summary report"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get time summary data
        time_summary = db.session.query(
            User.username,
            User.email,
            func.count(TimeEntry.id).label('total_entries'),
            func.sum(
                func.extract('epoch', TimeEntry.clock_out_time - TimeEntry.clock_in_time) / 3600
            ).label('total_hours')
        ).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                TimeEntry.clock_out_time.isnot(None)
            )
        ).group_by(User.id, User.username, User.email).all()
        
        return render_template('payroll/time_summary.html',
                             time_summary=time_summary,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        logging.error(f"Error in time summary report: {e}")
        flash("Error generating time summary report.", "error")
        return redirect(url_for('main.index'))

@payroll_bp.route('/reports/leave-summary')
@login_required
@role_required(['Super User', 'Manager'])
def leave_summary_report():
    """Leave usage summary report"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get leave summary data
        leave_summary = db.session.query(
            User.username,
            User.email,
            func.count(LeaveApplication.id).label('total_applications'),
            func.sum(
                func.extract('day', LeaveApplication.end_date - LeaveApplication.start_date) + 1
            ).label('total_days_requested'),
            func.sum(
                func.case(
                    (LeaveApplication.status == 'approved', 
                     func.extract('day', LeaveApplication.end_date - LeaveApplication.start_date) + 1),
                    else_=0
                )
            ).label('approved_days')
        ).join(
            LeaveApplication, User.id == LeaveApplication.user_id
        ).filter(
            and_(
                LeaveApplication.start_date >= start_date,
                LeaveApplication.start_date <= end_date
            )
        ).group_by(User.id, User.username, User.email).all()
        
        return render_template('payroll/leave_summary.html',
                             leave_summary=leave_summary,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        logging.error(f"Error in leave summary report: {e}")
        flash("Error generating leave summary report.", "error")
        return redirect(url_for('main.index'))

@payroll_bp.route('/reports/overtime-summary')
@login_required
@super_user_required
def overtime_summary_report():
    """Overtime summary report"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Calculate overtime for each employee
        employees = User.query.filter_by(is_active=True).all()
        overtime_data = []
        
        for employee in employees:
            # Get time entries for the period
            time_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == employee.id,
                    TimeEntry.clock_in_time >= start_date,
                    TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                    TimeEntry.clock_out_time.isnot(None)
                )
            ).all()
            
            if not time_entries:
                continue
            
            # Calculate total hours
            total_hours = 0
            for entry in time_entries:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
            
            # Calculate overtime
            regular_hours = min(total_hours, 40)
            ot_15_hours = max(0, min(total_hours - 40, 8))
            ot_20_hours = max(0, total_hours - 48)
            total_ot_hours = ot_15_hours + ot_20_hours
            
            if total_ot_hours > 0:  # Only include employees with overtime
                overtime_data.append({
                    'username': employee.username,
                    'email': employee.email,
                    'regular_hours': round(regular_hours, 2),
                    'ot_15_hours': round(ot_15_hours, 2),
                    'ot_20_hours': round(ot_20_hours, 2),
                    'total_ot_hours': round(total_ot_hours, 2),
                    'total_hours': round(total_hours, 2)
                })
        
        return render_template('payroll/overtime_summary.html',
                             overtime_data=overtime_data,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        logging.error(f"Error in overtime summary report: {e}")
        flash("Error generating overtime summary report.", "error")
        return redirect(url_for('main.index'))

@payroll_bp.route('/reports/custom-builder')
@login_required
@role_required('Super User')
def custom_report_builder():
    """Placeholder for custom report builder (Future implementation)"""
    try:
        # Available data sources for custom reports
        data_sources = {
            'time_entries': {
                'name': 'Time Entries',
                'fields': ['employee', 'date', 'clock_in', 'clock_out', 'hours', 'pay_code']
            },
            'leave_applications': {
                'name': 'Leave Applications',
                'fields': ['employee', 'leave_type', 'start_date', 'end_date', 'status', 'days']
            },
            'payroll_calculations': {
                'name': 'Payroll Calculations',
                'fields': ['employee', 'period', 'regular_hours', 'overtime', 'gross_pay', 'net_pay']
            },
            'schedules': {
                'name': 'Schedules',
                'fields': ['employee', 'date', 'shift_type', 'start_time', 'end_time']
            }
        }
        
        # Available report formats
        report_formats = ['CSV', 'Excel', 'PDF', 'JSON']
        
        return render_template('payroll/custom_builder.html',
                             data_sources=data_sources,
                             report_formats=report_formats)
        
    except Exception as e:
        logging.error(f"Error in custom report builder: {e}")
        flash("Error loading custom report builder.", "error")
        return redirect(url_for('main.index'))

@payroll_bp.route('/api/pay-codes')
@login_required
@role_required(['Super User', 'Manager'])
def api_pay_codes():
    """API endpoint to get available pay codes"""
    try:
        pay_codes = PayCode.query.filter_by(is_active=True).all()
        return jsonify([{
            'id': pc.id,
            'code': pc.code,
            'description': pc.description,
            'type': pc.type
        } for pc in pay_codes])
    except Exception as e:
        logging.error(f"Error getting pay codes: {e}")
        return jsonify({'error': 'Failed to retrieve pay codes'}), 500

@payroll_bp.route('/api/payroll-data')
@login_required
@role_required(['Super User', 'Manager'])
def api_payroll_data():
    """API endpoint to get payroll data for a specific period"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Start and end dates are required'}), 400
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get basic payroll summary
        summary = {
            'total_employees': 0,
            'total_hours': 0,
            'total_overtime': 0,
            'total_gross_pay': 0
        }
        
        employees = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).distinct().all()
        
        summary['total_employees'] = len(employees)
        
        for employee in employees:
            time_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == employee.id,
                    TimeEntry.clock_in_time >= start_date,
                    TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                    TimeEntry.clock_out_time.isnot(None)
                )
            ).all()
            
            employee_hours = 0
            for entry in time_entries:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                employee_hours += hours
            
            summary['total_hours'] += employee_hours
            summary['total_overtime'] += max(0, employee_hours - 40)
            summary['total_gross_pay'] += employee_hours * 15.0  # Base calculation
        
        return jsonify(summary)
        
    except Exception as e:
        logging.error(f"Error getting payroll data: {e}")
        return jsonify({'error': 'Failed to retrieve payroll data'}), 500

@payroll_bp.route('/configuration')
@login_required
@role_required('Super User')
def payroll_configuration():
    """Payroll configuration interface for Super Users"""
    current_config = {
        'base_rate': current_app.config.get('PAYROLL_BASE_RATE', 150.0),
        'overtime_multiplier': current_app.config.get('PAYROLL_OVERTIME_MULTIPLIER', 1.5),
        'double_time_multiplier': current_app.config.get('PAYROLL_DOUBLE_TIME_MULTIPLIER', 2.0),
        'deduction_rate': current_app.config.get('PAYROLL_DEDUCTION_RATE', 0.25)
    }
    
    return render_template('payroll/configuration.html', config=current_config)

@payroll_bp.route('/configuration/save', methods=['POST'])
@login_required
@role_required('Super User')
def save_payroll_configuration():
    """Save payroll configuration settings"""
    try:
        # Get form data
        base_rate = float(request.form.get('base_rate', 150.0))
        overtime_multiplier = float(request.form.get('overtime_multiplier', 1.5))
        double_time_multiplier = float(request.form.get('double_time_multiplier', 2.0))
        deduction_rate = float(request.form.get('deduction_rate', 0.25))
        
        # Validate ranges
        if base_rate < 0 or base_rate > 1000:
            flash("Base rate must be between R0 and R1000 per hour.", "error")
            return redirect(url_for('payroll.payroll_configuration'))
            
        if overtime_multiplier < 1.0 or overtime_multiplier > 5.0:
            flash("Overtime multiplier must be between 1.0x and 5.0x.", "error")
            return redirect(url_for('payroll.payroll_configuration'))
            
        if double_time_multiplier < 1.0 or double_time_multiplier > 5.0:
            flash("Double time multiplier must be between 1.0x and 5.0x.", "error")
            return redirect(url_for('payroll.payroll_configuration'))
            
        if deduction_rate < 0.0 or deduction_rate > 0.5:
            flash("Deduction rate must be between 0% and 50%.", "error")
            return redirect(url_for('payroll.payroll_configuration'))
        
        # Update application config (runtime only)
        current_app.config['PAYROLL_BASE_RATE'] = base_rate
        current_app.config['PAYROLL_OVERTIME_MULTIPLIER'] = overtime_multiplier
        current_app.config['PAYROLL_DOUBLE_TIME_MULTIPLIER'] = double_time_multiplier
        current_app.config['PAYROLL_DEDUCTION_RATE'] = deduction_rate
        
        # Log the configuration change
        logging.info(f"Payroll configuration updated by user {current_user.username}: "
                    f"Base Rate: R{base_rate}, OT: {overtime_multiplier}x, DT: {double_time_multiplier}x, "
                    f"Deductions: {deduction_rate*100}%")
        
        flash(f"Payroll configuration updated successfully. "
              f"Base Rate: R{base_rate}/hour, Overtime: {overtime_multiplier}x, "
              f"Double Time: {double_time_multiplier}x, Deductions: {deduction_rate*100}%", "success")
        
        return redirect(url_for('payroll.payroll_configuration'))
        
    except ValueError as e:
        flash("Invalid numeric values provided. Please check your input.", "error")
        return redirect(url_for('payroll.payroll_configuration'))
    except Exception as e:
        logging.error(f"Error saving payroll configuration: {e}")
        flash("An error occurred while saving configuration.", "error")
        return redirect(url_for('payroll.payroll_configuration'))