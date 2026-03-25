import logging

from kaggle_solver.tools.registry import create_tool

logger = logging.getLogger(__name__)


@create_tool(
    name="pip_install",
    description="Install Python packages in the sandbox with pip",
    parameters={
        "packages": {
            "type": "string",
            "description": "Package specifier(s) to install, for example 'pandas' or 'pandas scikit-learn'",
        },
        "upgrade": {
            "type": "boolean",
            "description": "Whether to pass --upgrade to pip",
            "default": False,
        },
    },
)
def pip_install_tool(packages: str, upgrade: bool = False, sandbox=None) -> dict:
    """Install Python packages inside the sandbox."""
    if sandbox is None:
        return {"success": False, "error": "Sandbox not provided"}

    package_list = (packages or "").strip()
    if not package_list:
        return {"success": False, "error": "No packages provided"}

    command_parts = ["python3", "-m", "pip", "install"]
    if upgrade:
        command_parts.append("--upgrade")
    command_parts.extend(package_list.split())
    command = " ".join(command_parts)

    logger.debug("PIP INSTALL TOOL: command='%s'", command)
    result = sandbox.execute(command, timeout=180)
    output = result.output or result.error or ""

    if result.success:
        return {
            "success": True,
            "command": command,
            "output": output.strip() or f"Installed packages: {package_list}",
        }

    return {
        "success": False,
        "command": command,
        "error": output.strip() or "pip install failed",
    }
