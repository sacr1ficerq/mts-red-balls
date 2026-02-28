import pytest
from pathlib import Path
from kaggle_solver.sandbox import Sandbox

class TestSandboxSecurity:
    @pytest.fixture
    def sandbox(self, tmp_path):
        return Sandbox(tmp_path)

    def test_blocked_patterns_bypass(self, sandbox):
        # Try to bypass blocked patterns
        
        # Semicolons should be blocked to prevent command chaining
        result = sandbox.execute("python3 -c \"import os; print('I am root')\"")
        assert not result.success
        assert "Command contains blocked patterns" in result.error
        
        # But running a script file should work (if content is safe)
        sandbox.write("script.py", "print('hello')")
        result = sandbox.execute("python3 script.py")
        assert result.success
        assert "hello" in result.output
        
    def test_path_traversal_write(self, sandbox):
        # Try to write outside sandbox
        try:
            sandbox.write("../outside.txt", "hacked")
            # If we get here, check if file exists
            assert not (sandbox.root.parent / "outside.txt").exists()
        except ValueError:
            pass # Expected

    def test_command_injection_chaining(self, sandbox):
        # Try chaining commands without the specific blocked patterns
        # e.g. using newlines or other separators
        # Note: \n is treated as whitespace by split(), so "echo hello\nls" -> "echo", "hello", "ls"
        # This doesn't trigger the separator logic unless we explicitly check for \n as a separator
        # But our new logic checks &&, ||, |
        
        # This should fail now because 'rm' is allowed but we want to test the logic
        # Let's try a disallowed command
        result = sandbox.execute("echo hello && whoami")
        assert result.success # whoami is allowed
        
        result = sandbox.execute("echo hello && notallowed")
        assert not result.success
        assert "Command not allowed in chain" in result.error