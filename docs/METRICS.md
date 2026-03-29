# Metrics Collection System

## Overview

The metrics collection system provides a non-intrusive way to monitor and analyze agent performance without modifying the core logic of the system.

## Features

- **Agent Performance Tracking**: Track execution time, success rate, and token usage for each agent
- **Tool Usage Statistics**: Monitor which tools are used most frequently
- **LLM Call Monitoring**: Track API calls, token consumption, and response times
- **Event Logging**: Record all significant events with timestamps
- **REST API Endpoints**: Access metrics via HTTP endpoints
- **Non-Intrusive**: Can be enabled/disabled without affecting system behavior

## API Endpoints

### Get Metrics Summary
```http
GET /api/metrics
```

Returns a comprehensive summary of all collected metrics.

**Response Example**:
```json
{
  "total_events": 150,
  "total_agent_runs": 25,
  "total_successful_runs": 22,
  "total_failed_runs": 3,
  "overall_success_rate": 0.88,
  "total_duration": 125.5,
  "total_tokens": 15000,
  "agents_count": 6,
  "tool_calls": {
    "console": 45,
    "files": 30,
    "search": 15
  },
  "agent_stats": {
    "Coordinator": {
      "total_runs": 5,
      "successful_runs": 5,
      "failed_runs": 0,
      "total_duration": 10.5,
      "total_tokens": 2000,
      "avg_duration": 2.1,
      "avg_tokens": 400,
      "success_rate": 1.0,
      "tool_calls": {
        "delegate": 10,
        "message": 5
      }
    }
  }
}
```

### Get Recent Events
```http
GET /api/metrics/events?limit=100
```

Returns recent metric events. Use the `limit` parameter to control the number of events returned.

**Response Example**:
```json
{
  "events": [
    {
      "timestamp": 1712345678.123,
      "datetime": "2026-03-29T17:14:38.123456",
      "event_type": "agent_start",
      "agent_name": "Coordinator",
      "data": {
        "query": "Solve Titanic competition"
      }
    },
    {
      "timestamp": 1712345680.456,
      "datetime": "2026-03-29T17:14:40.456789",
      "event_type": "agent_complete",
      "agent_name": "Coordinator",
      "data": {
        "success": true,
        "duration": 2.333,
        "tokens_used": 500,
        "error": ""
      }
    }
  ]
}
```

### Get Agent-Specific Metrics
```http
GET /api/metrics/agent/{agent_name}
```

Returns detailed statistics for a specific agent.

**Response Example**:
```json
{
  "total_runs": 10,
  "successful_runs": 9,
  "failed_runs": 1,
  "total_duration": 45.5,
  "total_tokens": 5000,
  "avg_duration": 4.55,
  "avg_tokens": 500,
  "success_rate": 0.9,
  "tool_calls": {
    "console": 20,
    "files": 15,
    "search": 5
  },
  "errors": [
    "Timeout error during model training"
  ]
}
```

### Clear Metrics
```http
POST /api/metrics/clear
```

Clears all collected metrics. Use with caution.

**Response Example**:
```json
{
  "message": "Metrics cleared"
}
```

## Programmatic Usage

### Using the Global Metrics Collector

```python
from kaggle_solver.metrics import (
    get_metrics,
    record_agent_start,
    record_agent_complete,
    record_tool_call,
    record_llm_call
)

# Record agent execution
record_agent_start("Coordinator", "Solve Titanic competition")

# ... agent runs ...

record_agent_complete(
    agent_name="Coordinator",
    success=True,
    duration=5.5,
    tokens_used=1000,
    error=""
)

# Record tool usage
record_tool_call(
    agent_name="ModelTrainer",
    tool_name="console",
    success=True,
    duration=2.0
)

# Record LLM API call
record_llm_call(
    agent_name="ModelTrainer",
    model="claude-3.5-sonnet",
    tokens_used=500,
    duration=1.5
)

# Get summary
metrics = get_metrics()
summary = metrics.get_summary()
print(f"Total runs: {summary['total_agent_runs']}")
print(f"Success rate: {summary['overall_success_rate']:.2%}")
```

### Using the MetricsCollector Class

```python
from kaggle_solver.metrics import MetricsCollector

# Create a new collector
collector = MetricsCollector()

# Enable/disable collection
collector.enable()
collector.disable()

# Record events
collector.record_agent_start("TestAgent", "test query")
collector.record_agent_complete("TestAgent", True, 1.5, 100)

# Get statistics
stats = collector.get_agent_stats("TestAgent")
print(f"Average duration: {stats['avg_duration']:.2f}s")

# Get summary
summary = collector.get_summary()

# Export events
events = collector.export_events(limit=100)

# Clear metrics
collector.clear()
```

## Metrics Collected

### Agent Metrics
- **Total Runs**: Number of times the agent was executed
- **Successful Runs**: Number of successful executions
- **Failed Runs**: Number of failed executions
- **Total Duration**: Cumulative execution time
- **Total Tokens**: Total tokens consumed by LLM calls
- **Average Duration**: Mean execution time per run
- **Average Tokens**: Mean tokens consumed per run
- **Success Rate**: Percentage of successful runs
- **Tool Calls**: Count of each tool used by the agent
- **Errors**: List of error messages from failed runs

### Tool Metrics
- **Tool Name**: Name of the tool executed
- **Success**: Whether the tool execution succeeded
- **Duration**: Time taken to execute the tool
- **Agent**: Which agent called the tool

### LLM Metrics
- **Model**: Name of the LLM model used
- **Tokens Used**: Number of tokens consumed
- **Duration**: Time taken for the API call
- **Agent**: Which agent made the call

## Event Types

1. **agent_start**: Agent execution started
2. **agent_complete**: Agent execution completed
3. **tool_call**: Tool was executed
4. **llm_call**: LLM API call was made

## Use Cases

### Performance Monitoring
Track agent performance over time to identify bottlenecks:
```python
metrics = get_metrics()
summary = metrics.get_summary()

for agent_name, stats in summary["agent_stats"].items():
    print(f"{agent_name}:")
    print(f"  Success rate: {stats['success_rate']:.2%}")
    print(f"  Avg duration: {stats['avg_duration']:.2f}s")
    print(f"  Avg tokens: {stats['avg_tokens']:.0f}")
```

### Cost Optimization
Monitor token usage to optimize costs:
```python
summary = get_metrics().get_summary()
total_tokens = summary["total_tokens"]
estimated_cost = total_tokens * 0.000003  # $3 per million tokens
print(f"Estimated cost: ${estimated_cost:.2f}")
```

### Error Analysis
Identify common errors and failure patterns:
```python
for agent_name, stats in get_metrics().get_summary()["agent_stats"].items():
    if stats["errors"]:
        print(f"{agent_name} errors:")
        for error in stats["errors"][:5]:  # Show first 5 errors
            print(f"  - {error}")
```

### Tool Usage Analysis
Understand which tools are used most frequently:
```python
tool_calls = get_metrics().get_summary()["tool_calls"]
sorted_tools = sorted(tool_calls.items(), key=lambda x: x[1], reverse=True)

for tool, count in sorted_tools:
    print(f"{tool}: {count} calls")
```

## Best Practices

1. **Enable in Production**: Keep metrics enabled in production to monitor system health
2. **Regular Review**: Review metrics regularly to identify performance issues
3. **Set Alerts**: Set up alerts for high failure rates or unusual token usage
4. **Clear Periodically**: Clear metrics periodically to avoid memory issues in long-running systems
5. **Export for Analysis**: Export metrics regularly for long-term trend analysis

## Performance Impact

The metrics system is designed to have minimal performance impact:
- **Non-blocking**: Metrics collection doesn't block agent execution
- **Low Overhead**: Recording an event takes < 1ms
- **Optional**: Can be disabled if needed
- **Memory Efficient**: Events are stored in memory with configurable limits

## Testing

Run the metrics tests:
```bash
cd backend
python3 -m pytest tests/test_metrics.py -v
```

All 15 tests should pass:
```
tests/test_metrics.py ...............                                        [100%]

================================ 15 passed in 0.10s ================================
```

## Future Enhancements

Potential improvements for the metrics system:
- Persistent storage (database integration)
- Real-time dashboard
- Alerting system
- Integration with monitoring tools (Prometheus, Grafana)
- Historical trend analysis
- Automated performance reports
