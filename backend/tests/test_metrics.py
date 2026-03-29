"""
Tests for the metrics collection system.

These tests verify that the metrics collector works correctly
without modifying the core logic of the system.
"""

import pytest
import time
from kaggle_solver.metrics import (
    MetricsCollector,
    get_metrics,
    record_agent_start,
    record_agent_complete,
    record_tool_call,
    record_llm_call,
)


class TestMetricsCollector:
    """Test the MetricsCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a fresh metrics collector for each test."""
        collector = MetricsCollector()
        yield collector
        collector.clear()
    
    def test_enable_disable(self, collector):
        """Test enabling and disabling metrics collection."""
        assert collector.is_enabled()
        
        collector.disable()
        assert not collector.is_enabled()
        
        collector.enable()
        assert collector.is_enabled()
    
    def test_record_agent_start(self, collector):
        """Test recording agent start events."""
        collector.record_agent_start("TestAgent", "test query")
        
        events = collector.export_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "agent_start"
        assert events[0]["agent_name"] == "TestAgent"
        assert "query" in events[0]["data"]
    
    def test_record_agent_complete(self, collector):
        """Test recording agent completion events."""
        collector.record_agent_complete(
            agent_name="TestAgent",
            success=True,
            duration=1.5,
            tokens_used=100,
            error=""
        )
        
        events = collector.export_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "agent_complete"
        assert events[0]["data"]["success"] is True
        assert events[0]["data"]["duration"] == 1.5
        assert events[0]["data"]["tokens_used"] == 100
    
    def test_record_tool_call(self, collector):
        """Test recording tool execution events."""
        collector.record_tool_call(
            agent_name="TestAgent",
            tool_name="console",
            success=True,
            duration=0.5
        )
        
        events = collector.export_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "tool_call"
        assert events[0]["data"]["tool_name"] == "console"
        assert events[0]["data"]["success"] is True
    
    def test_record_llm_call(self, collector):
        """Test recording LLM API call events."""
        collector.record_llm_call(
            agent_name="TestAgent",
            model="claude-3.5-sonnet",
            tokens_used=500,
            duration=2.0
        )
        
        events = collector.export_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "llm_call"
        assert events[0]["data"]["model"] == "claude-3.5-sonnet"
        assert events[0]["data"]["tokens_used"] == 500
    
    def test_agent_statistics(self, collector):
        """Test that agent statistics are calculated correctly."""
        # Record multiple agent runs
        collector.record_agent_complete("Agent1", True, 1.0, 100)
        collector.record_agent_complete("Agent1", True, 2.0, 200)
        collector.record_agent_complete("Agent1", False, 0.5, 50, error="Test error")
        
        stats = collector.get_agent_stats("Agent1")
        
        assert stats["total_runs"] == 3
        assert stats["successful_runs"] == 2
        assert stats["failed_runs"] == 1
        assert stats["total_duration"] == 3.5
        assert stats["total_tokens"] == 350
        assert stats["avg_duration"] == pytest.approx(1.1667, rel=1e-3)
        assert stats["avg_tokens"] == pytest.approx(116.67, rel=1e-2)
        assert stats["success_rate"] == pytest.approx(0.6667, rel=1e-3)
        assert len(stats["errors"]) == 1
    
    def test_tool_call_statistics(self, collector):
        """Test that tool call statistics are tracked."""
        collector.record_tool_call("Agent1", "console", True)
        collector.record_tool_call("Agent1", "console", True)
        collector.record_tool_call("Agent1", "files", True)
        
        stats = collector.get_agent_stats("Agent1")
        assert stats["tool_calls"]["console"] == 2
        assert stats["tool_calls"]["files"] == 1
    
    def test_get_summary(self, collector):
        """Test getting a summary of all metrics."""
        collector.record_agent_complete("Agent1", True, 1.0, 100)
        collector.record_agent_complete("Agent2", False, 2.0, 200)
        collector.record_tool_call("Agent1", "console", True)
        
        summary = collector.get_summary()
        
        assert summary["total_events"] == 3
        assert summary["total_agent_runs"] == 2
        assert summary["total_successful_runs"] == 1
        assert summary["total_failed_runs"] == 1
        assert summary["total_duration"] == 3.0
        assert summary["total_tokens"] == 300
        assert summary["agents_count"] == 2
        assert summary["tool_calls"]["console"] == 1
    
    def test_export_events_with_limit(self, collector):
        """Test exporting events with a limit."""
        for i in range(10):
            collector.record_agent_start(f"Agent{i}", f"query{i}")
        
        # Get all events
        all_events = collector.export_events()
        assert len(all_events) == 10
        
        # Get limited events
        limited_events = collector.export_events(limit=5)
        assert len(limited_events) == 5
    
    def test_clear(self, collector):
        """Test clearing all metrics."""
        collector.record_agent_start("TestAgent", "test")
        collector.record_agent_complete("TestAgent", True, 1.0, 100)
        
        assert len(collector.export_events()) == 2
        assert collector.get_summary()["total_events"] == 2
        
        collector.clear()
        
        assert len(collector.export_events()) == 0
        assert collector.get_summary()["total_events"] == 0
    
    def test_disabled_collection(self, collector):
        """Test that events are not recorded when disabled."""
        collector.disable()
        
        collector.record_agent_start("TestAgent", "test")
        collector.record_agent_complete("TestAgent", True, 1.0, 100)
        
        assert len(collector.export_events()) == 0
    
    def test_export_summary_json(self, collector):
        """Test exporting summary as JSON."""
        collector.record_agent_complete("TestAgent", True, 1.0, 100)
        
        json_str = collector.export_summary_json()
        assert isinstance(json_str, str)
        
        import json
        summary = json.loads(json_str)
        assert summary["total_agent_runs"] == 1


class TestGlobalMetrics:
    """Test the global metrics collector instance."""
    
    def test_get_metrics_singleton(self):
        """Test that get_metrics returns the same instance."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2
    
    def test_convenience_functions(self):
        """Test the convenience functions for recording metrics."""
        # Clear global metrics first
        get_metrics().clear()
        
        record_agent_start("TestAgent", "test query")
        record_agent_complete("TestAgent", True, 1.0, 100)
        record_tool_call("TestAgent", "console", True, 0.5)
        record_llm_call("TestAgent", "claude-3.5-sonnet", 500, 2.0)
        
        summary = get_metrics().get_summary()
        assert summary["total_events"] == 4
        
        # Clean up
        get_metrics().clear()


class TestMetricsIntegration:
    """Integration tests for metrics with the system."""
    
    def test_metrics_dont_break_normal_operation(self):
        """Test that enabling metrics doesn't break normal operation."""
        collector = MetricsCollector()
        
        # Simulate normal operation
        for i in range(5):
            collector.record_agent_start(f"Agent{i}", f"query{i}")
            time.sleep(0.01)  # Simulate some work
            collector.record_agent_complete(f"Agent{i}", True, 0.01, 10)
        
        # Verify metrics were collected
        summary = collector.get_summary()
        assert summary["total_agent_runs"] == 5
        assert summary["total_successful_runs"] == 5
        
        # Verify no errors occurred
        assert summary["total_failed_runs"] == 0
