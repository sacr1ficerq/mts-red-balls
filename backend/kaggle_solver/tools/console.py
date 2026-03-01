from kaggle_solver.tools.registry import create_tool


@create_tool(
    name="console", 
    description="Execute shell commands (python3, ls, cat, mkdir, rm, cp, etc.) in sandbox"
)
def console_tool(query: str, sandbox=None) -> str:
    """Execute shell commands in sandbox.
    
    Args:
        query: Shell command to execute (e.g., "python3 script.py", "ls -la", "cat file.txt")
    
    Returns:
        Command output or error message"""
    if sandbox is None:
        return "Error: Sandbox not provided"
    
    result = sandbox.execute(query)
    return result.output if result.success else f"Error: {result.error}"
