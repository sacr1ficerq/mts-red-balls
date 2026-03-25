# Production Guide

## Deployment

### Prerequisites

- Python 3.9+
- Node.js 18+
- OpenRouter API key
- Kaggle API credentials (optional)

### Environment Setup

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your API keys

# Frontend
cd frontend
npm install
```

### Running in Production

#### Backend (FastAPI with Uvicorn)

```bash
cd backend
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Frontend (Vite)

```bash
cd frontend
npm run build
npm run preview
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## Configuration

### Backend Configuration (`backend/config.yaml`)

```yaml
llm:
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.7
  max_tokens: 4096

sandbox:
  root: "./workspace"
  timeout: 120
  allowed_commands:
    - python3
    - pip
    - ls
    - cat
    - mkdir
    - rm
    - cp
```

### Environment Variables

```bash
# .env
OPENROUTER_API_KEY=your_key_here
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_kaggle_api_key
```

## Monitoring

### Logs

Logs are stored in `backend/logs/`:
- `server.log`: Server logs
- `sessions_requests.log`: Session request logs

### Health Check

```bash
curl http://localhost:8000/api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-22T18:00:00Z",
  "checks": {
    "database": "ok",
    "llm": "ok",
    "kaggle": "ok"
  }
}
```

## Performance

### Rate Limiting

- Default: 8 requests/minute
- Configurable in `config.yaml`
- Token bucket algorithm

### Timeouts

- Agent timeout: 300 seconds
- LLM timeout: 60 seconds
- Sandbox timeout: 120 seconds

### Retry Logic

- Max retries: 3
- Backoff: Exponential (1s → 2s → 4s)

## Security

### Sandbox Security

- Path traversal protection
- Command injection prevention
- Allowed command whitelist
- Output size limits

### API Security

- Rate limiting
- Timeout mechanisms
- Input validation

## Troubleshooting

### Common Issues

#### Agent Timeout
```
Error: Execution timeout after 300s
```
**Solution**: Increase timeout in `config.yaml` or optimize agent tasks.

#### Rate Limit Exceeded
```
Error: Key limit exceeded (daily limit)
```
**Solution**: Wait for quota reset or upgrade API plan.

#### Sandbox Security Error
```
Error: Path traversal attempt detected
```
**Solution**: Ensure file paths are within workspace directory.

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Scaling

### Horizontal Scaling

Run multiple server instances behind a load balancer:

```bash
# Instance 1
uvicorn server:app --port 8000

# Instance 2
uvicorn server:app --port 8001

# Instance 3
uvicorn server:app --port 8002
```

### Database Scaling

For production, use a proper database instead of JSON file storage:

```python
# config.yaml
database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  name: "kaggle_solver"
```

## Backup

### Session Data

```bash
# Backup sessions
cp backend/data/sessions.json backup/sessions_$(date +%Y%m%d).json
```

### Workspace

```bash
# Backup workspace
tar -czf backup/workspace_$(date +%Y%m%d).tar.gz backend/workspace/
```

## Maintenance

### Clean Old Sessions

```bash
# Remove sessions older than 7 days
find backend/data/sessions.json -mtime +7 -delete
```

### Clean Workspace

```bash
# Clean workspace files
rm -rf backend/workspace/*
```

## Updates

### Update Dependencies

```bash
# Backend
cd backend
pip install --upgrade -r requirements.txt

# Frontend
cd frontend
npm update
```

### Update System

```bash
git pull origin main
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```
