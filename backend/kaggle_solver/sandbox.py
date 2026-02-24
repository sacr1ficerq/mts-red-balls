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
        "date", "time", "touch", "which"
    }
    
    BLOCKED_PATTERNS = [
        "; rm -rf", "&& rm -rf", "| rm -rf",
        "> /dev/sd", "dd if=",
        "mkfs", "dd if=/dev/zero",
        "chmod 777 /", "chown -R",
        ":(){:|:&};:", "fork()",
    ]

    def __init__(self, root: Path, timeout: int = 60):
        self.root = root.resolve()
        self.timeout = timeout
        self.root.mkdir(parents=True, exist_ok=True)
        self._created_files = set()

    def _secure_path(self, path: str) -> Path:
        clean = path.replace("..", "").lstrip("/")
        full = (self.root / clean).resolve()

        if not str(full).startswith(str(self.root)):
            raise ValueError(f"Security: path outside sandbox: {path}")
        return full

    def _is_command_safe(self, command: str) -> bool:
        cmd_lower = command.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in cmd_lower:
                return False
        return True

    def read(self, path: str, encoding: str = "utf-8") -> str:
        return self._secure_path(path).read_text(encoding=encoding)

    def write(self, path: str, content: str, encoding: str = "utf-8"):
        p = self._secure_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        self._created_files.add(str(p))

    def exists(self, path: str) -> bool:
        return self._secure_path(path).exists()

    def list(self, path: str = ".") -> list:
        p = self._secure_path(path)
        if p.is_dir():
            return [str(x.relative_to(self.root)) for x in p.rglob("*")]
        return []

    def list_dir(self, path: str = ".") -> list:
        p = self._secure_path(path)
        if p.is_dir():
            return [str(x.relative_to(self.root)) for x in p.iterdir()]
        return []

    def delete(self, path: str):
        p = self._secure_path(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    def execute(self, command: str, timeout: int = None) -> Result:
        if not self._is_command_safe(command):
            return Result(False, error="Command contains blocked patterns", return_code=1)

        cmd = command.strip().split()
        if not cmd:
            return Result(False, error="Empty command")

        if cmd[0] not in self.ALLOWED_COMMANDS:
            return Result(False, error=f"Command not allowed: {cmd[0]}")

        if " /" in command or command.startswith("/"):
            return Result(False, error="Absolute paths not allowed", return_code=1)

        timeout = timeout or self.timeout
        
        try:
            r = run(
                command,
                shell=True,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "HOME": str(self.root)}
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
        except Exception as e:
            return Result(False, error=str(e), return_code=1)

    def execute_python(self, code: str, timeout: int = None) -> Result:
        script_path = self.root / "_temp_script.py"
        script_path.write_text(code)
        try:
            result = self.execute(f"python {script_path.name}", timeout=timeout)
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
