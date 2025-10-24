#!/usr/bin/env python3

import requests
import json

# Test the simplified dashboard endpoint
url = "http://localhost:8000/admin/dashboard"

# Test data (you'll need to get a real JWT token)
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OGNhOTY2OTdlZWVhZmFkMTA1Mjc4MGIiLCJlbWFpbCI6ImFkbWluQGxoLmlvLmluIiwicm9sZSI6IkFETUlOIiwiZXhwIjoxNzI4MjE3NDcyfQ.sXI1w-x7FqZGZBNOdOFVPdKrJmNQGQ2lBrE-VjZ6JT4",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n=== Dashboard Response ===")
        print(json.dumps(data, indent=2))
        
        # Show simplified structure
        print(f"\n=== Summary ===")
        print(f"Stats: {data.get('stats', {})}")
        print(f"Total Users: {len(data.get('users', []))}")
        print(f"Total Supervisors: {len(data.get('supervisors', []))}")
        print(f"Total Guards: {len(data.get('guards', []))}")
        
        # Show sample data with proper formatting
        if data.get('users'):
            print(f"\nSample User: {data['users'][0]}")
            admin_users = [u for u in data['users'] if 'area' in u]
            if admin_users:
                print(f"Sample Admin User (with area): {admin_users[0]}")
        if data.get('supervisors'):
            print(f"Sample Supervisor (no area): {data['supervisors'][0]}")
        if data.get('guards'):
            print(f"Sample Guard (no area): {data['guards'][0]}")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Error: {e}")