## 1. Project Setup & Configuration
- [x] 1.1 Verify Python environment and dependencies can be loaded.
- [x] 1.2 Create `app/` directory structure (`app/tools.py`, `app/agents.py`, `app/session.py`, `app/main.py`).

## 2. Tools Implementation (REQ-CONC-WEATHER, REQ-CONC-PREF, REQ-CONC-HITL)
- [x] 2.1 Implement mock `get_weather` tool.
- [x] 2.2 Implement preference-aware `search_restaurants` tool storing preferences in `tool_context.state`.
- [x] 2.3 Implement HITL-gated `book_reservation` tool using `tool_context.request_confirmation`.

## 3. Agent & Orchestration Setup
- [x] 3.1 Define `travel_worker` agent with the tools.
- [x] 3.2 Define `coordinator` agent wrapping `travel_worker` as an `AgentTool`.

## 4. Session & State Persistence (REQ-CONC-MEM)
- [x] 4.1 Configure SQLite session service and directory for `data/sessions.db`.
- [x] 4.2 Configure history compaction in the ADK runner/app.

## 5. FastAPI Service API
- [x] 5.1 Implement the FastAPI application shell and `/health` endpoint.
- [x] 5.2 Implement `/query` endpoint supporting standard query run and resume logic (passing `invocation_id` and confirmation response).

## 6. Observability & Logging (REQ-CONC-OBS)
- [x] 6.1 Set up JSON structured logging wrapper.
- [x] 6.2 Instrument tools and agent runs to log intent and outcome.

## 7. Verification & Testing
- [ ] 7.1 Write `pytest` integration tests covering:
    - Weather-aware planning (rain -> indoor only).
    - Preference storage and retrieval.
    - HITL pause on booking.
    - HITL resume and completion on booking confirmation.
- [ ] 7.2 Run the test suite and verify all pass.

## 8. Infrastructure
- [ ] 8.1 Create `terraform/main.tf` representing Cloud Run deployment and Secret Manager injection for `GEMINI_API_KEY`.
