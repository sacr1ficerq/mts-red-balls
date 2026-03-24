import requests
import json
import os
from pathlib import Path

def verify_kaggle_access():
    # Load credentials from settings.json
    settings_path = Path("backend/data/settings.json")
    if not settings_path.exists():
        print("Error: settings.json not found")
        return
        
    with open(settings_path) as f:
        data = json.load(f)
        username = data.get('kaggle_username', '')
        key = data.get('kaggle_api_key', '')
        
    print(f"Verifying access for {username} to Titanic competition...")
    
    # 1. Check if competition exists and is accessible
    url = "https://www.kaggle.com/api/v1/competitions/list?search=titanic"
    headers = {"Authorization": f"Bearer {key}"} if key.startswith("KGAT_") else {}
    auth = (username, key) if not key.startswith("KGAT_") else None
    
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        competitions = response.json()
        
        found = False
        for comp in competitions:
            ref = comp.get('ref', '')
            if ref == 'titanic' or ref.endswith('/titanic'):
                print(f"✓ Competition 'titanic' found. Title: {comp.get('title')}")
                found = True
                break
        
        if not found:
            print("✗ Competition 'titanic' NOT found in your accessible list.")
            return

        # 2. Try to list files (this requires actual participation access)
        print("Verifying file access...")
        url = "https://www.kaggle.com/api/v1/competitions/data/list/titanic"
        response = requests.get(url, headers=headers, auth=auth)
        
        if response.status_code == 200:
            files = response.json()
            print(f"✓ Successfully listed {len(files)} files:")
            for f in files:
                print(f"  - {f.get('name')} ({f.get('size')})")
            print("\n✓ FULL ACCESS CONFIRMED!")
        elif response.status_code == 403:
            print("✗ ACCESS DENIED (403 Forbidden). You probably need to accept the rules on the website.")
        else:
            print(f"✗ Failed to list files. Status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_kaggle_access()
