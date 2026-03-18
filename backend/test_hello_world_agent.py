#!/usr/bin/env python3
"""
Automated test for agent tool calls.
Tests that agents correctly use file creation and console execution tools.
"""

import requests
import time
import json
import sys

API_BASE = "http://localhost:8000/api"

def wait_for_session(session_id: str, timeout: int = 120) -> dict:
    """Wait for session to complete and return final state."""
    start = time.time()
    
    while time.time() - start < timeout:
        response = requests.get(f"{API_BASE}/session/{session_id}")
        if response.status_code != 200:
            raise Exception(f"Failed to get session: {response.status_code}")
        
        data = response.json()
        status = data.get("status")
        
        if status in ("completed", "error", "done"):
            return data
        
        time.sleep(1)
    
    raise TimeoutError(f"Session {session_id} did not complete within {timeout}s")


def test_hello_world_task():
    """Test that agents create file and run script."""
    print("=" * 60)
    print("TEST: Create a simple Python script that prints hello world")
    print("=" * 60)
    
    # Start the task
    query = "Create a simple Python script that prints hello world"
    
    print(f"\n[1] Starting task: {query}")
    response = requests.post(
        f"{API_BASE}/query",
        json={"query": query}
    )
    
    if response.status_code != 200:
        print(f"ERROR: Failed to start task: {response.status_code}")
        print(response.text)
        return False
    
    data = response.json()
    session_id = data.get("session_id")
    print(f"    Session ID: {session_id}")
    
    if not session_id:
        print("ERROR: No session_id in response")
        return False
    
    # Wait for completion
    print(f"\n[2] Waiting for session to complete...")
    try:
        session = wait_for_session(session_id, timeout=120)
    except TimeoutError as e:
        print(f"ERROR: {e}")
        return False
    
    print(f"    Status: {session.get('status')}")
    
    # Analyze events
    events = session.get("events", [])
    print(f"\n[3] Analyzing {len(events)} events...")
    
    # Track tool calls
    tool_calls = []
    file_operations = []
    console_commands = []
    result_found = False
    result_content = None
    
    for i, event in enumerate(events):
        event_type = event.get("type")
        
        if event_type == "tool":
            data = event.get("data", {})
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("input", {})
            tool_output = data.get("output", "")
            tool_success = data.get("success", True)
            
            tool_calls.append({
                "name": tool_name,
                "input": tool_input,
                "output_preview": tool_output[:200] if tool_output else "",
                "success": tool_success
            })
            
            if tool_name == "files":
                file_operations.append(tool_input)
                print(f"    [{i}] TOOL: files")
                print(f"        Input: {str(tool_input)[:100]}")
                print(f"        Output: {tool_output}")
            
            elif tool_name == "console":
                console_commands.append(tool_input)
                print(f"    [{i}] TOOL: console")
                print(f"        Input: {str(tool_input)[:100]}")
                print(f"        Output: {tool_output}")
            
            elif tool_name == "delegate":
                print(f"    [{i}] TOOL: delegate")
                print(f"        Output: {tool_output[:100] if tool_output else 'empty'}")
        
        elif event_type == "result":
            result_found = True
            result_content = event.get("data", {}).get("content", "")
            print(f"    [{i}] RESULT: {result_content[:200]}...")
        
        elif event_type == "thought":
            agent = event.get("agent", "unknown")
            content = event.get("data", {}).get("content", "")
            print(f"    [{i}] THOUGHT ({agent}): {content[:100]}...")
        
        elif event_type == "delegate":
            agent = event.get("data", {}).get("agent", "unknown")
            print(f"    [{i}] DELEGATE to: {agent}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    print(f"\nTotal events: {len(events)}")
    print(f"Tool calls: {len(tool_calls)}")
    print(f"File operations: {len(file_operations)}")
    print(f"Console commands: {len(console_commands)}")
    print(f"Result found: {result_found}")
    
    # Verify expectations
    print("\n" + "-" * 60)
    print("VERIFICATION")
    print("-" * 60)
    
    passed = True
    
    # Check 1: Files tool was called (to create script)
    if file_operations:
        print("✓ Files tool was called")
        for op in file_operations:
            if isinstance(op, dict):
                print(f"  - Operation: {op.get('operation', 'unknown')}")
                print(f"  - Path: {op.get('path', 'unknown')}")
    else:
        print("✗ Files tool was NOT called")
        passed = False
    
    # Check 2: Console tool was called (to run script)
    if console_commands:
        print("✓ Console tool was called")
        for cmd in console_commands:
            if isinstance(cmd, dict):
                print(f"  - Command: {cmd.get('command', 'unknown')}")
    else:
        print("✗ Console tool was NOT called")
        passed = False
    
    # Check 3: Result was returned
    if result_found:
        print("✓ Result was returned")
        print(f"  - Content: {result_content[:200] if result_content else 'empty'}...")
    else:
        print("✗ Result was NOT returned")
        passed = False
    
    # Check 4: Session completed successfully
    if session.get("status") == "completed":
        print("✓ Session completed successfully")
    else:
        print(f"✗ Session status: {session.get('status')}")
        passed = False
    
    print("\n" + "=" * 60)
    if passed:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 60)
    
    # Print all tool calls for debugging
    if tool_calls:
        print("\nAll tool calls:")
        for i, tc in enumerate(tool_calls):
            print(f"  {i+1}. {tc['name']}")
    
    return passed


if __name__ == "__main__":
    try:
        success = test_hello_world_task()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nEXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
