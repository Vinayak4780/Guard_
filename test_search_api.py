#!/usr/bin/env python3
"""
Test script for the updated search API with role parameter
Demonstrates the new role-based filtering functionality
"""

import requests
import json
from typing import Dict, Any

# Base URL of the application
BASE_URL = "http://localhost:8000"

class SearchAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.super_admin_token = None

    def login_super_admin(self, username: str, password: str) -> bool:
        """Login as super admin and store the access token"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.super_admin_token = data["access_token"]
                print(f"✅ Super Admin login successful: {username}")
                return True
            else:
                print(f"❌ Super Admin login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Super Admin login error: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for super admin"""
        if not self.super_admin_token:
            raise ValueError("No super admin token available")
        return {"Authorization": f"Bearer {self.super_admin_token}"}

    def test_search_without_role(self):
        """Test search without role parameter (searches all collections)"""
        print("\n🔍 Testing search without role parameter...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"query": "admin"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Search all collections successful. Found {len(data.get('users', []))} users")
                for user in data.get('users', [])[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) from {user.get('collection')}")
            else:
                print(f"❌ Search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Search error: {e}")

    def test_search_by_role_fieldofficer(self):
        """Test search with role=fieldofficer (should return supervisors)"""
        print("\n👷 Testing search with role=fieldofficer...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"role": "fieldofficer"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ Field officer search successful. Found {len(users)} supervisors")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Code: {user.get('code', 'N/A')}")
            else:
                print(f"❌ Field officer search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Field officer search error: {e}")

    def test_search_by_role_supervisor(self):
        """Test search with role=supervisor (should return guards)"""
        print("\n👮 Testing search with role=supervisor...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"role": "supervisor"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ Supervisor search successful. Found {len(users)} guards")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Employee Code: {user.get('employeeCode', 'N/A')}")
            else:
                print(f"❌ Supervisor search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Supervisor search error: {e}")

    def test_search_by_role_admin(self):
        """Test search with role=admin (should return admins)"""
        print("\n🔧 Testing search with role=admin...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"role": "admin"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ Admin search successful. Found {len(users)} admins")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Email: {user.get('email', 'N/A')}")
            else:
                print(f"❌ Admin search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Admin search error: {e}")

    def test_search_by_role_super_admin(self):
        """Test search with role=super_admin (should return super admins)"""
        print("\n⭐ Testing search with role=super_admin...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"role": "super_admin"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ Super admin search successful. Found {len(users)} super admins")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Email: {user.get('email', 'N/A')}")
            else:
                print(f"❌ Super admin search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Super admin search error: {e}")

    def test_search_with_query_and_role(self):
        """Test search with both query and role parameters"""
        print("\n🔍 Testing search with both query and role parameters...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"query": "john", "role": "fieldofficer"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ Combined search successful. Found {len(users)} supervisors named 'john'")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Code: {user.get('code', 'N/A')}")
            else:
                print(f"❌ Combined search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Combined search error: {e}")

    def test_search_with_state_filter(self):
        """Test search with state filter"""
        print("\n🏙️ Testing search with state filter...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/super-admin/search-users",
                params={"role": "fieldofficer", "state": "Mumbai"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                print(f"✅ State filter search successful. Found {len(users)} supervisors in Mumbai")
                for user in users[:3]:  # Show first 3 results
                    print(f"   - {user.get('name')} ({user.get('role')}) - Area: {user.get('areaCity', 'N/A')}")
            else:
                print(f"❌ State filter search failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ State filter search error: {e}")

    def run_all_tests(self):
        """Run all search API tests"""
        print("🚀 Starting Search API Tests with Role Parameter")
        print("=" * 60)
        
        # Note: You need to replace these with actual credentials
        if not self.login_super_admin("superadmin@example.com", "your_password"):
            print("❌ Failed to login as super admin. Please update credentials.")
            return
        
        self.test_search_without_role()
        self.test_search_by_role_fieldofficer()
        self.test_search_by_role_supervisor()
        self.test_search_by_role_admin()
        self.test_search_by_role_super_admin()
        self.test_search_with_query_and_role()
        self.test_search_with_state_filter()
        
        print("\n" + "=" * 60)
        print("🏁 Search API tests completed!")


if __name__ == "__main__":
    print("Search API Role Parameter Test Script")
    print("=====================================")
    print("This script tests the updated search API with the new 'role' parameter.")
    print("Make sure the server is running on http://localhost:8000")
    print("Update the super admin credentials before running the tests.")
    print()
    
    tester = SearchAPITester()
    tester.run_all_tests()