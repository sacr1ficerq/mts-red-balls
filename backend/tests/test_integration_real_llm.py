#!/usr/bin/env python3
"""
Integration tests with real LLM calls.

These tests use actual API calls to verify the system works end-to-end.
They are marked as slow and should be run separately from unit tests.
"""

import pytest
import asyncio
import os
from pathlib import Path
import tempfile

from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.agents.base import BaseAgent, AgentConfig
from kaggle_solver.core.state import StateManager, Session
from kaggle_solver.core.config import Config


class LLMIntegrationAgent(BaseAgent):
    def system_prompt(self) -> str:
        return """
You are a practical coding agent for integration tests.

Available actions:
- {"action": "tool", "tool": "files", "op": "read|write|list", "path": "...", "content": "..."}
- {"action": "tool", "tool": "console", "query": "..."}
- {"action": "done", "result": "..."}

Rules:
- Return exactly one JSON object per message.
- Use the simplest valid workflow for the task.
- Prefer Python standard library only; do not use pandas or other third-party packages.
- If a task asks to create or update a file, use the files tool before done.
- If a task asks to read data or count values, you may use files read or console with python3 -c.
- If a task asks to store an artifact, include it in the final result as [[artifact:key=value]].
- After any tool result, continue with the next step and finish with done.
""".strip()


@pytest.mark.slow
@pytest.mark.integration
class TestRealLLMIntegration:
    """Integration tests with real LLM API calls."""

    @pytest.fixture
    def api_key(self):
        """Get API key from environment."""
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            pytest.skip("No API key found in environment")
        return key

    @pytest.fixture
    def llm(self, api_key):
        """Create LLM instance with real API."""
        return LLM(api_key=api_key, requests_per_minute=8)

    @pytest.fixture
    def sandbox(self):
        """Create temporary sandbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir))

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry."""
        from kaggle_solver.tools.console import console_tool
        from kaggle_solver.tools.files import files_tool

        ToolRegistry._tools.clear()
        ToolRegistry.register("console", console_tool)
        ToolRegistry.register("files", files_tool)
        return ToolRegistry

    @pytest.fixture
    def session(self):
        """Create test session."""
        state = StateManager()
        return state.create_session("Test query")

    @pytest.fixture
    def agent_config(self):
        """Create agent config."""
        return AgentConfig(
            name="TestAgent",
            role="Test agent",
            tools=["console", "files"],
            model="openai/gpt-4o-mini",
            max_iterations=8,
            temperature=0.7,
        )

    @pytest.mark.asyncio
    async def test_llm_chat_simple(self, llm):
        """Test simple LLM chat with real API."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello, World!'"},
        ]

        response = await llm.chat(
            model="openai/gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=100,
        )

        assert response is not None
        assert len(response) > 0
        assert "hello" in response.lower() or "world" in response.lower()

    @pytest.mark.asyncio
    async def test_llm_chat_with_retry(self, llm):
        """Test LLM chat with retry logic."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
        ]

        response = await llm.chat(
            model="openai/gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            max_tokens=50,
        )

        assert response is not None
        assert "4" in response

    @pytest.mark.asyncio
    async def test_agent_simple_task(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent executing a simple task with real LLM."""

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Write a Python script that prints 'Hello, World!' to a file called hello.py",
            context={"session": session},
            timeout=120,
        )

        assert result.success
        assert "hello.py" in result.output.lower() or "hello" in result.output.lower()

        # Verify file was created
        assert sandbox.exists("hello.py")
        content = sandbox.read("hello.py")
        assert "Hello, World!" in content or "print" in content

    @pytest.mark.asyncio
    async def test_agent_with_artifacts(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent using shared artifacts."""

        # Set initial artifact
        session.set_artifact("test_data", "Sample data for testing")

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Read the test_data artifact and write it to a file called data.txt",
            context={"session": session, "artifacts": session.get_all_artifacts()},
            timeout=120,
        )

        assert result.success

        # Verify artifact was used
        assert sandbox.exists("data.txt")
        content = sandbox.read("data.txt")
        assert "Sample data" in content or "test_data" in content

    @pytest.mark.asyncio
    async def test_agent_timeout(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent timeout mechanism."""

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        # Set very short timeout
        result = await agent.run(
            "Write a very long and complex Python script with detailed comments",
            context={"session": session},
            timeout=5,  # 5 seconds
        )

        # Should either succeed quickly or timeout
        assert result is not None
        if not result.success:
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_agent_delegation_with_artifacts(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent delegation with artifact passing."""

        # Set initial artifact
        session.set_artifact("competition", "Titanic")

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Delegate to CodeAgent to write a simple Python script that prints the competition name",
            context={"session": session, "artifacts": session.get_all_artifacts()},
            timeout=120,
        )

        assert result is not None
        # Check if artifact was passed and used
        if result.success:
            assert (
                "titanic" in result.output.lower() or "script" in result.output.lower()
            )

    @pytest.mark.asyncio
    async def test_rate_limiting(self, llm):
        """Test rate limiting with multiple requests."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'OK'"},
        ]

        # Make multiple requests quickly
        tasks = []
        for _ in range(3):
            task = llm.chat(
                model="openai/gpt-4o-mini",
                messages=messages,
                temperature=0.0,
                max_tokens=10,
            )
            tasks.append(task)

        # Should handle rate limiting gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least some should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) > 0

    @pytest.mark.asyncio
    async def test_agent_with_console_tool(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent using console tool."""

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Use the console tool to run: echo 'Test output'",
            context={"session": session},
            timeout=60,
        )

        assert result.success
        assert "test output" in result.output.lower() or "echo" in result.output.lower()

    @pytest.mark.asyncio
    async def test_agent_with_files_tool(
        self, llm, sandbox, tool_registry, session, agent_config
    ):
        """Test agent using files tool."""

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Use the files tool to write 'Hello from files tool' to test.txt",
            context={"session": session},
            timeout=60,
        )

        assert result.success
        assert sandbox.exists("test.txt")
        content = sandbox.read("test.txt")
        assert "Hello from files tool" in content


@pytest.mark.slow
@pytest.mark.integration
class TestTitanicWorkflow:
    """Integration tests for Titanic competition workflow."""

    @pytest.fixture
    def api_key(self):
        """Get API key from environment."""
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            pytest.skip("No API key found in environment")
        return key

    @pytest.fixture
    def llm(self, api_key):
        """Create LLM instance with real API."""
        return LLM(api_key=api_key, requests_per_minute=8)

    @pytest.fixture
    def sandbox(self):
        """Create temporary sandbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir))

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry."""
        from kaggle_solver.tools.console import console_tool
        from kaggle_solver.tools.files import files_tool

        ToolRegistry._tools.clear()
        ToolRegistry.register("console", console_tool)
        ToolRegistry.register("files", files_tool)
        return ToolRegistry

    @pytest.fixture
    def session(self):
        """Create test session."""
        state = StateManager()
        return state.create_session("Solve Titanic competition")

    @pytest.mark.asyncio
    async def test_simple_titanic_analysis(self, llm, sandbox, tool_registry, session):
        """Test simple Titanic data analysis workflow."""

        # Create sample Titanic data
        sample_data = """PassengerId,Survived,Pclass,Name,Sex,Age,SibSp,Parch,Ticket,Fare,Cabin,Embarked
1,0,3,"Braund, Mr. Owen Harris",male,22,1,0,A/5 21171,7.25,,S
2,1,1,"Cumings, Mrs. John Bradley (Florence Briggs Thayer)",female,38,1,0,PC 17599,71.2833,C85,C
3,1,3,"Heikkinen, Miss. Laina",female,26,0,0,STON/O2. 3101282,7.925,,S"""

        sandbox.write("train.csv", sample_data)

        agent_config = AgentConfig(
            name="DataAnalyst",
            role="Analyze data",
            tools=["console", "files"],
            model="openai/gpt-4o-mini",
            max_iterations=8,
            temperature=0.7,
        )

        def agent_factory(**kwargs):
            return LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        agent = agent_factory()

        result = await agent.run(
            "Use the files tool to write a short Python script named count_rows.py that uses Python's standard library csv module to read train.csv and count rows where Survived == 1. Then use the console tool to run `python3 count_rows.py`, and return a done action with the count.",
            context={"session": session},
            timeout=120,
        )

        assert result.success
        # Should mention survival count (2 out of 3 in sample data)
        assert "2" in result.output

    @pytest.mark.asyncio
    async def test_titanic_artifact_workflow(
        self, llm, sandbox, tool_registry, session
    ):
        """Test Titanic workflow with artifact passing."""

        # Create sample data
        sample_data = """PassengerId,Survived,Pclass,Name,Sex,Age,SibSp,Parch,Ticket,Fare,Cabin,Embarked
1,0,3,"Braund, Mr. Owen Harris",male,22,1,0,A/5 21171,7.25,,S
2,1,1,"Cumings, Mrs. John Bradley (Florence Briggs Thayer)",female,38,1,0,PC 17599,71.2833,C85,C"""

        sandbox.write("train.csv", sample_data)

        # Agent 1: Analyze data
        agent_config1 = AgentConfig(
            name="DataAnalyst",
            role="Analyze data",
            tools=["console", "files"],
            model="openai/gpt-4o-mini",
            max_iterations=8,
            temperature=0.7,
        )

        def agent_factory1(**kwargs):
            return LLMIntegrationAgent(agent_config1, llm, sandbox, tool_registry)

        agent1 = agent_factory1()

        result1 = await agent1.run(
            "Use the files tool to write a short Python script named count_rows.py that uses Python's standard library csv module to read train.csv and count rows where Survived == 1. Then use the console tool to run `python3 count_rows.py`, and return done with [[artifact:survivor_count=<count>]].",
            context={"session": session},
            timeout=120,
        )

        assert result1.success

        # Check artifact was created
        survivor_count = session.get_artifact("survivor_count")
        assert survivor_count is not None

        # Agent 2: Use artifact
        agent_config2 = AgentConfig(
            name="ReportWriter",
            role="Write report",
            tools=["console", "files"],
            model="openai/gpt-4o-mini",
            max_iterations=8,
            temperature=0.7,
        )

        def agent_factory2(**kwargs):
            return LLMIntegrationAgent(agent_config2, llm, sandbox, tool_registry)

        agent2 = agent_factory2()

        result2 = await agent2.run(
            "Read the survivor_count artifact from shared context, use the files tool to write a short report to report.txt, then return done.",
            context={"session": session, "artifacts": session.get_all_artifacts()},
            timeout=120,
        )

        assert result2.success
        assert sandbox.exists("report.txt")
        content = sandbox.read("report.txt")
        assert "survivor" in content.lower() or "count" in content.lower()


@pytest.mark.slow
@pytest.mark.integration
class TestRustHelloWorld:
    """Integration tests for Rust file creation."""

    @pytest.fixture
    def api_key(self):
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            pytest.skip("No API key found")
        return key

    @pytest.fixture
    def llm(self, api_key):
        return LLM(api_key=api_key, requests_per_minute=8)

    @pytest.fixture
    def sandbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Sandbox(Path(tmpdir))

    @pytest.fixture
    def tool_registry(self):
        from kaggle_solver.tools.console import console_tool
        from kaggle_solver.tools.files import files_tool

        ToolRegistry._tools.clear()
        ToolRegistry.register("console", console_tool)
        ToolRegistry.register("files", files_tool)
        return ToolRegistry

    @pytest.fixture
    def session(self):
        state = StateManager()
        return state.create_session("Test rust")

    @pytest.fixture
    def agent_config(self):
        return AgentConfig(
            name="TestAgent",
            role="Test agent",
            tools=["console", "files"],
            model="openai/gpt-4o-mini",
            max_iterations=8,
            temperature=0.7,
        )

    @pytest.mark.asyncio
    async def test_rust_hello_world(
        self, llm, sandbox, tool_registry, session, agent_config, caplog, tmp_path
    ):
        """Test agent creating a Rust hello world file in sandbox."""
        import logging

        caplog.set_level(logging.DEBUG)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(tmp_path / "test.log"),
                logging.StreamHandler(),
            ],
        )

        agent = LLMIntegrationAgent(agent_config, llm, sandbox, tool_registry)

        result = await agent.run(
            "write hello world in rust",
            context={"session": session},
            timeout=120,
        )

        assert result.success
        rust_file = None
        for f in sandbox.list("."):
            if f.endswith(".rs"):
                rust_file = f
                break
        assert rust_file is not None, f"No .rs file found. Files: {sandbox.list('.')}"
        content = sandbox.read(rust_file)
        assert "hello" in content.lower() and "world" in content.lower()


@pytest.mark.slow
@pytest.mark.integration
class TestProductionFlow:
    """Test the actual production flow as if user visits the site."""

    @pytest.fixture
    def api_key(self):
        key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            pytest.skip("No API key found")
        return key

    @pytest.fixture
    def orchestrator(self, api_key, tmp_path):
        from kaggle_solver.core.orchestrator import Orchestrator
        import kaggle_solver.tools
        from kaggle_solver.core.config import Config
        from pathlib import Path

        config = Config.load(str(Path(__file__).parent.parent / "config.yaml"))
        config.sandbox.root = str(tmp_path / "workspace")
        config.llm.requests_per_minute = 8
        config.llm.model = "minimax/minimax-m2.7"

        orch = Orchestrator(config)
        return orch

    @pytest.fixture
    def session(self, orchestrator):
        return orchestrator.state.create_session("write hello world in rust")

    @pytest.mark.asyncio
    async def test_hello_world_rust_production(
        self, orchestrator, session, caplog, tmp_path
    ):
        """Test exactly like user does on the site - Coordinator delegates to CodeAgent."""
        import logging

        caplog.set_level(logging.DEBUG)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(tmp_path / "test.log"),
                logging.StreamHandler(),
            ],
        )

        events = []

        def event_callback(event):
            events.append(event)
            session.add_event(event)

        sandbox_path = tmp_path / "workspace" / session.id
        from kaggle_solver.sandbox import Sandbox

        session_sandbox = Sandbox(sandbox_path, timeout=300)

        coordinator = orchestrator.create_agent(
            name="Coordinator",
            role="Plan and delegate tasks",
            tools=["delegate", "message", "tool"],
            event_callback=event_callback,
            sandbox=session_sandbox,
        )

        result = await coordinator.run(
            "write hello world in rust", {"session": session}
        )

        assert result.success, f"Coordinator failed: {result.output}"

        rust_file = None
        for f in session_sandbox.list("."):
            if f.endswith(".rs"):
                rust_file = f
                break
        assert rust_file is not None, (
            f"No .rs file found. Files: {session_sandbox.list('.')}"
        )
        content = session_sandbox.read(rust_file)
        assert "hello" in content.lower() and "world" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
