# Mini-Concierge Travel & Activity Planner

A lightweight Python agent built using the Google Agent Development Kit (ADK) to demonstrate core agentic patterns: multi-agent orchestration, tool calling, state management, and Human-in-the-Loop (HITL) execution.

This project is designed to satisfy the evaluation criteria for the "5 Days of AI" program.

---

## 🧭 Architecture

The system uses a **Coordinator-Worker** pattern:
1.  **Coordinator Agent**: Receives the user request, plans the itinerary, and delegates sub-tasks.
2.  **Travel Worker Agent**: Executes specific tools to gather information and perform actions.

### Tools
*   `get_weather(city, date)`: Returns simulated weather info.
*   `search_restaurants(city, cuisine)`: Searches mock data, matching against user preferences stored in session state.
*   `book_reservation(restaurant_name, time)`: Simulates a booking. **Requires Human-in-the-Loop approval** before execution.

---

## 🛠️ Tech Stack & Concepts Demonstrated

*   **Framework**: `google-adk` (Python)
*   **Orchestration**: Multi-agent delegation
*   **State & Memory**: SQLite persistence (`DatabaseSessionService`) and history compaction.
*   **Observability**: Structured JSON logging of agent intent and tool outcomes.
*   **Security**: Gemini API key loaded via environment variables / Secret Manager.
*   **Infra**: Terraform deployment configuration.

---

## 🚀 Setup & Execution

(Instructions to be added as implementation progresses)
