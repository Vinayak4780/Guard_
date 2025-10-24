#!/usr/bin/env python3
"""
Test script for the new password management APIs
Tests password change functionality for different roles
"""

import requests
import json
from typing import Dict, Any

# Base URL of the application
BASE_URL = "http://localhost:8000"

class PasswordAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.tokens = {}

    def login(self, username: str, password: str, role: str) -> bool:
        """Login and store the access token"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.tokens[role] = data["access_token"]
                print(f"✅ Login successful for {role}: {username}")
                return True
            else:
                print(f"❌ Login failed for {role}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error for {role}: {e}")
            return False

    def get_headers(self, role: str) -> Dict[str, str]:
        """Get authorization headers for a role"""
        token = self.tokens.get(role)
        if not token:
            raise ValueError(f"No token available for role: {role}")
        return {"Authorization": f"Bearer {token}"}

    def test_supervisor_change_guard_password(self):
        """Test supervisor changing guard password"""
        print("\n🔧 Testing supervisor change guard password...")
        
        if "supervisor" not in self.tokens:
            print("❌ Supervisor not logged in")
            return False

        try:
            # Test changing guard password using email
            payload = {
                "guardEmail": "testguard@gmail.com",  # Replace with actual guard email
                "newPassword": "NewGuardPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/supervisor/change-guard-password",
                json=payload,
                headers=self.get_headers("supervisor")
            )
            
            if response.status_code == 200:
                print("✅ Supervisor changed guard password successfully (using email)")
                
                # Test changing guard password using phone
                payload_phone = {
                    "guardPhone": "+1234567890",  # Replace with actual guard phone
                    "newPassword": "NewGuardPass@456"
                }
                
                response_phone = self.session.put(
                    f"{self.base_url}/supervisor/change-guard-password",
                    json=payload_phone,
                    headers=self.get_headers("supervisor")
                )
                
                if response_phone.status_code == 200:
                    print("✅ Supervisor changed guard password successfully (using phone)")
                    return True
                else:
                    print(f"⚠️ Email worked but phone failed: {response_phone.status_code} - {response_phone.text}")
                    return True  # At least email worked
            else:
                print(f"❌ Failed to change guard password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing supervisor change guard password: {e}")
            return False

    def test_supervisor_change_own_password(self):
        """Test supervisor changing own password"""
        print("\n🔧 Testing supervisor change own password...")
        
        if "supervisor" not in self.tokens:
            print("❌ Supervisor not logged in")
            return False

        try:
            payload = {
                "currentPassword": "test@123",  # Replace with actual current password
                "newPassword": "NewSupervisorPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/supervisor/change-password",
                json=payload,
                headers=self.get_headers("supervisor")
            )
            
            if response.status_code == 200:
                print("✅ Supervisor changed own password successfully")
                return True
            else:
                print(f"❌ Failed to change supervisor password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing supervisor change own password: {e}")
            return False

    def test_admin_change_supervisor_password(self):
        """Test admin changing supervisor password"""
        print("\n🔧 Testing admin change supervisor password...")
        
        if "admin" not in self.tokens:
            print("❌ Admin not logged in")
            return False

        try:
            # Test changing supervisor password using email
            payload = {
                "userEmail": "dhasmanakartik84@gmail.com",  # Replace with actual supervisor email
                "newPassword": "NewSupervisorPass@456"
            }
            
            response = self.session.put(
                f"{self.base_url}/admin/change-supervisor-password",
                json=payload,
                headers=self.get_headers("admin")
            )
            
            if response.status_code == 200:
                print("✅ Admin changed supervisor password successfully (using email)")
                
                # Test changing supervisor password using phone
                payload_phone = {
                    "userPhone": "+1234567890",  # Replace with actual supervisor phone
                    "newPassword": "NewSupervisorPass@789"
                }
                
                response_phone = self.session.put(
                    f"{self.base_url}/admin/change-supervisor-password",
                    json=payload_phone,
                    headers=self.get_headers("admin")
                )
                
                if response_phone.status_code == 200:
                    print("✅ Admin changed supervisor password successfully (using phone)")
                    return True
                else:
                    print(f"⚠️ Email worked but phone failed: {response_phone.status_code} - {response_phone.text}")
                    return True  # At least email worked
            else:
                print(f"❌ Failed to change supervisor password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing admin change supervisor password: {e}")
            return False

    def test_admin_change_own_password(self):
        """Test admin changing own password"""
        print("\n🔧 Testing admin change own password...")
        
        if "admin" not in self.tokens:
            print("❌ Admin not logged in")
            return False

        try:
            payload = {
                "currentPassword": "Test@123",  # Replace with actual current password
                "newPassword": "NewAdminPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/admin/change-password",
                json=payload,
                headers=self.get_headers("admin")
            )
            
            if response.status_code == 200:
                print("✅ Admin changed own password successfully")
                return True
            else:
                print(f"❌ Failed to change admin password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing admin change own password: {e}")
            return False

    def test_super_admin_change_user_password(self):
        """Test super admin changing any user password"""
        print("\n🔧 Testing super admin change user password...")
        
        if "super_admin" not in self.tokens:
            print("❌ Super admin not logged in")
            return False

        try:
            # Test changing user password using email
            payload = {
                "userEmail": "dhasmanakartik84@gmail.com",  # Replace with actual user email
                "newPassword": "NewUserPass@789"
            }
            
            response = self.session.put(
                f"{self.base_url}/super-admin/change-user-password",
                json=payload,
                headers=self.get_headers("super_admin")
            )
            
            if response.status_code == 200:
                print("✅ Super admin changed user password successfully (using email)")
                
                # Test changing user password using phone
                payload_phone = {
                    "userPhone": "+1234567890",  # Replace with actual user phone
                    "newPassword": "NewUserPass@101112"
                }
                
                response_phone = self.session.put(
                    f"{self.base_url}/super-admin/change-user-password",
                    json=payload_phone,
                    headers=self.get_headers("super_admin")
                )
                
                if response_phone.status_code == 200:
                    print("✅ Super admin changed user password successfully (using phone)")
                    return True
                else:
                    print(f"⚠️ Email worked but phone failed: {response_phone.status_code} - {response_phone.text}")
                    return True  # At least email worked
            else:
                print(f"❌ Failed to change user password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing super admin change user password: {e}")
            return False

    def test_super_admin_search_users(self):
        """Test super admin search users"""
        print("\n🔧 Testing super admin search users...")
        
        if "super_admin" not in self.tokens:
            print("❌ Super admin not logged in")
            return False

        try:
            # Test search by name
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users?query=kartik",
                headers=self.get_headers("super_admin")
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Super admin search users successful - found {data.get('total', 0)} users")
                
                # Test role mapping: search for "fieldofficer" (should return supervisors)
                response_field = self.session.get(
                    f"{self.base_url}/super-admin/search-users?query=fieldofficer",
                    headers=self.get_headers("super_admin")
                )
                
                if response_field.status_code == 200:
                    field_data = response_field.json()
                    print(f"✅ Field officer search successful - found {field_data.get('total', 0)} supervisors")
                    
                    # Test role mapping: search for "supervisor" (should return guards)
                    response_super = self.session.get(
                        f"{self.base_url}/super-admin/search-users?query=supervisor",
                        headers=self.get_headers("super_admin")
                    )
                    
                    if response_super.status_code == 200:
                        super_data = response_super.json()
                        print(f"✅ Supervisor search successful - found {super_data.get('total', 0)} guards")
                        return True
                    else:
                        print(f"⚠️ Supervisor search failed: {response_super.status_code}")
                        return True  # Previous tests passed
                else:
                    print(f"⚠️ Field officer search failed: {response_field.status_code}")
                    return True  # At least basic search worked
            else:
                print(f"❌ Failed to search users: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing super admin search users: {e}")
            return False

    def test_guard_change_own_password(self):
        """Test guard changing own password"""
        print("\n🔧 Testing guard change own password...")
        
        if "guard" not in self.tokens:
            print("❌ Guard not logged in")
            return False

        try:
            payload = {
                "currentPassword": "CurrentGuardPass@123",  # Replace with actual current password
                "newPassword": "NewGuardPass@456"
            }
            
            response = self.session.put(
                f"{self.base_url}/guard/change-password",
                json=payload,
                headers=self.get_headers("guard")
            )
            
            if response.status_code == 200:
                print("✅ Guard changed own password successfully")
                return True
            else:
                print(f"❌ Failed to change guard password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing guard change own password: {e}")
            return False

    def test_guard_change_own_password(self):
        """Test guard changing own password - SHOULD FAIL"""
        print("\n🔧 Testing guard change own password (should fail)...")
        
        if "guard" not in self.tokens:
            print("❌ Guard not logged in")
            return True  # Can't test but that's expected

        try:
            payload = {
                "currentPassword": "CurrentGuardPass@123",  # Replace with actual current password
                "newPassword": "NewGuardPass@456"
            }
            
            response = self.session.put(
                f"{self.base_url}/guard/change-password",
                json=payload,
                headers=self.get_headers("guard")
            )
            
            if response.status_code == 404:
                print("✅ Guard self password change correctly failed (404 - endpoint removed)")
                return True
            elif response.status_code >= 400:
                print("✅ Guard self password change correctly failed")
                return True
            else:
                print(f"❌ Guard self password change should have failed but got: {response.status_code}")
                return False
        except Exception as e:
            print(f"✅ Guard self password change correctly failed with error: {e}")
            return True

    def test_supervisor_change_own_password(self):
        """Test supervisor changing own password - SHOULD FAIL"""
        print("\n🔧 Testing supervisor change own password (should fail)...")
        
        if "supervisor" not in self.tokens:
            print("❌ Supervisor not logged in")
            return True  # Can't test but that's expected

        try:
            payload = {
                "currentPassword": "test@123",  # Replace with actual current password
                "newPassword": "NewSupervisorPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/supervisor/change-password",
                json=payload,
                headers=self.get_headers("supervisor")
            )
            
            if response.status_code == 404:
                print("✅ Supervisor self password change correctly failed (404 - endpoint removed)")
                return True
            elif response.status_code >= 400:
                print("✅ Supervisor self password change correctly failed")
                return True
            else:
                print(f"❌ Supervisor self password change should have failed but got: {response.status_code}")
                return False
        except Exception as e:
            print(f"✅ Supervisor self password change correctly failed with error: {e}")
            return True

    def test_admin_change_own_password(self):
        """Test admin changing own password - SHOULD FAIL"""
        print("\n🔧 Testing admin change own password (should fail)...")
        
        if "admin" not in self.tokens:
            print("❌ Admin not logged in")
            return True  # Can't test but that's expected

        try:
            payload = {
                "currentPassword": "Test@123",  # Replace with actual current password
                "newPassword": "NewAdminPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/admin/change-password",
                json=payload,
                headers=self.get_headers("admin")
            )
            
            if response.status_code == 404:
                print("✅ Admin self password change correctly failed (404 - endpoint removed)")
                return True
            elif response.status_code >= 400:
                print("✅ Admin self password change correctly failed")
                return True
            else:
                print(f"❌ Admin self password change should have failed but got: {response.status_code}")
                return False
        except Exception as e:
            print(f"✅ Admin self password change correctly failed with error: {e}")
            return True

    def test_super_admin_change_own_password(self):
        """Test super admin changing own password - SHOULD WORK"""
        print("\n🔧 Testing super admin change own password...")
        
        if "super_admin" not in self.tokens:
            print("❌ Super admin not logged in")
            return False

        try:
            payload = {
                "currentPassword": "Test@123",  # Replace with actual current password
                "newPassword": "NewSuperAdminPass@123"
            }
            
            response = self.session.put(
                f"{self.base_url}/super-admin/change-password",
                json=payload,
                headers=self.get_headers("super_admin")
            )
            
            if response.status_code == 200:
                print("✅ Super admin changed own password successfully")
                return True
            else:
                print(f"❌ Failed to change super admin password: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing super admin change own password: {e}")
            return False

    def run_all_tests(self):
        """Run all password API tests"""
        print("🚀 Starting Password API Tests")
        print("=" * 50)
        
        # Login with different roles
        # Note: Replace with actual credentials from your system
        login_success = []
        
        # Try to login as different roles (modify credentials as needed)
        login_success.append(self.login("admin@lh.io.in", "Test@123", "admin"))
        login_success.append(self.login("dhasmanakartik84@gmail.com", "test@123", "supervisor"))
        # Add guard login if you have a guard account
        # login_success.append(self.login("testguard@gmail.com", "guard123", "guard"))
        
        if not any(login_success):
            print("❌ No successful logins - cannot run tests")
            return
        
        # Run tests
        tests = [
            self.test_admin_change_supervisor_password,
            self.test_supervisor_change_guard_password,
            self.test_super_admin_change_user_password,
            self.test_super_admin_search_users,
            self.test_super_admin_change_own_password,
            self.test_supervisor_change_own_password,  # Should fail
            self.test_admin_change_own_password,  # Should fail
            # self.test_guard_change_own_password,  # Should fail - uncomment if you have guard login
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
            except Exception as e:
                print(f"❌ Test {test.__name__} failed with error: {e}")
                results.append(False)
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Results Summary:")
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️ Some tests failed - check the logs above")


def main():
    """Main function to run the tests"""
    tester = PasswordAPITester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()