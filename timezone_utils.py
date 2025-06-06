"""
Timezone utilities for WFM application
Provides consistent GMT+2 (South African Standard Time) handling
"""

from datetime import datetime, timezone, timedelta
from flask import current_app

# South African Standard Time (GMT+2)
SAST = timezone(timedelta(hours=2))

def get_current_time():
    """Get current time in South African timezone (GMT+2)"""
    # Return timezone-naive datetime adjusted for GMT+2
    utc_now = datetime.utcnow()
    sast_time = utc_now + timedelta(hours=2)
    return sast_time

def localize_datetime(dt):
    """Convert a naive datetime to South African timezone"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SAST)
    return dt.astimezone(SAST)

def format_datetime(dt, format_string='%Y-%m-%d %H:%M:%S'):
    """Format datetime in South African timezone"""
    if dt is None:
        return ''
    
    # Assume stored datetime is already in GMT+2 (SAST)
    if dt.tzinfo is None:
        # Add 2 hours if stored as UTC
        if hasattr(dt, '_is_utc') and dt._is_utc:
            dt = dt + timedelta(hours=2)
    else:
        dt = dt.astimezone(SAST)
    return dt.strftime(format_string)

def format_date(dt, format_string='%Y-%m-%d'):
    """Format date in South African timezone"""
    if dt.tzinfo is None:
        dt = localize_datetime(dt)
    else:
        dt = dt.astimezone(SAST)
    return dt.strftime(format_string)

def format_time(dt, format_string='%H:%M:%S'):
    """Format time in South African timezone"""
    if dt.tzinfo is None:
        dt = localize_datetime(dt)
    else:
        dt = dt.astimezone(SAST)
    return dt.strftime(format_string)

def to_utc(dt):
    """Convert South African time to UTC"""
    if dt.tzinfo is None:
        dt = localize_datetime(dt)
    return dt.astimezone(timezone.utc)

def from_utc(dt):
    """Convert UTC time to South African timezone"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST)

# Template filters for Jinja2
def datetime_filter(dt):
    """Jinja2 filter for datetime formatting"""
    return format_datetime(dt)

def date_filter(dt):
    """Jinja2 filter for date formatting"""
    return format_date(dt)

def time_filter(dt):
    """Jinja2 filter for time formatting"""
    return format_time(dt)