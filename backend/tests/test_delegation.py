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

    def test_circular_delegation_limit(self, agent_factory):
        # Simulate A -> B -> A -> ...
        # We can't easily simulate full recursion without a real factory logic,
        # but we can check if the agent handles delegation correctly.
        
        # If we want to prevent infinite recursion, we might need a depth limit.
        # Currently, BaseAgent doesn't have a depth limit, but Python recursion limit applies.
        # Or max_iterations applies to the *current* agent.
        
        # Let's verify that delegation creates a NEW agent and runs it.
        
        config = AgentConfig(name="AgentA", role="Role", tools=[])
        agent = ConcreteAgent(config, Mock(), Mock(), Mock(), agent_factory=agent_factory)
        
        # Mock LLM to delegate
        agent.llm.chat.return_value = '{"action": "delegate", "agent": "AgentB", "task": "task"}'
        
        # Mock factory to return a mock agent
        sub_agent = Mock()
        sub_agent.run.return_value = AgentResult(success=True, output="result")
        agent_factory.side_effect = lambda **kwargs: sub_agent
        
        result = agent.run("start")
        
        assert result.success
        assert result.output == "result"
        agent_factory.assert_called()
        
        # To test infinite recursion, we'd need the factory to return an agent that delegates again.
        # This is hard to unit test without blowing up the stack.
        # But we can check if we can pass a "depth" parameter?
        # BaseAgent doesn't support depth.
        
        # Recommendation: Add depth limit to BaseAgent or Orchestrator.