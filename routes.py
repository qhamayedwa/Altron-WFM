from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
from app import db
from models import User, TimeEntry, Schedule, LeaveApplication, PayRule, PayCode
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import logging
import csv
import io
import json

# Create blueprint for main routes
main_bp = Blueprint('main', __name__)

def generate_dashboard_analytics(is_manager_or_admin, user_id=None):
    """Generate comprehensive analytics data for dashboard charts"""
    try:
        # Time range for analytics - last 30 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Base query filters
        base_filter = TimeEntry.clock_in_time >= start_date
        if not is_manager_or_admin and user_id:
            base_filter = and_(base_filter, TimeEntry.user_id == user_id)
        
        # 1. Daily attendance trends (last 7 days)
        daily_data = []
        for i in range(7):
            day = end_date - timedelta(days=i)
            day_entries = TimeEntry.query.filter(
                and_(
                    func.date(TimeEntry.clock_in_time) == day,
                    base_filter if not user_id else and_(base_filter, TimeEntry.user_id == user_id)
                )
            ).count()
            daily_data.append({
                'date': day.strftime('%m/%d'),
                'entries': day_entries
            })
        daily_data.reverse()
        
        # 2. Weekly hours distribution
        weekly_hours = []
        week_labels = []
        for i in range(4):  # Last 4 weeks
            week_start = end_date - timedelta(days=end_date.weekday() + (7 * i))
            week_end = week_start + timedelta(days=6)
            
            week_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.clock_in_time >= week_start,
                    TimeEntry.clock_in_time <= week_end + timedelta(days=1),
                    base_filter if not user_id else and_(base_filter, TimeEntry.user_id == user_id)
                )
            ).count()
            
            weekly_hours.append(week_entries * 8)  # Assume 8 hours per entry
            week_labels.append(f"Week {week_start.strftime('%m/%d')}")
        
        weekly_hours.reverse()
        week_labels.reverse()
        
        # 3. Leave application status distribution
        if is_manager_or_admin:
            leave_stats = {
                'pending': LeaveApplication.query.filter_by(status='pending').count(),
                'approved': LeaveApplication.query.filter_by(status='approved').count(),
                'rejected': LeaveApplication.query.filter_by(status='rejected').count()
            }
        else:
            leave_stats = {
                'pending': LeaveApplication.query.filter_by(user_id=user_id, status='pending').count(),
                'approved': LeaveApplication.query.filter_by(user_id=user_id, status='approved').count(),
                'rejected': LeaveApplication.query.filter_by(user_id=user_id, status='rejected').count()
            }
        
        # 4. Employee productivity insights (for managers)
        productivity_data = []
        if is_manager_or_admin:
            # Get top 5 most active employees with explicit join condition
            active_employees = db.session.query(
                User.username,
                func.count(TimeEntry.id).label('entry_count')
            ).join(TimeEntry, User.id == TimeEntry.user_id).filter(
                TimeEntry.clock_in_time >= start_date
            ).group_by(User.id, User.username).order_by(
                func.count(TimeEntry.id).desc()
            ).limit(5).all()
            
            productivity_data = [
                {'name': emp.username, 'hours': emp.entry_count * 8}
                for emp in active_employees
            ]
        
        # 5. Time tracking patterns (hourly distribution)
        hourly_patterns = [0] * 24
        time_entries = TimeEntry.query.filter(base_filter).all()
        
        for entry in time_entries:
            if entry.clock_in_time:
                hour = entry.clock_in_time.hour
                hourly_patterns[hour] += 1
        
        return {
            'daily_attendance': {
                'labels': [d['date'] for d in daily_data],
                'data': [d['entries'] for d in daily_data]
            },
            'weekly_hours': {
                'labels': week_labels,
                'data': weekly_hours
            },
            'leave_distribution': {
                'labels': ['Pending', 'Approved', 'Rejected'],
                'data': [leave_stats['pending'], leave_stats['approved'], leave_stats['rejected']]
            },
            'productivity_insights': productivity_data,
            'hourly_patterns': {
                'labels': [f"{i}:00" for i in range(24)],
                'data': hourly_patterns
            },
            'insights': {
                'peak_hour': hourly_patterns.index(max(hourly_patterns)) if hourly_patterns else 9,
                'total_entries_month': sum([d['entries'] for d in daily_data]),
                'avg_daily_entries': sum([d['entries'] for d in daily_data]) / len(daily_data) if daily_data else 0,
                'most_productive_day': max(daily_data, key=lambda x: x['entries'])['date'] if daily_data else 'N/A'
            }
        }
    except Exception as e:
        logging.error(f"Error generating analytics: {e}")
        return {
            'daily_attendance': {'labels': [], 'data': []},
            'weekly_hours': {'labels': [], 'data': []},
            'leave_distribution': {'labels': [], 'data': []},
            'productivity_insights': [],
            'hourly_patterns': {'labels': [], 'data': []},
            'insights': {'peak_hour': 9, 'total_entries_month': 0, 'avg_daily_entries': 0, 'most_productive_day': 'N/A'}
        }

@main_bp.route('/')
@login_required
def index():
    """Main dashboard for Time & Attendance system"""
    try:
        # Check if user has manager/admin roles for organization-wide data
        is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                              (current_user.has_role('Manager') or 
                               current_user.has_role('Admin') or 
                               current_user.has_role('Super User')))
        
        if is_manager_or_admin:
            # Organization-wide statistics for managers/admins
            total_employees = User.query.filter_by(is_active=True).count()
            try:
                active_schedules = Schedule.query.filter(
                    Schedule.start_time >= datetime.now().date()
                ).count()
            except:
                active_schedules = 0
            
            # Time Entry Statistics (Today) - Organization-wide
            today = datetime.now().date()
            today_entries = TimeEntry.query.filter(
                func.date(TimeEntry.clock_in_time) == today
            ).count()
            
            clocked_in_now = TimeEntry.query.filter(
                and_(
                    func.date(TimeEntry.clock_in_time) == today,
                    TimeEntry.clock_out_time.is_(None)
                )
            ).count()
            
            # Leave Applications (Pending) - Organization-wide
            pending_leave = LeaveApplication.query.filter_by(status='pending').count()
            
            # Recent Activity (Last 5 entries) - Organization-wide
            recent_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time >= datetime.now() - timedelta(days=7)
            ).order_by(TimeEntry.clock_in_time.desc()).limit(5).all()
        else:
            # Personal statistics only for basic users/employees
            total_employees = 1  # Just the current user
            try:
                active_schedules = Schedule.query.filter(
                    and_(
                        Schedule.user_id == current_user.id,
                        Schedule.start_time >= datetime.now().date()
                    )
                ).count()
            except:
                active_schedules = 0
            
            # Personal Time Entry Statistics (Today)
            today = datetime.now().date()
            today_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == current_user.id,
                    func.date(TimeEntry.clock_in_time) == today
                )
            ).count()
            
            clocked_in_now = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == current_user.id,
                    func.date(TimeEntry.clock_in_time) == today,
                    TimeEntry.clock_out_time.is_(None)
                )
            ).count()
            
            # Personal Leave Applications (Pending)
            pending_leave = LeaveApplication.query.filter_by(
                user_id=current_user.id,
                status='pending'
            ).count()
            
            # Personal Recent Activity (Last 5 entries)
            recent_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == current_user.id,
                    TimeEntry.clock_in_time >= datetime.now() - timedelta(days=7)
                )
            ).order_by(TimeEntry.clock_in_time.desc()).limit(5).all()
        
        # Pay Rules Count
        active_pay_rules = PayRule.query.filter_by(is_active=True).count()
        
        # Pay Codes Count
        active_pay_codes = PayCode.query.filter_by(is_active=True).count()
        
        # Weekly Hours Summary - filtered by role
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
        if is_manager_or_admin:
            # Organization-wide weekly hours for managers/admins
            weekly_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time >= week_start
            ).count()
        else:
            # Personal weekly hours for basic users/employees
            weekly_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == current_user.id,
                    TimeEntry.clock_in_time >= week_start
                )
            ).count()
        weekly_hours = weekly_entries * 8  # Simplified: assume 8 hours per entry
        
        # Get current user's time tracking status for user empowerment features
        current_status = {'is_clocked_in': False, 'clock_in_time': None}
        active_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if active_entry:
            current_status = {
                'is_clocked_in': True,
                'clock_in_time': active_entry.clock_in_time.strftime('%I:%M %p')
            }
        
        # Get pending approvals count for managers
        pending_approvals = 0
        if hasattr(current_user, 'has_role') and (current_user.has_role('Manager') or current_user.has_role('Super User')):
            pending_approvals = LeaveApplication.query.filter_by(status='Pending').count()
        
        # Generate analytics data for charts
        analytics_data = generate_dashboard_analytics(is_manager_or_admin, current_user.id if not is_manager_or_admin else None)
        
        return render_template('dashboard.html',
                             total_employees=total_employees,
                             active_schedules=active_schedules,
                             today_entries=today_entries,
                             clocked_in_now=clocked_in_now,
                             pending_leave=pending_leave,
                             recent_entries=recent_entries,
                             active_pay_rules=active_pay_rules,
                             active_pay_codes=active_pay_codes,
                             weekly_hours=weekly_hours,
                             current_status=current_status,
                             pending_approvals=pending_approvals,
                             analytics_data=analytics_data)
    except Exception as e:
        logging.error(f"Error in dashboard route: {e}")
        flash("An error occurred while loading the dashboard.", "error")
        # Provide default analytics data structure
        default_analytics = {
            'daily_attendance': {'labels': [], 'data': []},
            'weekly_hours': {'labels': [], 'data': []},
            'leave_distribution': {'labels': [], 'data': []},
            'productivity_insights': [],
            'hourly_patterns': {'labels': [], 'data': []},
            'insights': {'peak_hour': 9, 'total_entries_month': 0, 'avg_daily_entries': 0, 'most_productive_day': 'N/A'}
        }
        return render_template('dashboard.html',
                             total_employees=0,
                             active_schedules=0,
                             today_entries=0,
                             clocked_in_now=0,
                             pending_leave=0,
                             recent_entries=[],
                             active_pay_rules=0,
                             active_pay_codes=0,
                             weekly_hours=0,
                             current_status={'is_clocked_in': False, 'clock_in_time': None},
                             pending_approvals=0,
                             analytics_data=default_analytics)

@main_bp.route('/reports')
@login_required
def reports():
    """Reports dashboard with proper employee data restrictions"""
    try:
        # Check user role for data access control
        is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                              (current_user.has_role('Manager') or 
                               current_user.has_role('Admin') or 
                               current_user.has_role('Super User')))
        
        # Time range from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Default to current month if no dates provided
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Apply user-specific filters for data access
        base_time_filter = and_(
            TimeEntry.clock_in_time >= start_date,
            TimeEntry.clock_in_time <= end_date + timedelta(days=1)
        )
        
        if not is_manager_or_admin:
            # Restrict employees to only their own data
            base_time_filter = and_(
                base_time_filter,
                TimeEntry.user_id == current_user.id
            )
        
        # Total hours worked in period - filtered by user access
        period_entries = TimeEntry.query.filter(base_time_filter).all()
        
        # Calculate total hours from actual time entries
        total_hours = 0
        for entry in period_entries:
            if entry.total_hours:
                total_hours += entry.total_hours
            elif entry.clock_in_time and entry.clock_out_time:
                # Calculate hours if not stored
                duration = entry.clock_out_time - entry.clock_in_time
                total_hours += duration.total_seconds() / 3600
        
        overtime_hours = max(0, total_hours - (len(period_entries) * 8))
        
        # Employee attendance summary - restricted by user role
        if is_manager_or_admin:
            # Managers see all employees
            users_with_entries = db.session.query(User).join(
                TimeEntry, User.id == TimeEntry.user_id
            ).filter(base_time_filter).distinct().all()
        else:
            # Employees see only themselves
            users_with_entries = [current_user] if period_entries else []
        
        attendance_summary = []
        for user in users_with_entries:
            user_filter = and_(
                TimeEntry.user_id == user.id,
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
            
            user_entries = TimeEntry.query.filter(user_filter).all()
            
            days_worked = len(user_entries)
            user_total_hours = sum(entry.total_hours or 0 for entry in user_entries)
            avg_hours = user_total_hours / days_worked if days_worked > 0 else 0
            
            # Create summary with proper user identification
            user_name = f"{user.first_name} {user.last_name}".strip() if hasattr(user, 'first_name') and user.first_name else user.username
            
            user_summary = {
                'username': user.username,
                'name': user_name,
                'email': user.email,
                'total_days': days_worked,
                'total_hours': round(user_total_hours, 2),
                'avg_hours': round(avg_hours, 2)
            }
            attendance_summary.append(user_summary)
        
        # Leave applications in period - filtered by user access
        leave_filter = and_(
            LeaveApplication.start_date >= start_date,
            LeaveApplication.start_date <= end_date
        )
        
        if not is_manager_or_admin:
            leave_filter = and_(
                leave_filter,
                LeaveApplication.user_id == current_user.id
            )
        
        leave_applications = LeaveApplication.query.filter(leave_filter).count()
        
        # Add pay period summary data
        pay_period_summary = []
        if attendance_summary:
            for user_data in attendance_summary:
                pay_period = {
                    'period_start': start_date,
                    'period_end': end_date,
                    'regular_hours': min(user_data['total_hours'], 40),
                    'overtime_hours': max(0, user_data['total_hours'] - 40),
                    'total_hours': user_data['total_hours'],
                    'gross_pay': user_data['total_hours'] * 15.0  # $15/hour base rate
                }
                pay_period_summary.append(pay_period)

        return render_template('reports.html',
                             start_date=start_date,
                             end_date=end_date,
                             total_hours=total_hours,
                             overtime_hours=overtime_hours,
                             attendance_summary=attendance_summary,
                             pay_period_summary=pay_period_summary,
                             leave_applications=leave_applications)
        
    except Exception as e:
        logging.error(f"Error in reports route: {e}")
        flash("An error occurred while generating reports.", "error")
        return redirect(url_for('main.index'))

@main_bp.route('/export-csv')
@login_required
def export_csv():
    """Export attendance report to CSV with proper employee data restrictions"""
    try:
        # Check user role for data access control
        is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                              (current_user.has_role('Manager') or 
                               current_user.has_role('Admin') or 
                               current_user.has_role('Super User')))
        
        # Get the same data as reports page
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Apply user-specific filters for data access
        base_time_filter = and_(
            TimeEntry.clock_in_time >= start_date,
            TimeEntry.clock_in_time <= end_date + timedelta(days=1)
        )
        
        if not is_manager_or_admin:
            # Restrict employees to only their own data
            base_time_filter = and_(
                base_time_filter,
                TimeEntry.user_id == current_user.id
            )

        # Get attendance data based on user role
        if is_manager_or_admin:
            users_with_entries = db.session.query(User).join(
                TimeEntry, User.id == TimeEntry.user_id
            ).filter(base_time_filter).distinct().all()
        else:
            # Employees can only export their own data
            users_with_entries = [current_user]

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Employee', 'Email', 'Total Days', 'Total Hours', 'Average Hours/Day'])
        
        # Write data rows
        for user in users_with_entries:
            user_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == user.id,
                    TimeEntry.clock_in_time >= start_date,
                    TimeEntry.clock_in_time <= end_date + timedelta(days=1)
                )
            ).all()
            
            if user_entries:  # Only include users with entries
                days_worked = len(user_entries)
                total_hours = sum(entry.total_hours or 0 for entry in user_entries)
                avg_hours = total_hours / days_worked if days_worked > 0 else 0
                
                user_name = f"{user.first_name} {user.last_name}".strip() if hasattr(user, 'first_name') and user.first_name else user.username
                writer.writerow([user_name, user.email, days_worked, round(total_hours, 2), round(avg_hours, 2)])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        
        # Add role context to filename
        role_context = "manager" if is_manager_or_admin else "employee"
        response.headers['Content-Disposition'] = f'attachment; filename={role_context}_attendance_report_{start_date}_{end_date}.csv'
        
        return response
        
    except Exception as e:
        logging.error(f"Error exporting CSV: {e}")
        flash("Error generating CSV export.", "error")
        return redirect(url_for('main.reports'))

@main_bp.route('/export-payroll-csv')
@login_required
def export_payroll_csv():
    """Export payroll report to CSV"""
    try:
        # Get the same data as reports page
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            today = datetime.now().date()
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Get attendance data
        users_with_entries = db.session.query(User).join(
            TimeEntry, User.id == TimeEntry.user_id
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).distinct().all()

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Employee', 'Period Start', 'Period End', 'Regular Hours', 'Overtime Hours', 'Total Hours', 'Gross Pay'])
        
        # Write data rows
        for user in users_with_entries:
            user_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == user.id,
                    TimeEntry.clock_in_time >= start_date,
                    TimeEntry.clock_in_time <= end_date + timedelta(days=1)
                )
            ).all()
            
            total_hours = len(user_entries) * 8  # Simplified calculation
            regular_hours = min(total_hours, 40)
            overtime_hours = max(0, total_hours - 40)
            gross_pay = total_hours * 15.0  # $15/hour base rate
            
            writer.writerow([
                user.username, 
                start_date.strftime('%Y-%m-%d'), 
                end_date.strftime('%Y-%m-%d'), 
                regular_hours, 
                overtime_hours, 
                total_hours, 
                f"${gross_pay:.2f}"
            ])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=payroll_report_{start_date}_{end_date}.csv'
        
        return response
        
    except Exception as e:
        logging.error(f"Error exporting payroll CSV: {e}")
        flash("Error generating payroll CSV export.", "error")
        return redirect(url_for('main.reports'))

@main_bp.route('/quick-actions')
@login_required
def quick_actions():
    """Quick actions page for common tasks"""
    return render_template('quick_actions.html')

@main_bp.route('/time-entries')
@login_required
def time_entries():
    """Time entries management page with proper employee data restrictions"""
    # Check user role for data access control
    is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                          (current_user.has_role('Manager') or 
                           current_user.has_role('Admin') or 
                           current_user.has_role('Super User')))
    
    if is_manager_or_admin:
        # Managers see all time entries
        entries = TimeEntry.query.order_by(TimeEntry.clock_in_time.desc()).limit(100).all()
    else:
        # Employees see only their own time entries
        entries = TimeEntry.query.filter_by(user_id=current_user.id).order_by(TimeEntry.clock_in_time.desc()).limit(50).all()
    
    return render_template('time_entries.html', entries=entries, is_manager_view=is_manager_or_admin)

@main_bp.route('/schedules')
@login_required
def schedules():
    """Employee schedules page with proper employee data restrictions"""
    from datetime import date
    today = date.today()
    
    # Check user role for data access control
    is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                          (current_user.has_role('Manager') or 
                           current_user.has_role('Admin') or 
                           current_user.has_role('Super User')))
    
    if is_manager_or_admin:
        # Managers see all schedules
        schedules = Schedule.query.filter(Schedule.start_time >= today).order_by(Schedule.start_time).limit(50).all()
    else:
        # Employees see only their own schedules
        schedules = Schedule.query.filter(
            and_(
                Schedule.user_id == current_user.id,
                Schedule.start_time >= today
            )
        ).order_by(Schedule.start_time).limit(30).all()
    
    return render_template('schedules.html', schedules=schedules, is_manager_view=is_manager_or_admin)

@main_bp.route('/leave-management')
@login_required
def leave_management():
    """Leave management page with proper employee data restrictions"""
    # Check user role for data access control
    is_manager_or_admin = (hasattr(current_user, 'has_role') and 
                          (current_user.has_role('Manager') or 
                           current_user.has_role('Admin') or 
                           current_user.has_role('Super User')))
    
    if is_manager_or_admin:
        # Managers see all leave applications
        applications = LeaveApplication.query.order_by(LeaveApplication.created_at.desc()).limit(100).all()
    else:
        # Employees see only their own leave applications
        applications = LeaveApplication.query.filter_by(user_id=current_user.id).order_by(LeaveApplication.created_at.desc()).all()
    
    return render_template('leave_management.html', applications=applications, is_manager_view=is_manager_or_admin)