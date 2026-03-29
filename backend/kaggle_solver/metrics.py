"""
Simple metrics collection system for monitoring agent performance.

This module provides a non-intrusive way to collect metrics without
changing the core logic of the system.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class MetricEvent:
    """A single metric event."""
    timestamp: float
    event_type: str
    agent_name: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "data": self.data
        }


class MetricsCollector:
    """
    Collects and aggregates metrics from agent execution.
    
    This is a non-intrusive collector that observes events without
    modifying the core logic.
    """
    
    def __init__(self):
        self._events: List[MetricEvent] = []
        self._agent_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_duration": 0.0,
            "total_tokens": 0,
            "tool_calls": defaultdict(int),
            "errors": []
        })
        self._enabled = True
    
    def enable(self):
        """Enable metrics collection."""
        self._enabled = True
        logger.info("Metrics collection enabled")
    
    def disable(self):
        """Disable metrics collection."""
        self._enabled = False
        logger.info("Metrics collection disabled")
    
    def is_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled
    
    def record_agent_start(self, agent_name: str, query: str = ""):
        """Record the start of an agent execution."""
        if not self._enabled:
            return
        
        event = MetricEvent(
            timestamp=time.time(),
            event_type="agent_start",
            agent_name=agent_name,
            data={"query": query[:100]}  # Limit query length
        )
        self._events.append(event)
        logger.debug(f"Metrics: Agent {agent_name} started")
    
    def record_agent_complete(self, agent_name: str, success: bool, 
                            duration: float, tokens_used: int = 0,
                            error: str = ""):
        """Record the completion of an agent execution."""
        if not self._enabled:
            return
        
        event = MetricEvent(
            timestamp=time.time(),
            event_type="agent_complete",
            agent_name=agent_name,
            data={
                "success": success,
                "duration": duration,
                "tokens_used": tokens_used,
                "error": error[:200] if error else ""
            }
        )
        self._events.append(event)
        
        # Update agent statistics
        stats = self._agent_stats[agent_name]
        stats["total_runs"] += 1
        if success:
            stats["successful_runs"] += 1
        else:
            stats["failed_runs"] += 1
            if error:
                stats["errors"].append(error[:200])
        stats["total_duration"] += duration
        stats["total_tokens"] += tokens_used
        
        logger.debug(f"Metrics: Agent {agent_name} completed (success={success}, duration={duration:.2f}s)")
    
    def record_tool_call(self, agent_name: str, tool_name: str, 
                        success: bool, duration: float = 0.0):
        """Record a tool execution."""
        if not self._enabled:
            return
        
        event = MetricEvent(
            timestamp=time.time(),
            event_type="tool_call",
            agent_name=agent_name,
            data={
                "tool_name": tool_name,
                "success": success,
                "duration": duration
            }
        )
        self._events.append(event)
        
        # Update tool call statistics
        self._agent_stats[agent_name]["tool_calls"][tool_name] += 1
        
        logger.debug(f"Metrics: Tool {tool_name} called by {agent_name} (success={success})")
    
    def record_llm_call(self, agent_name: str, model: str, 
                       tokens_used: int, duration: float):
        """Record an LLM API call."""
        if not self._enabled:
            return
        
        event = MetricEvent(
            timestamp=time.time(),
            event_type="llm_call",
            agent_name=agent_name,
            data={
                "model": model,
                "tokens_used": tokens_used,
                "duration": duration
            }
        )
        self._events.append(event)
        
        logger.debug(f"Metrics: LLM call by {agent_name} (model={model}, tokens={tokens_used})")
    
    def get_agent_stats(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a specific agent or all agents."""
        if agent_name:
            stats = dict(self._agent_stats[agent_name])
            # Convert defaultdict to dict for JSON serialization
            stats["tool_calls"] = dict(stats["tool_calls"])
            # Calculate averages
            if stats["total_runs"] > 0:
                stats["avg_duration"] = stats["total_duration"] / stats["total_runs"]
                stats["avg_tokens"] = stats["total_tokens"] / stats["total_runs"]
                stats["success_rate"] = stats["successful_runs"] / stats["total_runs"]
            else:
                stats["avg_duration"] = 0.0
                stats["avg_tokens"] = 0
                stats["success_rate"] = 0.0
            return stats
        else:
            # Return stats for all agents
            result = {}
            for name, stats in self._agent_stats.items():
                result[name] = self.get_agent_stats(name)
            return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected metrics."""
        total_runs = sum(s["total_runs"] for s in self._agent_stats.values())
        total_successful = sum(s["successful_runs"] for s in self._agent_stats.values())
        total_duration = sum(s["total_duration"] for s in self._agent_stats.values())
        total_tokens = sum(s["total_tokens"] for s in self._agent_stats.values())
        
        # Count tool calls across all agents
        tool_counts = defaultdict(int)
        for stats in self._agent_stats.values():
            for tool, count in stats["tool_calls"].items():
                tool_counts[tool] += count
        
        return {
            "total_events": len(self._events),
            "total_agent_runs": total_runs,
            "total_successful_runs": total_successful,
            "total_failed_runs": total_runs - total_successful,
            "overall_success_rate": total_successful / total_runs if total_runs > 0 else 0.0,
            "total_duration": total_duration,
            "total_tokens": total_tokens,
            "agents_count": len(self._agent_stats),
            "tool_calls": dict(tool_counts),
            "agent_stats": self.get_agent_stats()
        }
    
    def export_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Export collected events as a list of dictionaries."""
        events = [event.to_dict() for event in self._events]
        if limit:
            events = events[-limit:]
        return events
    
    def export_summary_json(self) -> str:
        """Export summary as JSON string."""
        return json.dumps(self.get_summary(), indent=2, default=str)
    
    def clear(self):
        """Clear all collected metrics."""
        self._events.clear()
        self._agent_stats.clear()
        logger.info("Metrics cleared")


# Global metrics collector instance
_global_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _global_metrics


def record_agent_start(agent_name: str, query: str = ""):
    """Convenience function to record agent start."""
    _global_metrics.record_agent_start(agent_name, query)


def record_agent_complete(agent_name: str, success: bool, 
                         duration: float, tokens_used: int = 0,
                         error: str = ""):
    """Convenience function to record agent completion."""
    _global_metrics.record_agent_complete(agent_name, success, duration, 
                                         tokens_used, error)


def record_tool_call(agent_name: str, tool_name: str, 
                    success: bool, duration: float = 0.0):
    """Convenience function to record tool call."""
    _global_metrics.record_tool_call(agent_name, tool_name, success, duration)


def record_llm_call(agent_name: str, model: str, 
                   tokens_used: int, duration: float):
    """Convenience function to record LLM call."""
    _global_metrics.record_llm_call(agent_name, model, tokens_used, duration)
