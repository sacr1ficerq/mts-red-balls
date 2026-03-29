# Multi-Agent Kaggle Solver

Production-ready multi-agent system for solving Kaggle competitions using LLM-powered agents with secure sandbox execution.

## Features

- **6 Specialized Agents**: HypothesisGenerator, DataPreprocessor, FeatureEngineer, ModelTrainer, DataParser, KaggleSubmitter
- **Kaggle MCP Integration**: Download data, submit solutions, track leaderboard
- **Secure Sandbox**: Path traversal protection, command injection prevention
- **Production Ready**: Timeout mechanisms, retry logic, rate limiting, shared state
- **Web Interface**: Real-time agent execution monitoring with Alpine.js
- **Comprehensive Testing**: 260+ tests with 93.5% pass rate
- **Metrics Collection**: Built-in performance monitoring and analytics

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend)
- OpenRouter API key

### Installation

```bash
# Clone repository
git clone <repository-url>
cd mts-red-balls

# Backend setup
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Frontend setup
cd ../frontend
npm install
```

### Running

```bash
# Start backend and frontend (from project root)
make run-local

# Or use Docker
make run
```

Open http://localhost:5173 in your browser.

## Architecture

The system implements a modern multi-agent architecture with clear separation of concerns:

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
│   ├── metrics.py       # Performance monitoring
│   └── constants.py     # System constants
├── tests/               # Test suite
└── server.py            # FastAPI server

frontend/
├── index.html           # Main UI
└── src/
    ├── app.js           # Alpine.js application
    └── services/
        └── api.js       # API client
```

## Agent System

### CoordinatorAgent
Plans and delegates tasks to specialized agents. Uses a think-act-observe loop to orchestrate the entire workflow.

### HypothesisGeneratorAgent
Generates feature engineering hypotheses and creative ideas based on data analysis.

### DataPreprocessorAgent
Performs EDA, data cleaning, and preprocessing. Handles missing values, outliers, and data transformations.

### FeatureEngineerAgent
Creates new features based on hypotheses. Implements various feature engineering techniques.

### ModelTrainerAgent
Trains ML models and evaluates performance. Supports gradient boosting models (LightGBM, XGBoost, CatBoost).

### DataParserAgent
Automatically parses and understands data structure. Provides data profiling and statistics.

### KaggleSubmitterAgent
Submits solutions to Kaggle competitions. Validates submission format and tracks results.

## Design Patterns

### Agent Loop Pattern
Each agent follows a think-act-observe loop:
1. Receive input and context
2. Query LLM for next action
3. Execute action (tool, delegate, or complete)
4. Observe results and repeat

### Tool Registry Pattern
Centralized tool registration and execution with:
- Dynamic tool discovery
- Type-safe execution
- Error handling

### State Management Pattern
Session-based state with:
- Event history
- Artifact sharing between agents
- Token tracking

### Rate Limiting Pattern
Token bucket algorithm for API rate limiting:
- 30 requests/minute default
- Configurable per model
- Async-safe implementation

## Security & Isolation

### Sandbox Security
- **Path Traversal Protection**: `os.path.normpath()` prevents directory traversal attacks
- **Command Injection Prevention**: Blocks dangerous shell operators and patterns
- **Allowed Commands Whitelist**: Only permitted commands can execute
- **Device Path Blocking**: Prevents access to `/dev`, `/proc`, `/sys`
- **Symlink Protection**: Checks for symlinks pointing outside sandbox
- **Output Size Limits**: Restricts command output size

### API Security
- **Rate Limiting**: Token bucket algorithm prevents abuse
- **Timeout Mechanisms**: 900s agent timeout, 60s LLM timeout
- **Retry Logic**: 3 attempts with exponential backoff (1s → 2s → 4s)
- **Input Validation**: All inputs are validated

## Performance Optimizations

### Prompt Optimization
- Reduced prompt sizes by 60-88%
- Condensed agent instructions
- Removed redundant examples

### Caching
- Session state persistence
- Artifact sharing between agents
- Tool result caching

### Concurrency
- Async/await throughout
- Parallel tool execution
- Non-blocking I/O

## Configuration

Edit `backend/config.yaml`:

```yaml
llm:
  model: "xiaomi/mimo-v2-flash"
  temperature: 0.7
  max_tokens: 4096
  max_retries: 5
  retry_delay: 5.0
  requests_per_minute: 30

sandbox:
  root: "./workspace"
  timeout: 120

agents:
  timeout: 1800  # Maximum execution time in seconds (30 minutes)
```

## Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-openrouter
make test-model-access
make test-all

# Run Titanic test
make test-titanic
```

## Performance Metrics

- **Prompt Optimization**: 60-88% reduction in token usage
- **Rate Limiting**: 30 requests/minute with token bucket algorithm
- **Timeout**: 900s agent timeout, 60s LLM timeout
- **Retry Logic**: 3 attempts with exponential backoff (1s → 2s → 4s)
- **Test Coverage**: 260+ tests with 93.5% pass rate

## Security Features

- Path traversal protection with `os.path.normpath()`
- Command injection prevention
- Secure sandbox execution
- Input validation
- Session isolation

## Monitoring & Metrics

The system includes built-in metrics collection:

- **Agent Performance**: Execution time, success rate, token usage
- **Tool Usage**: Statistics on tool calls
- **LLM Monitoring**: API calls, token consumption, response times
- **Event Logging**: All significant events with timestamps

API Endpoints:
- `GET /api/metrics` - Summary of all metrics
- `GET /api/metrics/events` - Recent events
- `GET /api/metrics/agent/{name}` - Agent-specific metrics
- `POST /api/metrics/clear` - Clear metrics

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Detailed system architecture
- [Agent System](docs/AGENTS.md) - Agent implementation details
- [Production Guide](docs/PRODUCTION.md) - Deployment instructions
- [API Reference](docs/API.md) - API documentation
- [Metrics](docs/METRICS.md) - Metrics system documentation
- [Technical Details](docs/TECHNICAL.md) - Code quality improvements

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python3 -m pytest tests/ -v`
5. Submit a pull request

## License

MIT License

## Acknowledgments

Built with:
- FastAPI (backend)
- Alpine.js (frontend)
- OpenRouter (LLM API)
- Kaggle API
- Pytest (testing)
- sentence-transformers (RAG)
- FAISS (vector search)
