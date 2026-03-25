"""
Kaggle Tools

Tools for interacting with Kaggle competitions via MCP integration.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from kaggle_solver.mcp.kaggle_mcp import get_kaggle_mcp_client, KaggleMCPClient


KAGGLE_CLIENT_ERROR = (
    "Kaggle client not available. Install Kaggle CLI and configure `kaggle_key` in "
    "Settings (raw key, `username:key`, or kaggle.json payload). Ensure `KAGGLE_USERNAME` "
    "is available when username is not embedded in the token."
)


def _resolve_query(query: str = "", **kwargs) -> str:
    """Resolve competition query from common aliases used by agents."""
    if query:
        return query
    for alias in ("competition", "competition_name", "name"):
        value = kwargs.get(alias)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _resolve_path_in_sandbox(path: str, sandbox=None) -> Path:
    """Resolve file path inside sandbox when sandbox is available."""
    raw = (path or "").strip()
    if not raw:
        raw = "."

    if sandbox is None:
        return Path(raw)

    if not hasattr(sandbox, "resolve_path"):
        raise ValueError("Sandbox does not support secure path resolution")

    return sandbox.resolve_path(raw)


def _to_display_path(path: Path, sandbox=None) -> str:
    """Convert an absolute sandbox path to a sandbox-relative display path."""
    if sandbox is None:
        return str(path)

    try:
        relative = path.resolve().relative_to(Path(sandbox.root).resolve())
        return str(relative)
    except Exception:
        return str(path)


def kaggle_get_competition_info(query: str = "", **kwargs) -> Dict[str, Any]:
    """
    Get information about a Kaggle competition

    Args:
        query: Competition name (e.g., 'titanic', 'house-prices-advanced-regression-techniques')

    Returns:
        Dictionary with competition information
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}

    client = get_kaggle_mcp_client(sandbox=kwargs.get("sandbox"))
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        info = client.get_competition_info(query)
        return {"success": True, "data": info}
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_download_data(
    query: str = "", path: str = "./", files: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """
    Download competition data files

    Args:
        query: Competition name (e.g., 'titanic')
        path: Directory to save files (default: './')
        files: Comma-separated list of specific files to download (optional)

    Returns:
        Dictionary with download information
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}

    sandbox = kwargs.get("sandbox")
    client = get_kaggle_mcp_client(sandbox=sandbox)
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        if sandbox is None:
            destination = Path(path)
            destination_arg = path
        else:
            destination = _resolve_path_in_sandbox(path, sandbox)
            destination.mkdir(parents=True, exist_ok=True)
            destination_arg = str(destination)

        file_list = files.split(",") if files else None
        downloaded = client.download_competition_data(query, destination_arg, file_list)

        downloaded_paths = []
        for item in downloaded:
            item_path = Path(item)
            downloaded_paths.append(_to_display_path(item_path, sandbox))

        return {
            "success": True,
            "data": {
                "competition": query,
                "downloaded_files": downloaded_paths,
                "path": _to_display_path(destination, sandbox)
                if sandbox is not None
                else path,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_submit(
    query: str = "", submission_file: str = "", message: str = "", **kwargs
) -> Dict[str, Any]:
    """
    Submit predictions to a Kaggle competition

    Args:
        query: Competition name (e.g., 'titanic')
        submission_file: Path to submission file
        message: Submission message/description

    Returns:
        Dictionary with submission information
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}
    if not submission_file:
        return {"success": False, "error": "submission_file is required"}

    sandbox = kwargs.get("sandbox")
    client = get_kaggle_mcp_client(sandbox=sandbox)
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        if sandbox is not None:
            submission_path = _resolve_path_in_sandbox(submission_file, sandbox)
            if not submission_path.exists() or not submission_path.is_file():
                return {
                    "success": False,
                    "error": f"submission_file not found: {submission_file}",
                }
            submission_arg = str(submission_path)
        else:
            submission_arg = submission_file

        result = client.submit_prediction(query, submission_arg, message)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_get_submission_status(
    query: str = "", submission_id: str = "", **kwargs
) -> Dict[str, Any]:
    """
    Get status of a submission

    Args:
        query: Competition name (e.g., 'titanic')
        submission_id: Submission ID

    Returns:
        Dictionary with submission status
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}
    if not submission_id:
        return {"success": False, "error": "submission_id is required"}

    client = get_kaggle_mcp_client(sandbox=kwargs.get("sandbox"))
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        status = client.get_submission_status(query, submission_id)
        return {"success": True, "data": status}
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_get_leaderboard(query: str = "", **kwargs) -> Dict[str, Any]:
    """
    Get competition leaderboard

    Args:
        query: Competition name (e.g., 'titanic')

    Returns:
        Dictionary with leaderboard data
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}

    client = get_kaggle_mcp_client(sandbox=kwargs.get("sandbox"))
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        leaderboard = client.get_leaderboard(query)
        return {"success": True, "data": leaderboard}
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_list_competitions(
    query: str = "", category: str = "", **kwargs
) -> Dict[str, Any]:
    """
    List Kaggle competitions

    Args:
        query: Search query (optional)
        category: Competition category (e.g., 'gettingStarted', 'featured')

    Returns:
        Dictionary with list of competitions
    """
    client = get_kaggle_mcp_client(sandbox=kwargs.get("sandbox"))
    if not client:
        return {"success": False, "error": KAGGLE_CLIENT_ERROR}

    try:
        competitions = client.list_competitions(category=category, search=query)
        return {"success": True, "data": competitions}
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_validate_submission(
    query: str = "", submission_file: str = "", sample_file: str = "", **kwargs
) -> Dict[str, Any]:
    """
    Validate submission file against sample submission format

    Args:
        query: Competition name (for context)
        submission_file: Path to submission file
        sample_file: Path to sample submission file

    Returns:
        Dictionary with validation results
    """
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}
    if not submission_file:
        return {"success": False, "error": "submission_file is required"}
    if not sample_file:
        return {"success": False, "error": "sample_file is required"}

    try:
        import pandas as pd

        sandbox = kwargs.get("sandbox")
        submission_path = _resolve_path_in_sandbox(submission_file, sandbox)
        sample_path = _resolve_path_in_sandbox(sample_file, sandbox)

        # Read files
        submission_df = pd.read_csv(submission_path)
        sample_df = pd.read_csv(sample_path)

        issues = []

        # Check columns
        if set(submission_df.columns) != set(sample_df.columns):
            issues.append(
                f"Column mismatch. Expected: {list(sample_df.columns)}, Got: {list(submission_df.columns)}"
            )

        # Check number of rows
        if len(submission_df) != len(sample_df):
            issues.append(
                f"Row count mismatch. Expected: {len(sample_df)}, Got: {len(submission_df)}"
            )

        # Check ID column values (only if columns match)
        if set(submission_df.columns) == set(sample_df.columns):
            id_col = sample_df.columns[0]
            if not set(submission_df[id_col]) == set(sample_df[id_col]):
                issues.append(f"ID column values don't match")

        # Check for missing values
        missing_mask = submission_df.isnull().to_numpy().any(axis=0)
        if missing_mask.any():
            missing_cols = submission_df.columns[missing_mask].tolist()
            issues.append(f"Missing values found in columns: {missing_cols}")

        # Check data types (only for columns that exist in both)
        for col in submission_df.columns:
            if col in sample_df.columns:
                if submission_df[col].dtype != sample_df[col].dtype:
                    issues.append(
                        f"Data type mismatch in column '{col}'. Expected: {sample_df[col].dtype}, Got: {submission_df[col].dtype}"
                    )

        return {
            "success": True,
            "data": {
                "valid": len(issues) == 0,
                "issues": issues,
                "submission_rows": len(submission_df),
                "submission_columns": list(submission_df.columns),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaggle_prepare_submission(
    query: str = "",
    predictions_file: str = "",
    sample_file: str = "",
    output_file: str = "submission.csv",
    **kwargs,
) -> Dict[str, Any]:
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
    query = _resolve_query(query, **kwargs)
    if not query:
        return {"success": False, "error": "Competition query is required"}
    if not predictions_file:
        return {"success": False, "error": "predictions_file is required"}
    if not sample_file:
        return {"success": False, "error": "sample_file is required"}

    try:
        import pandas as pd

        sandbox = kwargs.get("sandbox")
        predictions_path = _resolve_path_in_sandbox(predictions_file, sandbox)
        sample_path = _resolve_path_in_sandbox(sample_file, sandbox)
        output_path = _resolve_path_in_sandbox(output_file, sandbox)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read files
        predictions_df = pd.read_csv(predictions_path)
        sample_df = pd.read_csv(sample_path)

        # Ensure columns are in the same order as sample
        submission_df = predictions_df[sample_df.columns].copy()

        # Sort by ID column to match sample order
        id_col = sample_df.columns.tolist()[0]
        submission_records = [dict(row) for _, row in submission_df.iterrows()]
        submission_records.sort(key=lambda row: row[id_col])
        submission_df = pd.DataFrame(submission_records, columns=sample_df.columns)

        # Save to CSV
        submission_df.to_csv(output_path, index=False)

        return {
            "success": True,
            "data": {
                "output_file": _to_display_path(output_path, sandbox),
                "rows": len(submission_df),
                "columns": list(submission_df.columns),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# Register tools
def register_kaggle_tools():
    """Register Kaggle tools with the tool registry"""
    from kaggle_solver.tools.registry import ToolRegistry

    tools = {
        "kaggle_get_competition_info": kaggle_get_competition_info,
        "kaggle_download_data": kaggle_download_data,
        "kaggle_submit": kaggle_submit,
        "kaggle_get_submission_status": kaggle_get_submission_status,
        "kaggle_get_leaderboard": kaggle_get_leaderboard,
        "kaggle_list_competitions": kaggle_list_competitions,
        "kaggle_validate_submission": kaggle_validate_submission,
        "kaggle_prepare_submission": kaggle_prepare_submission,
    }

    for name, func in tools.items():
        ToolRegistry.register(name, func)

    return tools


register_kaggle_tools()
