"""
Kaggle Tools

Tools for interacting with Kaggle competitions via MCP integration.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from kaggle_solver.mcp.kaggle_mcp import get_kaggle_mcp_client, KaggleMCPClient


def kaggle_get_competition_info(query: str, **kwargs) -> Dict[str, Any]:
    """
    Get information about a Kaggle competition
    
    Args:
        query: Competition name (e.g., 'titanic', 'house-prices-advanced-regression-techniques')
    
    Returns:
        Dictionary with competition information
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        info = client.get_competition_info(query)
        return {
            'success': True,
            'data': info
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_download_data(query: str, path: str = './', files: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Download competition data files
    
    Args:
        query: Competition name (e.g., 'titanic')
        path: Directory to save files (default: './')
        files: Comma-separated list of specific files to download (optional)
    
    Returns:
        Dictionary with download information
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        file_list = files.split(',') if files else None
        downloaded = client.download_competition_data(query, path, file_list)
        
        return {
            'success': True,
            'data': {
                'competition': query,
                'downloaded_files': downloaded,
                'path': path
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_submit(query: str, submission_file: str, message: str = '', **kwargs) -> Dict[str, Any]:
    """
    Submit predictions to a Kaggle competition
    
    Args:
        query: Competition name (e.g., 'titanic')
        submission_file: Path to submission file
        message: Submission message/description
    
    Returns:
        Dictionary with submission information
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        result = client.submit_prediction(query, submission_file, message)
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_get_submission_status(query: str, submission_id: str, **kwargs) -> Dict[str, Any]:
    """
    Get status of a submission
    
    Args:
        query: Competition name (e.g., 'titanic')
        submission_id: Submission ID
    
    Returns:
        Dictionary with submission status
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        status = client.get_submission_status(query, submission_id)
        return {
            'success': True,
            'data': status
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_get_leaderboard(query: str, **kwargs) -> Dict[str, Any]:
    """
    Get competition leaderboard
    
    Args:
        query: Competition name (e.g., 'titanic')
    
    Returns:
        Dictionary with leaderboard data
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        leaderboard = client.get_leaderboard(query)
        return {
            'success': True,
            'data': leaderboard
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_list_competitions(query: str = '', category: str = '', **kwargs) -> Dict[str, Any]:
    """
    List Kaggle competitions
    
    Args:
        query: Search query (optional)
        category: Competition category (e.g., 'gettingStarted', 'featured')
    
    Returns:
        Dictionary with list of competitions
    """
    client = get_kaggle_mcp_client()
    if not client:
        return {
            'success': False,
            'error': 'Kaggle MCP client not available. Please install kaggle package and set KAGGLE_API_KEY and KAGGLE_USERNAME environment variables.'
        }
    
    try:
        competitions = client.list_competitions(category=category, search=query)
        return {
            'success': True,
            'data': competitions
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_validate_submission(query: str, submission_file: str, sample_file: str, **kwargs) -> Dict[str, Any]:
    """
    Validate submission file against sample submission format
    
    Args:
        query: Competition name (for context)
        submission_file: Path to submission file
        sample_file: Path to sample submission file
    
    Returns:
        Dictionary with validation results
    """
    try:
        import pandas as pd
        
        # Read files
        submission_df = pd.read_csv(submission_file)
        sample_df = pd.read_csv(sample_file)
        
        issues = []
        
        # Check columns
        if set(submission_df.columns) != set(sample_df.columns):
            issues.append(f"Column mismatch. Expected: {list(sample_df.columns)}, Got: {list(submission_df.columns)}")
        
        # Check number of rows
        if len(submission_df) != len(sample_df):
            issues.append(f"Row count mismatch. Expected: {len(sample_df)}, Got: {len(submission_df)}")
        
        # Check ID column values (only if columns match)
        if set(submission_df.columns) == set(sample_df.columns):
            id_col = sample_df.columns[0]
            if not set(submission_df[id_col]) == set(sample_df[id_col]):
                issues.append(f"ID column values don't match")
        
        # Check for missing values
        if submission_df.isnull().any().any():
            missing_cols = submission_df.columns[submission_df.isnull().any()].tolist()
            issues.append(f"Missing values found in columns: {missing_cols}")
        
        # Check data types (only for columns that exist in both)
        for col in submission_df.columns:
            if col in sample_df.columns:
                if submission_df[col].dtype != sample_df[col].dtype:
                    issues.append(f"Data type mismatch in column '{col}'. Expected: {sample_df[col].dtype}, Got: {submission_df[col].dtype}")
        
        return {
            'success': True,
            'data': {
                'valid': len(issues) == 0,
                'issues': issues,
                'submission_rows': len(submission_df),
                'submission_columns': list(submission_df.columns)
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def kaggle_prepare_submission(query: str, predictions_file: str, sample_file: str, output_file: str = 'submission.csv', **kwargs) -> Dict[str, Any]:
    """
    Prepare submission file from predictions
    
    Args:
        query: Competition name (for context)
        predictions_file: Path to file with predictions
        sample_file: Path to sample submission file
        output_file: Output submission file path
    
    Returns:
        Dictionary with preparation results
    """
    try:
        import pandas as pd
        
        # Read files
        predictions_df = pd.read_csv(predictions_file)
        sample_df = pd.read_csv(sample_file)
        
        # Ensure columns are in the same order as sample
        submission_df = predictions_df[sample_df.columns].copy()
        
        # Sort by ID column to match sample order
        id_col = sample_df.columns[0]
        submission_df = submission_df.sort_values(id_col)
        
        # Save to CSV
        submission_df.to_csv(output_file, index=False)
        
        return {
            'success': True,
            'data': {
                'output_file': output_file,
                'rows': len(submission_df),
                'columns': list(submission_df.columns)
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# Register tools
def register_kaggle_tools():
    """Register Kaggle tools with the tool registry"""
    from kaggle_solver.tools.registry import ToolRegistry
    
    tools = {
        'kaggle_get_competition_info': kaggle_get_competition_info,
        'kaggle_download_data': kaggle_download_data,
        'kaggle_submit': kaggle_submit,
        'kaggle_get_submission_status': kaggle_get_submission_status,
        'kaggle_get_leaderboard': kaggle_get_leaderboard,
        'kaggle_list_competitions': kaggle_list_competitions,
        'kaggle_validate_submission': kaggle_validate_submission,
        'kaggle_prepare_submission': kaggle_prepare_submission
    }
    
    for name, func in tools.items():
        ToolRegistry.register(name, func)
    
    return tools
