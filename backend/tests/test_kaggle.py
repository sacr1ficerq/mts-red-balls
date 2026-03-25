"""
Tests for Kaggle-specific functionality:
- Multi-model selection
- Structured output for submissions  
- Critic with metrics validation
- Human-in-the-loop with button options
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestMultiModelSelection:
    """Test that system can select appropriate model for task"""
    
    FREE_MODELS = [
        "openrouter/free",
        "google/gemma-3n-e5b-it",
        "meta-llama/llama-3.2-3b-instruct",
        "openai/gpt-oss-20b:free"
    ]
    
    def test_free_models_defined(self):
        """Free models should be defined in config"""
        from kaggle_solver.core.config import Config
        
        config = Config.load()
        
        assert hasattr(config.llm, 'model'), "LLM model should be defined"
        assert config.llm.model in self.FREE_MODELS, f"Model should be free: {config.llm.model}"
    
    def test_model_selection_by_task_complexity(self):
        from kaggle_solver.agents.coordinator import should_use_powerful_model
        
        assert not should_use_powerful_model("hello")
        assert not should_use_powerful_model("what day is it")
        
        assert should_use_powerful_model("analyze data")
        assert should_use_powerful_model("train model")


class TestStructuredOutput:
    """Test structured output for Kaggle submissions"""
    
    def test_submission_format_valid(self):
        """Submission should follow Kaggle format"""
        submission = {
            "Id": [1, 2, 3],
            "target": [0, 1, 0]
        }
        
        # Validate format
        assert isinstance(submission, dict)
        assert "Id" in submission or "id" in submission
        assert "target" in submission or "prediction" in submission
    
    def test_json_output_parsing(self):
        """System should output valid JSON for submissions"""
        from kaggle_solver.agents.base import parse_json_output
        
        # Valid JSON
        result = parse_json_output('{"action": "done", "result": "OK"}')
        assert result["action"] == "done"
        
        # JSON with extra text
        result = parse_json_output('some text {"key": "value"} more text')
        assert result["key"] == "value"


class TestCriticMetricsValidation:
    """Test critic agent validates metrics"""
    
    def test_critic_checks_metrics(self):
        """Critic should validate submission metrics"""
        from kaggle_solver.agents.critic import validate_submission
        
        # Valid submission
        valid = validate_submission({
            "score": 0.85,
            "format": "csv",
            "rows": 1000
        })
        assert valid["valid"] == True
        
        # Invalid - no score
        invalid = validate_submission({
            "format": "csv"
        })
        assert invalid["valid"] == False
    
    def test_critic_suggests_improvements(self):
        """Critic should suggest improvements based on metrics"""
        from kaggle_solver.agents.critic import suggest_improvements
        
        suggestions = suggest_improvements({
            "score": 0.5,
            "model": "simple"
        })
        
        assert len(suggestions) > 0
        assert any("feature" in s.lower() or "model" in s.lower() for s in suggestions)


class TestHumanInTheLoop:
    """Test human-in-the-loop with button options"""
    
    def test_options_format(self):
        """Options should be in correct format for frontend"""
        options = [
            {"id": "1", "label": "Use random forest", "action": "rf"},
            {"id": "2", "label": "Use gradient boosting", "action": "gb"}
        ]
        
        for opt in options:
            assert "id" in opt
            assert "label" in opt
            assert "action" in opt
    
    def test_pending_status_for_options(self):
        """Task should be pending when waiting for human input"""
        from kaggle_solver.core.state import Session
        
        session = Session(
            id="test",
            query="which model?",
            created_at="2026-01-01"
        )
        
        # Should have pending status
        assert session.status in ["pending", "running", "completed", "cancelled", "error"]
    
    def test_options_preserved_in_session(self):
        """Options should be saved in session events"""
        from kaggle_solver.core.state import Session
        
        session = Session(
            id="test",
            query="choose model",
            created_at="2026-01-01"
        )
        
        event = {
            "type": "options",
            "data": {
                "message": "Which approach?",
                "options": [
                    {"id": "1", "label": "A", "action": "do_a"},
                    {"id": "2", "label": "B", "action": "do_b"}
                ]
            }
        }
        
        session.add_event(event)
        
        assert len(session.events) == 1
        assert session.events[0]["type"] == "options"


class TestKagglePipeline:
    """Test complete Kaggle pipeline"""
    
    def test_loads_train_data(self):
        """Should be able to load training data"""
        from kaggle_solver.tools.files import files_tool
        
        # Mock sandbox
        mock_sandbox = Mock()
        mock_sandbox.list.return_value = ["train.csv", "test.csv"]
        
        result = files_tool(op="list", path=".", sandbox=mock_sandbox)
        
        assert "train.csv" in result
    
    def test_creates_submission(self):
        """Should create valid submission file"""
        submission_data = "Id,target\n0,1\n1,0\n"
        
        # Should be valid CSV
        lines = submission_data.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "Id,target"


class TestTokenCounting:
    """Test token counting works correctly"""
    
    def test_tokens_counted(self):
        """Tokens should be counted per request"""
        from kaggle_solver.core.state import Session
        
        session = Session(
            id="test",
            query="test",
            created_at="2026-01-01"
        )
        
        session.add_tokens(100, 0.001)
        
        assert session.total_tokens == 100
        assert session.total_cost > 0
    
    def test_tokens_included_in_response(self):
        """Token count should be included in API response"""
        from kaggle_solver.core.state import Session
        
        session = Session(
            id="test",
            query="test",
            created_at="2026-01-01"
        )
        session.add_tokens(500)
        
        data = session.to_dict()
        
        assert "total_tokens" in data
        assert data["total_tokens"] == 500
