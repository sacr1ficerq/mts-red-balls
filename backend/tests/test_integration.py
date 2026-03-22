"""Integration tests for agent workflows."""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile

from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult, AgentState, AgentConstants
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""
    
    def system_prompt(self) -> str:
        return "You are a test agent."


@pytest.fixture
def mock_llm():
    """Mock LLM that returns configured responses."""
    llm = Mock()
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def mock_sandbox():
    """Mock sandbox for testing."""
    sandbox = Mock(spec=Sandbox)
    sandbox.root = Path("/tmp/test")
    return sandbox


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry."""
    registry = Mock(spec=ToolRegistry)
    registry.execute = Mock(return_value=Mock(success=True, output="Tool executed"))
    return registry


@pytest.fixture
def agent_config():
    """Create test agent config."""
    return AgentConfig(
        name="TestAgent",
        role="Test",
        tools=["tool"],
        model="test/model",
        temperature=0.7,
        max_iterations=3
    )


class TestAgentIntegration:
    """Integration tests for agent workflows."""
    
    def test_agent_completes_with_done_action(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent completes when LLM returns done action."""
        mock_llm.chat = AsyncMock(return_value='{"action": "done", "result": "Success"}')
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry
        )
        
        result = asyncio.run(agent.run("test query"))
        
        assert result.success is True
        assert result.output == "Success"
        assert mock_llm.chat.called
    
    def test_agent_executes_tool(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent executes tool when LLM returns tool action."""
        mock_llm.chat = AsyncMock(side_effect=[
            '{"action": "tool", "tool": "console", "query": "echo hello"}',
            '{"action": "done", "result": "Command executed"}'
        ])
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry
        )
        
        result = asyncio.run(agent.run("run a command"))
        
        assert mock_tool_registry.execute.called
    
    def test_agent_delegates_to_sub_agent(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent delegates task to another agent."""
        mock_llm.chat = AsyncMock(return_value='{"action": "delegate", "agent": "SearchAgent", "task": "search query"}')
        
        def create_sub_agent(name, role, tools, event_callback=None):
            sub_agent = ConcreteAgent(
                AgentConfig(name=name, role=role, tools=tools),
                mock_llm,
                mock_sandbox,
                mock_tool_registry
            )
            return sub_agent
        
        agent_config.agent_factory = create_sub_agent
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry
        )
        
        result = asyncio.run(agent.run("delegate this task"))
        
        # Should have called LLM at least twice (initial + after delegate)
        assert mock_llm.chat.call_count >= 1
    
    def test_agent_handles_invalid_json(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent handles invalid JSON gracefully."""
        mock_llm.chat = AsyncMock(return_value="This is not JSON")
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry
        )
        
        result = asyncio.run(agent.run("test"))
        
        # Should treat as done with raw text
        assert result.success is True
    
    def test_agent_respects_max_iterations(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent stops after max iterations."""
        agent_config.max_iterations = 2
        mock_llm.chat = AsyncMock(return_value='{"action": "tool", "tool": "console", "query": "echo test"}')
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry
        )
        
        result = asyncio.run(agent.run("test"))
        
        # Should have called chat max_iterations times
        assert mock_llm.chat.call_count == 2
    
    def test_agent_with_context_events(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Test agent uses context events."""
        mock_llm.chat = AsyncMock(return_value='{"action": "done", "result": "OK"}')
        
        # Create mock session with events
        mock_session = Mock()
        mock_session.get_events_by_ids = Mock(return_value=[
            {"event_id": 1, "type": "result", "data": {"content": "previous result"}}
        ])
        
        agent = ConcreteAgent(
            agent_config,
            mock_llm,
            mock_sandbox,
            mock_tool_registry,
            session=mock_session
        )
        
        result = asyncio.run(agent.run("test", context={"event_ids": [1, 2, 3]}))
        
        assert mock_session.get_events_by_ids.called
        assert result.success is True


class TestSandboxIntegration:
    """Integration tests for sandbox operations."""
    
    def test_sandbox_write_within_size_limit(self):
        """Test sandbox allows writes within size limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            content = "x" * (sandbox.MAX_FILE_SIZE - 1)
            
            sandbox.write("test.txt", content)
            assert sandbox.exists("test.txt")
    
    def test_sandbox_rejects_oversized_file(self):
        """Test sandbox rejects oversized files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(Path(tmpdir))
            content = "x" * (sandbox.MAX_FILE_SIZE + 1)
            
            with pytest.raises(ValueError, match="File too large"):
                sandbox.write("test.txt", content)


class TestRateLimiterIntegration:
    """Integration tests for rate limiter."""
    
    def test_rate_limiter_allows_requests_within_limit(self):
        """Test rate limiter allows requests within limit."""
        from server import RateLimiter
        
        limiter = RateLimiter(requests_per_minute=10, max_concurrent=2)
        
        # Should allow first request
        assert limiter.check("client1") is True
        limiter.record("client1")
        
        # Should still allow
        assert limiter.check("client1") is True
    
    def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks when over limit."""
        from server import RateLimiter
        
        limiter = RateLimiter(requests_per_minute=2, max_concurrent=1)
        
        limiter.record("client1")
        limiter.record("client1")
        
        # Should block third request
        assert limiter.check("client1") is False
    
    def test_rate_limiter_tracks_concurrent(self):
        """Test rate limiter tracks concurrent requests."""
        from server import RateLimiter
        
        limiter = RateLimiter(requests_per_minute=10, max_concurrent=2)
        
        limiter.record("client1")
        limiter.record("client1")
        
        # Should block third concurrent
        assert limiter.check("client1") is False
        
        limiter.release("client1")
        
        # Should allow after release
        assert limiter.check("client1") is True
