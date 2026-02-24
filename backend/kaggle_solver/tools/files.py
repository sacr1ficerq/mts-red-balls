from kaggle_solver.tools.registry import create_tool


@create_tool(name="files", description="File operations (read, write, list, delete)")
def files_tool(op: str, path: str, content: str = "", sandbox=None) -> str:
    """File operations: read, write, list, delete, exists, size."""
    if sandbox is None:
        return "Error: Sandbox not provided"

    try:
        if op == "read":
            return sandbox.read(path)
        elif op == "write":
            sandbox.write(path, content)
            return f"Written to {path}"
        elif op == "list":
            files = sandbox.list(path)
            return "\n".join(files) if files else "Empty"
        elif op == "delete":
            sandbox.delete(path)
            return f"Deleted {path}"
        elif op == "exists":
            return str(sandbox.exists(path))
        elif op == "size":
            return str(sandbox.get_file_size(path))
        return f"Unknown operation: {op}"
    except Exception as e:
        return f"Error: {e}"
