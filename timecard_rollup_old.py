"""
Timecard Data Rollup and SAGE API Integration Module
Provides flexible timecard data aggregation and SAGE API integration
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from models import User, TimeEntry, Department, PayCode
from auth import role_required, super_user_required
from datetime import datetime, timedelta, date
from sqlalchemy import and_, func, or_, desc
import logging
import json
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

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
    period: RollupPeriod
    rollup_type: RollupType
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
            self.logger.info(f"Generating rollup data for period {config.period.value} from {config.start_date} to {config.end_date}")
            
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
        query = db.session.query(TimeEntry).join(User, TimeEntry.user_id == User.id)
        
        # Date filter
        query = query.filter(
            and_(
                TimeEntry.clock_in_time >= config.start_date,
                TimeEntry.clock_in_time <= config.end_date + timedelta(days=1),
                TimeEntry.clock_out_time.isnot(None)
            )
        )
        
        # Department filter
        if config.department_filter:
            query = query.filter(User.department_id.in_(config.department_filter))
        
        # Employee filter
        if config.employee_filter:
            query = query.filter(User.id.in_(config.employee_filter))
        
        # Pay code filter
        if config.pay_code_filter:
            query = query.join(PayCode, TimeEntry.pay_code_id == PayCode.id)
            query = query.filter(PayCode.code.in_(config.pay_code_filter))
        
        return query
    
    def _rollup_by_day(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by day"""
        rollup_data = {"type": "daily", "periods": []}
        
        current_date = config.start_date
        while current_date <= config.end_date:
            day_entries = query.filter(
                and_(
                    TimeEntry.clock_in_time >= current_date,
                    TimeEntry.clock_in_time < current_date + timedelta(days=1)
                )
            ).all()
            
            day_summary = self._calculate_day_summary(day_entries, current_date)
            rollup_data["periods"].append(day_summary)
            current_date += timedelta(days=1)
        
        return rollup_data
    
    def _rollup_by_employee(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by employee"""
        rollup_data = {"type": "employee", "employees": []}
        
        # Group by employee
        employee_data = {}
        for entry in query.all():
            emp_id = entry.user_id
            if emp_id not in employee_data:
                employee_data[emp_id] = {
                    "employee_id": emp_id,
                    "username": entry.user.username,
                    "full_name": f"{entry.user.first_name} {entry.user.last_name}",
                    "department": entry.user.department,
                    "entries": []
                }
            employee_data[emp_id]["entries"].append(entry)
        
        # Calculate summaries for each employee
        for emp_id, emp_data in employee_data.items():
            summary = self._calculate_employee_summary(emp_data["entries"], config)
            emp_data.update(summary)
            del emp_data["entries"]  # Remove raw entries
            rollup_data["employees"].append(emp_data)
        
        return rollup_data
    
    def _rollup_by_department(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by department"""
        rollup_data = {"type": "department", "departments": []}
        
        # Group by department
        dept_data = {}
        for entry in query.all():
            dept_id = entry.user.department_id or 0  # Use 0 for no department
            if dept_id not in dept_data:
                dept_name = entry.user.employee_department.name if entry.user.employee_department else "Unassigned"
                dept_data[dept_id] = {
                    "department_id": dept_id,
                    "department_name": dept_name,
                    "entries": []
                }
            dept_data[dept_id]["entries"].append(entry)
        
        # Calculate summaries for each department
        for dept_id, dept_info in dept_data.items():
            summary = self._calculate_department_summary(dept_info["entries"], config)
            dept_info.update(summary)
            del dept_info["entries"]  # Remove raw entries
            rollup_data["departments"].append(dept_info)
        
        return rollup_data
    
    def _rollup_by_pay_code(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Rollup data by pay code"""
        rollup_data = {"type": "pay_code", "pay_codes": []}
        
        # Group by pay code
        paycode_data = {}
        for entry in query.all():
            pay_code = entry.pay_code.code if entry.pay_code else "REGULAR"
            if pay_code not in paycode_data:
                paycode_data[pay_code] = {
                    "pay_code": pay_code,
                    "description": entry.pay_code.description if entry.pay_code else "Regular Time",
                    "entries": []
                }
            paycode_data[pay_code]["entries"].append(entry)
        
        # Calculate summaries for each pay code
        for code, code_data in paycode_data.items():
            summary = self._calculate_paycode_summary(code_data["entries"], config)
            code_data.update(summary)
            del code_data["entries"]  # Remove raw entries
            rollup_data["pay_codes"].append(code_data)
        
        return rollup_data
    
    def _rollup_combined(self, query, config: RollupConfig) -> Dict[str, Any]:
        """Combined rollup with multiple dimensions"""
        rollup_data = {
            "type": "combined",
            "summary": self._calculate_overall_summary(query.all(), config),
            "by_employee": self._rollup_by_employee(query, config)["employees"],
            "by_department": self._rollup_by_department(query, config)["departments"],
            "by_pay_code": self._rollup_by_pay_code(query, config)["pay_codes"]
        }
        return rollup_data
    
    def _calculate_day_summary(self, entries: List[TimeEntry], date: date) -> Dict[str, Any]:
        """Calculate summary for a single day"""
        total_hours = 0
        total_employees = set()
        pay_code_breakdown = {}
        
        for entry in entries:
            if entry.clock_in_time and entry.clock_out_time:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
                total_employees.add(entry.user_id)
                
                pay_code = entry.pay_code.code if entry.pay_code else "REGULAR"
                if pay_code not in pay_code_breakdown:
                    pay_code_breakdown[pay_code] = 0
                pay_code_breakdown[pay_code] += hours
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_hours": round(total_hours, 2),
            "employee_count": len(total_employees),
            "entry_count": len(entries),
            "pay_code_breakdown": pay_code_breakdown
        }
    
    def _calculate_employee_summary(self, entries: List[TimeEntry], config: RollupConfig) -> Dict[str, Any]:
        """Calculate summary for an employee"""
        total_hours = 0
        regular_hours = 0
        overtime_hours = 0
        pay_code_breakdown = {}
        
        for entry in entries:
            if entry.clock_in_time and entry.clock_out_time:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
                
                pay_code = entry.pay_code.code if entry.pay_code else "REGULAR"
                if pay_code not in pay_code_breakdown:
                    pay_code_breakdown[pay_code] = 0
                pay_code_breakdown[pay_code] += hours
                
                # Categorize hours
                if pay_code in ["OVERTIME", "OT"]:
                    overtime_hours += hours
                else:
                    regular_hours += hours
        
        return {
            "total_hours": round(total_hours, 2),
            "regular_hours": round(regular_hours, 2),
            "overtime_hours": round(overtime_hours, 2),
            "entry_count": len(entries),
            "pay_code_breakdown": pay_code_breakdown
        }
    
    def _calculate_department_summary(self, entries: List[TimeEntry], config: RollupConfig) -> Dict[str, Any]:
        """Calculate summary for a department"""
        total_hours = 0
        total_employees = set()
        pay_code_breakdown = {}
        
        for entry in entries:
            if entry.clock_in_time and entry.clock_out_time:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
                total_employees.add(entry.user_id)
                
                pay_code = entry.pay_code.code if entry.pay_code else "REGULAR"
                if pay_code not in pay_code_breakdown:
                    pay_code_breakdown[pay_code] = 0
                pay_code_breakdown[pay_code] += hours
        
        return {
            "total_hours": round(total_hours, 2),
            "employee_count": len(total_employees),
            "entry_count": len(entries),
            "pay_code_breakdown": pay_code_breakdown
        }
    
    def _calculate_paycode_summary(self, entries: List[TimeEntry], config: RollupConfig) -> Dict[str, Any]:
        """Calculate summary for a pay code"""
        total_hours = 0
        total_employees = set()
        department_breakdown = {}
        
        for entry in entries:
            if entry.clock_in_time and entry.clock_out_time:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
                total_employees.add(entry.user_id)
                
                dept_name = entry.user.employee_department.name if entry.user.employee_department else "Unassigned"
                if dept_name not in department_breakdown:
                    department_breakdown[dept_name] = 0
                department_breakdown[dept_name] += hours
        
        return {
            "total_hours": round(total_hours, 2),
            "employee_count": len(total_employees),
            "entry_count": len(entries),
            "department_breakdown": department_breakdown
        }
    
    def _calculate_overall_summary(self, entries: List[TimeEntry], config: RollupConfig) -> Dict[str, Any]:
        """Calculate overall summary"""
        total_hours = 0
        total_employees = set()
        total_departments = set()
        
        for entry in entries:
            if entry.clock_in_time and entry.clock_out_time:
                hours = (entry.clock_out_time - entry.clock_in_time).total_seconds() / 3600
                total_hours += hours
                total_employees.add(entry.user_id)
                if entry.user.department_id:
                    total_departments.add(entry.user.department_id)
        
        return {
            "total_hours": round(total_hours, 2),
            "total_employees": len(total_employees),
            "total_departments": len(total_departments),
            "total_entries": len(entries),
            "period": f"{config.start_date} to {config.end_date}"
        }

class SAGEApiIntegration:
    """SAGE API integration service"""
    
    def __init__(self, config: SAGEConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.auth_token = None
    
    def authenticate(self) -> bool:
        """Authenticate with SAGE API"""
        try:
            auth_url = f"{self.config.endpoint_url}/auth/login"
            auth_data = {
                "username": self.config.username,
                "password": self.config.password,
                "company_database": self.config.company_database
            }
            
            response = self.session.post(
                auth_url,
                json=auth_data,
                timeout=self.config.timeout
            )
            
            if response.status_code == 200:
                auth_result = response.json()
                self.auth_token = auth_result.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                })
                self.logger.info("Successfully authenticated with SAGE API")
                return True
            else:
                self.logger.error(f"SAGE authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error authenticating with SAGE API: {e}")
            return False
    
    def transform_to_sage_payload(self, rollup_data: Dict[str, Any], transformation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform rollup data to SAGE API payload format"""
        try:
            sage_payload = {
                "company_database": self.config.company_database,
                "transaction_date": datetime.now().strftime("%Y-%m-%d"),
                "source": "WFM_Timecard_Rollup",
                "timecard_data": []
            }
            
            # Transform based on rollup type
            if rollup_data["type"] == "employee":
                sage_payload["timecard_data"] = self._transform_employee_data(rollup_data["employees"], transformation_config)
            elif rollup_data["type"] == "department":
                sage_payload["timecard_data"] = self._transform_department_data(rollup_data["departments"], transformation_config)
            elif rollup_data["type"] == "daily":
                sage_payload["timecard_data"] = self._transform_daily_data(rollup_data["periods"], transformation_config)
            elif rollup_data["type"] == "combined":
                sage_payload["timecard_data"] = self._transform_combined_data(rollup_data, transformation_config)
            
            return sage_payload
            
        except Exception as e:
            self.logger.error(f"Error transforming data to SAGE payload: {e}")
            raise
    
    def _transform_employee_data(self, employees: List[Dict], config: Dict[str, Any]) -> List[Dict]:
        """Transform employee rollup data to SAGE format"""
        sage_records = []
        
        for emp in employees:
            record = {
                "employee_code": emp.get("username"),
                "employee_name": emp.get("full_name"),
                "department": emp.get("department"),
                "total_hours": emp.get("total_hours", 0),
                "regular_hours": emp.get("regular_hours", 0),
                "overtime_hours": emp.get("overtime_hours", 0),
                "pay_codes": emp.get("pay_code_breakdown", {}),
                "transaction_type": "timecard_entry"
            }
            sage_records.append(record)
        
        return sage_records
    
    def _transform_department_data(self, departments: List[Dict], config: Dict[str, Any]) -> List[Dict]:
        """Transform department rollup data to SAGE format"""
        sage_records = []
        
        for dept in departments:
            record = {
                "department_code": str(dept.get("department_id")),
                "department_name": dept.get("department_name"),
                "total_hours": dept.get("total_hours", 0),
                "employee_count": dept.get("employee_count", 0),
                "pay_codes": dept.get("pay_code_breakdown", {}),
                "transaction_type": "department_summary"
            }
            sage_records.append(record)
        
        return sage_records
    
    def _transform_daily_data(self, periods: List[Dict], config: Dict[str, Any]) -> List[Dict]:
        """Transform daily rollup data to SAGE format"""
        sage_records = []
        
        for period in periods:
            record = {
                "date": period.get("date"),
                "total_hours": period.get("total_hours", 0),
                "employee_count": period.get("employee_count", 0),
                "entry_count": period.get("entry_count", 0),
                "pay_codes": period.get("pay_code_breakdown", {}),
                "transaction_type": "daily_summary"
            }
            sage_records.append(record)
        
        return sage_records
    
    def _transform_combined_data(self, combined_data: Dict, config: Dict[str, Any]) -> List[Dict]:
        """Transform combined rollup data to SAGE format"""
        sage_records = []
        
        # Add summary record
        summary_record = {
            "transaction_type": "period_summary",
            "summary": combined_data.get("summary", {}),
            "employee_data": self._transform_employee_data(combined_data.get("by_employee", []), config),
            "department_data": self._transform_department_data(combined_data.get("by_department", []), config)
        }
        sage_records.append(summary_record)
        
        return sage_records
    
    def send_to_sage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to SAGE API"""
        try:
            if not self.auth_token:
                if not self.authenticate():
                    return {"success": False, "error": "Authentication failed"}
            
            # Send to SAGE timecard endpoint
            timecard_url = f"{self.config.endpoint_url}/timecard/import"
            
            response = self.session.post(
                timecard_url,
                json=payload,
                timeout=self.config.timeout
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                self.logger.info(f"Successfully sent data to SAGE: {result}")
                return {"success": True, "response": result}
            else:
                error_msg = f"SAGE API error: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            error_msg = f"Error sending data to SAGE: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

# Flask Routes

@timecard_rollup_bp.route('/dashboard')
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
    # Get available departments and employees for filters
    departments = Department.query.filter_by(is_active=True).all()
    employees = User.query.filter_by(is_active=True).all()
    employees = [emp for emp in employees if not emp.has_role('Super User')]
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
        # Parse configuration from form
        rollup_period = RollupPeriod(request.form.get('rollup_period', 'custom'))
        rollup_type = RollupType(request.form.get('rollup_type', 'employee'))
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        
        # Optional filters
        department_filter = request.form.getlist('department_filter')
        employee_filter = request.form.getlist('employee_filter')
        pay_code_filter = request.form.getlist('pay_code_filter')
        
        config = RollupConfig(
            period=rollup_period,
            rollup_type=rollup_type,
            start_date=start_date,
            end_date=end_date,
            department_filter=[int(d) for d in department_filter if d],
            employee_filter=[int(e) for e in employee_filter if e],
            pay_code_filter=pay_code_filter if pay_code_filter else None
        )
        
        # Generate rollup data
        service = TimecardRollupService()
        rollup_data = service.generate_rollup_data(config)
        
        return jsonify({
            "success": True,
            "data": rollup_data,
            "config": {
                "period": rollup_period.value,
                "type": rollup_type.value,
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": end_date.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        logging.error(f"Error generating rollup data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@timecard_rollup_bp.route('/sage-config')
@login_required
@role_required('Super User')
def sage_configuration():
    """SAGE API configuration"""
    return render_template('timecard_rollup/sage_config.html')

@timecard_rollup_bp.route('/sage-config/save', methods=['POST'])
@login_required
@role_required('Super User')
def save_sage_config():
    """Save SAGE API configuration"""
    try:
        # Get configuration from form
        endpoint_url = request.form.get('endpoint_url')
        username = request.form.get('username')
        password = request.form.get('password')
        company_database = request.form.get('company_database')
        
        # Store in application config (in production, use encrypted storage)
        current_app.config['SAGE_ENDPOINT_URL'] = endpoint_url
        current_app.config['SAGE_USERNAME'] = username
        current_app.config['SAGE_PASSWORD'] = password
        current_app.config['SAGE_COMPANY_DATABASE'] = company_database
        
        flash("SAGE API configuration saved successfully.", "success")
        return redirect(url_for('timecard_rollup.sage_configuration'))
        
    except Exception as e:
        logging.error(f"Error saving SAGE configuration: {e}")
        flash("Error saving SAGE configuration.", "error")
        return redirect(url_for('timecard_rollup.sage_configuration'))

@timecard_rollup_bp.route('/sage-send', methods=['POST'])
@login_required
@role_required('Super User', 'Manager')
def send_to_sage():
    """Send rollup data to SAGE API"""
    try:
        # Get rollup data from request
        rollup_data = request.json.get('rollup_data')
        transformation_config = request.json.get('transformation_config', {})
        
        # Get SAGE configuration
        sage_config = SAGEConfig(
            endpoint_url=current_app.config.get('SAGE_ENDPOINT_URL'),
            username=current_app.config.get('SAGE_USERNAME'),
            password=current_app.config.get('SAGE_PASSWORD'),
            company_database=current_app.config.get('SAGE_COMPANY_DATABASE')
        )
        
        # Initialize SAGE integration
        sage_integration = SAGEApiIntegration(sage_config)
        
        # Transform data to SAGE format
        sage_payload = sage_integration.transform_to_sage_payload(rollup_data, transformation_config)
        
        # Send to SAGE
        result = sage_integration.send_to_sage(sage_payload)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error sending data to SAGE: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@timecard_rollup_bp.route('/test-sage-connection', methods=['POST'])
@login_required
@role_required('Super User')
def test_sage_connection():
    """Test SAGE API connection"""
    try:
        # Get SAGE configuration
        sage_config = SAGEConfig(
            endpoint_url=current_app.config.get('SAGE_ENDPOINT_URL'),
            username=current_app.config.get('SAGE_USERNAME'),
            password=current_app.config.get('SAGE_PASSWORD'),
            company_database=current_app.config.get('SAGE_COMPANY_DATABASE')
        )
        
        # Test connection
        sage_integration = SAGEApiIntegration(sage_config)
        success = sage_integration.authenticate()
        
        if success:
            return jsonify({"success": True, "message": "Successfully connected to SAGE API"})
        else:
            return jsonify({"success": False, "error": "Failed to authenticate with SAGE API"})
            
    except Exception as e:
        logging.error(f"Error testing SAGE connection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500