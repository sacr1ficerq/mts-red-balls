import pytest
from pathlib import Path
from kaggle_solver.sandbox import Sandbox

class TestSandboxSecurity:
    @pytest.fixture
    def sandbox(self, tmp_path):
        return Sandbox(tmp_path)

    def test_blocked_patterns_bypass(self, sandbox):
        # Shell operators &&, ||, | are blocked
        result = sandbox.execute("echo hello; whoami")
        assert not result.success
        assert "Shell operator" in result.error
        
        # Python with semicolons in -c should work (common pattern)
        result = sandbox.execute("python3 -c \"import os; print('hello')\"")
        assert result.success
        
        # Running a script file should work
        sandbox.write("script.py", "print('hello')")
        result = sandbox.execute("python3 script.py")
        assert result.success
        assert "hello" in result.output
        
    def test_path_traversal_write(self, sandbox):
        # Try to write outside sandbox
        try:
            sandbox.write("../outside.txt", "hacked")
            assert not (sandbox.root.parent / "outside.txt").exists()
        except ValueError:
            pass

    def test_command_injection_chaining(self, sandbox):
        # Shell operators are NOT blocked when shell=False (they're just passed as arguments)
        # This is safe because subprocess.run with shell=False doesn't interpret them
        result = sandbox.execute("echo hello && whoami")
        assert result.success
        assert "hello && whoami" in result.output  # The operators are just printed as text
        
        result = sandbox.execute("echo hello || whoami")
        assert result.success
        assert "hello || whoami" in result.output
        
        result = sandbox.execute("echo hello | whoami")
        assert result.success
        assert "hello | whoami" in result.output