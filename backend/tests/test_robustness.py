import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult

class ConcreteAgent(BaseAgent):
    def system_prompt(self) -> str:
        return "test"

class TestRobustness:
    @pytest.fixture
    def agent(self):
        config = AgentConfig(name="Test", role="Test", tools=[])
        return ConcreteAgent(config, Mock(), Mock(), Mock())

    def test_nested_json_parsing(self, agent):
        # LLM returns nested JSON which simple regex fails on
        nested_json = '{"action": "tool", "tool": "files", "args": {"content": "{\\"nested\\": true}"}}'
        agent.llm.chat = AsyncMock(side_effect=[
            nested_json,
            '{"action": "done", "result": "success"}'
        ])
        agent.tools.execute.return_value = Mock(success=True, output="ok")
        
        result = asyncio.run(agent.run("test"))
        assert result.success
        assert agent.tools.execute.called
        
    def test_tool_crash_handling(self, agent):
        # Tool raises exception
        agent.llm.chat = AsyncMock(side_effect=[
            '{"action": "tool", "tool": "crashy", "query": "run"}',
            '{"action": "done", "result": "Tool failed, but I am done"}'
        ])
        agent.tools.execute.return_value = Mock(success=False, error="Tool crashed")
        
        # We need the agent to see the error and try again or finish
        # Mock LLM to return done after seeing error
        
        result = asyncio.run(agent.run("test"))
        assert result.success
        assert "Tool failed" in result.output

    def test_llm_complete_failure(self, agent):
        # LLM fails completely
        agent.llm.chat = AsyncMock(side_effect=Exception("API Down"))
        
        result = asyncio.run(agent.run("test"))
        assert not result.success
        assert "API Down" in result.error