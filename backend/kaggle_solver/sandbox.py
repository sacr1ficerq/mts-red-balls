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
    
    BLOCKED_PATTERNS = [
        "rm -rf /", "rm -rf *", "rm -rf .",
        "> /dev/sd", "dd if=",
        "mkfs", "dd if=/dev/zero",
        "chmod 777", "chown -R",
        ":(){:|:&};:", "fork()",
        "/bin/sh", "/bin/bash", "nc -e", "socat",
        "wget http", "curl http", # Prevent downloading from arbitrary URLs if strict
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
        
        # Allow semicolons in Python -c commands (e.g., python3 -c "import x; print(x)")
        # But block them in shell commands for chaining
        if ";" in command and not command.strip().startswith("python"):
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
        # Fix: replace 'python' with 'python3' (python may not exist)
        if command.startswith("python "):
            command = "python3" + command[6:]
        
        # Fix: handle escaped newlines and literal newlines in strings
        # Agent may send: 'hello\nworld' which should stay as literal
        # or actual newlines which break shell
        command = command.replace('\\n', '\\\\n').replace('\\r', '\\\\r')
        
        if not self._is_command_safe(command):
            return Result(False, error="Command contains blocked patterns", return_code=1)

        try:
            cmd_parts = command.replace("&&", " ").replace("||", " ").replace("|", " ").split()
        except:
            cmd_parts = command.split()
            
        if not cmd_parts:
            return Result(False, error="Empty command")

        first_cmd = cmd_parts[0]
        if first_cmd not in self.ALLOWED_COMMANDS and not first_cmd.startswith("./"):
             return Result(False, error=f"Command not allowed: {first_cmd}")

        separators = {"&&", "||", "|"}
        parts = command.split()
        for i, part in enumerate(parts):
            if part in separators and i + 1 < len(parts):
                next_cmd = parts[i+1]
                if next_cmd not in self.ALLOWED_COMMANDS and not next_cmd.startswith("./"):
                    return Result(False, error=f"Command not allowed in chain: {next_cmd}")

        if " /" in command or command.startswith("/"):
            return Result(False, error="Absolute paths not allowed", return_code=1)

        timeout = timeout or self.timeout
        
        try:
            env = {**os.environ, "HOME": str(self.root)}
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")
            r = run(
                command,
                shell=True,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                executable="/bin/bash"
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
