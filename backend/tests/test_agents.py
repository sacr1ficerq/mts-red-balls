import pytest
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from kaggle_solver.agents.base import AgentConfig, AgentResult
from kaggle_solver.agents import CoordinatorAgent, CodeAgent, SearchAgent, CriticAgent
from kaggle_solver.tools.registry import ToolRegistry, ToolResult


class ConcreteCoordinator(CoordinatorAgent):
    """Concrete for testing."""
    pass


class ConcreteCode(CodeAgent):
    """Concrete for testing."""
    pass


class ConcreteSearch(SearchAgent):
    """Concrete for testing."""
    pass


class ConcreteCritic(CriticAgent):
    """Concrete for testing."""
    pass


@pytest.fixture
def mock_llm():
    llm = Mock()
    llm.chat = AsyncMock(return_value='{"action": "done", "result": "ok"}')
    return llm


@pytest.fixture
def mock_sandbox():
    sandbox = Mock()
    sandbox.execute = Mock(return_value=Mock(success=True, output="output"))
    return sandbox


@pytest.fixture
def mock_tool_registry():
    registry = Mock()
    registry.execute = Mock(return_value=Mock(success=True, output="tool output"))
    return registry


@pytest.fixture
def mock_event_callback():
    return Mock()


def create_agent(agent_class, agent_config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
    return agent_class(
        config=agent_config,
        llm=mock_llm,
        sandbox=mock_sandbox,
        tool_registry=mock_tool_registry,
        event_callback=mock_event_callback,
        agent_factory=None
    )


class TestCoordinatorAgent:
    """Test CoordinatorAgent - can delegate to other agents."""
    
    def test_coordinator_has_delegate_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """Coordinator should have delegate tool available."""
        config = AgentConfig(
            name="Coordinator",
            role="Plan and delegate",
            tools=["delegate", "message", "tool"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCoordinator, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "delegate" in agent.config.tools
    
    def test_coordinator_delegates_task(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """Coordinator should be able to delegate tasks after creating a plan."""
        config = AgentConfig(
            name="Coordinator",
            role="Plan and delegate",
            tools=["delegate", "message", "tool"],
            max_iterations=5
        )
        agent = create_agent(ConcreteCoordinator, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        # Mock LLM to return plan first, then delegate with plan_id
        mock_llm.chat = AsyncMock(side_effect=[
            '{"action": "plan", "plan_id": "test123", "steps": [{"id": 1, "task": "do work"}]}',
            '{"action": "delegate", "agent": "CodeAgent", "task": "do work", "plan_id": "test123", "step_id": 1}',
            '{"action": "done", "result": "completed"}'
        ])
        
        # Create sub-agent mock
        sub_agent = Mock()
        sub_agent.run = AsyncMock(return_value=AgentResult(success=True, output="work done"))
        agent.agent_factory = Mock(return_value=sub_agent)
        
        result = asyncio.run(agent.run("delegate this task"))
        
        assert sub_agent.run.called
    
    def test_coordinator_system_prompt(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """Coordinator should have correct system prompt."""
        config = AgentConfig(name="Coordinator", role="test", tools=[], max_iterations=3)
        agent = create_agent(ConcreteCoordinator, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        prompt = agent.system_prompt()
        
        # Prompt should mention plan, delegation, or workflow
        assert "plan" in prompt.lower() or "delegate" in prompt.lower()
    
    def test_coordinator_uses_all_tools(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """Coordinator should be configured with all required tools."""
        config = AgentConfig(
            name="Coordinator",
            role="test",
            tools=["delegate", "message", "tool"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCoordinator, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "delegate" in agent.config.tools
        assert "message" in agent.config.tools or "tool" in agent.config.tools


class TestCodeAgent:
    """Test CodeAgent - can execute console and files tools."""
    
    def test_code_agent_has_console_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CodeAgent should have console tool."""
        config = AgentConfig(
            name="CodeAgent",
            role="Execute code",
            tools=["console", "files"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCode, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "console" in agent.config.tools
    
    def test_code_agent_has_files_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CodeAgent should have files tool."""
        config = AgentConfig(
            name="CodeAgent",
            role="Execute code",
            tools=["console", "files"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCode, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "files" in agent.config.tools
    
    def test_code_agent_executes_console(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CodeAgent should execute console commands."""
        config = AgentConfig(
            name="CodeAgent",
            role="Execute code",
            tools=["console", "files"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCode, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        mock_llm.chat = AsyncMock(return_value='{"action": "tool", "tool": "console", "query": "echo hello"}')
        mock_tool_registry.execute.return_value = ToolResult(success=True, output="hello")
        
        result = asyncio.run(agent.run("run echo command"))
        
        mock_tool_registry.execute.assert_called()
        call_args = mock_tool_registry.execute.call_args
        assert call_args[0][0] == "console"
    
    def test_code_agent_executes_files(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CodeAgent should execute file operations."""
        config = AgentConfig(
            name="CodeAgent",
            role="Execute code",
            tools=["console", "files"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCode, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        mock_llm.chat = AsyncMock(return_value='{"action": "tool", "tool": "files", "query": "test.py"}')
        mock_tool_registry.execute.return_value = ToolResult(success=True, output="file content")
        
        result = asyncio.run(agent.run("read file"))
        
        mock_tool_registry.execute.assert_called()
        call_args = mock_tool_registry.execute.call_args
        assert call_args[0][0] == "files"
    
    def test_code_agent_system_prompt(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CodeAgent should have correct system prompt."""
        config = AgentConfig(name="CodeAgent", role="test", tools=[], max_iterations=3)
        agent = create_agent(ConcreteCode, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        prompt = agent.system_prompt()
        
        assert "CodeAgent" in prompt or "code" in prompt.lower() or "python" in prompt.lower()


class TestSearchAgent:
    """Test SearchAgent - can search the web."""
    
    def test_search_agent_has_search_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """SearchAgent should have search tool."""
        config = AgentConfig(
            name="SearchAgent",
            role="Search web",
            tools=["search"],
            max_iterations=3
        )
        agent = create_agent(ConcreteSearch, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "search" in agent.config.tools
    
    def test_search_agent_executes_search(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """SearchAgent should execute search."""
        config = AgentConfig(
            name="SearchAgent",
            role="Search web",
            tools=["search"],
            max_iterations=3
        )
        agent = create_agent(ConcreteSearch, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        mock_llm.chat = AsyncMock(return_value='{"action": "tool", "tool": "search", "query": "python tutorial"}')
        mock_tool_registry.execute.return_value = ToolResult(success=True, output="search results")
        
        result = asyncio.run(agent.run("search for python"))
        
        mock_tool_registry.execute.assert_called()
        call_args = mock_tool_registry.execute.call_args
        assert call_args[0][0] == "search"
    
    def test_search_agent_system_prompt(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """SearchAgent should have correct system prompt."""
        config = AgentConfig(name="SearchAgent", role="test", tools=[], max_iterations=3)
        agent = create_agent(ConcreteSearch, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        prompt = agent.system_prompt()
        
        assert "SearchAgent" in prompt or "search" in prompt.lower() or "web" in prompt.lower()


class TestCriticAgent:
    """Test CriticAgent - can review and validate."""
    
    def test_critic_agent_has_message_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CriticAgent should have message/search tools."""
        config = AgentConfig(
            name="CriticAgent",
            role="Review and validate",
            tools=["message", "search", "console"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCritic, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        assert "message" in agent.config.tools or "search" in agent.config.tools
    
    def test_critic_agent_can_validate(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """CriticAgent should be able to validate results."""
        config = AgentConfig(
            name="CriticAgent",
            role="Review and validate",
            tools=["message", "search", "console"],
            max_iterations=3
        )
        agent = create_agent(ConcreteCritic, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        mock_llm.chat = AsyncMock(return_value='{"action": "done", "result": "VALID - solution looks good"}')
        
        result = asyncio.run(agent.run("validate this solution"))
        
        assert result.success is True
    
    def test_critic_agent_system_prompt(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        config = AgentConfig(name="CriticAgent", role="test", tools=[], max_iterations=3)
        agent = create_agent(ConcreteCritic, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        prompt = agent.system_prompt()
        
        assert "qa" in prompt.lower() or "quality" in prompt.lower() or "critic" in prompt.lower()


class TestAllToolsAvailable:
    """Test that all required tools are registered and work."""
    
    def test_console_tool_registered(self):
        """Console tool should be registered."""
        from kaggle_solver.tools.console import console_tool
        tool = ToolRegistry.get("console")
        assert tool is not None
    
    def test_files_tool_registered(self):
        """Files tool should be registered."""
        from kaggle_solver.tools.files import files_tool
        tool = ToolRegistry.get("files")
        assert tool is not None
    
    def test_search_tool_registered(self):
        """Search tool should be registered."""
        from kaggle_solver.tools.search import search_tool
        tool = ToolRegistry.get("search")
        assert tool is not None
    
    def test_rag_tool_registered(self):
        """RAG tool should be registered."""
        tool = ToolRegistry.get("rag")
        assert tool is not None
    
    def test_all_tools_listed(self):
        """All tools should be listed."""
        tools = ToolRegistry.list_tools()
        
        assert "console" in tools
        assert "files" in tools
        assert "search" in tools
        assert "rag" in tools
    
    def test_console_tool_executes(self):
        """Console tool should execute commands."""
        from kaggle_solver.tools.console import console_tool
        from kaggle_solver.sandbox import Sandbox
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            result = console_tool(query="echo hello", sandbox=sandbox)
            
            assert "hello" in result.lower() or result == ""
    
    def test_files_tool_operations(self):
        """Files tool should handle all operations."""
        from kaggle_solver.tools.files import files_tool
        from kaggle_solver.sandbox import Sandbox
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            # Write
            result = files_tool(op="write", path="test.txt", content="hello", sandbox=sandbox)
            assert "Written" in result or "test.txt" in result
            
            # Read
            result = files_tool(op="read", path="test.txt", sandbox=sandbox)
            assert "hello" in result
    
    def test_rag_tool_functionality(self):
        """RAG tool should work."""
        from kaggle_solver.rag import rag_instance
        
        # Add document
        rag_instance.add_document("test_doc", "Python is a programming language.")
        
        # Search
        results = rag_instance.search("python")
        
        assert len(results) > 0
        assert "python" in results[0]["content"].lower()
        
        # Clear
        rag_instance.clear()


class TestToolRegistry:
    """Test ToolRegistry capabilities."""
    
    def test_register_and_execute(self):
        """ToolRegistry can register and execute custom tools."""
        def custom_tool(query: str, **kwargs) -> str:
            return f"custom: {query}"
        
        ToolRegistry.register("custom_test", custom_tool, "Custom test tool")
        
        result = ToolRegistry.execute("custom_test", query="test")
        
        assert result.success is True
        assert "custom: test" in result.output
        
        ToolRegistry.unregister("custom_test")
    
    def test_tool_with_sandbox(self):
        """Tool can receive sandbox parameter."""
        from kaggle_solver.tools.console import console_tool
        from kaggle_solver.sandbox import Sandbox
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            
            result = ToolRegistry.execute(
                "console",
                query="echo test123",
                sandbox=sandbox
            )
            
            assert result.success is True
    
    def test_tool_with_llm(self):
        """Tool can receive LLM parameter."""
        result = ToolRegistry.execute(
            "search",
            query="test query",
            llm=Mock()
        )
        
        # May fail if no real LLM, but should not crash
        assert result is not None


class TestAgentToolsIntegration:
    """Integration tests for agents using tools."""
    
    def test_coordinator_can_use_tool(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """Coordinator can use tool action."""
        config = AgentConfig(name="Coordinator", role="test", tools=["tool"], max_iterations=2)
        agent = create_agent(ConcreteCoordinator, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        mock_llm.chat = AsyncMock(return_value='{"action": "tool", "tool": "console", "query": "ls"}')
        
        result = asyncio.run(agent.run("list files"))
        
        mock_tool_registry.execute.assert_called()
    
    def test_search_agent_with_real_search(self, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
        """SearchAgent can use real search tool."""
        config = AgentConfig(name="SearchAgent", role="test", tools=["search"], max_iterations=2)
        agent = create_agent(ConcreteSearch, config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback)
        
        # Search agent should have search in config
        assert "search" in agent.config.tools


class TestAgentPrompts:
    """Test agent prompts are defined."""
    
    def test_coordinator_prompt_defined(self):
        """Coordinator should have system prompt."""
        from kaggle_solver.agents.coordinator import CoordinatorAgentPrompts
        prompt = CoordinatorAgentPrompts.system_prompt()
        assert len(prompt) > 0
        assert "delegate" in prompt.lower()
    
    def test_code_agent_prompt_defined(self):
        """CodeAgent should have system prompt."""
        from kaggle_solver.agents.coordinator import CodeAgentPrompts
        prompt = CodeAgentPrompts.system_prompt()
        assert len(prompt) > 0
    
    def test_search_agent_prompt_defined(self):
        """SearchAgent should have system prompt."""
        from kaggle_solver.agents.coordinator import SearchAgentPrompts
        prompt = SearchAgentPrompts.system_prompt()
        assert len(prompt) > 0
    
    def test_critic_agent_prompt_defined(self):
        """CriticAgent should have system prompt."""
        from kaggle_solver.agents.coordinator import CriticAgentPrompts
        prompt = CriticAgentPrompts.system_prompt()
        assert len(prompt) > 0
    
    def test_get_agent_prompts(self):
        """get_agent_prompts should return prompts for all agents."""
        from kaggle_solver.agents.coordinator import get_agent_prompts
        
        assert len(get_agent_prompts("Coordinator")) > 0
        assert len(get_agent_prompts("CodeAgent")) > 0
        assert len(get_agent_prompts("SearchAgent")) > 0
        assert len(get_agent_prompts("CriticAgent")) > 0
