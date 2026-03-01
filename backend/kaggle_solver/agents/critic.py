"""
Critic agent - validates submissions and suggests improvements
"""

from typing import Dict, Any, List


def validate_submission(submission: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Kaggle submission format and content"""
    errors = []
    
    # Check required fields
    if "score" not in submission and "accuracy" not in submission:
        errors.append("Missing score/accuracy")
    
    if "format" in submission:
        if submission["format"] not in ["csv", "json", "parquet"]:
            errors.append(f"Invalid format: {submission['format']}")
    
    # Check rows if provided
    if "rows" in submission:
        if submission["rows"] <= 0:
            errors.append("Invalid row count")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def suggest_improvements(metrics: Dict[str, Any]) -> List[str]:
    """Suggest improvements based on metrics"""
    suggestions = []
    
    score = metrics.get("score", metrics.get("accuracy", 0))
    
    if score < 0.6:
        suggestions.extend([
            "Try adding more features",
            "Consider feature engineering",
            "Check for data leakage"
        ])
    elif score < 0.8:
        suggestions.extend([
            "Try ensemble methods",
            "Hyperparameter tuning",
            "Cross-validation"
        ])
    else:
        suggestions.append("Good score! Consider model interpretability")
    
    # Model-specific
    model = metrics.get("model", "").lower()
    if "tree" in model or "forest" in model:
        suggestions.append("Try adding interaction features")
    
    if "logistic" in model:
        suggestions.append("Try polynomial features")
    
    return suggestions[:3]


def check_submission_format(content: str) -> Dict[str, Any]:
    """Check if submission file has correct format"""
    lines = content.strip().split('\n') if content else []
    
    if len(lines) < 2:
        return {"valid": False, "error": "Empty or too small"}
    
    header = lines[0].lower()
    
    # Check for Id column
    if "id" not in header and "id" not in header:
        return {"valid": False, "error": "Missing Id column"}
    
    return {"valid": True, "rows": len(lines) - 1}
