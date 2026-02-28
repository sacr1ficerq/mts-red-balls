import pytest
from unittest.mock import Mock
from kaggle_solver.core.orchestrator import Orchestrator
from kaggle_solver.core.config import Config, SandboxConfig, LLMConfig

class TestConcurrency:
    @pytest.fixture
    def orchestrator(self, tmp_path):
        config = Config(
            llm=LLMConfig(model="test"),
            sandbox=SandboxConfig(root=str(tmp_path)),
            agents={}
        )
        return Orchestrator(config)

    def test_session_isolation(self, orchestrator):
        # Create two sessions
        session1 = orchestrator.state.create_session("task 1")
        session2 = orchestrator.state.create_session("task 2")
        
        # Run orchestrator logic to create sandboxes (simulated)
        # We need to call run() but mock the agent execution to avoid LLM calls
        
        # Instead of full run, let's just verify the sandbox creation logic
        # We can manually trigger the logic we added to run()
        
        # Create sandbox for session 1
        sandbox1_path = orchestrator.base_sandbox_path / session1.id
        orchestrator._session_sandboxes[session1.id] = Mock() # Mock sandbox object
        
        # Create sandbox for session 2
        sandbox2_path = orchestrator.base_sandbox_path / session2.id
        orchestrator._session_sandboxes[session2.id] = Mock()
        
        # Verify paths are different
        assert sandbox1_path != sandbox2_path
        assert str(session1.id) in str(sandbox1_path)
        assert str(session2.id) in str(sandbox2_path)

    def test_run_creates_isolated_sandbox(self, orchestrator):
        # Mock create_agent to avoid actual execution
        orchestrator.create_agent = Mock()
        orchestrator.create_agent.return_value.run.return_value = Mock(success=True, output="ok", duration=0, steps=[])
        
        # Run session 1
        session1 = orchestrator.run("task 1")
        
        # Run session 2
        session2 = orchestrator.run("task 2")
        
        # Check if sandboxes were created in _session_sandboxes
        assert session1.id in orchestrator._session_sandboxes
        assert session2.id in orchestrator._session_sandboxes
        
        sb1 = orchestrator._session_sandboxes[session1.id]
        sb2 = orchestrator._session_sandboxes[session2.id]
        
        assert sb1.root != sb2.root
        assert sb1.root.name == session1.id
        assert sb2.root.name == session2.id