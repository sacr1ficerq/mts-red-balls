import logging
from kaggle_solver.tools.registry import create_tool

logger = logging.getLogger(__name__)


@create_tool(
    name="console",
    description="Execute shell commands (python3, ls, cat, mkdir, rm, cp, etc.) in sandbox",
)
def console_tool(query: str, sandbox=None) -> str:
    """Execute shell commands in sandbox.

    Args:
        query: Shell command to execute (e.g., "python3 script.py", "ls -la", "cat file.txt")

    Returns:
        Command output or error message"""
    if sandbox is None:
        return "Error: Sandbox not provided"

    logger.debug(f"CONSOLE TOOL: query='{query}'")
    result = sandbox.execute(query)
    logger.debug(
        f"CONSOLE RESULT: success={result.success}, output='{result.output}', error='{result.error}'"
    )
    if result.success:
        return result.output

    error_text = result.error or result.output or "Unknown error"
    return f"Error: {error_text}"
