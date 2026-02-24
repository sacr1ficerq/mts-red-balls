import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kaggle_solver.sandbox import Sandbox, Result
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.tools.console import console_tool
from kaggle_solver.tools.files import files_tool
from kaggle_solver.rag import RAG


class TestSandbox:
    def setup_method(self):
        self.sandbox = Sandbox(Path("/tmp/test_sandbox"))
        self.sandbox.cleanup()

    def teardown_method(self):
        self.sandbox.cleanup()

    def test_sandbox_execute_echo(self):
        result = self.sandbox.execute("echo hello")
        assert result.success is True
        assert "hello" in result.output

    def test_sandbox_execute_date(self):
        result = self.sandbox.execute("date")
        assert result.success is True

    def test_sandbox_execute_ls(self):
        result = self.sandbox.execute("ls")
        assert result.success is True

    def test_sandbox_write_read_file(self):
        self.sandbox.write("test.txt", "Hello World")
        content = self.sandbox.read("test.txt")
        assert content == "Hello World"

    def test_sandbox_list_files(self):
        self.sandbox.write("file1.txt", "content1")
        self.sandbox.write("file2.txt", "content2")
        files = self.sandbox.list(".")
        assert "file1.txt" in files
        assert "file2.txt" in files

    def test_sandbox_delete_file(self):
        self.sandbox.write("delete_me.txt", "content")
        assert self.sandbox.exists("delete_me.txt")
        self.sandbox.delete("delete_me.txt")
        assert not self.sandbox.exists("delete_me.txt")

    def test_sandbox_file_size(self):
        self.sandbox.write("size_test.txt", "Hello")
        size = self.sandbox.get_file_size("size_test.txt")
        assert size == 5

    def test_sandbox_security_path_traversal(self):
        result = self.sandbox.execute("ls /etc")
        assert result.success is False

    def test_sandbox_security_blocked_pattern(self):
        result = self.sandbox.execute("echo test; rm -rf /")
        assert result.success is False


class TestConsoleTool:
    def setup_method(self):
        self.sandbox = Sandbox(Path("/tmp/test_sandbox_console"))
        self.sandbox.cleanup()

    def teardown_method(self):
        self.sandbox.cleanup()

    def test_console_tool_echo(self):
        result = console_tool(query="echo test", sandbox=self.sandbox)
        assert "test" in result

    def test_console_tool_ls(self):
        result = console_tool(query="ls", sandbox=self.sandbox)
        assert result is not None

    def test_console_tool_date(self):
        result = console_tool(query="date", sandbox=self.sandbox)
        assert result is not None

    def test_console_tool_no_sandbox(self):
        result = console_tool(query="echo test", sandbox=None)
        assert "Error" in result


class TestFilesTool:
    def setup_method(self):
        self.sandbox = Sandbox(Path("/tmp/test_sandbox_files"))
        self.sandbox.cleanup()

    def teardown_method(self):
        self.sandbox.cleanup()

    def test_files_tool_write(self):
        result = files_tool(op="write", path="test.txt", content="Hello", sandbox=self.sandbox)
        assert "Written" in result

    def test_files_tool_read(self):
        self.sandbox.write("read_test.txt", "Test content")
        result = files_tool(op="read", path="read_test.txt", sandbox=self.sandbox)
        assert "Test content" in result

    def test_files_tool_list(self):
        self.sandbox.write("file1.txt", "c1")
        self.sandbox.write("file2.txt", "c2")
        result = files_tool(op="list", path=".", sandbox=self.sandbox)
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_files_tool_delete(self):
        self.sandbox.write("to_delete.txt", "content")
        result = files_tool(op="delete", path="to_delete.txt", sandbox=self.sandbox)
        assert "Deleted" in result

    def test_files_tool_exists(self):
        self.sandbox.write("exists.txt", "content")
        result = files_tool(op="exists", path="exists.txt", sandbox=self.sandbox)
        assert "True" in result

    def test_files_tool_no_sandbox(self):
        result = files_tool(op="read", path="test.txt", sandbox=None)
        assert "Error" in result


class TestRAG:
    def setup_method(self):
        self.rag = RAG()

    def test_rag_add_document(self):
        self.rag.add_document("doc1", "Python is a programming language")
        assert len(self.rag.documents) == 1

    def test_rag_search(self):
        self.rag.add_document("doc1", "Python is a programming language")
        results = self.rag.search("Python")
        assert len(results) > 0
        assert "Python" in results[0]["content"]

    def test_rag_get_context(self):
        self.rag.add_document("doc1", "Python is a programming language. It is widely used.")
        context = self.rag.get_context("What is Python?")
        assert len(context) > 0

    def test_rag_clear(self):
        self.rag.add_document("doc1", "Test content")
        self.rag.clear()
        assert len(self.rag.documents) == 0


class TestToolRegistry:
    def setup_method(self):
        ToolRegistry._tools = {}
        ToolRegistry._tool_metadata = {}

    def test_register_tool(self):
        def dummy_tool(query: str) -> str:
            return "result"

        ToolRegistry.register("dummy", dummy_tool, "A dummy tool")
        assert "dummy" in ToolRegistry.list_tools()

    def test_execute_tool(self):
        def test_tool(query: str) -> str:
            return f"processed: {query}"

        ToolRegistry.register("test", test_tool)
        result = ToolRegistry.execute("test", query="hello")
        assert result.success is True
        assert "processed: hello" in result.output

    def test_execute_unknown_tool(self):
        result = ToolRegistry.execute("unknown_tool", query="test")
        assert result.success is False
        assert "Unknown tool" in result.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
