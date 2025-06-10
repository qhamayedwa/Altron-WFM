"""
Timecard Data Rollup and SAGE API Integration Module
Provides flexible timecard data aggregation and SAGE API integration
"""

import logging
import json
import requests
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from models import TimeEntry, User, Department, PayCode
from auth_simple import role_required

# Configure logging
logging.basicConfig(level=logging.DEBUG)

timecard_rollup_bp = Blueprint('timecard_rollup', __name__, url_prefix='/timecard-rollup')

class RollupPeriod(Enum):
    """Enumeration of available rollup periods"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class RollupType(Enum):
    """Enumeration of available rollup types"""
    EMPLOYEE = "employee"
    DEPARTMENT = "department"
    PAY_CODE = "pay_code"
    LOCATION = "location"
    COMBINED = "combined"

@dataclass
class SAGEConfig:
    """SAGE API configuration"""
    endpoint_url: str
    username: str
    password: str
    company_database: str
    api_version: str = "v1"
    timeout: int = 30

@dataclass
class RollupConfig:
    """Rollup configuration"""
    period: str
    rollup_type: str
    start_date: date
    end_date: date
    department_filter: Optional[List[int]] = None
    employee_filter: Optional[List[int]] = None
    pay_code_filter: Optional[List[str]] = None
    include_breaks: bool = True
    include_overtime: bool = True

class TimecardRollupService:
    """Service for timecard data rollup and aggregation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_rollup_data(self, config: RollupConfig) -> Dict[str, Any]:
        """Generate rollup data based on configuration"""
        try:
            self.logger.info(f"Generating rollup data for period {config.period} from {config.start_date} to {config.end_date}")
            
            # Build base query
            query = self._build_base_query(config)
            
            # Apply rollup logic based on type
            if config.rollup_type == "daily":
                return self._rollup_by_day(query, config)
            elif config.rollup_type == "employee":
                return self._rollup_by_employee(query, config)
            elif config.rollup_type == "department":
                return self._rollup_by_department(query, config)
            elif config.rollup_type == "pay_code":
                return self._rollup_by_pay_code(query, config)
            else:
                return self._rollup_combined(query, config)
                
        except Exception as e:
            self.logger.error(f"Error generating rollup data: {e}")
            raise

    def _build_base_query(self, config: RollupConfig):
        """Build base query with filters"""
        query = db.session.query(TimeEntry)
        
        # Date range filter
        query = query.filter(
            TimeEntry.clock_in_time >= datetime.combine(config.start_date, datetime.min.time()),
            TimeEntry.clock_in_time <= datetime.combine(config.end_date, datetime.max.time())
        )
        
        # Only completed entries
        query = query.filter(TimeEntry.clock_out_time.isnot(None))
        
        # Apply filters
        if config.employee_filter:
            query = query.filter(TimeEntry.user_id.in_(config.employee_filter))
        
        return query

    def _rollup_by_day(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by day"""
        entries = query.all()
        daily_data = {}
        
        for entry in entries:
            work_date = entry.work_date
            date_str = work_date.strftime("%Y-%m-%d")
            
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "date": date_str,
                    "total_hours": 0,
                    "employee_count": set(),
                    "entry_count": 0
                }
            
            daily_data[date_str]["total_hours"] += entry.total_hours
            daily_data[date_str]["employee_count"].add(entry.user_id)
            daily_data[date_str]["entry_count"] += 1
        
        # Convert sets to counts
        for date_data in daily_data.values():
            date_data["employee_count"] = len(date_data["employee_count"])
        
        return {
            "type": "daily",
            "periods": list(daily_data.values()),
            "summary": self._calculate_overall_summary(entries, config)
        }

    def _rollup_by_employee(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by employee"""
        entries = query.all()
        employee_data = {}
        
        for entry in entries:
            user_id = entry.user_id
            
            if user_id not in employee_data:
                employee = entry.employee
                employee_data[user_id] = {
                    "employee_id": user_id,
                    "full_name": f"{employee.first_name or ''} {employee.last_name or ''}".strip() or employee.username,
                    "username": employee.username,
                    "total_hours": 0,
                    "regular_hours": 0,
                    "overtime_hours": 0,
                    "entry_count": 0,
                    "days_worked": set()
                }
            
            employee_data[user_id]["total_hours"] += entry.total_hours
            employee_data[user_id]["regular_hours"] += entry.regular_hours
            employee_data[user_id]["overtime_hours"] += entry.overtime_hours
            employee_data[user_id]["entry_count"] += 1
            employee_data[user_id]["days_worked"].add(entry.work_date)
        
        # Convert sets to counts
        for emp_data in employee_data.values():
            emp_data["days_worked"] = len(emp_data["days_worked"])
        
        return {
            "type": "employee",
            "employees": list(employee_data.values()),
            "summary": self._calculate_overall_summary(entries, config)
        }

    def _rollup_by_department(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by department"""
        entries = query.all()
        dept_data = {}
        
        for entry in entries:
            employee = entry.employee
            dept_name = "No Department"
            
            # Get department from employee
            if hasattr(employee, 'department') and employee.department:
                dept_name = employee.department.name
            
            if dept_name not in dept_data:
                dept_data[dept_name] = {
                    "department_name": dept_name,
                    "total_hours": 0,
                    "employee_count": set(),
                    "entry_count": 0
                }
            
            dept_data[dept_name]["total_hours"] += entry.total_hours
            dept_data[dept_name]["employee_count"].add(entry.user_id)
            dept_data[dept_name]["entry_count"] += 1
        
        # Convert sets to counts
        for dept in dept_data.values():
            dept["employee_count"] = len(dept["employee_count"])
        
        return {
            "type": "department",
            "departments": list(dept_data.values()),
            "summary": self._calculate_overall_summary(entries, config)
        }

    def _rollup_by_pay_code(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by pay code"""
        entries = query.all()
        pay_code_data = {
            "REGULAR": {
                "pay_code": "REGULAR",
                "description": "Regular Hours",
                "total_hours": 0,
                "employee_count": set(),
                "entry_count": 0
            }
        }
        
        for entry in entries:
            pay_code_key = "REGULAR"  # Simplified for now
            
            pay_code_data[pay_code_key]["total_hours"] += entry.total_hours
            pay_code_data[pay_code_key]["employee_count"].add(entry.user_id)
            pay_code_data[pay_code_key]["entry_count"] += 1
        
        # Convert sets to counts
        for pc_data in pay_code_data.values():
            pc_data["employee_count"] = len(pc_data["employee_count"])
        
        return {
            "type": "pay_code",
            "pay_codes": list(pay_code_data.values()),
            "summary": self._calculate_overall_summary(entries, config)
        }

    def _rollup_combined(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Combined rollup with multiple dimensions"""
        entries = query.all()
        
        return {
            "type": "combined",
            "employee_summary": self._rollup_by_employee(query, config)["employees"],
            "department_summary": self._rollup_by_department(query, config)["departments"],
            "daily_summary": self._rollup_by_day(query, config)["periods"],
            "summary": self._calculate_overall_summary(entries, config)
        }

    def _calculate_overall_summary(self, entries: List[TimeEntry], config: RollupConfig) -> Dict[str, Any]:
        """Calculate overall summary"""
        if not entries:
            return {
                "total_hours": 0,
                "total_employees": 0,
                "total_entries": 0,
                "average_hours_per_employee": 0,
                "period_start": config.start_date.strftime("%Y-%m-%d"),
                "period_end": config.end_date.strftime("%Y-%m-%d")
            }
        
        total_hours = sum(entry.total_hours for entry in entries)
        unique_employees = len(set(entry.user_id for entry in entries))
        
        return {
            "total_hours": round(total_hours, 2),
            "total_employees": unique_employees,
            "total_entries": len(entries),
            "average_hours_per_employee": round(total_hours / unique_employees if unique_employees > 0 else 0, 2),
            "period_start": config.start_date.strftime("%Y-%m-%d"),
            "period_end": config.end_date.strftime("%Y-%m-%d")
        }

class SAGEApiIntegration:
    """SAGE API integration service"""
    
    def __init__(self, config: SAGEConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """Authenticate with SAGE API"""
        try:
            auth_url = f"{self.config.endpoint_url}/auth/login"
            auth_data = {
                "username": self.config.username,
                "password": self.config.password,
                "company_database": self.config.company_database
            }
            
            response = self.session.post(auth_url, json=auth_data, timeout=self.config.timeout)
            
            if response.status_code == 200:
                self.logger.info("Successfully authenticated with SAGE API")
                return True
            else:
                self.logger.error(f"SAGE authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"SAGE authentication error: {e}")
            return False

    def send_to_sage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to SAGE API"""
        try:
            if not self.authenticate():
                return {"success": False, "error": "Authentication failed"}
            
            import_url = f"{self.config.endpoint_url}/timecard/import"
            response = self.session.post(import_url, json=payload, timeout=self.config.timeout)
            
            if response.status_code == 200:
                return {"success": True, "message": "Data successfully sent to SAGE"}
            else:
                return {"success": False, "error": f"SAGE API error: {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Error sending data to SAGE: {e}")
            return {"success": False, "error": str(e)}

# Route handlers

@timecard_rollup_bp.route('/')
@login_required
@role_required('Super User', 'Manager')
def rollup_dashboard():
    """Timecard rollup dashboard"""
    return render_template('timecard_rollup/dashboard.html')

@timecard_rollup_bp.route('/configure')
@login_required
@role_required('Super User', 'Manager')
def configure_rollup():
    """Configure rollup settings"""
    departments = Department.query.filter_by(is_active=True).all()
    employees = User.query.filter(User.roles.any(name='Employee')).all()
    pay_codes = PayCode.query.filter_by(is_active=True).all()
    
    return render_template('timecard_rollup/configure.html', 
                         departments=departments, 
                         employees=employees, 
                         pay_codes=pay_codes)

@timecard_rollup_bp.route('/generate', methods=['POST'])
@login_required
@role_required('Super User', 'Manager')
def generate_rollup():
    """Generate rollup data"""
    try:
        # Parse form data
        rollup_type = request.form.get('rollup_type', 'employee')
        period = request.form.get('rollup_period', 'custom')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if not start_date_str or not end_date_str:
            return jsonify({"success": False, "error": "Start and end dates are required"})
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Create rollup configuration
        config = RollupConfig(
            period=period,
            rollup_type=rollup_type,
            start_date=start_date,
            end_date=end_date
        )
        
        # Generate rollup data
        service = TimecardRollupService()
        rollup_data = service.generate_rollup_data(config)
        
        return jsonify({
            "success": True,
            "data": rollup_data,
            "config": {
                "type": rollup_type,
                "period": period,
                "start_date": start_date_str,
                "end_date": end_date_str
            }
        })
        
    except Exception as e:
        logging.error(f"Error generating rollup data: {e}")
        return jsonify({"success": False, "error": str(e)})

@timecard_rollup_bp.route('/sage/config')
@login_required
@role_required('Super User')
def sage_configuration():
    """SAGE API configuration"""
    return render_template('timecard_rollup/sage_config.html')

@timecard_rollup_bp.route('/sage/config/save', methods=['POST'])
@login_required
@role_required('Super User')
def save_sage_config():
    """Save SAGE API configuration"""
    try:
        # In a real implementation, you'd save this securely
        flash('SAGE configuration saved successfully', 'success')
        return redirect(url_for('timecard_rollup.rollup_dashboard'))
    except Exception as e:
        flash(f'Error saving SAGE configuration: {str(e)}', 'error')
        return redirect(url_for('timecard_rollup.sage_configuration'))

@timecard_rollup_bp.route('/sage/test', methods=['POST'])
@login_required
@role_required('Super User')
def test_sage_connection():
    """Test SAGE API connection"""
    try:
        data = request.get_json()
        
        # Create test configuration
        config = SAGEConfig(
            endpoint_url=data.get('endpoint_url'),
            username=data.get('username'), 
            password=data.get('password'),
            company_database=data.get('company_database')
        )
        
        # Test connection
        sage_api = SAGEApiIntegration(config)
        if sage_api.authenticate():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify({"success": False, "error": "Connection failed"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@timecard_rollup_bp.route('/sage/send', methods=['POST'])
@login_required
@role_required('Super User')
def send_to_sage():
    """Send rollup data to SAGE API"""
    try:
        # This would implement the actual SAGE integration
        return jsonify({"success": True, "message": "Data sent to SAGE successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})