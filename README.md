# Multi-Agent Kaggle Solver

Production-ready multi-agent system for solving Kaggle competitions using LLM-powered agents with secure sandbox execution.

## 🚀 Features

- **6 Specialized Agents**: HypothesisGenerator, DataPreprocessor, FeatureEngineer, ModelTrainer, DataParser, KaggleSubmitter
- **Kaggle MCP Integration**: Download data, submit solutions, track leaderboard
- **Secure Sandbox**: Path traversal protection, command injection prevention
- **Production Ready**: Timeout mechanisms, retry logic, rate limiting, shared state
- **Web Interface**: Real-time agent execution monitoring with Alpine.js
- **Comprehensive Testing**: 230+ tests with 93.5% pass rate

## 📋 Quick Start

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
# Start backend (from project root)
cd backend
python3 server.py

# Start frontend (in another terminal)
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## 🏗️ Architecture

```
backend/
├── kaggle_solver/
│   ├── agents/          # Agent implementations
│   ├── core/            # Core components (orchestrator, state, config)
│   ├── tools/           # Tool implementations
│   ├── mcp/             # Model Context Protocol clients
│   └── prompts/         # Agent prompts (YAML)
├── tests/               # Test suite
└── server.py            # FastAPI server

frontend/
├── index.html           # Main UI
└── src/
    ├── app.js           # Alpine.js application
    └── services/        # API client
```

## 🤖 Agents

### CoordinatorAgent
Plans and delegates tasks to specialized agents.

### HypothesisGeneratorAgent
Generates feature engineering hypotheses and creative ideas.

### DataPreprocessorAgent
Performs EDA, data cleaning, and preprocessing.

### FeatureEngineerAgent
Creates new features based on hypotheses.

### ModelTrainerAgent
Trains ML models and evaluates performance.

### DataParserAgent
Automatically parses and understands data structure.

### KaggleSubmitterAgent
Submits solutions to Kaggle competitions.

## 🔧 Configuration

Edit `backend/config.yaml`:

```yaml
llm:
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.7
  max_tokens: 4096

sandbox:
  root: "./workspace"
  timeout: 120
```

## 🧪 Testing

```bash
cd backend
python3 -m pytest tests/ -v
```

## 📊 Performance

- **Prompt Optimization**: 60-88% reduction in token usage
- **Rate Limiting**: 8 requests/minute with token bucket algorithm
- **Timeout**: 300s agent timeout, 60s LLM timeout
- **Retry Logic**: 3 attempts with exponential backoff (1s → 2s → 4s)

## 🔒 Security

- Path traversal protection with `os.path.normpath()`
- Command injection prevention
- Secure sandbox execution
- Input validation

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Agent System](docs/AGENTS.md)
- [Production Guide](docs/PRODUCTION.md)
- [API Reference](docs/API.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python3 -m pytest tests/ -v`
5. Submit a pull request

## 📄 License

MIT License

## 🙏 Acknowledgments

Built with:
- FastAPI (backend)
- Alpine.js (frontend)
- OpenRouter (LLM API)
- Kaggle API
- Pytest (testing)
