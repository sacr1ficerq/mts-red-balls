import re
from pathlib import Path

from kaggle_solver.tools.registry import create_tool


def _normalize_write_content(path: str, content: str) -> str:
    if not isinstance(content, str) or not content:
        return content

    if "\n" in content or "\r" in content:
        return content

    file_suffix = Path(path).suffix.lower()
    if file_suffix != ".py":
        return content

    if r"\n" not in content and r"\r" not in content:
        return content

    try:
        compile(content, path or "<string>", "exec")
        return content
    except SyntaxError:
        pass

    try:
        decoded = content.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return content

    if decoded == content:
        return content

    try:
        compile(decoded, path or "<string>", "exec")
        return decoded
    except SyntaxError:
        return content

    return content


@create_tool(
    name="files",
    description="File operations: read, write, edit, list, delete, exists, size, is_dir",
)
def files_tool(
    op: str,
    path: str,
    content: str = "",
    search: str = "",
    replace: str = "",
    sandbox=None,
) -> str:
    """File operations in sandbox.

    Operations:
    - read: Read file content. Args: path="filename"
    - write: Write full content to file. Args: path="filename", content="text"
    - edit: Search & Replace in file. Args: path="filename", search="text to find", replace="new text"
    - edit_regex: Replace using regex. Args: path="filename", search="pattern", replace="replacement"
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
            sandbox.write(path, _normalize_write_content(path, content))
            return f"Written to {path}"

        elif op == "edit":
            if not search:
                return "Error: 'search' parameter required for edit operation"
            file_content = sandbox.read(path)
            if search not in file_content:
                return f"Error: Search text not found in {path}"
            new_content = file_content.replace(search, replace, 1)
            sandbox.write(path, new_content)
            return f"Edited {path}: replaced 1 occurrence"

        elif op == "edit_regex":
            if not search:
                return "Error: 'search' parameter required for edit_regex operation"
            file_content = sandbox.read(path)
            new_content, count = re.subn(search, replace, file_content, count=1)
            if count == 0:
                return f"Error: Regex pattern not found in {path}"
            sandbox.write(path, new_content)
            return f"Edited {path}: replaced {count} occurrence(s)"

        elif op == "edit_all":
            if not search:
                return "Error: 'search' parameter required for edit_all operation"
            file_content = sandbox.read(path)
            new_content = file_content.replace(search, replace)
            sandbox.write(path, new_content)
            return f"Edited {path}: replaced all occurrences"

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
