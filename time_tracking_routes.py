"""
Time Tracking Routes for Clock In/Out Functionality
Provides simple routes for dashboard time tracking buttons
"""

from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from models import TimeEntry
from sqlalchemy import and_
from timezone_utils import get_current_time

# Create blueprint for time tracking
time_tracking_bp = Blueprint('time_tracking', __name__)

@time_tracking_bp.route('/clock-in', methods=['POST'])
@login_required
def clock_in():
    """Simple clock in endpoint for dashboard buttons"""
    try:
        # Check if user already has an active time entry
        active_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if active_entry:
            return jsonify({
                'success': False,
                'message': 'You are already clocked in!'
            }), 400
        
        # Create new time entry
        new_entry = TimeEntry(
            user_id=current_user.id,
            clock_in_time=get_current_time(),
            status='Open'
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Successfully clocked in!',
            'clock_in_time': new_entry.clock_in_time.strftime('%I:%M %p')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Clock in failed: {str(e)}'
        }), 500

@time_tracking_bp.route('/clock-out', methods=['POST'])
@login_required
def clock_out():
    """Simple clock out endpoint for dashboard buttons"""
    try:
        # Find active time entry
        active_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if not active_entry:
            return jsonify({
                'success': False,
                'message': 'No active clock-in found!'
            }), 400
        
        # Clock out
        active_entry.clock_out_time = get_current_time()
        active_entry.status = 'Closed'
        
        db.session.commit()
        
        # Calculate total hours
        total_hours = active_entry.total_hours
        
        return jsonify({
            'success': True,
            'message': f'Successfully clocked out! Total hours: {total_hours}',
            'clock_out_time': active_entry.clock_out_time.strftime('%I:%M %p'),
            'total_hours': total_hours
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Clock out failed: {str(e)}'
        }), 500

@time_tracking_bp.route('/current-status')
@login_required
def current_status():
    """Get current time tracking status"""
    try:
        # Check for active entry
        active_entry = TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.clock_out_time.is_(None)
            )
        ).first()
        
        if active_entry:
            return jsonify({
                'success': True,
                'is_clocked_in': True,
                'clock_in_time': active_entry.clock_in_time.strftime('%I:%M %p'),
                'entry_id': active_entry.id
            })
        else:
            return jsonify({
                'success': True,
                'is_clocked_in': False,
                'clock_in_time': None,
                'entry_id': None
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500