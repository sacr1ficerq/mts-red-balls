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
        # Test that after plan, delegation happens automatically
        
        config = AgentConfig(name="AgentA", role="Role", tools=[], max_iterations=5)
        agent = ConcreteAgent(config, Mock(), Mock(), Mock(), agent_factory=agent_factory)
        
        # First call returns plan - then auto-delegate happens and returns
        agent.llm.chat.return_value = '{"action": "plan", "plan_id": "test123", "steps": [{"id": 1, "task": "do task"}]}'
        
        sub_agent = Mock()
        sub_agent.run.return_value = AgentResult(success=True, output="AgentB result")
        agent_factory.return_value = sub_agent
        
        result = agent.run("start")
        
        assert result.success
        assert "AgentB result" in result.output

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