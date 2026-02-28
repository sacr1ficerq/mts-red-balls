import pytest
from unittest.mock import Mock
from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult

class ConcreteAgent(BaseAgent):
    def system_prompt(self) -> str:
        return "test"

class TestDelegation:
    @pytest.fixture
    def agent_factory(self):
        factory = Mock()
        return factory

    def test_delegation_creates_sub_agent(self, agent_factory):
        # Test that delegation creates and runs a sub-agent
        
        config = AgentConfig(name="AgentA", role="Role", tools=[], max_iterations=2)
        agent = ConcreteAgent(config, Mock(), Mock(), Mock(), agent_factory=agent_factory)
        
        # First call returns delegate, second call returns done
        agent.llm.chat.side_effect = [
            '{"action": "delegate", "agent": "AgentB", "task": "task"}',
            '{"action": "done", "result": "delegation completed"}'
        ]
        
        # Mock factory to return a mock agent
        sub_agent = Mock()
        sub_agent.run.return_value = AgentResult(success=True, output="AgentB result")
        agent_factory.side_effect = lambda **kwargs: sub_agent
        
        result = agent.run("start")
        
        # Agent should complete successfully
        assert result.success
        # The final result comes from the LLM's "done" response
        assert "delegation completed" in result.output
        # But the factory was called to create the sub-agent
        agent_factory.assert_called()

    def test_delegation_without_factory(self):
        # Test behavior when delegation is requested but no factory exists
        
        config = AgentConfig(name="AgentA", role="Role", tools=[], max_iterations=2)
        agent = ConcreteAgent(config, Mock(), Mock(), Mock(), agent_factory=None)
        
        # LLM returns delegate action, but no factory to handle it
        # Agent should detect it's repeating and stop
        agent.llm.chat.return_value = '{"action": "delegate", "agent": "AgentB", "task": "task"}'
        
        result = agent.run("start")
        
        # Without factory, delegate is ignored, agent loops and eventually detects repetition
        assert result.error in ["Agent stuck in a loop", "Max iterations"]