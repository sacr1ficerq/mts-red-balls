"""
Kaggle MCP Server Integration

This module provides MCP (Model Context Protocol) integration for Kaggle competitions,
allowing agents to download competition data, submit predictions, and retrieve competition information.
"""

import csv
import json
import os
import logging
import shutil
import subprocess
from io import StringIO
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

KAGGLE_AVAILABLE = shutil.which("kaggle") is not None


class KaggleMCPClient:
    """Kaggle MCP client for competition operations"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        working_dir: Optional[str] = None,
    ):
        """
        Initialize Kaggle MCP client

        Args:
            api_key: Kaggle API key (if None, reads from KAGGLE_API_KEY env var)
            username: Kaggle username (if None, reads from KAGGLE_USERNAME env var)
        """
        self.api_key = api_key or os.getenv("KAGGLE_API_KEY")
        self.username = username or os.getenv("KAGGLE_USERNAME")
        self.kaggle_cmd = shutil.which("kaggle") or "kaggle"
        self.working_dir = working_dir
        self._authenticate()

    def _authenticate(self):
        """Prepare Kaggle CLI authentication context."""
        if not KAGGLE_AVAILABLE:
            raise RuntimeError("Kaggle CLI is not installed or not in PATH")

        if self.api_key:
            # Always overwrite to ensure token checks use the latest provided value.
            os.environ["KAGGLE_API_TOKEN"] = self.api_key
            os.environ["KAGGLE_API_KEY"] = self.api_key

        if self.api_key and self.username:
            # Create kaggle.json file for authentication when both values are available
            kaggle_dir = Path.home() / ".kaggle"
            kaggle_dir.mkdir(exist_ok=True)

            kaggle_json = kaggle_dir / "kaggle.json"
            with open(kaggle_json, "w") as f:
                json.dump({"username": self.username, "key": self.api_key}, f)

            # Set permissions
            os.chmod(kaggle_json, 0o600)

    def _run_cli_command(self, args: List[str]) -> str:
        """Run a Kaggle CLI command and return stdout."""
        command = [self.kaggle_cmd, *args]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                cwd=self.working_dir,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            message = stderr or stdout or str(exc)
            raise RuntimeError(message)

    @staticmethod
    def _parse_csv_output(output: str) -> List[Dict[str, Any]]:
        """Parse CSV text output into list of dict rows."""
        if not output.strip():
            return []

        reader = csv.DictReader(StringIO(output))
        return [dict(row) for row in reader]

    def get_competition_info(self, competition_name: str) -> Dict[str, Any]:
        """
        Get information about a Kaggle competition

        Args:
            competition_name: Name of the competition (e.g., 'titanic')

        Returns:
            Dictionary with competition information
        """
        try:
            output = self._run_cli_command(
                ["competitions", "list", "-s", competition_name, "-v", "--csv"]
            )
            competitions = self._parse_csv_output(output)
            for competition in competitions:
                ref = (competition.get("ref") or "").strip()
                if ref.lower() == competition_name.lower():
                    return competition

            if competitions:
                return competitions[0]
            raise ValueError(f"Competition '{competition_name}' not found")
        except Exception as e:
            raise RuntimeError(f"Failed to get competition info: {str(e)}")

    def download_competition_data(
        self,
        competition_name: str,
        destination_path: str = "./",
        files: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Download competition data files

        Args:
            competition_name: Name of the competition
            destination_path: Directory to save files
            files: List of specific files to download (if None, downloads all)

        Returns:
            List of downloaded file paths
        """
        try:
            path_obj = Path(destination_path)
            path_obj.mkdir(parents=True, exist_ok=True)

            if files:
                downloaded = []
                for file in files:
                    self._run_cli_command(
                        [
                            "competitions",
                            "download",
                            "-c",
                            competition_name,
                            "-f",
                            file,
                            "-p",
                            str(path_obj),
                        ]
                    )
                    downloaded.append(str(path_obj / file))

                return downloaded
            else:
                self._run_cli_command(
                    [
                        "competitions",
                        "download",
                        "-c",
                        competition_name,
                        "-p",
                        str(path_obj),
                    ]
                )

                # List downloaded files
                downloaded = [str(f) for f in path_obj.glob("*") if f.is_file()]
                return downloaded

        except Exception as e:
            raise RuntimeError(f"Failed to download competition data: {str(e)}")

    def submit_prediction(
        self, competition_name: str, submission_file: str, message: str = ""
    ) -> Dict[str, Any]:
        """
        Submit predictions to a Kaggle competition

        Args:
            competition_name: Name of the competition
            submission_file: Path to submission file
            message: Submission message/description

        Returns:
            Dictionary with submission information
        """
        try:
            output = self._run_cli_command(
                [
                    "competitions",
                    "submit",
                    "-c",
                    competition_name,
                    "-f",
                    submission_file,
                    "-m",
                    message,
                ]
            )
            return {
                "status": "submitted",
                "message": message,
                "submission_id": None,
                "raw_output": output,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to submit prediction: {str(e)}")

    def get_submission_status(
        self, competition_name: str, submission_id: str
    ) -> Dict[str, Any]:
        """
        Get status of a submission

        Args:
            competition_name: Name of the competition
            submission_id: Submission ID

        Returns:
            Dictionary with submission status
        """
        try:
            output = self._run_cli_command(
                ["competitions", "submissions", "-c", competition_name, "-v", "--csv"]
            )
            submissions = self._parse_csv_output(output)

            for submission in submissions:
                ref = (
                    submission.get("ref")
                    or submission.get("submissionId")
                    or submission.get("id")
                    or ""
                )
                if str(ref).strip() == str(submission_id):
                    return submission

            raise ValueError(f"Submission {submission_id} not found")

        except Exception as e:
            raise RuntimeError(f"Failed to get submission status: {str(e)}")

    def get_leaderboard(
        self, competition_name: str, page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get competition leaderboard

        Args:
            competition_name: Name of the competition
            page: Page number (for pagination)

        Returns:
            List of leaderboard entries
        """
        try:
            output = self._run_cli_command(
                [
                    "competitions",
                    "leaderboard",
                    "-c",
                    competition_name,
                    "-v",
                    "--csv",
                ]
            )
            return self._parse_csv_output(output)

        except Exception as e:
            raise RuntimeError(f"Failed to get leaderboard: {str(e)}")

    def list_competitions(
        self, category: str = "", search: str = ""
    ) -> List[Dict[str, Any]]:
        """
        List Kaggle competitions

        Args:
            category: Competition category (e.g., 'gettingStarted', 'featured')
            search: Search query

        Returns:
            List of competitions
        """
        try:
            args = ["competitions", "list", "-v", "--csv"]
            if search:
                args.extend(["-s", search])
            output = self._run_cli_command(args)
            competitions = self._parse_csv_output(output)

            if category:
                category_lower = category.strip().lower()
                competitions = [
                    competition
                    for competition in competitions
                    if (competition.get("category") or "").strip().lower()
                    == category_lower
                ]

            return competitions

        except Exception as e:
            raise RuntimeError(f"Failed to list competitions: {str(e)}")


def _parse_kaggle_token(token: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a Kaggle token string into username and key.

    Supported formats:
    - JSON string: {"username":"...","key":"..."}
    - Colon-delimited: username:key
    - Raw key only: key
    """
    if not token:
        return None, None

    raw = token.strip()
    if not raw:
        return None, None

    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            username = payload.get("username")
            key = payload.get("key")
            if isinstance(username, str) and isinstance(key, str):
                return username.strip() or None, key.strip() or None
    except Exception:
        pass

    if ":" in raw:
        username, key = raw.split(":", 1)
        return username.strip() or None, key.strip() or None

    return None, raw


# MCP Tool Wrappers


def kaggle_get_competition_info(query: str, mcp_client: KaggleMCPClient) -> str:
    """
    Get information about a Kaggle competition

    Args:
        query: Competition name (e.g., 'titanic')
        mcp_client: KaggleMCPClient instance

    Returns:
        Competition information as JSON string
    """
    try:
        info = mcp_client.get_competition_info(query)
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def kaggle_download_data(
    query: str, mcp_client: KaggleMCPClient, path: str = "./"
) -> str:
    """
    Download competition data files

    Args:
        query: Competition name (e.g., 'titanic')
        mcp_client: KaggleMCPClient instance
        path: Directory to save files (default: './')

    Returns:
        Downloaded files information as JSON string
    """
    try:
        files = mcp_client.download_competition_data(query, path)
        return json.dumps(
            {"competition": query, "downloaded_files": files, "path": path}, indent=2
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def kaggle_submit(
    query: str, mcp_client: KaggleMCPClient, submission_file: str, message: str = ""
) -> str:
    """
    Submit predictions to a Kaggle competition

    Args:
        query: Competition name (e.g., 'titanic')
        mcp_client: KaggleMCPClient instance
        submission_file: Path to submission file
        message: Submission message

    Returns:
        Submission information as JSON string
    """
    try:
        result = mcp_client.submit_prediction(query, submission_file, message)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def kaggle_get_submission_status(
    query: str, mcp_client: KaggleMCPClient, submission_id: str
) -> str:
    """
    Get status of a submission

    Args:
        query: Competition name (e.g., 'titanic')
        mcp_client: KaggleMCPClient instance
        submission_id: Submission ID

    Returns:
        Submission status as JSON string
    """
    try:
        status = mcp_client.get_submission_status(query, submission_id)
        return json.dumps(status, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def kaggle_get_leaderboard(query: str, mcp_client: KaggleMCPClient) -> str:
    """
    Get competition leaderboard

    Args:
        query: Competition name (e.g., 'titanic')
        mcp_client: KaggleMCPClient instance

    Returns:
        Leaderboard as JSON string
    """
    try:
        leaderboard = mcp_client.get_leaderboard(query)
        return json.dumps(leaderboard, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def kaggle_list_competitions(
    query: str, mcp_client: KaggleMCPClient, category: str = ""
) -> str:
    """
    List Kaggle competitions

    Args:
        query: Search query
        mcp_client: KaggleMCPClient instance
        category: Competition category

    Returns:
        List of competitions as JSON string
    """
    try:
        competitions = mcp_client.list_competitions(category=category, search=query)
        return json.dumps(competitions, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Initialize Kaggle MCP client
def get_kaggle_mcp_client(sandbox=None) -> Optional[KaggleMCPClient]:
    """
    Get or create Kaggle MCP client instance

    Returns:
        KaggleMCPClient instance or None if not available
    """
    try:
        if not KAGGLE_AVAILABLE:
            logger.error("Kaggle CLI executable is not available")
            return None

        username = os.getenv("KAGGLE_USERNAME")
        api_key = os.getenv("KAGGLE_API_KEY")

        try:
            from kaggle_solver.core.settings import SettingsManager

            settings = SettingsManager().get_settings()
            token_username, token_key = _parse_kaggle_token(settings.kaggle_key)
            if token_key and not api_key:
                api_key = token_key
            if token_username and not username:
                username = token_username
        except Exception as settings_error:
            logger.debug(f"Could not read Kaggle key from settings: {settings_error}")

        if api_key:
            os.environ["KAGGLE_API_KEY"] = api_key
            os.environ["KAGGLE_API_TOKEN"] = api_key
        if username:
            os.environ["KAGGLE_USERNAME"] = username

        working_dir = None
        if sandbox is not None and hasattr(sandbox, "root"):
            working_dir = str(sandbox.root)

        return KaggleMCPClient(
            api_key=api_key,
            username=username,
            working_dir=working_dir,
        )
    except Exception as e:
        logger.error(f"Failed to initialize Kaggle MCP client: {str(e)}")
        return None
