#!/usr/bin/env python3
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kaggle_solver.core.settings import SettingsManager

def main():
    if len(sys.argv) < 3:
        print("Usage: python setup_kaggle.py <username> <api_key>")
        sys.exit(1)
    
    username = sys.argv[1]
    api_key = sys.argv[2]
    
    settings = SettingsManager()
    settings.update_settings(
        kaggle_username=username,
        kaggle_key=api_key
    )
    print(f"Kaggle credentials updated for {username}")

    # Verify credentials
    print("Verifying credentials...")
    try:
        from kaggle_solver.mcp.kaggle_mcp import KaggleMCPClient
        client = KaggleMCPClient(api_key=api_key, username=username)
        # Try a simple API call
        client.list_competitions(search='titanic')
        print("✓ Credentials verified successfully!")
    except Exception as e:
        print(f"✗ Credential verification failed: {e}")
        print("Please ensure your username and API key are correct.")

if __name__ == "__main__":
    main()
