#!/usr/bin/env python3
"""
Quick database reset using existing Lambda functions.
This will create the test user that's needed for development.
"""

import os
import sys
import json
import requests

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def create_test_user_via_api():
    """Create test user by calling API directly."""
    api_url = "https://8sm0pyqys1.execute-api.us-east-1.amazonaws.com/api/v1/income"
    
    # First try to create an income entry - this should trigger user creation
    test_payload = {
        "amount": 1.00,
        "source": "Setup", 
        "date": "2026-04-27",
        "notes": "Initial setup - will be deleted"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Origin": "http://pfip-staging-frontend.s3-website-us-east-1.amazonaws.com",
        "Authorization": "Bearer local-dev-token"
    }
    
    try:
        response = requests.post(api_url, json=test_payload, headers=headers, timeout=30)
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {response.text}")
        
        if response.status_code == 201:
            print("✅ Test user created successfully!")
            return True
        else:
            print(f"❌ Failed to create test user: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return False


def main():
    print("Creating test user via API call...")
    success = create_test_user_via_api()
    
    if success:
        print("\n✅ Database setup completed!")
        sys.exit(0)
    else:
        print("\n❌ Database setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
