from pathlib import Path
from subprocess import run, PIPE, TimeoutExpired
from dataclasses import dataclass
import shutil
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class Result:
    success: bool
    output: str = ""
    error: str = ""
    return_code: int = 0


class Sandbox:
    ALLOWED_COMMANDS = {
        "python", "python3", "pip", "pip3",
        "ls", "cat", "head", "tail", "grep", "find",
        "mkdir", "rm", "rmdir", "cp", "mv",
        "curl", "wget", "tar", "unzip", "zip",
        "chmod", "chown", "echo", "pwd", "whoami",
        "date", "time", "touch", "which", "cd", "exit",
        "docker", "node", "npm", "npx"
    }
    
    PREINSTALL_PACKAGES = [
        "scikit-learn", "pandas", "numpy", "catboost", "xgboost", 
        "lightgbm", "matplotlib", "seaborn", "joblib"
    ]
    
    BLOCKED_PATTERNS = [
        "rm -rf /", "rm -rf *", "rm -rf .",
        "> /dev/sd", "dd if=",
        "mkfs", "dd if=/dev/zero",
        "chmod 777", "chown -R",
        ":(){:|:&};:", "fork()",
        "/bin/sh", "/bin/bash", "nc -e", "socat",
        "wget http", "curl http", # Prevent downloading from arbitrary URLs if strict
    ]

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    
    def __init__(self, root: Path, timeout: int = 60, preinstall: bool = True):
        self.root = root.resolve()
        self.timeout = timeout
        self.root.mkdir(parents=True, exist_ok=True)
        self._created_files = set()
        
        # Preinstall common ML packages
        if preinstall:
            self._preinstall_packages()
    
    def _preinstall_packages(self):
        """Preinstall common ML packages."""
        import subprocess
        import sys
        for pkg in self.PREINSTALL_PACKAGES:
            try:
                # Install to system Python (works because we're using system python3)
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "--user", pkg],
                    capture_output=True,
                    timeout=180
                )
                if result.returncode == 0:
                    logger.info(f"Preinstalled: {pkg}")
                else:
                    logger.warning(f"Failed to install {pkg}: {result.stderr.decode()[:100]}")
            except Exception as e:
                logger.warning(f"Failed to preinstall {pkg}: {e}")

    def _secure_path(self, path: str) -> Path:
        # Remove all path traversal attempts iteratively
        clean = path
        while ".." in clean:
            clean = clean.replace("..", "")
        clean = clean.lstrip("/")
        
        # Resolve to absolute path
        full = (self.root / clean).resolve()

        # Check if resolved path is within sandbox
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
        cmd_lower = command.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in cmd_lower:
                return False
        
        # Block shell operators for chaining
        shell_operators = ["&&", "||", "|", ";"]
        is_python_cmd = command.strip().startswith("python")
        
        for op in shell_operators:
            if op in command:
                # Allow semicolons in Python -c commands
                if op == ";" and is_python_cmd:
                    continue
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
        if timeout is None:
            timeout = self.timeout
            
        cmd = command.strip().split()
        
        if not cmd:
            return Result(False, error="Empty command")
            
        if not self._is_command_safe(command):
            return Result(False, error="Shell operator or blocked pattern detected")
        
        if cmd[0] not in self.ALLOWED_COMMANDS:
            return Result(False, error=f"Command not allowed: {cmd[0]}")
        
        try:
            import shlex
            cmd_parts = shlex.split(command)
        except ValueError as e:
            return Result(False, error=f"Invalid command syntax: {e}", return_code=1)
            
        if not cmd_parts:
            return Result(False, error="Empty command")

        first_cmd = cmd_parts[0]
        if first_cmd not in self.ALLOWED_COMMANDS and not first_cmd.startswith("./"):
             return Result(False, error=f"Command not allowed: {first_cmd}")

        # Block absolute paths
        for part in cmd_parts:
            if part.startswith("/") and not part.startswith("--"):
                return Result(False, error="Absolute paths not allowed", return_code=1)

        timeout = timeout or self.timeout
        
        try:
            import site
            user_site = site.getusersitepackages()
            env = {**os.environ, "HOME": str(self.root)}
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
            # Add user site-packages to PYTHONPATH so installed packages are found
            if user_site:
                env["PYTHONPATH"] = user_site
            
            # Use shell=False for security - pass args as list
            r = run(
                cmd_parts,
                shell=False,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            output = r.stdout + (r.stderr if r.stderr else "")
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
