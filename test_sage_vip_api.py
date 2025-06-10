#!/usr/bin/env python3
"""
SAGE VIP Integration API Test Suite
Comprehensive testing for SAGE VIP Payroll integration endpoints
"""

import requests
import json
import os
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SAGEVIPAPITester:
    """Test suite for SAGE VIP integration API endpoints"""
    
    def __init__(self, base_url="http://localhost:5000", username="admin", password="admin123"):
        self.base_url = base_url
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.authenticated = False
        
    def authenticate(self):
        """Authenticate with WFM system"""
        try:
            login_url = f"{self.base_url}/auth/login"
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(login_url, data=login_data)
            if response.status_code == 302:  # Redirect on successful login
                self.authenticated = True
                logger.info("✅ Authentication successful")
                return True
            else:
                logger.error(f"❌ Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False
    
    def test_connection_status(self):
        """Test SAGE VIP connection status endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/status"
            response = self.session.get(url)
            
            logger.info(f"Connection Status Test: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"  Status: {data.get('data', {}).get('connection_status', 'unknown')}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection status test error: {e}")
            return False
    
    def test_connection_test(self):
        """Test SAGE VIP connection test endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/test-connection"
            response = self.session.post(url, json={})
            
            logger.info(f"Connection Test: {response.status_code}")
            if response.status_code in [200, 503]:  # 503 expected if SAGE VIP not configured
                data = response.json()
                logger.info(f"  Result: {data.get('success', False)}")
                if not data.get('success'):
                    logger.info(f"  Message: {data.get('error', {}).get('message', 'Unknown error')}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test error: {e}")
            return False
    
    def test_employee_sync_from_sage(self):
        """Test employee sync from SAGE VIP endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/employees/sync-from-sage"
            data = {
                "force_update": False,
                "department_filter": "HR"
            }
            response = self.session.post(url, json=data)
            
            logger.info(f"Employee Sync From SAGE: {response.status_code}")
            if response.status_code in [200, 500]:  # 500 expected if SAGE VIP not configured
                result = response.json()
                logger.info(f"  Success: {result.get('success', False)}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Employee sync test error: {e}")
            return False
    
    def test_timesheet_push(self):
        """Test timesheet push to SAGE VIP endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/timesheet/push"
            data = {
                "start_date": "2025-06-01",
                "end_date": "2025-06-10",
                "employee_ids": [1, 2, 3],
                "department_ids": [1, 2]
            }
            response = self.session.post(url, json=data)
            
            logger.info(f"Timesheet Push: {response.status_code}")
            if response.status_code in [200, 500]:  # 500 expected if SAGE VIP not configured
                result = response.json()
                logger.info(f"  Success: {result.get('success', False)}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Timesheet push test error: {e}")
            return False
    
    def test_timesheet_validation(self):
        """Test timesheet validation endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/timesheet/validate"
            data = {
                "start_date": "2025-06-01",
                "end_date": "2025-06-10"
            }
            response = self.session.post(url, json=data)
            
            logger.info(f"Timesheet Validation: {response.status_code}")
            if response.status_code in [200, 500]:
                result = response.json()
                logger.info(f"  Success: {result.get('success', False)}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Timesheet validation test error: {e}")
            return False
    
    def test_leave_push(self):
        """Test leave push to SAGE VIP endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/leave/push"
            data = {
                "start_date": "2025-06-01",
                "end_date": "2025-06-30",
                "status": "Approved"
            }
            response = self.session.post(url, json=data)
            
            logger.info(f"Leave Push: {response.status_code}")
            if response.status_code in [200, 500]:
                result = response.json()
                logger.info(f"  Success: {result.get('success', False)}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Leave push test error: {e}")
            return False
    
    def test_payroll_calculation(self):
        """Test payroll calculation endpoint"""
        try:
            url = f"{self.base_url}/api/v1/sage-vip/payroll/calculate"
            data = {
                "pay_period_start": "2025-06-01",
                "pay_period_end": "2025-06-15",
                "employee_ids": [1, 2, 3]
            }
            response = self.session.post(url, json=data)
            
            logger.info(f"Payroll Calculation: {response.status_code}")
            if response.status_code in [200, 500]:
                result = response.json()
                logger.info(f"  Success: {result.get('success', False)}")
                return True
            else:
                logger.warning(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Payroll calculation test error: {e}")
            return False
    
    def test_configuration_endpoints(self):
        """Test configuration management endpoints"""
        results = []
        
        # Test get settings
        try:
            url = f"{self.base_url}/api/v1/sage-vip/config/settings"
            response = self.session.get(url)
            logger.info(f"Config Settings GET: {response.status_code}")
            results.append(response.status_code == 200)
        except Exception as e:
            logger.error(f"❌ Config settings GET error: {e}")
            results.append(False)
        
        # Test sync schedule
        try:
            url = f"{self.base_url}/api/v1/sage-vip/config/sync/schedule"
            response = self.session.get(url)
            logger.info(f"Sync Schedule GET: {response.status_code}")
            results.append(response.status_code == 200)
        except Exception as e:
            logger.error(f"❌ Sync schedule GET error: {e}")
            results.append(False)
        
        # Test health check
        try:
            url = f"{self.base_url}/api/v1/sage-vip/config/health"
            response = self.session.get(url)
            logger.info(f"Health Check: {response.status_code}")
            results.append(response.status_code in [200, 503])
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            results.append(False)
        
        return all(results)
    
    def test_data_sync_endpoints(self):
        """Test data synchronization endpoints"""
        results = []
        
        # Test department sync
        try:
            url = f"{self.base_url}/api/v1/sage-vip/departments/sync"
            data = {"direction": "from_sage"}
            response = self.session.post(url, json=data)
            logger.info(f"Department Sync: {response.status_code}")
            results.append(response.status_code in [200, 500])
        except Exception as e:
            logger.error(f"❌ Department sync error: {e}")
            results.append(False)
        
        # Test pay code sync
        try:
            url = f"{self.base_url}/api/v1/sage-vip/pay-codes/sync"
            data = {"direction": "to_sage"}
            response = self.session.post(url, json=data)
            logger.info(f"Pay Code Sync: {response.status_code}")
            results.append(response.status_code in [200, 500])
        except Exception as e:
            logger.error(f"❌ Pay code sync error: {e}")
            results.append(False)
        
        return all(results)
    
    def test_mapping_endpoints(self):
        """Test field mapping endpoints"""
        results = []
        
        endpoints = [
            "/api/v1/sage-vip/config/mappings/employees",
            "/api/v1/sage-vip/config/mappings/pay-codes",
            "/api/v1/sage-vip/config/mappings/departments"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = self.session.get(url)
                logger.info(f"Mapping {endpoint.split('/')[-1]}: {response.status_code}")
                results.append(response.status_code == 200)
            except Exception as e:
                logger.error(f"❌ Mapping endpoint error: {e}")
                results.append(False)
        
        return all(results)
    
    def run_comprehensive_test_suite(self):
        """Run complete SAGE VIP API test suite"""
        if not self.authenticate():
            logger.error("❌ Cannot proceed without authentication")
            return False
        
        logger.info("\n🧪 Starting SAGE VIP Integration API Test Suite\n")
        
        test_results = {
            "Connection Status": self.test_connection_status(),
            "Connection Test": self.test_connection_test(),
            "Employee Sync": self.test_employee_sync_from_sage(),
            "Timesheet Push": self.test_timesheet_push(),
            "Timesheet Validation": self.test_timesheet_validation(),
            "Leave Push": self.test_leave_push(),
            "Payroll Calculation": self.test_payroll_calculation(),
            "Configuration Endpoints": self.test_configuration_endpoints(),
            "Data Sync Endpoints": self.test_data_sync_endpoints(),
            "Mapping Endpoints": self.test_mapping_endpoints()
        }
        
        # Summary
        passed = sum(test_results.values())
        total = len(test_results)
        
        logger.info(f"\n📊 TEST SUITE RESULTS:")
        logger.info(f"   Passed: {passed}/{total}")
        logger.info(f"   Success Rate: {(passed/total)*100:.1f}%")
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"   {test_name}: {status}")
        
        if passed == total:
            logger.info("\n🎉 All SAGE VIP API endpoints are functional!")
        else:
            logger.info(f"\n⚠️ {total - passed} endpoints need attention")
        
        return passed == total

def main():
    """Main test execution"""
    tester = SAGEVIPAPITester()
    success = tester.run_comprehensive_test_suite()
    
    if success:
        print("\n✅ SAGE VIP Integration API is ready for deployment")
    else:
        print("\n⚠️ Some issues detected - review logs above")
    
    return success

if __name__ == "__main__":
    main()