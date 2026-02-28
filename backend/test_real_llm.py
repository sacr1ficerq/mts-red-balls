"""
Real integration tests with actual LLM - no hardcoding!
"""
import json
from pathlib import Path
import tempfile
import shutil
from kaggle_solver.agents.base import AgentConfig
from kaggle_solver.agents import CodeAgent
from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.tools.console import console_tool
from kaggle_solver.tools.files import files_tool


def test_real_llm_simple_print():
    """Test with real LLM: simple print task."""
    print("\n" + "="*60)
    print("REAL LLM TEST 1: Print hello world")
    print("="*60)
    
    # Create real sandbox
    tmpdir = tempfile.mkdtemp()
    sandbox = Sandbox(Path(tmpdir))
    
    # Register real tools
    ToolRegistry.register("console", lambda query, sandbox=sandbox: console_tool(query, sandbox))
    ToolRegistry.register("files", lambda op, path, content="", sandbox=sandbox: files_tool(op, path, content, sandbox))
    
    # Use real LLM
    llm = LLM()
    
    config = AgentConfig(
        name="CodeAgent", 
        role="Execute code", 
        tools=["console", "files"],
        model="meta-llama/llama-3.1-8b-instruct",
        max_iterations=5,
        temperature=0.7
    )
    agent = CodeAgent(config, llm, sandbox, ToolRegistry)
    
    result = agent.run('print hello world')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output[:200] if result.output else 'empty'}")
    print(f"Error: {result.error}")
    
    # Cleanup
    shutil.rmtree(tmpdir)
    
    return result.success


def test_real_llm_generate_sort_save():
    """Test with real LLM: generate, sort, save."""
    print("\n" + "="*60)
    print("REAL LLM TEST 2: Generate, sort, save to file")
    print("="*60)
    
    tmpdir = tempfile.mkdtemp()
    sandbox = Sandbox(Path(tmpdir))
    
    ToolRegistry.register("console", lambda query, sandbox=sandbox: console_tool(query, sandbox))
    ToolRegistry.register("files", lambda op, path, content="", sandbox=sandbox: files_tool(op, path, content, sandbox))
    
    llm = LLM()
    
    config = AgentConfig(
        name="CodeAgent",
        role="Execute code",
        tools=["console", "files"],
        model="meta-llama/llama-3.1-8b-instruct",
        max_iterations=5,
        temperature=0.7
    )
    agent = CodeAgent(config, llm, sandbox, ToolRegistry)
    
    result = agent.run('напиши скрипт который сгенерирует 10 случайных чисел, отсортирует их и сохранит в файл result.txt')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output[:300] if result.output else 'empty'}")
    print(f"Error: {result.error}")
    
    # Check if file was created
    files = sandbox.list(".")
    print(f"Files in sandbox: {files}")
    
    shutil.rmtree(tmpdir)
    
    return result.success


def test_real_llm_read_file():
    """Test with real LLM: create and read file."""
    print("\n" + "="*60)
    print("REAL LLM TEST 3: Create and read file")
    print("="*60)
    
    tmpdir = tempfile.mkdtemp()
    sandbox = Sandbox(Path(tmpdir))
    sandbox.write("test.txt", "Hello from real LLM!")
    
    ToolRegistry.register("console", lambda query, sandbox=sandbox: console_tool(query, sandbox))
    ToolRegistry.register("files", lambda op, path, content="", sandbox=sandbox: files_tool(op, path, content, sandbox))
    
    llm = LLM()
    
    config = AgentConfig(
        name="CodeAgent",
        role="Execute code",
        tools=["console", "files"],
        model="meta-llama/llama-3.1-8b-instruct",
        max_iterations=5
    )
    agent = CodeAgent(config, llm, sandbox, ToolRegistry)
    
    result = agent.run('прочитай файл test.txt и выведи его содержимое')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output[:200] if result.output else 'empty'}")
    print(f"Error: {result.error}")
    
    shutil.rmtree(tmpdir)
    
    return result.success


if __name__ == "__main__":
    print("\n" + "="*60)
    print("RUNNING REAL LLM INTEGRATION TESTS")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Simple print", test_real_llm_simple_print()))
    except Exception as e:
        print(f"Error: {e}")
        results.append(("Simple print", False))
    
    try:
        results.append(("Generate sort save", test_real_llm_generate_sort_save()))
    except Exception as e:
        print(f"Error: {e}")
        results.append(("Generate sort save", False))
    
    try:
        results.append(("Read file", test_real_llm_read_file()))
    except Exception as e:
        print(f"Error: {e}")
        results.append(("Read file", False))
    
    print("\n" + "="*60)
    print("RESULTS:")
    for name, success in results:
        print(f"  {name}: {'✓ PASSED' if success else '✗ FAILED'}")
    print("="*60)
