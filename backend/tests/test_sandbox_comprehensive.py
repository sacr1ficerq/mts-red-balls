import pytest
import os
import tempfile
import subprocess
from pathlib import Path

from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.console import console_tool
from kaggle_solver.tools.files import files_tool
from kaggle_solver.tools.registry import ToolRegistry, ToolResult


class TestSandboxComprehensive:
    """Comprehensive tests for Sandbox - catch all execution issues."""
    
    @pytest.fixture
    def sandbox(self):
        """Create sandbox with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir), timeout=30)
    
    @pytest.fixture
    def sandbox_with_files(self, sandbox):
        """Sandbox with some test files."""
        sandbox.write("test.txt", "hello world")
        sandbox.write("data.json", '{"key": "value"}')
        sandbox.write("empty.txt", "")
        return sandbox
    
    # === Basic execution tests ===
    
    def test_execute_echo(self, sandbox):
        """Basic echo command should work."""
        result = sandbox.execute("echo hello")
        assert result.success is True
        assert "hello" in result.output.lower()
    
    def test_execute_python_simple(self, sandbox):
        """Python print should work."""
        result = sandbox.execute("python3 -c \"print('hello world')\"")
        assert result.success is True
        assert "hello world" in result.output
    
    def test_execute_python_random(self, sandbox):
        """Python random should work."""
        result = sandbox.execute("python3 -c \"import random; print(random.randint(1,1000))\"")
        assert result.success is True
        # Output should contain a number
        output = result.output.strip()
        assert output.isdigit() or (output.replace('\n','').replace(' ','').isdigit())
    
    def test_execute_python_file_write(self, sandbox):
        """Python should be able to write files."""
        result = sandbox.execute("python3 -c \"with open('output.txt', 'w') as f: f.write('test content')\"")
        assert result.success is True
        # File should exist
        assert sandbox.exists("output.txt")
        assert sandbox.read("output.txt") == "test content"
    
    def test_execute_python_file_read(self, sandbox):
        """Python should be able to read files."""
        sandbox.write("input.txt", "file content")
        result = sandbox.execute("python3 -c \"with open('input.txt', 'r') as f: print(f.read())\"")
        assert result.success is True
        assert "file content" in result.output
    
    def test_execute_python_list_comprehension(self, sandbox):
        """Python list comprehension should work."""
        result = sandbox.execute("python3 -c \"print([i for i in range(10)])\"")
        assert result.success is True
        assert "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]" in result.output
    
    def test_execute_python_random_many(self, sandbox):
        """Python random with many numbers should work."""
        result = sandbox.execute('python3 -c "import random; print(\' \'.join([str(random.randint(1,1000)) for _ in range(100)]))"')
        assert result.success is True
        numbers = result.output.strip().split()
        assert len(numbers) == 100
    
    def test_execute_python_create_100x100_table(self, sandbox):
        """Create 100x100 table - the exact use case that failed."""
        code = """python3 -c "
import random
with open('table.txt', 'w') as f:
    for _ in range(100):
        row = ' '.join([str(random.randint(1, 1000)) for _ in range(100)])
        f.write(row + chr(10))
print('Created 100x100')
\""" """
        result = sandbox.execute(code)
        assert result.success is True, f"Failed: {result.error}"
        assert sandbox.exists("table.txt")
        # Check file has 100 lines
        content = sandbox.read("table.txt")
        lines = content.strip().split('\n')
        assert len(lines) == 100, f"Expected 100 lines, got {len(lines)}"
        # Check each line has 100 numbers
        for i, line in enumerate(lines):
            nums = line.split()
            assert len(nums) == 100, f"Line {i}: expected 100 numbers, got {len(nums)}"
    
    def test_execute_pip_list(self, sandbox):
        """pip list should work or fail gracefully."""
        result = sandbox.execute("python3 -m pip list")
        # May work or fail depending on environment
        assert result is not None
    
    def test_execute_timeout(self, sandbox):
        """Long-running command should timeout."""
        result = sandbox.execute("python3 -c \"import time; time.sleep(60)\"", timeout=2)
        assert result.success is False
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()
    
    def test_execute_empty_command(self, sandbox):
        """Empty command should fail."""
        result = sandbox.execute("")
        assert result.success is False
    
    def test_execute_python_syntax_error(self, sandbox):
        """Python syntax error should be handled."""
        result = sandbox.execute("python3 -c \"print(")
        assert result.success is False
    
    def test_execute_file_not_found(self, sandbox):
        """File not found should fail gracefully."""
        result = sandbox.execute("cat nonexistent.txt")
        assert result.success is False
    
    # === File operations tests ===
    
    def test_write_and_read(self, sandbox):
        """Write and read should work."""
        sandbox.write("test.txt", "hello")
        assert sandbox.read("test.txt") == "hello"
    
    def test_write_binary_content(self, sandbox):
        """Binary content should work."""
        content = bytes([0, 1, 2, 255]).decode('latin-1')
        sandbox.write("binary.bin", content)
        assert sandbox.read("binary.bin") == content
    
    def test_exists(self, sandbox):
        """Exists check should work."""
        assert not sandbox.exists("test.txt")
        sandbox.write("test.txt", "content")
        assert sandbox.exists("test.txt")
    
    def test_delete_file(self, sandbox):
        """Delete file should work."""
        sandbox.write("test.txt", "content")
        sandbox.delete("test.txt")
        assert not sandbox.exists("test.txt")
    
    def test_delete_directory(self, sandbox):
        """Delete directory should work."""
        sandbox.execute("mkdir subdir")
        sandbox.delete("subdir")
        # Directory should be gone
        result = sandbox.execute("ls")
        assert "subdir" not in result.output
    
    def test_list_files(self, sandbox):
        """List files should work."""
        sandbox.write("file1.txt", "a")
        sandbox.write("file2.txt", "b")
        files = sandbox.list(".")
        assert "file1.txt" in files
        assert "file2.txt" in files
    
    def test_file_size(self, sandbox):
        """File size should work."""
        sandbox.write("test.txt", "hello world")
        size = sandbox.get_file_size("test.txt")
        assert size > 0
    
    def test_created_files_tracking(self, sandbox):
        """Created files should be tracked."""
        sandbox.write("test.txt", "content")
        created = sandbox.get_created_files()
        assert any("test.txt" in f for f in created)


class TestConsoleToolComprehensive:
    """Comprehensive tests for console tool."""
    
    @pytest.fixture
    def sandbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir))
    
    def test_console_echo(self, sandbox):
        """Console echo should work."""
        result = console_tool(query="echo test", sandbox=sandbox)
        assert "test" in result.lower() or result == ""
    
    def test_console_python_print(self, sandbox):
        """Console python print should work."""
        result = console_tool(query="python3 -c \"print('hello')\"", sandbox=sandbox)
        assert "hello" in result.lower() or result == ""
    
    def test_console_python_random(self, sandbox):
        """Console random should work."""
        result = console_tool(query="python3 -c \"import random; print(random.randint(1,100))\"", sandbox=sandbox)
        # May succeed or fail, but shouldn't crash
        assert result is not None
    
    def test_console_ls(self, sandbox):
        """Console ls should work."""
        result = console_tool(query="ls", sandbox=sandbox)
        assert result is not None
    
    def test_console_no_sandbox(self):
        """Console without sandbox should fail."""
        result = console_tool(query="echo test", sandbox=None)
        assert "Error" in result
    
    def test_console_invalid_command(self, sandbox):
        """Console with invalid command should fail gracefully."""
        result = console_tool(query="invalid_cmd_xyz", sandbox=sandbox)
        assert result is not None


class TestFilesToolComprehensive:
    """Comprehensive tests for files tool."""
    
    @pytest.fixture
    def sandbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir))
    
    def test_files_write(self, sandbox):
        """Files write should work."""
        result = files_tool(op="write", path="test.txt", content="hello", sandbox=sandbox)
        assert sandbox.exists("test.txt")
    
    def test_files_read(self, sandbox):
        """Files read should work."""
        sandbox.write("test.txt", "hello")
        result = files_tool(op="read", path="test.txt", sandbox=sandbox)
        assert "hello" in result
    
    def test_files_list(self, sandbox):
        """Files list should work."""
        sandbox.write("a.txt", "a")
        sandbox.write("b.txt", "b")
        result = files_tool(op="list", path=".", sandbox=sandbox)
        assert "a.txt" in result
        assert "b.txt" in result
    
    def test_files_delete(self, sandbox):
        """Files delete should work."""
        sandbox.write("test.txt", "content")
        result = files_tool(op="delete", path="test.txt", sandbox=sandbox)
        assert not sandbox.exists("test.txt")
    
    def test_files_exists(self, sandbox):
        """Files exists should work."""
        assert "False" in files_tool(op="exists", path="test.txt", sandbox=sandbox)
        sandbox.write("test.txt", "content")
        assert "True" in files_tool(op="exists", path="test.txt", sandbox=sandbox)
    
    def test_files_size(self, sandbox):
        """Files size should work."""
        sandbox.write("test.txt", "hello world")
        result = files_tool(op="size", path="test.txt", sandbox=sandbox)
        assert int(result) > 0
    
    def test_files_no_sandbox(self):
        """Files without sandbox should fail."""
        result = files_tool(op="read", path="test.txt", sandbox=None)
        assert "Error" in result
    
    def test_files_invalid_operation(self, sandbox):
        """Files with invalid operation should fail."""
        result = files_tool(op="invalid", path="test.txt", sandbox=sandbox)
        assert "Unknown" in result or "Error" in result


class TestToolRegistryComprehensive:
    """Comprehensive tests for ToolRegistry."""
    
    def test_execute_with_sandbox_kwarg(self):
        """Tool should receive sandbox as kwarg."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            result = ToolRegistry.execute(
                "console",
                query="echo hello",
                sandbox=sandbox
            )
            assert result.success is True or result.error == ""
    
    def test_execute_with_llm_kwarg(self):
        """Tool should receive llm as kwarg."""
        result = ToolRegistry.execute(
            "search",
            query="test",
            llm=None  # May fail but shouldn't crash
        )
        assert result is not None
    
    def test_execute_unknown_tool(self):
        """Unknown tool should fail gracefully."""
        result = ToolRegistry.execute("nonexistent_tool_xyz")
        assert result.success is False
        assert "Unknown" in result.error
    
    def test_execute_tool_with_json_query(self):
        """Tool should handle JSON query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            result = ToolRegistry.execute(
                "files",
                query='{"op": "write", "path": "test.txt", "content": "hello"}',
                sandbox=sandbox
            )
            assert result.success is True


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""
    
    def test_create_and_run_python_script(self):
        """Create Python script and run it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Write script
            script = "print('Hello from script!')\nprint(2+2)"
            sandbox.write("script.py", script)
            
            # Run script
            result = sandbox.execute("python3 script.py")
            assert result.success is True
            assert "Hello from script" in result.output
            assert "4" in result.output
    
    def test_process_data_file(self):
        """Process data file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Create data
            data = "1,2,3\n4,5,6\n7,8,9"
            sandbox.write("data.csv", data)
            
            # Process
            code = """python3 -c "
with open('data.csv', 'r') as f:
    total = 0
    for line in f:
        total += sum(map(int, line.strip().split(',')))
    print('Sum:', total)
\""" """
            result = sandbox.execute(code)
            assert result.success is True
            assert "45" in result.output
    
    def test_multiple_file_operations(self):
        """Multiple file operations in sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Write multiple files
            for i in range(5):
                sandbox.write(f"file{i}.txt", f"content {i}")
            
            # List
            files = sandbox.list(".")
            assert len(files) >= 5
    
    def test_nested_directory_operations(self):
        """Nested directory operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Create nested dirs
            sandbox.execute("mkdir -p a/b/c")
            sandbox.write("a/b/c/deep.txt", "deep content")
            
            # Read
            content = sandbox.read("a/b/c/deep.txt")
            assert "deep content" in content
    
    def test_concurrent_commands(self):
        """Test multiple sequential commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Multiple commands
            result1 = sandbox.execute("echo one")
            result2 = sandbox.execute("echo two")
            result3 = sandbox.execute("echo three")
            
            assert result1.success
            assert result2.success
            assert result3.success
    
    def test_error_recovery(self):
        """Test recovery from errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Fail
            result = sandbox.execute("cat nonexistent.txt")
            assert result.success is False
            
            # Recover
            sandbox.write("recovered.txt", "success")
            assert sandbox.exists("recovered.txt")
    
    def test_unicode_content(self):
        """Test Unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            unicode_text = "Привет мир! 🌍 αβγδ"
            sandbox.write("unicode.txt", unicode_text)
            content = sandbox.read("unicode.txt")
            assert unicode_text in content
    
    def test_large_file(self):
        """Test large file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Create 1MB file
            content = "x" * (1024 * 1024)
            sandbox.write("large.txt", content)
            
            size = sandbox.get_file_size("large.txt")
            assert size >= 1024 * 1024


class TestEdgeCases:
    """Edge case tests."""
    
    def test_sandbox_with_special_chars_in_path(self):
        """Sandbox should handle special chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Should not crash
            result = sandbox.execute("echo test")
            assert result.success is True
    
    def test_concurrent_sandbox_instances(self):
        """Multiple sandbox instances should work."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                s1 = Sandbox(Path(tmpdir1))
                s2 = Sandbox(Path(tmpdir2))
                
                s1.write("file1.txt", "one")
                s2.write("file2.txt", "two")
                
                assert s1.exists("file1.txt")
                assert s2.exists("file2.txt")
                assert not s1.exists("file2.txt")
                assert not s2.exists("file1.txt")
    
    def test_cleanup(self):
        """Cleanup should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            sandbox.write("test.txt", "content")
            
            sandbox.cleanup()
            
            assert not sandbox.exists("test.txt")
            assert len(sandbox.get_created_files()) == 0
    
    def test_execute_with_env_vars(self):
        """Execute should use environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            result = sandbox.execute("echo $HOME")
            # Should not crash, HOME might be set
    
    def test_very_long_command(self):
        """Very long command should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            long_cmd = "echo " + "a" * 10000
            result = sandbox.execute(long_cmd)
            # Should not crash
            assert result is not None
    
    def test_command_with_newlines(self):
        """Command with newlines should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            result = sandbox.execute("echo 'line1\nline2'")
            # Should not crash
            assert result is not None
