#!/usr/bin/env python3

import requests
import sys
import json
import base64
from datetime import datetime
from pathlib import Path
from PIL import Image
import io

class RBACTrainingTester:
    def __init__(self, base_url="https://brain-scan-ai-11.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_session = requests.Session()
        self.doctor_session = requests.Session()
        self.nurse_session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.doctor_user_id = None
        self.nurse_user_id = None

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, session, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/api{endpoint}"
        headers = {'Content-Type': 'application/json'} if not files else {}

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = session.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = session.post(url, data=data, files=files)
                else:
                    response = session.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = session.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = session.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def setup_users(self):
        """Setup admin, doctor, and nurse users"""
        self.log("🚀 Setting up test users...")
        
        # Login as admin
        success, _ = self.run_test(
            "Admin Login",
            self.admin_session,
            "POST",
            "/auth/login",
            200,
            data={"email": "admin@example.com", "password": "admin123"}
        )
        if not success:
            return False

        # Register doctor user
        timestamp = datetime.now().strftime('%H%M%S')
        success, doctor_data = self.run_test(
            "Register Doctor User",
            self.doctor_session,
            "POST",
            "/auth/register",
            200,
            data={
                "email": f"doctor{timestamp}@test.com",
                "password": "testpass123",
                "name": f"Dr. Test {timestamp}"
            }
        )
        if success:
            self.doctor_user_id = doctor_data.get('id')
            self.log(f"   Doctor registered with role: {doctor_data.get('role')}")

        # Register nurse user (will be doctor by default)
        success, nurse_data = self.run_test(
            "Register Nurse User",
            self.nurse_session,
            "POST",
            "/auth/register",
            200,
            data={
                "email": f"nurse{timestamp}@test.com",
                "password": "testpass123",
                "name": f"Nurse Test {timestamp}"
            }
        )
        if success:
            self.nurse_user_id = nurse_data.get('id')
            self.log(f"   Nurse registered with role: {nurse_data.get('role')}")

        return True

    def test_admin_endpoints(self):
        """Test admin-only endpoints"""
        self.log("\n=== Testing Admin Endpoints ===")
        
        # Test GET /api/admin/users (admin only)
        success, users_data = self.run_test(
            "Get Users List (Admin Only)",
            self.admin_session,
            "GET",
            "/admin/users",
            200
        )
        
        if success and users_data:
            self.log(f"   Found {len(users_data)} users")
            
            # Change nurse user role to nurse
            if self.nurse_user_id:
                success, _ = self.run_test(
                    "Change User Role to Nurse",
                    self.admin_session,
                    "PUT",
                    f"/admin/users/{self.nurse_user_id}/role",
                    200,
                    data={"role": "nurse"}
                )
                if success:
                    self.log("   Successfully changed user role to nurse")

        # Test non-admin cannot access admin endpoints
        success, _ = self.run_test(
            "Doctor Access Admin Users (Should Fail)",
            self.doctor_session,
            "GET",
            "/admin/users",
            403
        )

        return True

    def test_rbac_permissions(self):
        """Test role-based access control permissions"""
        self.log("\n=== Testing RBAC Permissions ===")
        
        # Test nurse cannot create patients (should get 403)
        success, _ = self.run_test(
            "Nurse Create Patient (Should Fail - 403)",
            self.nurse_session,
            "POST",
            "/patients",
            403,
            data={
                "name": "Test Patient",
                "age": 45,
                "gender": "male",
                "medical_history": "Test history"
            }
        )

        # Test nurse cannot analyze scans (should get 403)
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        success2, _ = self.run_test(
            "Nurse Analyze Scan (Should Fail - 403)",
            self.nurse_session,
            "POST",
            "/scans/analyze",
            403,
            files={'file': ('test.png', img_bytes, 'image/png')},
            data={'patient_name': 'Test Patient'}
        )

        # Test doctor can create patients
        success3, patient_data = self.run_test(
            "Doctor Create Patient (Should Succeed)",
            self.doctor_session,
            "POST",
            "/patients",
            200,
            data={
                "name": "Doctor Test Patient",
                "age": 50,
                "gender": "female",
                "medical_history": "Created by doctor"
            }
        )

        return success and success2 and success3

    def test_training_endpoints(self):
        """Test training endpoints"""
        self.log("\n=== Testing Training Endpoints ===")
        
        # Test GET /api/training/status (all authenticated users)
        success1, status_data = self.run_test(
            "Get Training Status",
            self.doctor_session,
            "GET",
            "/training/status",
            200
        )
        
        if success1:
            self.log(f"   Training status: is_trained={status_data.get('is_trained')}, total_samples={status_data.get('total_samples')}")

        # Test GET /api/training/history (all authenticated users)
        success2, history_data = self.run_test(
            "Get Training History",
            self.doctor_session,
            "GET",
            "/training/history",
            200
        )

        # Test POST /api/training/upload (doctor+ only)
        img = Image.new('RGB', (256, 256), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        success3, upload_data = self.run_test(
            "Upload Training Sample (Doctor)",
            self.doctor_session,
            "POST",
            "/training/upload",
            200,
            files={'file': ('hemorrhagic_sample.png', img_bytes, 'image/png')},
            data={'label': 'hemorrhagic'}
        )

        # Test nurse cannot upload training data
        img2 = Image.new('RGB', (256, 256), color='green')
        img_bytes2 = io.BytesIO()
        img2.save(img_bytes2, format='PNG')
        img_bytes2.seek(0)
        
        success4, _ = self.run_test(
            "Nurse Upload Training Sample (Should Fail - 403)",
            self.nurse_session,
            "POST",
            "/training/upload",
            403,
            files={'file': ('ischemic_sample.png', img_bytes2, 'image/png')},
            data={'label': 'ischemic'}
        )

        # Test POST /api/training/train (admin only, will fail due to insufficient samples)
        success5, train_data = self.run_test(
            "Trigger Training (Admin - Expected 400 due to insufficient samples)",
            self.admin_session,
            "POST",
            "/training/train",
            400
        )

        # Test doctor cannot trigger training
        success6, _ = self.run_test(
            "Doctor Trigger Training (Should Fail - 403)",
            self.doctor_session,
            "POST",
            "/training/train",
            403
        )

        return success1 and success2 and success3 and success4 and success5 and success6

    def test_registration_default_role(self):
        """Test that new registrations get 'doctor' role by default"""
        self.log("\n=== Testing Registration Default Role ===")
        
        timestamp = datetime.now().strftime('%H%M%S')
        new_session = requests.Session()
        
        success, user_data = self.run_test(
            "Register New User (Should Get Doctor Role)",
            new_session,
            "POST",
            "/auth/register",
            200,
            data={
                "email": f"newuser{timestamp}@test.com",
                "password": "testpass123",
                "name": f"New User {timestamp}"
            }
        )
        
        if success:
            returned_role = user_data.get('role')
            if returned_role == 'doctor':
                self.log(f"✅ New user correctly assigned 'doctor' role")
                return True
            else:
                self.log(f"❌ New user got '{returned_role}' role instead of 'doctor'")
                return False
        
        return False

def main():
    print("🧠 NeuroScan AI - RBAC & Training Features Test")
    print("=" * 60)
    
    tester = RBACTrainingTester()
    
    # Setup users
    if not tester.setup_users():
        print("❌ Failed to setup test users")
        return 1
    
    # Test admin endpoints
    tester.test_admin_endpoints()
    
    # Test RBAC permissions
    tester.test_rbac_permissions()
    
    # Test training endpoints
    tester.test_training_endpoints()
    
    # Test registration default role
    tester.test_registration_default_role()
    
    # Print results
    print(f"\n📊 RBAC & Training Tests Summary")
    print("=" * 60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.tests_passed >= tester.tests_run * 0.8:
        print("✅ Backend RBAC & Training tests mostly successful")
        return 0
    else:
        print("❌ Backend RBAC & Training tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())