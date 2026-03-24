import requests
import json
import os
from pathlib import Path

def verify_kaggle_requests():
    # Load credentials from settings.json
    settings_path = Path("backend/data/settings.json")
    if not settings_path.exists():
        print("Error: settings.json not found")
        return
        
    with open(settings_path) as f:
        data = json.load(f)
        username = data.get('kaggle_username', '')
        key = data.get('kaggle_api_key', '')
        
    if not username or not key:
        print("Error: Kaggle credentials not found in settings.json")
        return
        
    print(f"Verifying credentials for {username} via direct requests...")
    
    # Kaggle API v1 endpoint
    url = "https://www.kaggle.com/api/v1/competitions/list"
    
    try:
        response = requests.get(url, auth=(username, key))
        print(f"Response Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Credentials are VALID!")
        elif response.status_code == 401:
            print("✗ Credentials are INVALID (401 Unauthorized)")
            print(f"Response: {response.text}")
        else:
            print(f"? Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    verify_kaggle_requests()
