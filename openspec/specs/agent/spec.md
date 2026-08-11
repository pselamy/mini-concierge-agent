# Specification: Mini-Concierge Travel & Activity Planner

## 1. Purpose
The Mini-Concierge agent provides travel and activity planning assistance. It uses tools to check weather and search for restaurants, maintains user preferences in session state, and requires explicit human confirmation before making bookings.

---

## 2. Requirements

### Requirement: Weather-Aware Planning (REQ-CONC-WEATHER)
The agent SHALL check the weather for the target destination and date before recommending outdoor activities.
*   **Scenario: Rain forecast**
    *   **WHEN** the user asks to plan a day in "Chicago" on "2026-08-15"
    *   **AND** the weather tool returns "Rain" for that date
    *   **THEN** the agent SHALL only suggest indoor activities (e.g., museums, indoor dining).

### Requirement: Preference-Aware Restaurant Search (REQ-CONC-PREF)
The agent SHALL store user culinary preferences in session state and prioritize matching restaurants in subsequent turns.
*   **Scenario: Store and recall preference**
    *   **WHEN** the user mentions "I like Italian food"
    *   **THEN** the agent stores this preference in `user:preference`.
    *   **WHEN** the user later asks "Suggest a place to eat"
    *   **THEN** the agent retrieves `user:preference` and prioritizes Italian restaurants.

### Requirement: Human-in-the-Loop Booking (REQ-CONC-HITL)
The agent MUST pause execution and request explicit human confirmation before finalizing a restaurant booking.
*   **Scenario: Booking requires approval**
    *   **WHEN** the user says "Book a table at Gino's East for 7 PM"
    *   **THEN** the agent SHALL call the `book_reservation` tool which triggers a confirmation request.
    *   **AND** the service SHALL return a status indicating execution is paused, yielding the `approval_id` and `invocation_id`.
*   **Scenario: Resume after approval**
    *   **WHEN** the user confirms the booking (confirmed: true)
    *   **THEN** the agent SHALL resume execution and complete the booking.

### Requirement: Session Persistence & Compaction (REQ-CONC-MEM)
The agent SHALL persist conversation history in a local SQLite database and compact context history every 3 turns to prevent token bloat.

### Requirement: Structured Logging (REQ-CONC-OBS)
The service SHALL log agent activities in structured JSON format, recording:
1.  **Intent**: The action the agent decided to take before executing it (e.g., calling a tool).
2.  **Outcome**: The result of the action.

---

## 3. API Surface

The service exposes a single query endpoint that handles both initial queries and resumption after a pause.

### `POST /query`

**Request Payload:**
```json
{
  "user_id": "string",
  "session_id": "string",
  "query": "string (optional if resuming)",
  "invocation_id": "string (optional, required if resuming)",
  "approval_response": {
    "approval_id": "string",
    "confirmed": true
  } (optional, required if resuming)
}
```

**Response Payload (Standard):**
```json
{
  "status": "success",
  "response": "string (agent response text)",
  "session_id": "string"
}
```

**Response Payload (Paused for HITL):**
```json
{
  "status": "paused",
  "message": "Requires human approval",
  "session_id": "string",
  "invocation_id": "string",
  "approval_info": {
    "approval_id": "string",
    "hint": "Confirm booking at Gino's East for 7 PM?"
  }
}
```
