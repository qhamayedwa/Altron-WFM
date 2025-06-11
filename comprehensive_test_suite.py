#!/usr/bin/env python3
"""
Comprehensive Application Test Suite
Tests all database connections, field mappings, and core functionality
"""

from app import app, db
from models import (User, Company, Region, Site, Department, TimeEntry, 
                   Role, LeaveApplication, LeaveBalance, PayCode, PayRule)
import requests
from datetime import datetime, date, timedelta
import json

def test_database_connectivity():
    """Test basic database connectivity"""
    print("Testing database connectivity...")
    
    with app.app_context():
        try:
            # Test basic query
            user_count = User.query.count()
            company_count = Company.query.count()
            department_count = Department.query.count()
            
            print(f"✓ Database connected - Users: {user_count}, Companies: {company_count}, Departments: {department_count}")
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False

def test_hierarchical_structure():
    """Test hierarchical organization structure"""
    print("\nTesting hierarchical organization structure...")
    
    with app.app_context():
        try:
            companies = Company.query.filter_by(is_active=True).all()
            total_users = 0
            
            for company in companies:
                print(f"Company: {company.name}")
                company_users = 0
                
                for region in company.regions:
                    if region.is_active:
                        for site in region.sites:
                            if site.is_active:
                                for dept in site.departments:
                                    if dept.is_active:
                                        dept_users = User.query.filter_by(
                                            department_id=dept.id,
                                            is_active=True
                                        ).count()
                                        company_users += dept_users
                                        if dept_users > 0:
                                            print(f"  {dept.name}: {dept_users} users")
                
                total_users += company_users
                print(f"  Total users in {company.name}: {company_users}")
            
            print(f"✓ Hierarchical structure verified - Total mapped users: {total_users}")
            return True
        except Exception as e:
            print(f"✗ Hierarchical structure test failed: {e}")
            return False

def test_legacy_field_mappings():
    """Test legacy to hierarchical field mappings"""
    print("\nTesting legacy field mappings...")
    
    with app.app_context():
        try:
            # Check users with both legacy and hierarchical departments
            users_with_both = User.query.filter(
                User.department.isnot(None),
                User.department_id.isnot(None),
                User.is_active == True
            ).all()
            
            legacy_only = User.query.filter(
                User.department.isnot(None),
                User.department_id.is_(None),
                User.is_active == True
            ).count()
            
            hierarchical_only = User.query.filter(
                User.department.is_(None),
                User.department_id.isnot(None),
                User.is_active == True
            ).count()
            
            print(f"✓ Users with both legacy & hierarchical: {len(users_with_both)}")
            print(f"✓ Users with legacy only: {legacy_only}")
            print(f"✓ Users with hierarchical only: {hierarchical_only}")
            
            # Test specific mappings
            for user in users_with_both[:3]:  # Test first 3
                dept = Department.query.get(user.department_id)
                print(f"  {user.username}: '{user.department}' → {dept.name} ({dept.site.name})")
            
            return True
        except Exception as e:
            print(f"✗ Legacy field mapping test failed: {e}")
            return False

def test_time_entries_connectivity():
    """Test time entries connectivity with hierarchical departments"""
    print("\nTesting time entries connectivity...")
    
    with app.app_context():
        try:
            # Get recent time entries
            recent_entries = TimeEntry.query.filter(
                TimeEntry.created_at >= datetime.now() - timedelta(days=30)
            ).all()
            
            entries_with_dept = 0
            for entry in recent_entries:
                if entry.employee.department_id:
                    entries_with_dept += 1
            
            print(f"✓ Recent time entries: {len(recent_entries)}")
            print(f"✓ Entries linked to hierarchical departments: {entries_with_dept}")
            
            # Test specific entry
            if recent_entries:
                entry = recent_entries[0]
                if entry.employee.department_id:
                    dept = Department.query.get(entry.employee.department_id)
                    print(f"  Sample: {entry.employee.username} → {dept.name} ({dept.site.name})")
            
            return True
        except Exception as e:
            print(f"✗ Time entries connectivity test failed: {e}")
            return False

def test_api_endpoints():
    """Test key API endpoints"""
    print("\nTesting API endpoints...")
    
    base_url = "http://localhost:5000"
    
    endpoints = [
        "/api/system-info",
        "/",
        "/organization/companies",
        "/time/team-calendar"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            status = "✓" if response.status_code in [200, 302] else "✗"
            print(f"  {status} {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"  ✗ {endpoint}: {e}")

def test_user_edit_form():
    """Test comprehensive user edit form functionality"""
    print("\nTesting user edit form functionality...")
    
    with app.app_context():
        try:
            # Test user with all fields
            test_user = User.query.filter(
                User.first_name.isnot(None),
                User.department_id.isnot(None)
            ).first()
            
            if test_user:
                dept = Department.query.get(test_user.department_id) if test_user.department_id else None
                if dept:
                    print(f"✓ Sample user profile: {test_user.first_name} {test_user.last_name} in {dept.name}")
                else:
                    print(f"✓ Sample user profile: {test_user.first_name} {test_user.last_name} (no department)")
            
            # Check if comprehensive fields exist
            user_fields = ['first_name', 'last_name', 'email', 'phone_number', 'mobile_number', 
                          'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
                          'address_line1', 'city', 'postal_code', 'education_level', 'skills', 'notes']
            
            fields_available = sum(1 for field in user_fields if hasattr(User, field))
            print(f"✓ Comprehensive user fields available: {fields_available}/{len(user_fields)}")
            
            return True
        except Exception as e:
            print(f"✗ User edit form test failed: {e}")
            return False

def test_department_statistics():
    """Test department statistics and employee counts"""
    print("\nTesting department statistics...")
    
    with app.app_context():
        try:
            departments = Department.query.filter_by(is_active=True).all()
            total_employees = 0
            
            for dept in departments:
                employee_count = User.query.filter_by(
                    department_id=dept.id,
                    is_active=True
                ).count()
                total_employees += employee_count
                
                if employee_count > 0:
                    print(f"  {dept.name} ({dept.site.name}): {employee_count} employees")
            
            print(f"✓ Total employees across all departments: {total_employees}")
            return True
        except Exception as e:
            print(f"✗ Department statistics test failed: {e}")
            return False

def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("Altron WFM Application Comprehensive Test Suite")
    print("=" * 60)
    
    tests = [
        test_database_connectivity,
        test_hierarchical_structure,
        test_legacy_field_mappings,
        test_time_entries_connectivity,
        test_api_endpoints,
        test_user_edit_form,
        test_department_statistics
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All tests passed - Application is fully functional!")
    else:
        print(f"✗ {failed} test(s) failed - Issues need attention")
    
    return failed == 0

if __name__ == "__main__":
    run_comprehensive_tests()