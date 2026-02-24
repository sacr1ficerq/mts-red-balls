from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def init_env():
    """Load environment variables from .env file."""
    if ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)
        except ImportError:
            pass


def get_project_root() -> Path:
    """Get project root directory."""
    return PROJECT_ROOT


init_env()
