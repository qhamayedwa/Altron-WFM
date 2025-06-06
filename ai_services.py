"""
AI Services Module for WFM System
Provides OpenAI-powered intelligent features for workforce management
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from openai import OpenAI
from flask import current_app
from sqlalchemy import func, and_, or_
from app import db
from models import User, TimeEntry, Schedule, LeaveApplication, PayRule, PayCalculation
from ai_fallback import fallback_service

# Initialize OpenAI client with error handling
try:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
except Exception as e:
    logging.error(f"OpenAI client initialization error: {e}")
    client = None

class WFMIntelligence:
    """AI-powered workforce management intelligence engine"""
    
    def __init__(self):
        self.client = client
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
        self.is_available = client is not None and os.environ.get("OPENAI_API_KEY") is not None
    
    def analyze_scheduling_patterns(self, department_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """Analyze scheduling patterns and provide AI insights"""
        if not self.is_available:
            # Use fallback statistical analysis
            return fallback_service.analyze_scheduling_patterns(department_id, days)
            
        try:
            # Get scheduling data
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            query = Schedule.query.filter(
                func.date(Schedule.start_time) >= start_date,
                func.date(Schedule.start_time) <= end_date
            )
            
            if department_id:
                query = query.join(User).filter(User.department == str(department_id))
            
            schedules = query.all()
            
            # Prepare data for AI analysis
            schedule_data = []
            for schedule in schedules:
                schedule_data.append({
                    'date': schedule.start_time.date().isoformat(),
                    'day_of_week': schedule.start_time.weekday(),
                    'start_time': schedule.start_time.strftime('%H:%M'),
                    'end_time': schedule.end_time.strftime('%H:%M'),
                    'duration_hours': schedule.duration_hours(),
                    'shift_type': schedule.shift_type.name if hasattr(schedule, 'shift_type') and schedule.shift_type else 'Regular',
                    'employee_id': schedule.user_id,
                    'status': schedule.status
                })
            
            # Create AI prompt
            prompt = f"""
            Analyze the following scheduling data for workforce management insights:
            
            {json.dumps(schedule_data[:50], indent=2)}  # Limit for token efficiency
            
            Provide insights in JSON format with the following structure:
            {{
                "patterns_identified": ["pattern1", "pattern2"],
                "optimization_suggestions": ["suggestion1", "suggestion2"],
                "coverage_analysis": {{
                    "understaffed_periods": ["time_period"],
                    "overstaffed_periods": ["time_period"]
                }},
                "efficiency_score": 0-100,
                "recommendations": ["recommendation1", "recommendation2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a workforce management expert analyzing scheduling patterns."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'analysis': analysis,
                'data_period': f"{start_date} to {end_date}",
                'total_schedules_analyzed': len(schedules)
            }
            
        except Exception as e:
            logging.error(f"AI scheduling analysis error: {e}")
            error_msg = str(e)
            if 'quota' in error_msg.lower() or 'insufficient_quota' in error_msg.lower():
                error_msg = 'OpenAI API quota exceeded. Please check your billing details.'
            elif '429' in error_msg:
                error_msg = 'API rate limit reached. Please try again in a few moments.'
            return {
                'success': False,
                'error': error_msg,
                'fallback_available': True
            }
    
    def generate_payroll_insights(self, pay_period_start: date, pay_period_end: date) -> Dict[str, Any]:
        """Generate AI-powered payroll insights and anomaly detection"""
        if not self.is_available:
            # Use fallback statistical analysis
            return fallback_service.generate_payroll_insights(pay_period_start, pay_period_end)
            
        try:
            # Get payroll calculations for the period
            calculations = PayCalculation.query.filter(
                PayCalculation.pay_period_start >= pay_period_start,
                PayCalculation.pay_period_end <= pay_period_end
            ).all()
            
            # Get time entries for comparison
            time_entries = TimeEntry.query.filter(
                func.date(TimeEntry.clock_in_time) >= pay_period_start,
                func.date(TimeEntry.clock_in_time) <= pay_period_end
            ).all()
            
            # Prepare payroll data
            payroll_data = []
            for calc in calculations:
                payroll_data.append({
                    'employee_id': calc.employee_id,
                    'gross_pay': float(calc.gross_pay),
                    'regular_hours': float(calc.regular_hours),
                    'overtime_hours': float(calc.overtime_hours),
                    'total_hours': float(calc.total_hours),
                    'hourly_rate': float(calc.hourly_rate) if calc.hourly_rate else 0,
                })
            
            # Time tracking data
            time_data = []
            for entry in time_entries:
                if entry.total_hours:
                    time_data.append({
                        'employee_id': entry.user_id,
                        'date': entry.clock_in_time.date().isoformat(),
                        'total_hours': float(entry.total_hours),
                        'clock_in': entry.clock_in_time.strftime('%H:%M'),
                        'clock_out': entry.clock_out_time.strftime('%H:%M') if entry.clock_out_time else None
                    })
            
            prompt = f"""
            Analyze this payroll data for anomalies and insights:
            
            Payroll Calculations: {json.dumps(payroll_data[:20], indent=2)}
            Time Tracking Data: {json.dumps(time_data[:30], indent=2)}
            
            Provide analysis in JSON format:
            {{
                "anomalies_detected": [
                    {{
                        "type": "anomaly_type",
                        "employee_id": "id",
                        "description": "description",
                        "severity": "low|medium|high"
                    }}
                ],
                "cost_analysis": {{
                    "total_payroll_cost": "amount",
                    "overtime_percentage": "percentage",
                    "average_hourly_rate": "rate"
                }},
                "recommendations": ["recommendation1", "recommendation2"],
                "compliance_notes": ["note1", "note2"],
                "efficiency_insights": ["insight1", "insight2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a payroll expert analyzing workforce costs and compliance."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            insights = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'insights': insights,
                'period': f"{pay_period_start} to {pay_period_end}",
                'calculations_analyzed': len(calculations),
                'time_entries_analyzed': len(time_entries)
            }
            
        except Exception as e:
            logging.error(f"AI payroll insights error: {e}")
            error_msg = str(e)
            if 'quota' in error_msg.lower() or 'insufficient_quota' in error_msg.lower():
                error_msg = 'OpenAI API quota exceeded. Please check your billing details.'
            elif '429' in error_msg:
                error_msg = 'API rate limit reached. Please try again in a few moments.'
            return {
                'success': False,
                'error': error_msg,
                'fallback_available': True
            }
    
    def analyze_attendance_patterns(self, employee_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """Analyze attendance patterns and predict potential issues"""
        if not self.is_available:
            # Use fallback statistical analysis
            return fallback_service.analyze_attendance_patterns(employee_id, days)
            
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            query = TimeEntry.query.filter(
                func.date(TimeEntry.clock_in_time) >= start_date,
                func.date(TimeEntry.clock_in_time) <= end_date
            )
            
            if employee_id:
                query = query.filter(TimeEntry.user_id == employee_id)
            
            entries = query.all()
            
            # Prepare attendance data
            attendance_data = []
            for entry in entries:
                attendance_data.append({
                    'employee_id': entry.user_id,
                    'date': entry.clock_in_time.date().isoformat(),
                    'clock_in_time': entry.clock_in_time.strftime('%H:%M'),
                    'clock_out_time': entry.clock_out_time.strftime('%H:%M') if entry.clock_out_time else 'Still active',
                    'total_hours': float(entry.total_hours) if entry.total_hours else 0,
                    'day_of_week': entry.clock_in_time.weekday(),
                    'is_late': entry.clock_in_time.time() > datetime.strptime('09:00', '%H:%M').time(),
                    'break_minutes': getattr(entry, 'total_break_minutes', 0) or 0
                })
            
            prompt = f"""
            Analyze attendance patterns for workforce insights:
            
            {json.dumps(attendance_data[:40], indent=2)}
            
            Provide analysis in JSON format:
            {{
                "attendance_trends": {{
                    "punctuality_score": 0-100,
                    "consistency_score": 0-100,
                    "average_daily_hours": "hours"
                }},
                "patterns_identified": ["pattern1", "pattern2"],
                "risk_indicators": [
                    {{
                        "type": "risk_type",
                        "employee_id": "id",
                        "description": "description",
                        "probability": "low|medium|high"
                    }}
                ],
                "recommendations": ["recommendation1", "recommendation2"],
                "productivity_insights": ["insight1", "insight2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an HR analytics expert analyzing employee attendance patterns."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'analysis': analysis,
                'period': f"{start_date} to {end_date}",
                'entries_analyzed': len(entries)
            }
            
        except Exception as e:
            logging.error(f"AI attendance analysis error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def suggest_optimal_schedule(self, target_date: date, department_id: Optional[int] = None) -> Dict[str, Any]:
        """Generate AI-optimized schedule suggestions"""
        try:
            # Get historical data for the same day of week
            day_of_week = target_date.weekday()
            historical_schedules = Schedule.query.filter(
                func.extract('dow', Schedule.start_time) == day_of_week
            ).limit(50).all()
            
            # Get employee availability and preferences
            employees_query = User.query.filter(User.is_active == True)
            if department_id:
                employees_query = employees_query.filter(User.department == str(department_id))
            
            employees = employees_query.all()
            
            # Get recent time entries for performance analysis
            recent_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time >= target_date - timedelta(days=14)
            ).all()
            
            # Prepare data for AI
            historical_data = []
            for schedule in historical_schedules:
                historical_data.append({
                    'date': schedule.start_time.date().isoformat(),
                    'employee_id': schedule.user_id,
                    'start_time': schedule.start_time.strftime('%H:%M'),
                    'end_time': schedule.end_time.strftime('%H:%M'),
                    'shift_type': schedule.shift_type.name if hasattr(schedule, 'shift_type') and schedule.shift_type else 'Regular'
                })
            
            employee_data = []
            for emp in employees:
                employee_data.append({
                    'id': emp.id,
                    'role': [role.name for role in emp.roles][0] if emp.roles else 'Employee',
                    'department': emp.department or 'General'
                })
            
            prompt = f"""
            Generate an optimal schedule for {target_date.isoformat()} ({target_date.strftime('%A')}):
            
            Historical same-day schedules: {json.dumps(historical_data[:20], indent=2)}
            Available employees: {json.dumps(employee_data, indent=2)}
            
            Provide optimized schedule in JSON format:
            {{
                "recommended_schedule": [
                    {{
                        "employee_id": "id",
                        "shift_start": "HH:MM",
                        "shift_end": "HH:MM",
                        "shift_type": "Regular|Overtime|Night",
                        "reasoning": "why this assignment"
                    }}
                ],
                "coverage_analysis": {{
                    "peak_hours_covered": true/false,
                    "minimum_staffing_met": true/false,
                    "optimal_distribution": true/false
                }},
                "efficiency_score": 0-100,
                "cost_estimate": "estimated_cost",
                "notes": ["note1", "note2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a workforce optimization expert creating efficient schedules."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            suggestions = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'suggestions': suggestions,
                'target_date': target_date.isoformat(),
                'employees_available': len(employees)
            }
            
        except Exception as e:
            logging.error(f"AI schedule optimization error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def natural_language_query(self, query: str) -> Dict[str, Any]:
        """Process natural language queries about workforce data"""
        try:
            # Get recent summary data
            total_employees = User.query.filter(User.is_active == True).count()
            recent_entries = TimeEntry.query.filter(
                TimeEntry.clock_in_time >= datetime.now() - timedelta(days=7)
            ).count()
            recent_schedules = Schedule.query.filter(
                func.date(Schedule.start_time) >= date.today() - timedelta(days=7)
            ).count()
            pending_leave = LeaveApplication.query.filter(
                LeaveApplication.status == 'pending'
            ).count()
            
            context = f"""
            Current WFM System Status:
            - Total Active Employees: {total_employees}
            - Time Entries (Last 7 days): {recent_entries}
            - Schedules (Last 7 days): {recent_schedules}
            - Pending Leave Applications: {pending_leave}
            - Current Date: {date.today().isoformat()}
            """
            
            prompt = f"""
            {context}
            
            User Query: "{query}"
            
            Provide a helpful response about the workforce management system in JSON format:
            {{
                "response": "direct answer to the query",
                "insights": ["relevant insight1", "relevant insight2"],
                "suggested_actions": ["action1", "action2"],
                "related_data": {{
                    "metric1": "value1",
                    "metric2": "value2"
                }}
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful WFM assistant providing insights about workforce data."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'query': query,
                'result': result
            }
            
        except Exception as e:
            logging.error(f"AI natural language query error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Global AI service instance
ai_service = WFMIntelligence()