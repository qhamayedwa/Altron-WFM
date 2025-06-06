#!/usr/bin/env python3
"""
Simple timezone test to verify GMT+2 implementation
"""

from datetime import datetime, timezone, timedelta
from timezone_utils import get_current_time, format_datetime

def test_timezone():
    print("Testing GMT+2 timezone implementation...")
    
    # Get current UTC time
    utc_now = datetime.utcnow()
    print(f"Current UTC time: {utc_now}")
    
    # Get our GMT+2 time
    sast_time = get_current_time()
    print(f"Our GMT+2 time: {sast_time}")
    
    # Calculate expected GMT+2 time
    expected_sast = utc_now + timedelta(hours=2)
    print(f"Expected GMT+2 time: {expected_sast}")
    
    # Check if they match (within 1 second tolerance)
    time_diff = abs((sast_time - expected_sast).total_seconds())
    print(f"Time difference: {time_diff} seconds")
    
    if time_diff <= 1:
        print("✓ Timezone implementation is working correctly!")
    else:
        print("✗ Timezone implementation has issues")
    
    # Test formatting
    formatted = format_datetime(sast_time)
    print(f"Formatted time: {formatted}")

if __name__ == "__main__":
    test_timezone()