"""
Kaggle MCP Server Integration

This module provides MCP (Model Context Protocol) integration for Kaggle competitions,
allowing agents to download competition data, submit predictions, and retrieve competition information.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)

KAGGLE_AVAILABLE = True
try:
    import kaggle
    # Immediately remove from sys.modules to prevent cached config
    import sys
    if 'kaggle' in sys.modules:
        del sys.modules['kaggle']
except ImportError:
    KAGGLE_AVAILABLE = False


class KaggleMCPClient:
    """Kaggle MCP client for competition operations"""
    
    def __init__(self, api_key: Optional[str] = None, username: Optional[str] = None):
        """
        Initialize Kaggle MCP client
        
        Args:
            api_key: Kaggle API key (if None, reads from KAGGLE_API_KEY env var)
            username: Kaggle username (if None, reads from KAGGLE_USERNAME env var)
        """
        self.api_key = api_key or os.getenv('KAGGLE_API_KEY')
        self.username = username or os.getenv('KAGGLE_USERNAME')
        self.api = None
        
        if KAGGLE_AVAILABLE:
            self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Kaggle API"""
        if not self.api_key or not self.username:
            raise ValueError("Kaggle API credentials not provided. Set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.")
        
        # Log masked credentials for debugging
        masked_key = self.api_key[:4] + "..." + self.api_key[-4:] if len(self.api_key) > 8 else "****"
        logger.info(f"Authenticating Kaggle API for user: {self.username} with key: {masked_key}")

        # Set environment variables explicitly - this is the most reliable way
        os.environ['KAGGLE_USERNAME'] = self.username
        os.environ['KAGGLE_KEY'] = self.api_key
        
        # Create kaggle.json file for authentication as a backup
        kaggle_dir = Path.home() / '.kaggle'
        kaggle_dir.mkdir(exist_ok=True)
        
        kaggle_json = kaggle_dir / 'kaggle.json'
        try:
            with open(kaggle_json, 'w') as f:
                json.dump({
                    'username': self.username,
                    'key': self.api_key
                }, f)
            
            # Set permissions
            if os.name != 'nt':
                os.chmod(kaggle_json, 0o600)
        except Exception as e:
            logger.warning(f"Failed to write kaggle.json: {e}. Continuing with environment variables.")
        
        # Initialize API
        try:
            import kaggle
            # Create a fresh API instance
            self.api = kaggle.KaggleApi()
            
            # Manually set configuration to bypass any cached/file settings
            self.api.config_values['username'] = self.username
            self.api.config_values['key'] = self.api_key
            
            self.api.authenticate()
        except Exception as e:
            logger.error(f"Kaggle API authentication failed: {e}")
            raise
    
    def _request(self, endpoint: str, method: str = "GET", **kwargs) -> requests.Response:
        """Make a request to Kaggle API, handling Bearer or Basic auth"""
        import requests
        url = f"https://www.kaggle.com/api/v1/{endpoint}"
        
        if self.api_key.startswith("KGAT_"):
            headers = kwargs.get("headers", {})
            headers["Authorization"] = f"Bearer {self.api_key}"
            kwargs["headers"] = headers
        else:
            kwargs["auth"] = (self.username, self.api_key)
            
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def get_competition_info(self, competition_name: str) -> Dict[str, Any]:
        """
        Get information about a Kaggle competition
        
        Args:
            competition_name: Name of the competition (e.g., 'titanic')
        
        Returns:
            Dictionary with competition information
        """
        try:
            # Use direct request to handle Bearer tokens correctly
            response = self._request(f"competitions/list?search={competition_name}")
            competitions = response.json()
            
            target = None
            for comp in competitions:
                ref = comp.get('ref', '')
                # Handle both slug and full URL
                if ref == competition_name or ref.endswith(f"/{competition_name}"):
                    target = comp
                    break
            
            if not target:
                raise ValueError(f"Competition '{competition_name}' not found")

            info = {
                'name': target.get('ref', ''),
                'title': target.get('title', ''),
                'description': target.get('description', ''),
                'evaluation_metric': target.get('evaluationMetric', ''),
                'max_daily_submissions': target.get('maxDailySubmissions', 0),
                'max_team_size': target.get('maxTeamSize', 0),
                'reward': target.get('reward', ''),
                'deadline': str(target.get('deadline', '')),
                'enabled_date': str(target.get('enabledDate', '')),
                'total_teams': target.get('totalTeams', 0),
                'total_submissions': target.get('totalSubmissions', 0)
            }
            
            return info
        except Exception as e:
            raise RuntimeError(f"Failed to get competition info: {str(e)}")
    
    def download_competition_data(self, competition_name: str, path: str = './', files: Optional[List[str]] = None) -> List[str]:
        """
        Download competition data files
        
        Args:
            competition_name: Name of the competition
            path: Directory to save files
            files: List of specific files to download (if None, downloads all)
        
        Returns:
            List of downloaded file paths
        """
        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            
            if self.api_key.startswith("KGAT_"):
                # Use direct request for Bearer tokens
                if files:
                    downloaded = []
                    for file in files:
                        url = f"competitions/data/download/{competition_name}/{file}"
                        response = self._request(url, stream=True)
                        target = path / file
                        with open(target, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        downloaded.append(str(target))
                    return downloaded
                else:
                    # Download all as zip
                    url = f"competitions/data/download-all/{competition_name}"
                    response = self._request(url, stream=True)
                    target = path / f"{competition_name}.zip"
                    with open(target, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return [str(target)]
            else:
                # Use library for legacy keys
                if not self.api: self._authenticate()
                if files:
                    downloaded = []
                    for file in files:
                        self.api.competition_download_file(competition_name, file, path=str(path))
                        downloaded.append(str(path / file))
                    return downloaded
                else:
                    self.api.competition_download_files(competition_name, path=str(path))
                    return [str(f) for f in path.glob('*') if f.is_file()]
        
        except Exception as e:
            raise RuntimeError(f"Failed to download competition data: {str(e)}")
    
    def submit_prediction(self, competition_name: str, submission_file: str, message: str = "") -> Dict[str, Any]:
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
            if self.api_key.startswith("KGAT_"):
                # Use direct request for Bearer tokens
                url = f"competitions/submit/{competition_name}"
                with open(submission_file, 'rb') as f:
                    files = {'file': f}
                    data = {'message': message}
                    response = self._request(url, method="POST", files=files, data=data)
                result = response.json()
                return {
                    'status': 'submitted',
                    'message': message,
                    'competition': competition_name,
                    'ref': result.get('ref', str(result))
                }
            else:
                if not self.api: self._authenticate()
                result = self.api.competition_submit(submission_file, message, competition_name)
                return {
                    'status': 'submitted',
                    'message': message,
                    'competition': competition_name,
                    'ref': getattr(result, 'ref', str(result))
                }
        except Exception as e:
            raise RuntimeError(f"Failed to submit prediction: {str(e)}")
    
    def get_submission_status(self, competition_name: str, submission_id: str) -> Dict[str, Any]:
        """
        Get status of a submission
        
        Args:
            competition_name: Name of the competition
            submission_id: Submission ID
        
        Returns:
            Dictionary with submission status
        """
        try:
            if self.api_key.startswith("KGAT_"):
                # Use direct request for Bearer tokens
                response = self._request(f"competitions/submissions/list/{competition_name}")
                submissions = response.json()
                for sub in submissions:
                    if str(sub.get('ref', '')) == str(submission_id):
                        return {
                            'status': sub.get('status', ''),
                            'public_score': sub.get('publicScore'),
                            'private_score': sub.get('privateScore'),
                            'submitted_at': str(sub.get('date', '')),
                            'message': sub.get('description', '')
                        }
            else:
                if not self.api: self._authenticate()
                result = self.api.competition_submissions(competition_name)
                for submission in result:
                    if str(submission.ref) == str(submission_id):
                        return {
                            'status': submission.status,
                            'public_score': submission.publicScore,
                            'private_score': submission.privateScore,
                            'submitted_at': str(submission.date),
                            'message': submission.description
                        }
            
            raise ValueError(f"Submission {submission_id} not found")
        except Exception as e:
            raise RuntimeError(f"Failed to get submission status: {str(e)}")
    
    def get_leaderboard(self, competition_name: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get competition leaderboard
        
        Args:
            competition_name: Name of the competition
            page: Page number (for pagination)
        
        Returns:
            List of leaderboard entries
        """
        try:
            if self.api_key.startswith("KGAT_"):
                # Use direct request for Bearer tokens
                response = self._request(f"competitions/leaderboard/view/{competition_name}")
                leaderboard = response.json()
                # Handle both list and response object
                entries = leaderboard.get('submissions', []) if isinstance(leaderboard, dict) else leaderboard
                result = []
                for entry in entries:
                    result.append({
                        'team_name': entry.get('teamName', ''),
                        'team_id': entry.get('teamId', ''),
                        'rank': entry.get('rank', 0),
                        'score': entry.get('score', 0)
                    })
                return result
            else:
                if not self.api: self._authenticate()
                leaderboard = self.api.competition_leaderboard(competition_name)
                result = []
                for team in leaderboard:
                    result.append({
                        'team_name': team.teamName,
                        'team_id': team.teamId,
                        'rank': team.rank,
                        'score': team.score
                    })
                return result
        except Exception as e:
            raise RuntimeError(f"Failed to get leaderboard: {str(e)}")
    
    def list_competitions(self, category: str = '', search: str = '') -> List[Dict[str, Any]]:
        """
        List Kaggle competitions
        
        Args:
            category: Competition category (e.g., 'gettingStarted', 'featured')
            search: Search query
        
        Returns:
            List of competitions
        """
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            competitions = self.api.competitions_list(category=category, search=search)
            
            comp_list = []
            for comp in competitions:
                comp_info = {
                    'name': comp.ref,
                    'title': comp.title,
                    'description': comp.description,
                    'category': comp.category,
                    'reward': comp.reward,
                    'deadline': comp.deadline,
                    'total_teams': comp.totalTeams
                }
                comp_list.append(comp_info)
            
            return comp_list
        
        except Exception as e:
            raise RuntimeError(f"Failed to list competitions: {str(e)}")


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
        return json.dumps({'error': str(e)})


def kaggle_download_data(query: str, mcp_client: KaggleMCPClient, path: str = './') -> str:
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
        return json.dumps({
            'competition': query,
            'downloaded_files': files,
            'path': path
        }, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)})


def kaggle_submit(query: str, mcp_client: KaggleMCPClient, submission_file: str, message: str = '') -> str:
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
        return json.dumps({'error': str(e)})


def kaggle_get_submission_status(query: str, mcp_client: KaggleMCPClient, submission_id: str) -> str:
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
        return json.dumps({'error': str(e)})


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
        return json.dumps({'error': str(e)})


def kaggle_list_competitions(query: str, mcp_client: KaggleMCPClient, category: str = '') -> str:
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
        return json.dumps({'error': str(e)})


# Initialize Kaggle MCP client
def get_kaggle_mcp_client() -> Optional[KaggleMCPClient]:
    """
    Get or create Kaggle MCP client instance.
    
    Credentials are loaded from (in order of priority):
    1. SettingsManager (stored via UI)
    2. Environment variables (KAGGLE_API_KEY, KAGGLE_USERNAME)
    
    Returns:
        KaggleMCPClient instance or None if not available
    """
    if not KAGGLE_AVAILABLE:
        return None
    
    try:
        from kaggle_solver.core.settings import get_settings_manager
        
        settings_manager = get_settings_manager()
        api_key, username = settings_manager.get_kaggle_credentials()
        
        return KaggleMCPClient(api_key=api_key, username=username)
    except Exception as e:
        logger.error(f"Failed to initialize Kaggle MCP client: {str(e)}")
        return None
