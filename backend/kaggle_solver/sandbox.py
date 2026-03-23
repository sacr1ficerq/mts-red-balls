from pathlib import Path
from subprocess import run, PIPE, TimeoutExpired
from dataclasses import dataclass
import shutil
import logging
import os

from kaggle_solver.constants import SandboxConstants

logger = logging.getLogger(__name__)


@dataclass
class Result:
    success: bool
    output: str = ""
    error: str = ""
    return_code: int = 0


class Sandbox:
    # ==================== PREINSTALL CONFIGURATION ====================
    # Set to False to disable all package preinstallation
    ENABLE_PREINSTALL = False
    
    # Packages to preinstall when ENABLE_PREINSTALL is True
    PREINSTALL_PACKAGES = [
        "scikit-learn", "pandas", "numpy", "catboost", "xgboost",
        "lightgbm", "matplotlib", "seaborn", "joblib"
    ]
    # ==================================================================
    
    ALLOWED_COMMANDS = SandboxConstants.ALLOWED_COMMANDS
    BLOCKED_PATTERNS = SandboxConstants.BLOCKED_PATTERNS
    BLOCKED_ESCAPE_SEQUENCES = SandboxConstants.BLOCKED_ESCAPE_SEQUENCES
    BLOCKED_PATH_PREFIXES = SandboxConstants.BLOCKED_PATH_PREFIXES
    MAX_FILE_SIZE = SandboxConstants.MAX_WRITE_FILE_SIZE
    
    def __init__(self, root: Path, timeout: int = 60, preinstall: bool = None):
        self.root = root.resolve()
        self.timeout = timeout
        self.root.mkdir(parents=True, exist_ok=True)
        self._created_files = set()
        
        # Preinstall common ML packages
        # Use class-level ENABLE_PREINSTALL if preinstall parameter not explicitly set
        should_preinstall = preinstall if preinstall is not None else self.ENABLE_PREINSTALL
        if should_preinstall:
            self._preinstall_packages()
    
    def _preinstall_packages(self):
        """Preinstall common ML packages."""
        if not self.ENABLE_PREINSTALL:
            logger.info("Preinstall disabled by ENABLE_PREINSTALL=False")
            return
            
        import subprocess
        import sys
        logger.info(f"Preinstalling {len(self.PREINSTALL_PACKAGES)} packages...")
        for pkg in self.PREINSTALL_PACKAGES:
            try:
                # Install to system Python (works because we're using system python3)
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "--user", pkg],
                    capture_output=True,
                    timeout=SandboxConstants.PREINSTALL_TIMEOUT
                )
                if result.returncode == 0:
                    logger.info(f"Preinstalled: {pkg}")
                else:
                    logger.warning(f"Failed to install {pkg}: {result.stderr.decode()[:100]}")
            except Exception as e:
                logger.warning(f"Failed to preinstall {pkg}: {e}")

    def _secure_path(self, path: str) -> Path:
        """Securely resolve a path within the sandbox.
        
        This method prevents path traversal attacks by:
        1. Normalizing the path to resolve any .. or . components
        2. Ensuring the resolved path is within the sandbox root
        3. Checking for symlinks that point outside the sandbox
        4. Blocking access to device paths (/dev, /proc, /sys, etc.)
        
        Args:
            path: The path to secure (can be relative or absolute)
            
        Returns:
            The resolved, secure Path object
            
        Raises:
            ValueError: If the path attempts to escape the sandbox
        """
        # Block device paths and other sensitive system paths
        path_lower = path.lower()
        for blocked_prefix in self.BLOCKED_PATH_PREFIXES:
            if path_lower.startswith(blocked_prefix.lower()):
                raise ValueError(f"Security: device path not allowed: {path}")
        
        # CRITICAL: Use os.path.normpath to properly normalize path components
        # This handles all forms of path traversal (.., ., etc.)
        clean = os.path.normpath(path)
        
        # Remove leading slashes to make it relative to sandbox root
        clean = clean.lstrip("/")
        
        # Resolve to absolute path within sandbox
        full = (self.root / clean).resolve()

        # CRITICAL: Check if resolved path is within sandbox
        # This is the primary defense against path traversal
        try:
            full.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Security: path outside sandbox: {path}")
        
        # Check for symlinks pointing outside sandbox
        if full.is_symlink():
            target = full.readlink()
            if target.is_absolute():
                raise ValueError(f"Security: absolute symlink not allowed: {path}")
            resolved_target = (full.parent / target).resolve()
            try:
                resolved_target.relative_to(self.root)
            except ValueError:
                raise ValueError(f"Security: symlink points outside sandbox: {path}")
        
        return full

    def _is_command_safe(self, command: str) -> bool:
        """Check if a command is safe to execute.
        
        Security checks:
        1. Block shell operators for command chaining
        2. Block dangerous patterns (network tools, privilege escalation)
        3. Block escape sequences that could bypass validation
        4. Block command substitution patterns
        
        Args:
            command: The command string to validate
            
        Returns:
            True if the command is safe, False otherwise
        """
        cmd_lower = command.lower()
        
        # Check if this is a Python command (for special handling)
        is_python_cmd = command.strip().startswith("python") or command.strip().startswith("python3")
        
        # Block shell operators for chaining
        shell_operators = ["&&", "||", "|", ";"]
        
        for op in shell_operators:
            if op in command:
                # Allow semicolons in Python -c commands
                if op == ";" and is_python_cmd:
                    continue
                return False
        
        # Check blocked patterns (but skip semicolon for Python commands)
        for pattern in self.BLOCKED_PATTERNS:
            if pattern == ";" and is_python_cmd:
                continue
            if pattern in cmd_lower:
                return False
        
        # Block escape sequences that could be used to bypass validation
        # Note: newlines and carriage returns are allowed in Python commands
        for seq in self.BLOCKED_ESCAPE_SEQUENCES:
            if seq in command:
                # Allow \n and \r in Python commands for multi-line code
                if is_python_cmd and seq in ("\n", "\r"):
                    continue
                return False
        
        # Additional check: block raw escape characters (except newlines/tabs in Python commands)
        if is_python_cmd:
            # For Python commands, only block truly dangerous control characters
            dangerous_chars = [c for c in command if ord(c) < 32 and c not in ' \t\n\r']
            if dangerous_chars:
                return False
        else:
            # For non-Python commands, block all control characters except space and tab
            if any(ord(c) < 32 and c not in ' \t' for c in command):
                return False
            
        return True

    def read(self, path: str, encoding: str = "utf-8") -> str:
        p = self._secure_path(path)
        if p.is_dir():
            return f"Error: Path is a directory: {path}. Use list to see contents."
        return p.read_text(encoding=encoding)

    def write(self, path: str, content: str, encoding: str = "utf-8"):
        if len(content.encode(encoding)) > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large. Max size: {self.MAX_FILE_SIZE} bytes")
        p = self._secure_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        self._created_files.add(str(p))

    def exists(self, path: str) -> bool:
        return self._secure_path(path).exists()

    def is_dir(self, path: str) -> bool:
        return self._secure_path(path).is_dir()

    def list(self, path: str = ".") -> list:
        p = self._secure_path(path)
        if p.is_dir():
            return [str(x.relative_to(self.root)) for x in p.rglob("*") if not x.name.startswith('.') and x.name not in ('__pycache__', 'node_modules', '.git')]
        return []

    def list_dir(self, path: str = ".") -> list:
        p = self._secure_path(path)
        if p.is_dir():
            return [str(x.relative_to(self.root)) for x in p.iterdir() if not x.name.startswith('.') and x.name not in ('__pycache__', 'node_modules', '.git')]
        return []

    def delete(self, path: str):
        p = self._secure_path(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    def execute(self, command: str, timeout: int = None) -> Result:
        """Execute a command in the sandbox with enhanced security.
        
        Security measures:
        - Only whitelisted commands allowed
        - No shell operators (&&, ||, ;, |, etc.)
        - No absolute paths
        - No path traversal (..)
        - No environment variable expansion
        - Command output size limited
        - Timeout enforced
        - shell=False to prevent shell injection
        
        Args:
            command: The command string to execute
            timeout: Optional timeout in seconds (defaults to instance timeout)
            
        Returns:
            Result object with success status, output, and error information
        """
        if timeout is None:
            timeout = self.timeout
            
        # Validate command is not empty
        if not command or not command.strip():
            return Result(False, error="Empty command")
        
        # Check for shell operators and blocked patterns
        if not self._is_command_safe(command):
            return Result(False, error="Shell operator or blocked pattern detected")
        
        # Parse command safely using shlex to handle quoted arguments
        try:
            import shlex
            cmd_parts = shlex.split(command)
        except ValueError as e:
            return Result(False, error=f"Invalid command syntax: {e}", return_code=1)
            
        if not cmd_parts:
            return Result(False, error="Empty command")

        # CRITICAL: Only allow whitelisted commands - NO ./ scripts
        first_cmd = cmd_parts[0]
        if first_cmd not in self.ALLOWED_COMMANDS:
            return Result(False, error=f"Command not allowed: {first_cmd}")

        # CRITICAL: Validate all command arguments for security
        for i, part in enumerate(cmd_parts[1:], start=1):  # Skip the command itself
            # Block absolute paths (except for flags starting with --)
            if part.startswith("/") and not part.startswith("--"):
                return Result(False, error=f"Absolute paths not allowed in argument {i}: {part}", return_code=1)
            
            # Block path traversal attempts
            if ".." in part:
                return Result(False, error=f"Path traversal not allowed in argument {i}: {part}", return_code=1)
            
            # Block environment variable expansion
            if "$" in part:
                return Result(False, error=f"Environment variable expansion not allowed in argument {i}: {part}", return_code=1)
            
            # Block command substitution
            if "`" in part or "$(" in part:
                return Result(False, error=f"Command substitution not allowed in argument {i}: {part}", return_code=1)
            
            # Block pipe redirection attempts
            if ">" in part or "<" in part:
                return Result(False, error=f"Redirection not allowed in argument {i}: {part}", return_code=1)

        timeout = timeout or self.timeout
        
        try:
            import site
            user_site = site.getusersitepackages()
            
            # Create minimal, safe environment with no dangerous variables
            env = {
                "HOME": str(self.root),
                "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                "PYTHONPATH": user_site if user_site else "",
                "PYTHONUNBUFFERED": "1",  # Ensure Python output is not buffered
            }
            
            # CRITICAL: Use shell=False to prevent shell injection
            # This ensures command arguments are passed directly to the executable
            r = run(
                cmd_parts,
                shell=False,  # CRITICAL: Never use shell=True with user input
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            # Limit output size to prevent memory issues
            output = r.stdout + (r.stderr if r.stderr else "")
            if len(output) > SandboxConstants.MAX_OUTPUT_SIZE:
                output = output[:SandboxConstants.MAX_OUTPUT_SIZE] + "\n... (output truncated)"
            
            return Result(
                success=r.returncode == 0,
                output=output,
                return_code=r.returncode
            )
        except TimeoutExpired:
            return Result(False, error="Command timed out", return_code=124)
        except PermissionError as e:
            return Result(False, error=f"Permission denied: {e}")
        except FileNotFoundError as e:
            return Result(False, error=f"Command not found: {e}")
        except Exception as e:
            logger.error(f"Unexpected error executing command: {e}", exc_info=True)
            return Result(False, error=str(e), return_code=1)

    def execute_python(self, code: str, timeout: int = None) -> Result:
        import uuid
        script_name = f"_temp_script_{uuid.uuid4().hex}.py"
        script_path = self.root / script_name
        script_path.write_text(code)
        try:
            result = self.execute(f"python3 {script_name}", timeout=timeout)
            return result
        finally:
            if script_path.exists():
                script_path.unlink()

    def get_file_size(self, path: str) -> int:
        return self._secure_path(path).stat().st_size

    def cleanup(self):
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True)
        self._created_files.clear()

    def get_created_files(self) -> list:
        return list(self._created_files)
