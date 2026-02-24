from kaggle_solver.tools.registry import create_tool


@create_tool(name="console", description="Execute shell commands in sandbox")
def console_tool(query: str, sandbox=None) -> str:
    """Execute shell commands in sandbox."""
    if sandbox is None:
        return "Error: Sandbox not provided"
    
    result = sandbox.execute(query)
    return result.output if result.success else f"Error: {result.error}"
