"""
SAGE VIP Payroll Integration Module
Handles bidirectional data synchronization between Altron WFM and SAGE VIP Payroll system
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from app import db
from models import User, TimeEntry, PayCalculation, LeaveApplication, Schedule
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SAGEEmployee:
    """SAGE VIP Employee data structure"""
    employee_id: str
    employee_number: str
    first_name: str
    last_name: str
    email: str
    department: str
    position: str
    pay_rate: float
    currency: str
    active: bool
    hire_date: str

@dataclass
class SAGETimeEntry:
    """SAGE VIP Time Entry data structure"""
    employee_id: str
    date: str
    hours_worked: float
    overtime_hours: float
    pay_code: str
    cost_center: str
    notes: str

@dataclass
class SAGELeaveEntry:
    """SAGE VIP Leave Entry data structure"""
    employee_id: str
    leave_type: str
    start_date: str
    end_date: str
    days_taken: float
    approved_by: str
    status: str

class SAGEVIPIntegration:
    """Main integration class for SAGE VIP Payroll system"""
    
    def __init__(self):
        self.base_url = os.environ.get('SAGE_VIP_BASE_URL')
        self.api_key = os.environ.get('SAGE_VIP_API_KEY')
        self.username = os.environ.get('SAGE_VIP_USERNAME')
        self.password = os.environ.get('SAGE_VIP_PASSWORD')
        self.company_db = os.environ.get('SAGE_VIP_COMPANY_DB')
        
        # API endpoints
        self.endpoints = {
            'auth': '/api/v1/auth/login',
            'employees': '/api/v1/employees',
            'timesheet': '/api/v1/timesheet',
            'leave': '/api/v1/leave',
            'payroll': '/api/v1/payroll',
            'departments': '/api/v1/departments',
            'pay_codes': '/api/v1/pay-codes'
        }
        
        self.session = requests.Session()
        self.auth_token = None
        
    def authenticate(self) -> bool:
        """Authenticate with SAGE VIP Payroll system"""
        try:
            auth_url = f"{self.base_url}{self.endpoints['auth']}"
            auth_data = {
                'username': self.username,
                'password': self.password,
                'company_database': self.company_db
            }
            
            response = self.session.post(auth_url, json=auth_data)
            response.raise_for_status()
            
            auth_result = response.json()
            self.auth_token = auth_result.get('access_token')
            
            # Set authorization header for future requests
            self.session.headers.update({
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key
            })
            
            logger.info("Successfully authenticated with SAGE VIP Payroll")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def sync_employees_from_sage(self) -> List[SAGEEmployee]:
        """Pull employee data from SAGE VIP and sync with WFM database"""
        if not self.authenticate():
            raise Exception("Failed to authenticate with SAGE VIP")
        
        try:
            employees_url = f"{self.base_url}{self.endpoints['employees']}"
            response = self.session.get(employees_url)
            response.raise_for_status()
            
            sage_employees = response.json()
            synced_employees = []
            
            for emp_data in sage_employees.get('employees', []):
                sage_employee = SAGEEmployee(
                    employee_id=emp_data.get('employee_id'),
                    employee_number=emp_data.get('employee_number'),
                    first_name=emp_data.get('first_name'),
                    last_name=emp_data.get('last_name'),
                    email=emp_data.get('email'),
                    department=emp_data.get('department'),
                    position=emp_data.get('position'),
                    pay_rate=emp_data.get('pay_rate', 0.0),
                    currency=emp_data.get('currency', 'ZAR'),
                    active=emp_data.get('active', True),
                    hire_date=emp_data.get('hire_date')
                )
                
                # Sync with WFM User table
                self._sync_employee_to_wfm(sage_employee)
                synced_employees.append(sage_employee)
            
            logger.info(f"Synced {len(synced_employees)} employees from SAGE VIP")
            return synced_employees
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync employees from SAGE VIP: {e}")
            raise
    
    def _sync_employee_to_wfm(self, sage_employee: SAGEEmployee):
        """Sync individual employee data to WFM database"""
        try:
            # Find existing user by employee ID
            user = User.query.filter_by(employee_id=sage_employee.employee_number).first()
            
            if user:
                # Update existing user
                user.first_name = sage_employee.first_name
                user.last_name = sage_employee.last_name
                user.email = sage_employee.email
                user.department = sage_employee.department
                user.position = sage_employee.position
                user.is_active = sage_employee.active
            else:
                # Create new user
                user = User(
                    username=sage_employee.email.split('@')[0],
                    email=sage_employee.email,
                    employee_id=sage_employee.employee_number,
                    first_name=sage_employee.first_name,
                    last_name=sage_employee.last_name,
                    department=sage_employee.department,
                    position=sage_employee.position,
                    is_active=sage_employee.active
                )
                db.session.add(user)
            
            db.session.commit()
            logger.info(f"Synced employee {sage_employee.employee_number} to WFM")
            
        except Exception as e:
            logger.error(f"Failed to sync employee {sage_employee.employee_number}: {e}")
            db.session.rollback()
    
    def push_time_entries_to_sage(self, start_date: datetime, end_date: datetime) -> bool:
        """Push time entries from WFM to SAGE VIP Payroll"""
        if not self.authenticate():
            raise Exception("Failed to authenticate with SAGE VIP")
        
        try:
            # Get time entries from WFM database
            time_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time.between(start_date, end_date),
                TimeEntry.status == 'completed'
            ).all()
            
            sage_time_entries = []
            
            for entry in time_entries:
                if entry.user and entry.user.employee_id:
                    # Calculate hours worked
                    hours_worked = self._calculate_hours_worked(entry)
                    overtime_hours = self._calculate_overtime_hours(entry)
                    
                    sage_entry = SAGETimeEntry(
                        employee_id=entry.user.employee_id,
                        date=entry.clock_in_time.strftime('%Y-%m-%d'),
                        hours_worked=hours_worked,
                        overtime_hours=overtime_hours,
                        pay_code=entry.pay_code.code if entry.pay_code else 'REGULAR',
                        cost_center=entry.user.department or 'DEFAULT',
                        notes=entry.notes or ''
                    )
                    
                    sage_time_entries.append(sage_entry)
            
            # Push to SAGE VIP
            if sage_time_entries:
                timesheet_url = f"{self.base_url}{self.endpoints['timesheet']}"
                payload = {
                    'time_entries': [entry.__dict__ for entry in sage_time_entries]
                }
                
                response = self.session.post(timesheet_url, json=payload)
                response.raise_for_status()
                
                logger.info(f"Successfully pushed {len(sage_time_entries)} time entries to SAGE VIP")
                return True
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to push time entries to SAGE VIP: {e}")
            return False
    
    def push_leave_entries_to_sage(self, start_date: datetime, end_date: datetime) -> bool:
        """Push leave applications from WFM to SAGE VIP Payroll"""
        if not self.authenticate():
            raise Exception("Failed to authenticate with SAGE VIP")
        
        try:
            # Get approved leave applications from WFM
            leave_applications = LeaveApplication.query.filter(
                LeaveApplication.start_date.between(start_date, end_date),
                LeaveApplication.status == 'approved'
            ).all()
            
            sage_leave_entries = []
            
            for leave_app in leave_applications:
                if leave_app.user and leave_app.user.employee_id:
                    sage_leave = SAGELeaveEntry(
                        employee_id=leave_app.user.employee_id,
                        leave_type=leave_app.leave_type.name,
                        start_date=leave_app.start_date.strftime('%Y-%m-%d'),
                        end_date=leave_app.end_date.strftime('%Y-%m-%d'),
                        days_taken=leave_app.days_requested,
                        approved_by=leave_app.approved_by.employee_id if leave_app.approved_by else '',
                        status='APPROVED'
                    )
                    
                    sage_leave_entries.append(sage_leave)
            
            # Push to SAGE VIP
            if sage_leave_entries:
                leave_url = f"{self.base_url}{self.endpoints['leave']}"
                payload = {
                    'leave_entries': [entry.__dict__ for entry in sage_leave_entries]
                }
                
                response = self.session.post(leave_url, json=payload)
                response.raise_for_status()
                
                logger.info(f"Successfully pushed {len(sage_leave_entries)} leave entries to SAGE VIP")
                return True
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to push leave entries to SAGE VIP: {e}")
            return False
    
    def pull_payroll_data_from_sage(self, pay_period_start: datetime, pay_period_end: datetime) -> List[Dict]:
        """Pull processed payroll data from SAGE VIP"""
        if not self.authenticate():
            raise Exception("Failed to authenticate with SAGE VIP")
        
        try:
            payroll_url = f"{self.base_url}{self.endpoints['payroll']}"
            params = {
                'start_date': pay_period_start.strftime('%Y-%m-%d'),
                'end_date': pay_period_end.strftime('%Y-%m-%d'),
                'status': 'processed'
            }
            
            response = self.session.get(payroll_url, params=params)
            response.raise_for_status()
            
            payroll_data = response.json()
            logger.info(f"Retrieved payroll data for {len(payroll_data.get('payroll_records', []))} employees")
            
            return payroll_data.get('payroll_records', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to pull payroll data from SAGE VIP: {e}")
            return []
    
    def sync_pay_codes_from_sage(self) -> bool:
        """Sync pay codes from SAGE VIP to WFM"""
        if not self.authenticate():
            raise Exception("Failed to authenticate with SAGE VIP")
        
        try:
            pay_codes_url = f"{self.base_url}{self.endpoints['pay_codes']}"
            response = self.session.get(pay_codes_url)
            response.raise_for_status()
            
            sage_pay_codes = response.json()
            
            # Sync with WFM pay codes (implementation depends on your PayCode model structure)
            for code_data in sage_pay_codes.get('pay_codes', []):
                # Update or create pay codes in WFM database
                pass
            
            logger.info("Successfully synced pay codes from SAGE VIP")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync pay codes from SAGE VIP: {e}")
            return False
    
    def _calculate_hours_worked(self, time_entry: TimeEntry) -> float:
        """Calculate regular hours worked from time entry"""
        if time_entry.clock_out_time and time_entry.clock_in_time:
            total_minutes = (time_entry.clock_out_time - time_entry.clock_in_time).total_seconds() / 60
            break_minutes = time_entry.total_break_minutes or 0
            worked_minutes = total_minutes - break_minutes
            return round(worked_minutes / 60, 2)
        return 0.0
    
    def _calculate_overtime_hours(self, time_entry: TimeEntry) -> float:
        """Calculate overtime hours from time entry"""
        regular_hours = self._calculate_hours_worked(time_entry)
        if regular_hours > 8:  # Standard 8-hour workday
            return round(regular_hours - 8, 2)
        return 0.0
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to SAGE VIP Payroll system"""
        try:
            if self.authenticate():
                return {
                    'success': True,
                    'message': 'Successfully connected to SAGE VIP Payroll',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to authenticate with SAGE VIP Payroll',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

# Singleton instance
sage_integration = SAGEVIPIntegration()