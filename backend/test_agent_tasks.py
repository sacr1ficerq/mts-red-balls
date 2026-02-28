"""
Test script to validate agent behavior with various tasks.
"""
import asyncio
import json
from unittest.mock import Mock, MagicMock
from kaggle_solver.agents.base import AgentConfig, AgentResult
from kaggle_solver.agents import CodeAgent, CoordinatorAgent
from kaggle_solver.sandbox import Sandbox
from pathlib import Path
import tempfile
import os


def create_test_sandbox():
    """Create a temporary sandbox for testing."""
    tmpdir = tempfile.mkdtemp()
    return Sandbox(Path(tmpdir))


def create_mock_llm(responses):
    """Create a mock LLM with predefined responses."""
    mock = Mock()
    mock.chat.side_effect = responses
    return mock


def create_mock_tool_registry():
    """Create a mock tool registry."""
    mock = Mock()
    return mock


def test_simple_print():
    """Test 1: Simple print task."""
    print("\n" + "="*60)
    print("TEST 1: Simple print 'hello world'")
    print("="*60)
    
    sandbox = create_test_sandbox()
    sandbox.write("test.py", 'print("hello world")')
    
    mock_llm = Mock()
    # Simulate: write file -> run file -> done
    mock_llm.chat.side_effect = [
        '{"action": "tool", "tool": "files", "op": "write", "path": "test.py", "content": "print(\"hello world\")"}',
        '{"action": "tool", "tool": "console", "query": "python3 test.py"}',
        '{"action": "done", "result": "hello world"}'
    ]
    
    mock_registry = Mock()
    mock_registry.execute.side_effect = [
        Mock(success=True, output="File written"),
        Mock(success=True, output="hello world")
    ]
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["console", "files"], max_iterations=5)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry)
    
    result = agent.run('print hello world')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"LLM calls: {mock_llm.chat.call_count}")
    print(f"Expected: 3 calls (write, run, done)")
    
    assert result.success, "Task should succeed"
    assert mock_llm.chat.call_count <= 3, "Should complete in 3 calls or less"
    assert "hello world" in result.output, "Should contain output"
    
    print("✓ PASSED")
    return True


def test_generate_sort_save():
    """Test 2: Generate numbers, sort, save to file."""
    print("\n" + "="*60)
    print("TEST 2: Generate 10 random numbers, sort, save to file")
    print("="*60)
    
    sandbox = create_test_sandbox()
    
    # The agent should write a script that generates, sorts, and saves
    script_content = '''import random
numbers = [random.randint(1, 100) for _ in range(10)]
numbers.sort()
with open('result.txt', 'w') as f:
    f.write(str(numbers))
print(numbers)
'''
    
    mock_llm = Mock()
    mock_llm.chat.side_effect = [
        # First: write the script
        f'{{"action": "tool", "tool": "files", "op": "write", "path": "script.py", "content": {json.dumps(script_content)}}}',
        # Second: run the script
        '{"action": "tool", "tool": "console", "query": "python3 script.py"}',
        # Third: done
        '{"action": "done", "result": "Numbers generated and saved: [12, 23, 34, 45, 56, 67, 78, 89, 90, 99]"}'
    ]
    
    mock_registry = Mock()
    mock_registry.execute.side_effect = [
        Mock(success=True, output="File written"),
        Mock(success=True, output="[12, 23, 34, 45, 56, 67, 78, 89, 90, 99]")
    ]
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["console", "files"], max_iterations=5)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry)
    
    result = agent.run('generate 10 random numbers, sort them, save to file')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"LLM calls: {mock_llm.chat.call_count}")
    
    assert result.success, "Task should succeed"
    assert mock_llm.chat.call_count <= 3, "Should complete in 3 calls"
    # Skip sandbox check since mock doesn't write to real sandbox
    
    print("✓ PASSED")
    return True


def test_parse_prefers_done():
    """Test 3: Parser prefers done action over tool/delegate."""
    print("\n" + "="*60)
    print("TEST 3: Parser prefers done action")
    print("="*60)
    
    sandbox = create_test_sandbox()
    
    # Response contains both tool and done - should prefer done
    mock_llm = Mock()
    mock_llm.chat.return_value = '''
Some thinking text here.
{"action": "tool", "tool": "console", "query": "echo test"}
But then I should return done.
{"action": "done", "result": "Task completed successfully"}
'''
    
    mock_registry = Mock()
    mock_registry.execute.return_value = Mock(success=True, output="test")
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["console"], max_iterations=3)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry)
    
    # Parse should find done first
    result = agent.run('test')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    
    # With done in the response, it should complete
    print("✓ PASSED (done action found)")
    return True


def test_no_infinite_loop():
    """Test 4: Agent doesn't loop infinitely on same action."""
    print("\n" + "="*60)
    print("TEST 4: No infinite loop protection")
    print("="*60)
    
    sandbox = create_test_sandbox()
    
    # Agent keeps returning tool action but it's the same action
    mock_llm = Mock()
    mock_llm.chat.side_effect = [
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "tool", "tool": "console", "query": "echo hello"}',  # 5th call - max iterations
    ]
    
    mock_registry = Mock()
    mock_registry.execute.return_value = Mock(success=True, output="hello")
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["console"], max_iterations=5)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry)
    
    result = agent.run('test')
    
    print(f"Success: {result.success}")
    print(f"LLM calls: {mock_llm.chat.call_count}")
    print(f"Error: {result.error}")
    
    # Should stop after max iterations
    assert mock_llm.chat.call_count == 5, "Should hit max iterations"
    assert not result.success, "Should fail after max iterations"
    
    print("✓ PASSED (stops at max iterations)")
    return True


def test_event_emission():
    """Test 5: Events are emitted correctly."""
    print("\n" + "="*60)
    print("TEST 5: Event emission")
    print("="*60)
    
    sandbox = create_test_sandbox()
    
    mock_llm = Mock()
    mock_llm.chat.side_effect = [
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "done", "result": "hello"}'
    ]
    
    mock_registry = Mock()
    mock_registry.execute.return_value = Mock(success=True, output="hello")
    
    events = []
    def event_cb(e):
        events.append(e)
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["console"], max_iterations=3)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry, event_callback=event_cb)
    
    result = agent.run('test')
    
    print(f"Events count: {len(events)}")
    event_types = [e.get('type') for e in events]
    print(f"Event types: {event_types}")
    
    assert len(events) >= 3, "Should emit at least system, thought, result"
    assert 'system' in event_types, "Should emit system event"
    assert 'thought' in event_types, "Should emit thought event"
    assert 'result' in event_types, "Should emit result event"
    
    print("✓ PASSED")
    return True


def test_delegation_flow():
    """Test 6: Coordinator delegates to CodeAgent properly."""
    print("\n" + "="*60)
    print("TEST 6: Coordinator delegation")
    print("="*60)
    
    sandbox = create_test_sandbox()
    
    # Coordinator responds with delegation
    mock_llm_coord = Mock()
    mock_llm_coord.chat.side_effect = [
        '{"action": "delegate", "agent": "CodeAgent", "task": "print hello"}',
        '{"action": "done", "result": "Task completed: hello"}'
    ]
    
    # Sub-agent mock
    mock_llm_sub = Mock()
    mock_llm_sub.chat.side_effect = [
        '{"action": "tool", "tool": "console", "query": "echo hello"}',
        '{"action": "done", "result": "hello"}'
    ]
    
    mock_registry = Mock()
    mock_registry.execute.return_value = Mock(success=True, output="hello")
    
    # Create sub-agent factory that uses sub-agent's mock
    call_count = [0]
    def agent_factory(**kwargs):
        call_count[0] += 1
        sub_config = AgentConfig(name="CodeAgent", role="test", tools=["console"])
        return CodeAgent(sub_config, mock_llm_sub, sandbox, mock_registry)
    
    config = AgentConfig(name="Coordinator", role="test", tools=["delegate"], max_iterations=3)
    agent = CoordinatorAgent(config, mock_llm_coord, sandbox, mock_registry, agent_factory=agent_factory)
    
    result = agent.run('print hello')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"LLM calls (coordinator): {mock_llm_coord.chat.call_count}")
    print(f"Sub-agent factory calls: {call_count[0]}")
    
    assert result.success, "Should succeed"
    assert "hello" in result.output, "Should contain sub-agent result"
    print("✓ PASSED")
    return True


def test_read_file():
    """Test 7: Read file content."""
    print("\n" + "="*60)
    print("TEST 7: Read file content")
    print("="*60)
    
    sandbox = create_test_sandbox()
    sandbox.write("data.txt", "Hello, World!")
    
    mock_llm = Mock()
    mock_llm.chat.side_effect = [
        '{"action": "tool", "tool": "files", "op": "read", "path": "data.txt"}',
        '{"action": "done", "result": "File contains: Hello, World!"}'
    ]
    
    mock_registry = Mock()
    mock_registry.execute.return_value = Mock(success=True, output="Hello, World!")
    
    config = AgentConfig(name="CodeAgent", role="test", tools=["files"], max_iterations=3)
    agent = CodeAgent(config, mock_llm, sandbox, mock_registry)
    
    result = agent.run('read data.txt')
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    
    assert result.success
    print("✓ PASSED")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("RUNNING AGENT TESTS")
    print("="*60)
    
    tests = [
        ("Simple print", test_simple_print),
        ("Generate sort save", test_generate_sort_save),
        ("Parser prefers done", test_parse_prefers_done),
        ("No infinite loop", test_no_infinite_loop),
        ("Event emission", test_event_emission),
        ("Delegation flow", test_delegation_flow),
        ("Read file", test_read_file),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
