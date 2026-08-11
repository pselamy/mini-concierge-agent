## Why
We need to initialize the "Mini-Concierge Travel & Activity Planner" agent codebase to demonstrate mastery of the "5 Days of AI" concepts. This project will serve as the lightweight evaluation submission, replacing the complex capstone.

## What Changes
1.  **Project Structure**: Establish python package structure.
2.  **Tools**: Implement `get_weather`, `search_restaurants` (preference-aware), and `book_reservation` (HITL-gated).
3.  **ADK Orchestration**: Define Coordinator and Travel Worker agents using `google-adk` Workflows.
4.  **Memory & State**: Configure SQLite persistence and history compaction.
5.  **API Layer**: Create a FastAPI app exposing `/query` for chat interaction (supporting HITL pause/resume).
6.  **Observability**: Configure JSON logging of agent intents and tool executions.
7.  **Infra & CI**:
    *   Create `main.tf` for deployment representation.
    *   Create `pytest` test suite verifying the flow.

## Capabilities
*   `mini-concierge-agent`: Main service that plans travel, checks weather, suggests restaurants, and handles reservation bookings securely with human confirmation.
