"""
AI-Powered Routes for WFM System
Provides web interface for OpenAI-enhanced workforce management features
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from auth_simple import role_required, super_user_required
from ai_services import ai_service
import json
import logging

# Create AI blueprint
ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

@ai_bp.route('/dashboard')
@login_required
@role_required('Manager', 'Super User', 'HR')
def ai_dashboard():
    """AI-powered insights dashboard"""
    try:
        # Get recent insights
        scheduling_insights = ai_service.analyze_scheduling_patterns(days=14)
        attendance_insights = ai_service.analyze_attendance_patterns(days=14)
        
        return render_template('ai/dashboard.html',
                             scheduling_insights=scheduling_insights,
                             attendance_insights=attendance_insights)
    except Exception as e:
        logging.error(f"AI dashboard error: {e}")
        flash('Error loading AI dashboard. Please check your OpenAI configuration.', 'danger')
        return redirect(url_for('main.index'))

@ai_bp.route('/scheduling-optimizer')
@login_required
@role_required('Manager', 'Super User')
def scheduling_optimizer():
    """AI-powered scheduling optimization interface"""
    return render_template('ai/scheduling_optimizer.html')

@ai_bp.route('/payroll-insights')
@login_required
@role_required('Manager', 'Super User', 'Payroll')
def payroll_insights():
    """AI-powered payroll analysis interface"""
    return render_template('ai/payroll_insights.html')

@ai_bp.route('/attendance-analyzer')
@login_required
@role_required('Manager', 'Super User', 'HR')
def attendance_analyzer():
    """AI-powered attendance pattern analysis"""
    return render_template('ai/attendance_analyzer.html')

@ai_bp.route('/natural-query')
@login_required
def natural_query():
    """Natural language query interface"""
    return render_template('ai/natural_query.html')

# API Endpoints for AI Features

@ai_bp.route('/api/analyze-scheduling', methods=['POST'])
@login_required
@role_required('Manager', 'Super User')
def api_analyze_scheduling():
    """API endpoint for scheduling analysis"""
    try:
        data = request.get_json()
        department_id = data.get('department_id')
        days = data.get('days', 30)
        
        result = ai_service.analyze_scheduling_patterns(department_id, days)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API scheduling analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze scheduling patterns'
        }), 500

@ai_bp.route('/api/generate-payroll-insights', methods=['POST'])
@login_required
@role_required('Manager', 'Super User', 'Payroll')
def api_generate_payroll_insights():
    """API endpoint for payroll insights"""
    try:
        data = request.get_json()
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        result = ai_service.generate_payroll_insights(start_date, end_date)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API payroll insights error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate payroll insights'
        }), 500

@ai_bp.route('/api/analyze-attendance', methods=['POST'])
@login_required
@role_required('Manager', 'Super User', 'HR')
def api_analyze_attendance():
    """API endpoint for attendance analysis"""
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        days = data.get('days', 30)
        
        result = ai_service.analyze_attendance_patterns(employee_id, days)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API attendance analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze attendance patterns'
        }), 500

@ai_bp.route('/api/suggest-schedule', methods=['POST'])
@login_required
@role_required('Manager', 'Super User')
def api_suggest_schedule():
    """API endpoint for AI schedule suggestions"""
    try:
        data = request.get_json()
        target_date = datetime.strptime(data['target_date'], '%Y-%m-%d').date()
        department_id = data.get('department_id')
        
        result = ai_service.suggest_optimal_schedule(target_date, department_id)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API schedule suggestion error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate schedule suggestions'
        }), 500

@ai_bp.route('/api/natural-query', methods=['POST'])
@login_required
def api_natural_query():
    """API endpoint for natural language queries"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        result = ai_service.natural_language_query(query)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API natural query error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to process natural language query'
        }), 500

@ai_bp.route('/api/quick-insights', methods=['GET'])
@login_required
def api_quick_insights():
    """API endpoint for quick AI insights for dashboard widgets"""
    try:
        # Get quick insights without heavy computation
        insights = {
            'workforce_status': 'Analyzing current workforce patterns...',
            'efficiency_score': 'Calculating efficiency metrics...',
            'recommendations': ['Enable AI insights for detailed analysis']
        }
        
        return jsonify({
            'success': True,
            'insights': insights
        })
        
    except Exception as e:
        logging.error(f"Quick insights error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate quick insights'
        }), 500

@ai_bp.route('/api/test-connection', methods=['POST'])
@login_required
@super_user_required
def api_test_ai_connection():
    """Test OpenAI API connection"""
    try:
        # Simple test query
        result = ai_service.natural_language_query("Test connection - what is the current date?")
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'OpenAI connection successful',
                'test_result': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Connection test failed')
            })
            
    except Exception as e:
        logging.error(f"AI connection test error: {e}")
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }), 500