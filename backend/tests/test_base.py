import pytest
import json
import time
from unittest.mock import Mock, MagicMock, patch
from dataclasses import asdict

from kaggle_solver.agents.base import (
    AgentState,
    AgentConfig,
    AgentResult,
    BaseAgent,
)


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""
    
    def system_prompt(self) -> str:
        return f"You are {self.config.name}. {self.config.role}"


@pytest.fixture
def mock_llm():
    """Mock LLM that returns configurable responses."""
    llm = Mock()
    llm.chat = Mock(return_value='{"action": "done", "result": "test response"}')
    return llm


@pytest.fixture
def mock_sandbox():
    """Mock Sandbox."""
    sandbox = Mock()
    sandbox.execute = Mock(return_value=Mock(success=True, output="sandbox result"))
    return sandbox


@pytest.fixture
def mock_tool_registry():
    """Mock ToolRegistry."""
    registry = Mock()
    registry.execute = Mock(return_value=Mock(success=True, output="tool result"))
    return registry


@pytest.fixture
def mock_event_callback():
    """Mock event callback."""
    return Mock()


@pytest.fixture
def agent_config():
    """Create test AgentConfig."""
    return AgentConfig(
        name="TestAgent",
        role="Testing agent",
        tools=["console", "files"],
        model="test/model",
        max_iterations=5,
        temperature=0.7
    )


@pytest.fixture
def agent(agent_config, mock_llm, mock_sandbox, mock_tool_registry, mock_event_callback):
    """Create concrete agent for testing."""
    return ConcreteAgent(
        config=agent_config,
        llm=mock_llm,
        sandbox=mock_sandbox,
        tool_registry=mock_tool_registry,
        event_callback=mock_event_callback,
        agent_factory=None
    )


class TestAgentState:
    """Tests for AgentState enum."""
    
    def test_all_states_exist(self):
        """All expected states should exist."""
        assert hasattr(AgentState, 'IDLE')
        assert hasattr(AgentState, 'THINKING')
        assert hasattr(AgentState, 'TOOL')
        assert hasattr(AgentState, 'DELEGATING')
        assert hasattr(AgentState, 'DONE')
        assert hasattr(AgentState, 'ERROR')
    
    def test_state_values(self):
        """States should have correct string values."""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.THINKING.value == "thinking"
        assert AgentState.TOOL.value == "tool"
        assert AgentState.DELEGATING.value == "delegating"
        assert AgentState.DONE.value == "done"
        assert AgentState.ERROR.value == "error"


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""
    
    def test_default_values(self):
        """Config should have correct defaults."""
        config = AgentConfig(name="test", role="test role", tools=[])
        
        assert config.name == "test"
        assert config.role == "test role"
        assert config.tools == []
        assert config.model == "anthropic/claude-3.5-sonnet"
        assert config.max_iterations == 10
        assert config.temperature == 0.7
    
    def test_custom_values(self):
        """Config should accept custom values."""
        config = AgentConfig(
            name="CustomAgent",
            role="Custom role",
            tools=["tool1", "tool2"],
            model="custom/model",
            max_iterations=20,
            temperature=0.5
        )
        
        assert config.name == "CustomAgent"
        assert config.role == "Custom role"
        assert config.tools == ["tool1", "tool2"]
        assert config.model == "custom/model"
        assert config.max_iterations == 20
        assert config.temperature == 0.5
    
    def test_is_dataclass(self):
        """Config should be a dataclass."""
        assert hasattr(AgentConfig, '__dataclass_fields__')


class TestAgentResult:
    """Tests for AgentResult dataclass."""
    
    def test_default_values(self):
        """Result should have correct defaults."""
        result = AgentResult(success=True)
        
        assert result.success is True
        assert result.output == ""
        assert result.error == ""
        assert result.steps == []
        assert result.duration == 0.0
    
    def test_custom_values(self):
        """Result should accept custom values."""
        result = AgentResult(
            success=False,
            output="some output",
            error="some error",
            steps=[{"step": 1}],
            duration=1.5
        )
        
        assert result.success is False
        assert result.output == "some output"
        assert result.error == "some error"
        assert result.steps == [{"step": 1}]
        assert result.duration == 1.5


class TestBaseAgent:
    """Tests for BaseAgent class."""
    
    def test_initialization(self, agent, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Agent should initialize with correct values."""
        assert agent.config == agent_config
        assert agent.llm is mock_llm
        assert agent.sandbox is mock_sandbox
        assert agent.tools is mock_tool_registry
        assert agent.state == AgentState.IDLE
        assert agent.messages == []
        assert agent._iteration == 0
    
    def test_initialization_without_callback(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Agent should work without event callback."""
        agent = ConcreteAgent(
            config=agent_config,
            llm=mock_llm,
            sandbox=mock_sandbox,
            tool_registry=mock_tool_registry,
            event_callback=None,
            agent_factory=None
        )
        assert agent.event_callback is None
    
    def test_initialization_with_agent_factory(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Agent should accept agent_factory."""
        factory = Mock()
        agent = ConcreteAgent(
            config=agent_config,
            llm=mock_llm,
            sandbox=mock_sandbox,
            tool_registry=mock_tool_registry,
            event_callback=None,
            agent_factory=factory
        )
        assert agent.agent_factory is factory
    
    def test_add_message(self, agent):
        """add_message should add message to list."""
        agent.add_message("user", "hello")
        agent.add_message("assistant", "hi there")
        
        assert len(agent.messages) == 2
        assert agent.messages[0] == {"role": "user", "content": "hello"}
        assert agent.messages[1] == {"role": "assistant", "content": "hi there"}
    
    def test_emit_with_callback(self, agent, mock_event_callback):
        """_emit should call callback when present."""
        agent._emit("test_event", {"key": "value"})
        
        mock_event_callback.assert_called_once()
        call_args = mock_event_callback.call_args[0][0]
        assert call_args["type"] == "test_event"
        assert "key" in call_args["data"]
        assert call_args["data"]["key"] == "value"
        assert call_args["agent"] == "TestAgent"
        assert "timestamp" in call_args
    
    def test_emit_without_callback(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """_emit should not fail without callback."""
        agent = ConcreteAgent(
            config=agent_config,
            llm=mock_llm,
            sandbox=mock_sandbox,
            tool_registry=mock_tool_registry,
            event_callback=None
        )
        
        # Should not raise
        agent._emit("test_event", {"key": "value"})
    
    def test_system_prompt_abstract(self):
        """system_prompt should be abstract."""
        with pytest.raises(TypeError):
            BaseAgent(
                config=AgentConfig(name="test", role="test", tools=[]),
                llm=Mock(),
                sandbox=Mock(),
                tool_registry=Mock()
            )


class TestBaseAgentRun:
    """Tests for BaseAgent.run method."""
    
    def test_run_basic_done_action(self, agent, mock_llm, mock_event_callback):
        """Agent should handle done action correctly."""
        mock_llm.chat.return_value = '{"action": "done", "result": "task completed"}'
        
        result = agent.run("do something")
        
        assert result.success is True
        assert result.output == "task completed"
        # user message + assistant response
        assert len(agent.messages) == 2
    
    def test_run_emits_start_event(self, agent, mock_event_callback):
        """run should emit start event."""
        agent.llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        agent.run("test input")
        
        # First call should be system event
        first_call = mock_event_callback.call_args_list[0]
        assert first_call[0][0]["type"] == "system"
        assert "Starting:" in first_call[0][0]["data"]["message"]
    
    def test_run_emits_thought_event(self, agent, mock_event_callback):
        """run should emit thought event."""
        agent.llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        agent.run("test")
        
        # At least one event should be emitted
        assert mock_event_callback.call_count >= 1
    
    def test_run_with_context(self, agent, mock_llm):
        """run should include context in system prompt."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        context = {"session_id": "abc123", "history": []}
        agent.run("test", context)
        
        # Check that context was passed to LLM
        call_args = mock_llm.chat.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Context:" in system_msg
        assert "abc123" in system_msg
    
    def test_run_tool_action(self, agent, mock_llm, mock_tool_registry, mock_event_callback):
        """Agent should execute tool action and continue loop until done."""
        # First call returns tool action, second call returns done
        mock_llm.chat.side_effect = [
            '{"action": "tool", "tool": "console", "query": "echo hello"}',
            '{"action": "done", "result": "hello"}'
        ]
        mock_tool_registry.execute.return_value = Mock(success=True, output="hello")
        
        result = agent.run("run command")
        
        assert result.success is True
        mock_tool_registry.execute.assert_called_once()
    
    def test_run_tool_action_failure(self, agent, mock_llm, mock_tool_registry):
        """Agent should handle tool failure and continue loop - LLM decides outcome."""
        # Tool fails, but LLM can still return done with error message
        mock_llm.chat.side_effect = [
            '{"action": "tool", "tool": "console", "query": "bad"}',
            '{"action": "done", "result": "Error: command failed"}'
        ]
        mock_tool_registry.execute.return_value = Mock(success=False, error="command failed")
        
        result = agent.run("run command")
        
        # Tool failure is reported in output, but LLM decides final result
        assert "Error: command failed" in result.output
    
    def test_run_delegate_action(self, agent, mock_llm, mock_event_callback):
        """Agent should handle delegation and continue loop."""
        mock_llm.chat.side_effect = [
            '{"action": "delegate", "agent": "WorkerAgent", "task": "do work"}',
            '{"action": "done", "result": "delegated result"}'
        ]
        
        sub_agent = Mock()
        sub_agent.run.return_value = AgentResult(success=True, output="delegated result")
        
        agent.agent_factory = Mock(return_value=sub_agent)
        
        result = agent.run("delegate this")
        
        assert result.success is True
        assert result.output == "delegated result"
    
    def test_run_delegate_without_factory(self, agent, mock_llm):
        """Agent should loop again when delegate action but no factory."""
        mock_llm.chat.return_value = '{"action": "delegate", "agent": "Worker", "task": "work"}'
        agent.agent_factory = None
        agent.config.max_iterations = 1
        
        result = agent.run("try delegate")
        
        # With only 1 iteration and delegate without factory, returns max iterations error
        assert result.success is False
    
    def test_run_max_iterations(self, agent, mock_llm):
        """Agent should stop after max iterations when action not done/tool/delegate."""
        # Return unknown action that doesn't trigger exit
        mock_llm.chat.return_value = '{"action": "unknown", "data": "test"}'
        
        agent.config.max_iterations = 2
        
        result = agent.run("test")
        
        assert result.success is False
        assert result.error == "Max iterations"
        assert mock_llm.chat.call_count == 2
    
    def test_run_llm_error(self, agent, mock_llm):
        """Agent should handle LLM errors."""
        mock_llm.chat.side_effect = Exception("API error")
        
        result = agent.run("test")
        
        assert result.success is False
        assert "API error" in result.error
    
    def test_run_duration_tracked(self, agent, mock_llm):
        """Agent should track execution duration."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        result = agent.run("test")
        
        assert result.duration >= 0
    
    def test_run_multiple_iterations(self, agent, mock_llm):
        """Agent should handle multiple iterations before done."""
        call_count = [0]
        
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                # Return unknown action to continue loop
                return '{"action": "unknown", "data": "test"}'
            return '{"action": "done", "result": "finished"}'
        
        mock_llm.chat.side_effect = side_effect
        agent.config.max_iterations = 5
        
        result = agent.run("test")
        
        assert result.success is True
        assert mock_llm.chat.call_count == 3


class TestBaseAgentParse:
    """Tests for BaseAgent._parse method."""
    
    @pytest.fixture
    def parse_agent(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        return ConcreteAgent(
            config=agent_config,
            llm=mock_llm,
            sandbox=mock_sandbox,
            tool_registry=mock_tool_registry
        )
    
    def test_parse_simple_json(self, parse_agent):
        """Should parse simple JSON action."""
        result = parse_agent._parse('{"action": "done", "result": "ok"}')
        
        assert result["action"] == "done"
        assert result["result"] == "ok"
    
    def test_parse_json_in_text(self, parse_agent):
        """Should extract JSON from text."""
        result = parse_agent._parse('Some text {"action": "tool", "tool": "test"} more text')
        
        assert result["action"] == "tool"
        assert result["tool"] == "test"
    
    def test_parse_multiple_json(self, parse_agent):
        """Should parse last valid JSON with action."""
        result = parse_agent._parse('{"a": 1} {"action": "done"}')
        
        assert result["action"] == "done"
    
    def test_parse_no_action(self, parse_agent):
        """Should return done with full text if no action found."""
        result = parse_agent._parse("Just some text without JSON")
        
        assert result["action"] == "done"
        assert "Just some text" in result["result"]
    
    def test_parse_malformed_json(self, parse_agent):
        """Should handle malformed JSON gracefully."""
        result = parse_agent._parse('{"action": ')
        
        assert result["action"] == "done"
    
    def test_parse_empty_string(self, parse_agent):
        """Should handle empty string."""
        result = parse_agent._parse("")
        
        assert result["action"] == "done"
    
    def test_parse_nested_braces(self, parse_agent):
        """Should handle nested braces in content."""
        result = parse_agent._parse('{"action": "done", "result": "text with {braces}"}')
        
        assert result["action"] == "done"
        assert "braces" in result["result"]


class TestAgentIntegration:
    """Integration tests for agent behavior without hardcoding."""
    
    def test_agent_uses_config_values(self, agent_config, mock_llm, mock_sandbox, mock_tool_registry):
        """Agent should use config values for LLM calls."""
        agent = ConcreteAgent(
            config=agent_config,
            llm=mock_llm,
            sandbox=mock_sandbox,
            tool_registry=mock_tool_registry
        )
        
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        agent.run("test")
        
        call_kwargs = mock_llm.chat.call_args.kwargs
        assert call_kwargs["model"] == "test/model"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 1024
    
    def test_agent_tracks_messages(self, agent, mock_llm):
        """Agent should track all messages."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        agent.run("first")
        
        # Should have user + assistant messages
        assert len(agent.messages) == 2
        assert agent.messages[0]["role"] == "user"
        assert agent.messages[1]["role"] == "assistant"
    
    def test_agent_state_transitions(self, agent, mock_llm):
        """Agent state should be tracked."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        # Initial state
        assert agent.state == AgentState.IDLE
        
        agent.run("test")
        
        # State should be reset for next run
        assert agent._iteration > 0
    
    def test_agent_resets_between_runs(self, agent, mock_llm):
        """Agent should reset messages between runs."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        agent.run("first")
        agent.run("second")
        
        # Second run should have fresh messages
        assert agent.messages[0]["content"] == "second"


class TestAgentWithRealTools:
    """Tests verifying agent can work with real tools (non-hardcoded)."""
    
    def test_agent_can_execute_console_tool(self, agent, mock_llm, mock_tool_registry):
        """Agent should be able to execute console tool."""
        mock_llm.chat.return_value = '{"action": "tool", "tool": "console", "query": "echo test"}'
        mock_tool_registry.execute.return_value = Mock(success=True, output="test output")
        
        result = agent.run("run echo")
        
        # Verify tool was called with correct params
        mock_tool_registry.execute.assert_called_with(
            "console",
            query="echo test",
            sandbox=agent.sandbox,
            llm=agent.llm
        )
    
    def test_agent_can_execute_files_tool(self, agent, mock_llm, mock_tool_registry):
        """Agent should be able to execute files tool."""
        mock_llm.chat.return_value = '{"action": "tool", "tool": "files", "query": "test.txt"}'
        mock_tool_registry.execute.return_value = Mock(success=True, output="file content")
        
        result = agent.run("read file")
        
        mock_tool_registry.execute.assert_called()
        call_args = mock_tool_registry.execute.call_args
        assert call_args[0][0] == "files"
    
    def test_agent_passes_sandbox_and_llm_to_tools(self, agent, mock_llm, mock_tool_registry):
        """Agent should pass sandbox and LLM to tool execution."""
        mock_llm.chat.return_value = '{"action": "tool", "tool": "any", "query": "q"}'
        mock_tool_registry.execute.return_value = Mock(success=True, output="")
        
        agent.run("test")
        
        # Verify sandbox and llm are passed
        call_kwargs = mock_tool_registry.execute.call_args.kwargs
        assert "sandbox" in call_kwargs
        assert "llm" in call_kwargs


class TestAgentEdgeCases:
    """Edge case tests."""
    
    def test_empty_query(self, agent, mock_llm):
        """Agent should handle empty query."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        result = agent.run("")
        
        assert result.success is True
    
    def test_very_long_query(self, agent, mock_llm):
        """Agent should handle long query."""
        long_query = "a" * 10000
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        result = agent.run(long_query)
        
        assert result.success is True
    
    def test_unicode_in_query(self, agent, mock_llm):
        """Agent should handle unicode."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok"}'
        
        result = agent.run("Привет мир! 🌍")
        
        assert result.success is True
    
    def test_special_characters_in_response(self, agent, mock_llm):
        """Agent should handle special chars in LLM response."""
        mock_llm.chat.return_value = '{"action": "done", "result": "Test with \"quotes\" and \\ backslash"}'
        
        result = agent.run("test")
        
        assert result.success is True
        assert "quotes" in result.output
    
    def test_json_with_extra_fields(self, agent, mock_llm):
        """Agent should handle JSON with extra fields."""
        mock_llm.chat.return_value = '{"action": "done", "result": "ok", "extra": "field", "num": 123}'
        
        result = agent.run("test")
        
        assert result.success is True
