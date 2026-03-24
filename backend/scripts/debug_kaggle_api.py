import kaggle
import os
import json
from pathlib import Path

def debug_kaggle():
    # Try to load credentials from settings.json
    settings_path = Path("backend/data/settings.json")
    if settings_path.exists():
        with open(settings_path) as f:
            data = json.load(f)
            os.environ['KAGGLE_USERNAME'] = data.get('kaggle_username', '')
            os.environ['KAGGLE_KEY'] = data.get('kaggle_api_key', '')
    
    api = kaggle.KaggleApi()
    api.authenticate()
    print(f"Kaggle version: {kaggle.__version__}")
    
    try:
        res = api.competitions_list(search='titanic')
        print(f"competitions_list return type: {type(res)}")
        
        # Check competition_view
        try:
            comp = api.competition_view('titanic')
            print("competition_view exists")
        except AttributeError:
            print("competition_view does NOT exist")
            
    except Exception as e:
        print(f"Kaggle API call failed: {e}")

if __name__ == "__main__":
    debug_kaggle()
