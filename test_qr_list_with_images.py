#!/usr/bin/env python3

import requests
import json
import base64
from io import BytesIO

# Test the updated QR list endpoint with images
url = "http://localhost:8000/qr/list"

# Use the supervisor token from your example
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNjhkMzdlYmZhOTUyZDIzNDQwYWY5ZWNhIiwiZW1haWwiOm51bGwsInBob25lIjoiODgwMjc2NDM4MCIsInJvbGUiOiJTVVBFUlZJU09SIiwiZXhwIjoxNzkxMjg3MDA3LCJ0eXBlIjoiYWNjZXNzIn0.IzQX-LI3mF1XCFaiVwv6OzpGxNvZYJeTwf0nLRYjD88",
    "Accept": "application/json"
}

params = {
    "site": "Google"
}

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n=== QR List Response ===")
        print(f"Total QR codes: {data.get('total', 0)}")
        print(f"Site filter: {data.get('site_filter', 'None')}")
        print(f"Message: {data.get('message', '')}")
        
        qr_codes = data.get('qr_codes', [])
        for i, qr in enumerate(qr_codes):
            print(f"\n--- QR Code {i+1} ---")
            print(f"QR ID: {qr.get('qr_id')}")
            print(f"Site: {qr.get('site')}")
            print(f"Post: {qr.get('post')}")
            print(f"QR Content: {qr.get('qr_content')}")
            print(f"QR Image URL: {qr.get('qr_image_url')}")
            print(f"Created: {qr.get('created_at')}")
            
            # Show how to use the QR image data
            qr_image = qr.get('qr_image')
            if qr_image:
                print(f"✓ QR Image available (data:image/png format)")
                print("  - This can be used directly in:")
                print("    * HTML: <img src=\"{qr_image}\" />")
                print("    * Mobile apps: ImageView.setImageBitmap()")
                print("    * Web browsers: Direct display")
                
                # Optionally save the image to file for testing
                if qr_image.startswith("data:image/png;base64,"):
                    try:
                        base64_data = qr_image.split(",")[1]
                        image_data = base64.b64decode(base64_data)
                        with open(f"qr_code_{i+1}.png", "wb") as f:
                            f.write(image_data)
                        print(f"    * Saved as: qr_code_{i+1}.png")
                    except Exception as e:
                        print(f"    * Could not save image: {e}")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Error: {e}")

print("\n=== How to Use QR Images ===")
print("The 'qr_image' field contains a data URL that can be used directly:")
print("1. In HTML: <img src=\"data:image/png;base64,...\" />")
print("2. In mobile apps: Convert base64 to bitmap/image")
print("3. In web applications: Set as src attribute")
print("4. Save to file: Decode base64 and write to .png file")