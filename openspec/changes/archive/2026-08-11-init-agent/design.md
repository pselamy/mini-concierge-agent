## 1. System Architecture

The Mini-Concierge service will run as a FastAPI application. It uses the `google-adk` library to manage agents, tools, sessions, and state.

```
┌────────────────────────────────────────────────────────┐
│                     FASTAPI APP                        │
│                                                        │
│   ┌───────────────┐                  ┌─────────────┐   │
│   │ Coordinator   │ ──(Calls)──────► │    Travel   │   │
│   │    Agent      │                  │    Worker   │   │
│   └───────────────┘                  └─────────────┘   │
│           │                                 │          │
│       (Returns)                         (Executes)     │
│           │                                 │          │
│           ▼                                 ▼          │
│      User Reply                         Tools (HITL)   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Component Design

### 2.1. Agents
*   **`travel_worker`**:
    *   Class: `google.adk.Agent`
    *   Model: `gemini-2.5-flash` (for fast tool execution)
    *   Tools: `get_weather`, `search_restaurants`, `book_reservation`
    *   Instructions: "You are a travel assistant. Help the coordinator by looking up weather, searching restaurants, and booking reservations."
*   **`coordinator`**:
    *   Class: `google.adk.Agent`
    *   Model: `gemini-2.5-pro` (for planning and reasoning)
    *   Tools: `AgentTool(travel_worker)`
    *   Instructions: "You are a personal concierge. Help the user plan their day. Delegate travel details to the travel_worker agent. Keep track of user preferences."

### 2.2. Tools
*   `get_weather(city: str, date: str) -> str`:
    *   Returns mock weather: "Rain" for Chicago on 2026-08-15, "Sunny" otherwise.
*   `search_restaurants(city: str, cuisine: str, tool_context: ToolContext) -> list`:
    *   Saves `cuisine` to `tool_context.state["user:preference"]`.
    *   Returns mock list of restaurants. Prioritizes cuisine matching the user preference if cuisine is not specified.
*   `book_reservation(restaurant_name: str, time: str, tool_context: ToolContext) -> dict`:
    *   **HITL Gated**:
        *   If `tool_context.tool_confirmation` is None, calls `tool_context.request_confirmation(hint=..., payload=...)` and returns pending.
        *   If confirmed, returns success. If rejected, returns failure.

### 2.3. Session & State Management
*   **Service**: `DatabaseSessionService` using a local SQLite database (`data/sessions.db`).
*   **Compaction**: `EventsCompactionConfig(compaction_interval=3, overlap_size=1)`.
*   **User State**: Shared preferences stored in `tool_context.state` with `user:` prefix.

### 2.4. FastAPI Endpoints
*   `POST /query`:
    *   Runs the `coordinator` agent using the `Runner`.
    *   Exposes options to pass `invocation_id` and `confirmed` response to resume paused runs.
*   `GET /health`: Returns status 200.

### 2.5. Observability (Logging)
*   Configure standard Python logging to output JSON format.
*   Log pre-tool execution (Intent) and post-tool execution (Outcome).

---

## 3. Risks & Mitigations

*   **Risk**: Gemini API key exposed.
    *   **Mitigation**: Force loading from `GEMINI_API_KEY` env var; error out on startup if missing.
*   **Risk**: SQLite database locked during concurrent requests.
    *   **Mitigation**: Acceptable for local dev/demo. For production, the Terraform config will document migrating to Cloud SQL.
