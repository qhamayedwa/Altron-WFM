"""
Payroll Processing and Reporting Blueprint
Handles payroll preparation, processing, and advanced reporting functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
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
        
        # Default to current pay period if no dates provided
        if not start_date or not end_date:
            today = datetime.now().date()
            # Assume bi-weekly pay periods starting from first of month
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get all employees with time entries in the period
        employees_with_entries = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).distinct().all()
        
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
                        # PayCode model doesn't have hourly_rate field, use default base rate
                        base_rate = 150.0
                        
                        pay_code_breakdown[code_name] = {
                            'hours': 0,
                            'rate': base_rate,
                            'amount': 0
                        }
                    
                    pay_code_breakdown[code_name]['hours'] += hours
                    pay_code_breakdown[code_name]['amount'] = pay_code_breakdown[code_name]['hours'] * pay_code_breakdown[code_name]['rate']
                
                # Calculate overtime breakdown
                total_hours = sum([breakdown['hours'] for breakdown in pay_code_breakdown.values()])
                regular_hours = min(total_hours, 40)
                ot_15_hours = max(0, min(total_hours - 40, 8))  # First 8 hours over 40
                ot_20_hours = max(0, total_hours - 48)  # Hours over 48
                
                # Calculate gross pay from pay code breakdown amounts
                calculated_gross_pay = sum([breakdown['amount'] for breakdown in pay_code_breakdown.values()])
                
                # Apply overtime rates if applicable
                if ot_15_hours > 0 or ot_20_hours > 0:
                    base_rate = 150.0  # Base hourly rate in ZAR
                    overtime_15_rate = base_rate * 1.5  # Time and a half
                    overtime_20_rate = base_rate * 2.0  # Double time
                    
                    # Recalculate with proper overtime rates
                    regular_pay = regular_hours * base_rate
                    ot_15_pay = ot_15_hours * overtime_15_rate
                    ot_20_pay = ot_20_hours * overtime_20_rate
                    calculated_gross_pay = regular_pay + ot_15_pay + ot_20_pay
                
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
                    'net_pay': pay_calculation.get('net_pay', calculated_gross_pay * 0.75) if pay_calculation else calculated_gross_pay * 0.75,  # 25% tax/deductions
                    'deductions': pay_calculation.get('deductions', calculated_gross_pay * 0.25) if pay_calculation else calculated_gross_pay * 0.25
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
        include_codes = request.args.getlist('include_codes')
        exclude_codes = request.args.getlist('exclude_codes')
        
        if not start_date or not end_date:
            flash("Start and end dates are required for export.", "error")
            return redirect(url_for('payroll.payroll_processing'))
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get payroll data (reuse logic from processing)
        employees_with_entries = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1),
                User.is_active == True
            )
        ).distinct().all()
        
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
                    pay_code_data[code_name] = {'hours': 0, 'amount': 0}
                
                pay_code_data[code_name]['hours'] += hours
                pay_code_data[code_name]['amount'] += hours * 15.0  # Base rate
            
            # Calculate overtime
            regular_hours = min(total_hours, 40)
            ot_15_hours = max(0, min(total_hours - 40, 8))
            ot_20_hours = max(0, total_hours - 48)
            
            # Calculate pay
            regular_pay = regular_hours * 15.0
            ot_15_pay = ot_15_hours * 22.5  # 1.5x rate
            ot_20_pay = ot_20_hours * 30.0  # 2.0x rate
            gross_pay = regular_pay + ot_15_pay + ot_20_pay
            deductions = gross_pay * 0.2  # Simplified 20% deductions
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