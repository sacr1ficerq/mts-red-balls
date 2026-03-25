# API Reference

## Base URL

```
http://localhost:8000/api
```

## Endpoints

### Health Check

```http
GET /api/health
```

**Response**:
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

### Start Task

```http
POST /api/query
Content-Type: application/json

{
  "query": "Solve Titanic competition",
  "session_id": "optional-session-id"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "running"
}
```

### Get Session

```http
GET /api/session/{session_id}
```

**Response**:
```json
{
  "id": "uuid",
  "query": "Solve Titanic competition",
  "status": "completed",
  "created_at": "2026-03-22T18:00:00Z",
  "events": [...],
  "artifacts": {...}
}
```

### Continue Session

```http
POST /api/session/{session_id}/continue
Content-Type: application/json

{
  "message": "Continue with feature engineering"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "running"
}
```

### Select Option

```http
POST /api/session/{session_id}/select
Content-Type: application/json

{
  "event_id": 123,
  "option": "Option 1"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "running"
}
```

### Stop Session

```http
POST /api/session/{session_id}/stop
```

**Response**:
```json
{
  "success": true
}
```

### List Sessions

```http
GET /api/sessions
```

**Response**:
```json
{
  "active": [...],
  "historical": [...]
}
```

### Clear Sessions

```http
POST /api/sessions/clear
```

**Response**:
```json
{
  "success": true
}
```

### List Workspace Files

```http
GET /api/workspace/files?session_id={session_id}
```

**Response**:
```json
{
  "files": [
    {
      "path": "train.csv",
      "size": 1024,
      "type": "file"
    }
  ]
}
```

### Read Workspace File

```http
GET /api/workspace/read?path=train.csv
```

**Response**:
```json
{
  "content": "file content..."
}
```

### Get Tools

```http
GET /api/tools
```

**Response**:
```json
{
  "tools": [
    {
      "name": "console",
      "description": "Execute shell commands"
    }
  ]
}
```

### Get Agents

```http
GET /api/agents
```

**Response**:
```json
{
  "agents": [
    {
      "name": "Coordinator",
      "role": "Plan and delegate tasks"
    }
  ]
}
```

## Server-Sent Events (SSE)

### Session Events

```http
GET /api/sse/{session_id}
```

**Event Types**:
- `system`: System messages
- `thought`: Agent thoughts
- `tool`: Tool execution
- `delegate`: Agent delegation
- `plan`: Plan updates
- `result`: Final results
- `error`: Errors

**Example Event**:
```json
{
  "type": "tool",
  "data": {
    "tool_name": "console",
    "query": "python train.py",
    "output": "Training complete..."
  },
  "agent": "ModelTrainer",
  "timestamp": "2026-03-22T18:00:00Z"
}
```

## Error Responses

All endpoints may return errors:

```json
{
  "error": "Error message",
  "status": 400
}
```

**Status Codes**:
- `400`: Bad Request
- `404`: Not Found
- `500`: Internal Server Error

## Rate Limiting

- Default: 10 requests/minute per client
- Headers included:
  - `X-RateLimit-Limit`: Total limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset time

## Authentication

Currently no authentication required. For production, implement API key or OAuth authentication.
