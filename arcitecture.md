# System Architecture Overview

This project is a small multi-agent platform with three major layers:

1. `frontend/`: a browser UI that starts tasks, shows session history, and streams agent events live.
2. `backend/server.py`: a FastAPI application that exposes HTTP + SSE endpoints and owns session lifecycle.
3. `backend/kaggle_solver/`: the actual agent runtime: config, orchestration, agents, tools, sandbox, state, and optional helper subsystems such as RAG and MCP.

The system is designed around a single idea: the frontend sends a user request, the backend creates a session, a coordinator agent decides what to do, specialized agents use tools inside a sandbox, and every intermediate event is pushed back to the UI.

## High-level runtime picture

```text
User
  -> Frontend UI (Alpine.js)
  -> POST /api/query
  -> FastAPI server
  -> Session + per-session sandbox
  -> Coordinator agent
  -> LLM loop
  -> Tool calls and/or delegated sub-agents
  -> Events recorded in session state
  -> SSE /api/sse/{session_id}
  -> Frontend event feed
  -> Final result shown to user
```

## Main abstractions

### 1. API layer

`backend/server.py` is the system entrypoint.

It is responsible for:

- loading config via `ConfigHolder`
- initializing logging
- exposing REST endpoints for starting, continuing, stopping, and inspecting sessions
- exposing SSE for real-time event streaming
- creating or reusing the singleton `Orchestrator`
- creating a dedicated sandbox directory per session
- translating agent events into session events visible in the UI

Important endpoints:

- `POST /api/query`: create a session and start execution in the background
- `GET /api/sse/{session_id}`: stream session events to the browser
- `GET /api/session/{session_id}`: fetch persisted session state
- `POST /api/session/{session_id}/continue`: continue a conversation
- `POST /api/session/{session_id}/select`: resume a session after a button-choice event
- `GET /api/sessions`: list active and historical sessions
- `GET /api/workspace/files` and `GET /api/workspace/read`: inspect sandbox files from the UI

### 2. Configuration model

`backend/kaggle_solver/core/config.py` defines strongly-shaped config dataclasses:

- `LLMConfig`
- `SandboxConfig`
- `AgentSettings`
- `SearchConfig`
- `ServerConfig`
- `LoggingConfig`
- `Config`

`backend/config.yaml` is the concrete runtime config. It defines:

- the default LLM model
- sandbox root and allowed commands
- agent roles, tools, and iteration limits
- search and RAG settings
- server settings

`ConfigHolder` is a simple singleton so the rest of the code can access one shared loaded config.

### 3. Orchestrator

`backend/kaggle_solver/core/orchestrator.py` contains the central runtime abstraction: `Orchestrator`.

It owns:

- `state`: persistent sessions via `StateManager`
- `llm`: the shared `LLM` client
- `sandbox`: a default sandbox rooted at `workspace/`
- `base_sandbox_path`: parent directory for per-session sandboxes
- `tool_registry`: global registry of tools
- `_session_sandboxes`: one sandbox per session id

Its main job is not to solve tasks itself but to assemble the execution environment:

- create agents with the right config
- wire event callbacks
- attach the right sandbox
- persist session state
- support both initial run and later continuation

### 4. Session and persistent state

`backend/kaggle_solver/core/state.py` defines the long-lived conversation model.

Core objects:

- `Session`: one user task or ongoing conversation
- `Step`: one recorded action inside a session
- `StateManager`: load/save all sessions to `backend/data/sessions.json`

`Session` stores:

- original user query
- status (`running`, `completed`, `error`, `cancelled`)
- event timeline for UI playback
- message history for continuation
- steps for structured audit trail
- artifacts like final result, duration, errors
- token and cost counters

This is the main bridge between runtime execution and UI observability.

### 5. Agent registry and agent classes

Agent implementations are intentionally thin.

- `backend/kaggle_solver/agents/registry.py`: `AgentRegistry` maps agent names to classes
- `backend/kaggle_solver/agents/__init__.py`: registers `CoordinatorAgent`, `CodeAgent`, `SearchAgent`, `CriticAgent`
- `backend/kaggle_solver/agents/base.py`: contains almost all execution logic in `BaseAgent`

This means the project uses a "prompt-specialized agents with one shared runtime" architecture:

- the class mostly changes the `system_prompt()`
- the real behavior loop is shared by all agents in `BaseAgent`

### 6. Prompt-driven agent specialization

`backend/kaggle_solver/agents/coordinator.py` loads prompt YAML files from `backend/kaggle_solver/prompts/`.

Each agent is specialized mainly by prompt:

- `coordinator.yaml`: plan and delegate
- `code.yaml`: write files and run commands
- `search.yaml`: search the web and summarize
- `critic.yaml`: review outputs

Tool action instructions are also stored as YAML fragments under `prompts/tools/` and interpolated into agent prompts.

So, conceptually:

- `BaseAgent` = engine
- prompt YAML = policy/instructions
- registry = naming and construction

### 7. LLM adapter

`backend/kaggle_solver/llm.py` wraps the OpenRouter/OpenAI-compatible chat API.

Responsibilities:

- load API key from `.env`
- call chat completion API
- retry on rate limits/timeouts/API errors
- convert tool calls from model output into the JSON action format expected by `BaseAgent`
- provide a mock mode when no API key exists

The entire agent system expects the LLM to produce one JSON action at a time, such as:

- `{"action": "tool", ...}`
- `{"action": "delegate", ...}`
- `{"action": "plan", ...}`
- `{"action": "done", ...}`

### 8. Agent execution loop

`BaseAgent.run()` is the heart of the system.

Every agent follows roughly this loop:

1. Start with system prompt + user input + optional context.
2. Ask the LLM what to do next.
3. Parse the first valid JSON action from the model response.
4. Execute the action:
   - tool call
   - delegation to another agent
   - emit plan/update/options event
   - return final result
5. Append tool results back into the message history.
6. Repeat until `done`, an error, or max iterations.

Important design detail: the parser intentionally executes only the first valid action found in a response. This is a guard against the model trying to do multiple things at once.

### 9. Tool abstraction

`backend/kaggle_solver/tools/registry.py` provides the global `ToolRegistry`.

Registered tools include:

- `console`: run shell commands in the sandbox
- `files`: read/write/edit/list/delete sandbox files
- `search`: DuckDuckGo-based web search with optional LLM filtering
- `rag`: local retrieval over indexed documents

Tools are registered by decorators when `kaggle_solver.tools` is imported.

This gives the system a plugin-like architecture:

- tool implementation lives in its own module
- metadata is registered once globally
- agents call tools only by string name

### 10. Sandbox

`backend/kaggle_solver/sandbox.py` is the safety boundary for code and file operations.

It provides:

- path confinement under a root directory
- file helpers (`read`, `write`, `delete`, `list`)
- command allowlist
- blocked pattern checks for dangerous shell usage
- subprocess execution with timeout
- per-session isolated working directories

This is the key abstraction that prevents agents from directly touching the whole host filesystem.

### 11. Frontend state model

The frontend is mostly one Alpine.js app in `frontend/src/app.js` plus a thin fetch wrapper in `frontend/src/services/api.js`.

The frontend owns UI-side state such as:

- current session id
- active and historical sessions
- streamed events
- expanded/collapsed event cards
- current plan visualization
- file tree preview
- token metrics

`frontend/index.html` renders everything in one page and binds directly to the Alpine component.

## End-to-end data flow

### A. User starts a task

1. The user types a request in the browser.
2. `frontend/src/app.js` calls `API.startTask(task)`.
3. `frontend/src/services/api.js` sends `POST /api/query` with `{ "query": task }`.

### B. Backend creates session and sandbox

Inside `POST /api/query` in `backend/server.py`:

1. the request is rate-limited
2. the orchestrator singleton is created or reused
3. `StateManager.create_session()` creates a new `Session`
4. an event callback is prepared for this session
5. a dedicated sandbox directory `workspace/<session_id>/` is created
6. a background task is scheduled so the HTTP response can return immediately

The HTTP response already contains `session_id` and initial session state, so the frontend can switch to the new conversation immediately.

### C. Frontend subscribes to live events

After receiving the `session_id`:

1. the frontend stores the new active session
2. it opens `EventSource('/api/sse/{session_id}')`
3. the SSE endpoint first sends existing events, then polls the session object for new ones
4. each new event is appended to the session feed in the UI

This is why the interface shows an incremental thought/tool/delegation timeline instead of waiting for a final answer.

### D. Coordinator agent runs

In the background task:

1. the server creates a `Coordinator` agent via `Orchestrator.create_agent()`
2. the coordinator receives the user query and session context
3. `BaseAgent.run()` sends the prompt and current messages to the LLM
4. the LLM returns a JSON action

Typical coordinator outputs:

- `plan`: create a multi-step plan
- `delegate`: send a task to `CodeAgent`, `SearchAgent`, or `CriticAgent`
- `done`: directly answer if no tools are needed

### E. Delegated agents use tools

When the action is `delegate`:

1. `BaseAgent._handle_delegate_action()` creates the target sub-agent through the shared agent factory
2. the sub-agent inherits the same session and sandbox context
3. the sub-agent runs its own LLM loop
4. if it emits a `tool` action, `ToolRegistry.execute()` runs the named tool
5. tools interact with the sandbox or web and return outputs back into the agent loop

Examples:

- `CodeAgent` -> `files` -> writes code into the session sandbox
- `CodeAgent` -> `console` -> runs `python3 ...` inside the sandbox
- `SearchAgent` -> `search` -> queries DuckDuckGo and summarizes results

### F. Events are produced at every step

Agents never update the UI directly. They emit structured events.

`BaseAgent._emit()` produces event objects like:

- `system`
- `thought`
- `tool`
- `delegate`
- `plan`
- `update_plan`
- `button_options`
- `result`

Those events flow through the callback chain:

`BaseAgent` -> session callback -> `Session.add_event()` / `Session.add_step()` -> persisted state -> SSE stream -> frontend feed

This event model is the central observability mechanism of the whole project.

### G. Session finishes

When an agent returns `done` or errors out:

1. the background task marks the session `completed` or `error`
2. final artifacts such as `result`, `duration`, and `steps` are stored
3. state is saved to `backend/data/sessions.json`
4. the SSE endpoint emits a terminal `session_done` event
5. the frontend stops treating the session as actively running

### H. Continuation and human-in-the-loop

The system also supports pausing and resuming conversation state.

Two flows exist:

- `POST /api/session/{session_id}/continue`: append a free-form user message and run the coordinator again with recent message history
- `POST /api/session/{session_id}/select`: append a structured user choice after a `button_options` event and continue execution

Continuation uses `Session.messages` and `Session.get_context()` so agents can reuse prior history and artifacts.

## What each built-in agent is for

- `Coordinator`: top-level planner/router; should mostly delegate rather than execute work directly
- `CodeAgent`: file and command executor inside sandbox
- `SearchAgent`: web researcher using DuckDuckGo + optional LLM relevance filtering
- `CriticAgent`: review/improvement agent, currently available but not deeply integrated into the main happy path

## Important supporting subsystems

### RAG

`backend/kaggle_solver/rag.py` implements a simple in-memory retrieval system:

- documents are split into chunks
- search is keyword-overlap based, not embedding-based
- the `rag` tool returns matching context

It is registered globally, but the current prompts do not strongly rely on it, so it is more of an available subsystem than a primary path.

### MCP

`backend/kaggle_solver/mcp/` and `tools/mcp.py` sketch MCP integration.

Right now this is mostly scaffold/stub code:

- the client stores connection metadata
- tool invocation returns placeholder text
- it is not a central runtime path yet

### Kaggle pipeline

`backend/kaggle_solver/kaggle.py` contains a structured ML pipeline abstraction for Kaggle-style work.

It models phases such as:

- analyze
- preprocess
- feature engineering
- train
- predict

This is a domain-specific helper, not the core orchestration mechanism.

## Architectural style in one sentence

This is an event-driven, prompt-configured, multi-agent orchestration system where a FastAPI backend manages persistent sessions and isolated sandboxes, while a thin browser client streams and visualizes the agents' internal reasoning and tool usage.

## Practical notes and current quirks

While reading the code, a few important implementation details stand out:

- The real agent behavior is centralized in `BaseAgent`; agent subclasses are mostly prompt wrappers.
- `POST /api/query` manually creates and runs a coordinator in a background task instead of calling `Orchestrator.run()`, so there are effectively two similar entry paths in the backend.
- Session events are kept both in memory and on disk; the UI depends heavily on them for reconstruction.
- The frontend uses `frontend/src/services/api.js`; `frontend/src/api.js` looks like an older parallel API wrapper and is not the main path.
- The HTML files in `frontend/src/components/` look like extracted component templates, but `frontend/index.html` currently contains the actual rendered layout inline.
- Workspace inspection endpoints use `orch.sandbox` (shared root sandbox) rather than the current session sandbox, so the file browser is closer to a global workspace view than a strict per-session view.

## Minimal mental model

If you want the shortest possible way to think about the system, use this:

1. FastAPI creates a session.
2. A coordinator agent asks an LLM what action to take.
3. The action is either delegate, use a tool, or finish.
4. Tools run inside a sandbox or on the web.
5. Every action emits events.
6. Events are saved and streamed to the frontend.
7. The frontend is mainly an event viewer plus session manager.

That is the core architecture of the project.
