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

try:
    import kaggle
    KAGGLE_AVAILABLE = True
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
        
        # Create kaggle.json file for authentication
        kaggle_dir = Path.home() / '.kaggle'
        kaggle_dir.mkdir(exist_ok=True)
        
        kaggle_json = kaggle_dir / 'kaggle.json'
        with open(kaggle_json, 'w') as f:
            json.dump({
                'username': self.username,
                'key': self.api_key
            }, f)
        
        # Set permissions
        os.chmod(kaggle_json, 0o600)
        
        # Initialize API
        self.api = kaggle.KaggleApi()
        self.api.authenticate()
    
    def get_competition_info(self, competition_name: str) -> Dict[str, Any]:
        """
        Get information about a Kaggle competition
        
        Args:
            competition_name: Name of the competition (e.g., 'titanic')
        
        Returns:
            Dictionary with competition information
        """
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            competition = self.api.competition_view(competition_name)
            
            info = {
                'name': competition.ref,
                'title': competition.title,
                'description': competition.description,
                'evaluation_metric': competition.evaluationMetric,
                'max_daily_submissions': competition.maxDailySubmissions,
                'max_team_size': competition.maxTeamSize,
                'reward': competition.reward,
                'deadline': competition.deadline,
                'enabled_date': competition.enabledDate,
                'total_teams': competition.totalTeams,
                'total_submissions': competition.totalSubmissions
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
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            
            if files:
                downloaded = []
                for file in files:
                    self.api.competition_download_file(
                        competition_name,
                        file,
                        path=str(path)
                    )
                    downloaded.append(str(path / file))
                
                return downloaded
            else:
                # Download all competition files
                self.api.competition_download_files(
                    competition_name,
                    path=str(path)
                )
                
                # List downloaded files
                downloaded = [str(f) for f in path.glob('*') if f.is_file()]
                return downloaded
        
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
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            result = self.api.competition_submit(
                submission_file,
                message,
                competition_name
            )
            
            submission_info = {
                'status': result.status,
                'message': message,
                'submitted_at': result.date,
                'submission_id': result.ref
            }
            
            return submission_info
        
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
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            result = self.api.competition_submissions(competition_name)
            
            for submission in result:
                if submission.ref == submission_id:
                    return {
                        'status': submission.status,
                        'public_score': submission.publicScore,
                        'private_score': submission.privateScore,
                        'submitted_at': submission.date,
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
        if not self.api:
            raise RuntimeError("Kaggle API not initialized")
        
        try:
            leaderboard = self.api.competition_leaderboard(competition_name)
            
            entries = []
            for team in leaderboard:
                entry = {
                    'team_name': team.teamName,
                    'team_id': team.teamId,
                    'rank': team.rank,
                    'score': team.score,
                    'last_submission': team.lastSubmission
                }
                entries.append(entry)
            
            return entries
        
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
    Get or create Kaggle MCP client instance
    
    Returns:
        KaggleMCPClient instance or None if not available
    """
    if not KAGGLE_AVAILABLE:
        return None
    
    try:
        return KaggleMCPClient()
    except Exception as e:
        logger.error(f"Failed to initialize Kaggle MCP client: {str(e)}")
        return None
