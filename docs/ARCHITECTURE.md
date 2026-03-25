# Architecture

## System Overview

The Multi-Agent Kaggle Solver is a production-ready system that uses LLM-powered agents to solve Kaggle competitions autonomously.

## Components

### Backend (FastAPI)

```
backend/
├── kaggle_solver/
│   ├── agents/          # Agent implementations
│   │   ├── base.py      # BaseAgent abstract class
│   │   ├── coordinator.py
│   │   ├── hypothesis.py
│   │   ├── data_preprocessor.py
│   │   ├── feature_engineer.py
│   │   ├── model_trainer.py
│   │   ├── data_parser.py
│   │   └── kaggle_submitter.py
│   ├── core/            # Core components
│   │   ├── orchestrator.py  # Agent coordination
│   │   ├── state.py         # Session state management
│   │   └── config.py        # Configuration
│   ├── tools/           # Tool implementations
│   │   ├── console.py   # Shell command execution
│   │   ├── files.py     # File operations
│   │   ├── search.py    # Web search
│   │   └── kaggle.py    # Kaggle API tools
│   ├── mcp/             # Model Context Protocol
│   │   └── kaggle_mcp.py
│   ├── llm.py           # LLM client with rate limiting
│   ├── sandbox.py       # Secure execution environment
│   └── constants.py     # System constants
├── tests/               # Test suite
└── server.py            # FastAPI server
```

### Frontend (Alpine.js)

```
frontend/
├── index.html           # Main UI
└── src/
    ├── app.js           # Alpine.js application
    └── services/
        └── api.js       # API client
```

## Agent Execution Flow

```
User Query
    ↓
CoordinatorAgent
    ↓
Plan Generation
    ↓
Delegate to Specialized Agents
    ├─→ HypothesisGeneratorAgent
    ├─→ DataPreprocessorAgent
    ├─→ FeatureEngineerAgent
    ├─→ ModelTrainerAgent
    ├─→ DataParserAgent
    └─→ KaggleSubmitterAgent
    ↓
Tool Execution (in Sandbox)
    ↓
Result Aggregation
    ↓
Final Output
```

## Key Design Patterns

### 1. Agent Loop
Each agent follows a think-act-observe loop:
1. Receive input and context
2. Query LLM for next action
3. Execute action (tool, delegate, or complete)
4. Observe results and repeat

### 2. Tool Registry
Centralized tool registration and execution with:
- Dynamic tool discovery
- Type-safe execution
- Error handling

### 3. State Management
Session-based state with:
- Event history
- Artifact sharing between agents
- Token tracking

### 4. Rate Limiting
Token bucket algorithm for API rate limiting:
- 8 requests/minute default
- Configurable per model
- Async-safe implementation

## Security

### Sandbox Security
- Path traversal protection with `os.path.normpath()`
- Command injection prevention
- Allowed command whitelist
- Output size limits

### API Security
- Rate limiting
- Timeout mechanisms
- Retry logic with exponential backoff

## Performance Optimizations

### Prompt Optimization
- Reduced prompt sizes by 60-88%
- Condensed agent instructions
- Removed redundant examples

### Caching
- Session state persistence
- Artifact sharing
- Tool result caching

### Concurrency
- Async/await throughout
- Parallel tool execution
- Non-blocking I/O

## Data Flow

```
┌─────────────┐
│   Frontend  │
└──────┬──────┘
       │ HTTP/WebSocket
       ↓
┌─────────────┐
│   Server    │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│ Orchestrator│
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
       ↓                 ↓
┌─────────────┐   ┌─────────────┐
│   Agents    │   │   Tools     │
└──────┬──────┘   └──────┬──────┘
       │                 │
       ↓                 ↓
┌─────────────┐   ┌─────────────┐
│     LLM     │   │   Sandbox   │
└─────────────┘   └─────────────┘
```

## Configuration

All configuration is centralized in `backend/config.yaml`:

```yaml
llm:
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.7
  max_tokens: 4096

sandbox:
  root: "./workspace"
  timeout: 120

agents:
  - name: "Coordinator"
    role: "Plan and delegate tasks"
    tools: ["delegate", "message"]
```

## Testing

Test coverage:
- Unit tests: Agent logic, tools, utilities
- Integration tests: Agent coordination, state management
- Security tests: Sandbox security, input validation
- Performance tests: Rate limiting, timeouts

Run tests:
```bash
cd backend
python3 -m pytest tests/ -v
```
