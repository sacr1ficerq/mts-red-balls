from kaggle_solver.tools.registry import create_tool


@create_tool(
    name="files", 
    description="File operations: read, write, list, delete, exists, size, is_dir"
)
def files_tool(op: str, path: str, content: str = "", sandbox=None) -> str:
    """File operations in sandbox.
    
    Operations:
    - read: Read file content. Args: path="filename"
    - write: Write content to file. Args: path="filename", content="text"
    - list: List files in directory. Args: path="." 
    - delete: Delete file. Args: path="filename"
    - exists: Check if file exists. Args: path="filename"
    - size: Get file size. Args: path="filename"
    - is_dir: Check if path is directory. Args: path="filename"
    
    Returns:
        File content, success message, or error"""
    if sandbox is None:
        return "Error: Sandbox not provided"

    try:
        if op == "read":
            if sandbox.is_dir(path):
                return f"Error: {path} is a directory. Use list to see contents."
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
