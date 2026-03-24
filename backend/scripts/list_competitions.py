import requests
import json
import os
from pathlib import Path

def list_user_competitions():
    # Load credentials from settings.json
    settings_path = Path("backend/data/settings.json")
    if not settings_path.exists():
        print("Error: settings.json not found")
        return
        
    with open(settings_path) as f:
        data = json.load(f)
        username = data.get('kaggle_username', '')
        key = data.get('kaggle_api_key', '')
        
    print(f"Listing competitions for {username}...")
    
    # Try to list all competitions
    url = "https://www.kaggle.com/api/v1/competitions/list"
    headers = {"Authorization": f"Bearer {key}"} if key.startswith("KGAT_") else {}
    auth = (username, key) if not key.startswith("KGAT_") else None
    
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        competitions = response.json()
        
        print(f"Found {len(competitions)} competitions:")
        for comp in competitions[:20]: # Show first 20
            print(f"  - {comp.get('ref')} ({comp.get('title')})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_user_competitions()
