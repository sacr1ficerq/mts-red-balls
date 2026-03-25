from pathlib import Path


def _detect_project_root() -> Path:
    pkg_dir = Path(__file__).resolve().parent
    candidates = [
        pkg_dir.parent.parent,
        pkg_dir.parent,
    ]

    for candidate in candidates:
        if (candidate / "backend" / "kaggle_solver").exists():
            return candidate
        if (candidate / "kaggle_solver").exists():
            return candidate

    return pkg_dir.parent


PROJECT_ROOT = _detect_project_root()
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
