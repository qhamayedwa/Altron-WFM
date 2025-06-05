from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, TimeEntry, Schedule, LeaveApplication, PayRule, PayCode
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

# Create blueprint for main routes
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Main dashboard for Time & Attendance system"""
    try:
        # System Statistics
        total_employees = User.query.filter_by(is_active=True).count()
        try:
            active_schedules = Schedule.query.filter(
                Schedule.date >= datetime.now().date()
            ).count()
        except:
            active_schedules = 0
        
        # Time Entry Statistics (Today)
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
        
        # Leave Applications (Pending)
        pending_leave = LeaveApplication.query.filter_by(status='pending').count()
        
        # Recent Activity (Last 5 entries)
        recent_entries = TimeEntry.query.filter(
            TimeEntry.clock_in_time >= datetime.now() - timedelta(days=7)
        ).order_by(TimeEntry.clock_in_time.desc()).limit(5).all()
        
        # Pay Rules Count
        active_pay_rules = PayRule.query.filter_by(is_active=True).count()
        
        # Pay Codes Count
        active_pay_codes = PayCode.query.filter_by(is_active=True).count()
        
        # Weekly Hours Summary
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
        weekly_hours = db.session.query(
            func.sum(TimeEntry.total_hours)
        ).filter(
            TimeEntry.clock_in_time >= week_start
        ).scalar() or 0
        
        return render_template('dashboard.html',
                             total_employees=total_employees,
                             active_schedules=active_schedules,
                             today_entries=today_entries,
                             clocked_in_now=clocked_in_now,
                             pending_leave=pending_leave,
                             recent_entries=recent_entries,
                             active_pay_rules=active_pay_rules,
                             active_pay_codes=active_pay_codes,
                             weekly_hours=weekly_hours)
    except Exception as e:
        logging.error(f"Error in dashboard route: {e}")
        flash("An error occurred while loading the dashboard.", "error")
        return render_template('dashboard.html',
                             total_employees=0,
                             active_schedules=0,
                             today_entries=0,
                             clocked_in_now=0,
                             pending_leave=0,
                             recent_entries=[],
                             active_pay_rules=0,
                             active_pay_codes=0,
                             weekly_hours=0)

@main_bp.route('/reports')
@login_required
def reports():
    """Reports dashboard"""
    try:
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
        
        # Total hours worked in period
        total_hours = db.session.query(
            func.sum(TimeEntry.total_hours)
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).scalar() or 0
        
        # Overtime hours
        overtime_hours = db.session.query(
            func.sum(TimeEntry.overtime_hours)
        ).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).scalar() or 0
        
        # Employee attendance summary
        attendance_summary = db.session.query(
            User.username,
            func.count(TimeEntry.id).label('days_worked'),
            func.sum(TimeEntry.total_hours).label('total_hours'),
            func.avg(TimeEntry.total_hours).label('avg_hours')
        ).join(TimeEntry).filter(
            and_(
                TimeEntry.clock_in_time >= start_date,
                TimeEntry.clock_in_time <= end_date + timedelta(days=1)
            )
        ).group_by(User.id, User.username).all()
        
        # Leave applications in period
        leave_applications = LeaveApplication.query.filter(
            and_(
                LeaveApplication.start_date >= start_date,
                LeaveApplication.start_date <= end_date
            )
        ).count()
        
        return render_template('reports.html',
                             start_date=start_date,
                             end_date=end_date,
                             total_hours=total_hours,
                             overtime_hours=overtime_hours,
                             attendance_summary=attendance_summary,
                             leave_applications=leave_applications)
        
    except Exception as e:
        logging.error(f"Error in reports route: {e}")
        flash("An error occurred while generating reports.", "error")
        return redirect(url_for('main.index'))

@main_bp.route('/quick-actions')
@login_required
def quick_actions():
    """Quick actions page for common tasks"""
    return render_template('quick_actions.html')