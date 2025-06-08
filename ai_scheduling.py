"""
AI-Powered Scheduling Module for WFM
Provides intelligent schedule optimization, availability matching, and automated schedule generation
"""

from datetime import datetime, timedelta, time
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from app import db
from models import User, Schedule, TimeEntry, LeaveApplication
from auth_simple import role_required
import logging

# Create blueprint for AI scheduling
ai_scheduling_bp = Blueprint('ai_scheduling', __name__, url_prefix='/ai-scheduling')

class SchedulingAI:
    """
    Core AI scheduling engine for intelligent workforce management
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_employee_availability(self, employee_id, start_date, end_date):
        """
        Analyze employee availability patterns and constraints
        """
        try:
            # Get employee's historical schedule patterns
            historical_schedules = Schedule.query.filter(
                and_(
                    Schedule.user_id == employee_id,
                    Schedule.start_time >= start_date - timedelta(days=30),
                    Schedule.start_time <= start_date
                )
            ).all()
            
            # Get leave applications for the period
            leave_applications = LeaveApplication.query.filter(
                and_(
                    LeaveApplication.user_id == employee_id,
                    LeaveApplication.start_date <= end_date,
                    LeaveApplication.end_date >= start_date,
                    LeaveApplication.status.in_(['Approved', 'Pending'])
                )
            ).all()
            
            # Get time entry patterns for preferred working hours
            time_entries = TimeEntry.query.filter(
                and_(
                    TimeEntry.user_id == employee_id,
                    TimeEntry.clock_in_time >= start_date - timedelta(days=60)
                )
            ).all()
            
            availability_data = {
                'employee_id': employee_id,
                'historical_patterns': self._analyze_patterns(historical_schedules),
                'leave_constraints': self._process_leave_constraints(leave_applications),
                'preferred_hours': self._calculate_preferred_hours(time_entries),
                'availability_score': self._calculate_availability_score(historical_schedules, leave_applications)
            }
            
            return availability_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing employee availability: {e}")
            return None
    
    def generate_optimized_schedule(self, department_id=None, start_date=None, end_date=None):
        """
        Generate optimized schedule using AI algorithms
        """
        try:
            if not start_date:
                start_date = datetime.now().date()
            if not end_date:
                end_date = start_date + timedelta(days=7)
            
            # Get active employees
            if department_id:
                employees = User.query.filter(
                    and_(
                        User.is_active == True,
                        User.department == department_id
                    )
                ).all()
            else:
                employees = User.query.filter_by(is_active=True).all()
            
            # Analyze availability for all employees
            employee_availability = {}
            for employee in employees:
                availability = self.analyze_employee_availability(
                    employee.id, start_date, end_date
                )
                if availability:
                    employee_availability[employee.id] = availability
            
            # Generate schedule recommendations
            schedule_recommendations = self._optimize_schedule_distribution(
                employee_availability, start_date, end_date
            )
            
            return {
                'success': True,
                'schedule_recommendations': schedule_recommendations,
                'optimization_metrics': self._calculate_optimization_metrics(schedule_recommendations),
                'coverage_analysis': self._analyze_coverage(schedule_recommendations)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating optimized schedule: {e}")
            return {'success': False, 'error': str(e)}
    
    def _analyze_patterns(self, schedules):
        """Analyze historical scheduling patterns"""
        patterns = {
            'preferred_days': {},
            'preferred_shifts': {},
            'average_hours_per_week': 0
        }
        
        if not schedules:
            return patterns
        
        total_hours = 0
        for schedule in schedules:
            # Day preference analysis
            day_of_week = schedule.start_time.weekday()
            patterns['preferred_days'][day_of_week] = patterns['preferred_days'].get(day_of_week, 0) + 1
            
            # Shift time analysis
            shift_hour = schedule.start_time.hour
            patterns['preferred_shifts'][shift_hour] = patterns['preferred_shifts'].get(shift_hour, 0) + 1
            
            # Calculate hours
            if schedule.end_time:
                hours = (schedule.end_time - schedule.start_time).total_seconds() / 3600
                total_hours += hours
        
        if schedules:
            patterns['average_hours_per_week'] = total_hours / len(schedules) * 7
        
        return patterns
    
    def _process_leave_constraints(self, leave_applications):
        """Process leave constraints for scheduling"""
        constraints = []
        
        for leave in leave_applications:
            constraints.append({
                'start_date': leave.start_date,
                'end_date': leave.end_date,
                'type': leave.leave_type_id,
                'status': leave.status
            })
        
        return constraints
    
    def _calculate_preferred_hours(self, time_entries):
        """Calculate preferred working hours based on clock-in patterns"""
        hour_frequency = {}
        
        for entry in time_entries:
            hour = entry.clock_in_time.hour
            hour_frequency[hour] = hour_frequency.get(hour, 0) + 1
        
        if hour_frequency:
            most_common_hour = max(hour_frequency, key=hour_frequency.get)
            return {
                'preferred_start_hour': most_common_hour,
                'hour_distribution': hour_frequency
            }
        
        return {'preferred_start_hour': 9, 'hour_distribution': {}}
    
    def _calculate_availability_score(self, schedules, leave_applications):
        """Calculate overall availability score for employee"""
        base_score = 100
        
        # Reduce score for frequent leave applications
        if leave_applications:
            leave_penalty = min(len(leave_applications) * 5, 30)
            base_score -= leave_penalty
        
        # Increase score for consistent scheduling
        if schedules:
            consistency_bonus = min(len(schedules), 20)
            base_score += consistency_bonus
        
        return max(0, min(base_score, 100))
    
    def _optimize_schedule_distribution(self, employee_availability, start_date, end_date):
        """Optimize schedule distribution using AI algorithms"""
        recommendations = []
        
        # Generate recommendations for each day in the period
        current_date = start_date
        while current_date <= end_date:
            day_recommendations = self._generate_day_schedule(
                employee_availability, current_date
            )
            recommendations.extend(day_recommendations)
            current_date += timedelta(days=1)
        
        return recommendations
    
    def _generate_day_schedule(self, employee_availability, target_date):
        """Generate schedule recommendations for a specific day"""
        day_schedules = []
        
        # Define standard shifts
        shifts = [
            {'name': 'Morning', 'start': time(9, 0), 'end': time(17, 0)},
            {'name': 'Evening', 'start': time(17, 0), 'end': time(1, 0)},
            {'name': 'Night', 'start': time(1, 0), 'end': time(9, 0)}
        ]
        
        for shift in shifts:
            # Find best employees for this shift
            best_employees = self._rank_employees_for_shift(
                employee_availability, target_date, shift
            )
            
            # Assign top-ranked employees to shifts
            for i, (employee_id, score) in enumerate(best_employees[:3]):  # Top 3 employees
                day_schedules.append({
                    'employee_id': employee_id,
                    'date': target_date,
                    'shift_name': shift['name'],
                    'start_time': datetime.combine(target_date, shift['start']),
                    'end_time': datetime.combine(target_date, shift['end']),
                    'ai_score': score,
                    'priority': i + 1
                })
        
        return day_schedules
    
    def _rank_employees_for_shift(self, employee_availability, date, shift):
        """Rank employees for a specific shift based on AI scoring"""
        rankings = []
        
        for employee_id, availability in employee_availability.items():
            score = self._calculate_shift_fit_score(availability, date, shift)
            rankings.append((employee_id, score))
        
        # Sort by score (highest first)
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def _calculate_shift_fit_score(self, availability, date, shift):
        """Calculate how well an employee fits a specific shift"""
        base_score = availability['availability_score']
        
        # Check if employee has leave constraints for this date
        for constraint in availability['leave_constraints']:
            if constraint['start_date'] <= date <= constraint['end_date']:
                return 0  # Cannot work on leave days
        
        # Bonus for preferred day of week
        day_of_week = date.weekday()
        preferred_days = availability['historical_patterns']['preferred_days']
        if day_of_week in preferred_days:
            day_bonus = preferred_days[day_of_week] * 2
            base_score += day_bonus
        
        # Bonus for preferred shift time
        shift_hour = shift['start'].hour
        preferred_shifts = availability['historical_patterns']['preferred_shifts']
        if shift_hour in preferred_shifts:
            shift_bonus = preferred_shifts[shift_hour] * 3
            base_score += shift_bonus
        
        return min(base_score, 100)
    
    def _calculate_optimization_metrics(self, recommendations):
        """Calculate metrics for schedule optimization"""
        if not recommendations:
            return {}
        
        total_shifts = len(recommendations)
        unique_employees = len(set(rec['employee_id'] for rec in recommendations))
        avg_ai_score = sum(rec['ai_score'] for rec in recommendations) / total_shifts
        
        return {
            'total_shifts_assigned': total_shifts,
            'employees_scheduled': unique_employees,
            'average_fit_score': round(avg_ai_score, 2),
            'schedule_efficiency': round((avg_ai_score / 100) * 100, 1)
        }
    
    def _analyze_coverage(self, recommendations):
        """Analyze schedule coverage and gaps"""
        coverage = {
            'shifts_covered': {},
            'potential_gaps': [],
            'over_coverage': []
        }
        
        # Group by date and shift
        date_shifts = {}
        for rec in recommendations:
            date_str = rec['date'].strftime('%Y-%m-%d')
            if date_str not in date_shifts:
                date_shifts[date_str] = {}
            
            shift_name = rec['shift_name']
            if shift_name not in date_shifts[date_str]:
                date_shifts[date_str][shift_name] = []
            
            date_shifts[date_str][shift_name].append(rec)
        
        # Analyze coverage
        for date_str, shifts in date_shifts.items():
            coverage['shifts_covered'][date_str] = list(shifts.keys())
            
            for shift_name, assignments in shifts.items():
                if len(assignments) == 0:
                    coverage['potential_gaps'].append(f"{date_str} {shift_name}")
                elif len(assignments) > 3:
                    coverage['over_coverage'].append(f"{date_str} {shift_name}")
        
        return coverage

# Initialize AI scheduling engine
scheduling_ai = SchedulingAI()

@ai_scheduling_bp.route('/')
@login_required
@role_required('Manager', 'Admin', 'Super User')
def ai_dashboard():
    """AI Scheduling dashboard"""
    return render_template('ai_scheduling/dashboard.html')

@ai_scheduling_bp.route('/generate', methods=['GET', 'POST'])
@login_required
@role_required('Manager', 'Admin', 'Super User')
def generate_schedule():
    """Generate AI-optimized schedule"""
    if request.method == 'POST':
        try:
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not start_date_str or not end_date_str:
                flash('Start date and end date are required', 'error')
                return redirect(url_for('ai_scheduling.generate_schedule'))
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            department_id = request.form.get('department_id') or None
            
            # Generate optimized schedule
            result = scheduling_ai.generate_optimized_schedule(
                department_id=department_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if result['success']:
                flash('AI-optimized schedule generated successfully!', 'success')
                return render_template('ai_scheduling/results.html', 
                                     recommendations=result['schedule_recommendations'],
                                     metrics=result['optimization_metrics'],
                                     coverage=result['coverage_analysis'])
            else:
                flash(f'Error generating schedule: {result.get("error", "Unknown error")}', 'error')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    # Get departments for dropdown - check multiple sources
    try:
        # First try to get departments from users
        user_departments = db.session.query(User.department).filter(
            User.department.isnot(None),
            User.department != ''
        ).distinct().all()
        
        # Also try to get from hierarchical department structure if it exists
        try:
            from models import HierarchicalDepartment
            hierarchical_departments = db.session.query(HierarchicalDepartment.department_name).filter(
                HierarchicalDepartment.department_name.isnot(None)
            ).distinct().all()
            departments_list = list(set([d[0] for d in user_departments if d[0]] + 
                                      [d[0] for d in hierarchical_departments if d[0]]))
        except ImportError:
            # Fallback to user departments only
            departments_list = [d[0] for d in user_departments if d[0]]
        
        # Sort departments alphabetically
        departments_list.sort()
        
    except Exception as e:
        flash(f'Warning: Could not load departments: {str(e)}', 'warning')
        departments_list = []
    
    return render_template('ai_scheduling/generate.html', 
                         departments=departments_list,
                         datetime=datetime,
                         timedelta=timedelta)

@ai_scheduling_bp.route('/analyze/<int:employee_id>')
@login_required
@role_required('Manager', 'Admin', 'Super User')
def analyze_employee(employee_id):
    """Analyze individual employee availability patterns"""
    try:
        start_date = datetime.now().date() - timedelta(days=30)
        end_date = datetime.now().date() + timedelta(days=30)
        
        availability = scheduling_ai.analyze_employee_availability(
            employee_id, start_date, end_date
        )
        
        if availability:
            employee = User.query.get_or_404(employee_id)
            return render_template('ai_scheduling/employee_analysis.html',
                                 employee=employee,
                                 availability=availability)
        else:
            flash('Could not analyze employee availability', 'error')
            return redirect(url_for('ai_scheduling.ai_dashboard'))
            
    except Exception as e:
        flash(f'Error analyzing employee: {str(e)}', 'error')
        return redirect(url_for('ai_scheduling.ai_dashboard'))

@ai_scheduling_bp.route('/apply-schedule', methods=['POST'])
@login_required
@role_required('Manager', 'Admin', 'Super User')
def apply_schedule():
    """Apply AI-generated schedule to the system"""
    try:
        schedule_data = request.get_json()
        
        applied_count = 0
        for recommendation in schedule_data.get('recommendations', []):
            # Create new schedule entry
            new_schedule = Schedule(
                user_id=recommendation['employee_id'],
                start_time=datetime.fromisoformat(recommendation['start_time']),
                end_time=datetime.fromisoformat(recommendation['end_time']),
                notes=f"AI-generated schedule (Score: {recommendation['ai_score']})"
            )
            
            db.session.add(new_schedule)
            applied_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully applied {applied_count} schedule entries',
            'applied_count': applied_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@ai_scheduling_bp.route('/api/availability/<int:employee_id>')
@login_required
@role_required('Manager', 'Admin', 'Super User')
def api_employee_availability(employee_id):
    """API endpoint for employee availability data"""
    try:
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=14)
        
        availability = scheduling_ai.analyze_employee_availability(
            employee_id, start_date, end_date
        )
        
        return jsonify({
            'success': True,
            'availability': availability
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@ai_scheduling_bp.route('/optimization-history')
@login_required
@role_required('Manager', 'Admin', 'Super User')
def optimization_history():
    """View AI scheduling optimization history"""
    # Get recent AI-generated schedules
    ai_schedules = Schedule.query.filter(
        Schedule.notes.like('%AI-generated%')
    ).order_by(Schedule.created_at.desc()).limit(50).all()
    
    return render_template('ai_scheduling/history.html', schedules=ai_schedules)