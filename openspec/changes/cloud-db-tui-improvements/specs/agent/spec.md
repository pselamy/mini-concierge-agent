# Specification Delta: Cloud SQL Integration, TUI Client, and Immutability Enforcements

## MODIFIED Requirements
### Requirement: Session Persistence & Backend Fallback (REQ-CONC-MEM)
The agent SHALL persist conversation history in a SQL database.

#### Scenario: Fallback to SQLite locally
- **WHEN** the service starts up locally without Cloud SQL configuration
- **THEN** it falls back to using a local SQLite database for session persistence.

#### Scenario: Connect to Cloud SQL in production
- **WHEN** the service starts up in production with Cloud SQL connector settings
- **THEN** it connects to the Cloud SQL PostgreSQL instance using IAM database authentication.


## ADDED Requirements
### Requirement: Interactive TUI Client (REQ-CONC-CLI-TUI)
The system SHALL provide an interactive Text User Interface (TUI) client built using the Textual framework to communicate with the Mini-Concierge travel planner API.
#### Scenario: Run TUI and Query Travel Planner
- **WHEN** the TUI client is launched with a parameterized service URL
- **THEN** it displays a clean, user-friendly interface with an input query bar and chat history.
- **WHEN** the user inputs a travel query (e.g., "Plan a day in Chicago")
- **THEN** the TUI sends the REST request to the travel planner service, shows the loading state, and appends the agent's response to the conversation log.

#### Scenario: Handle Interactive Approval
- **WHEN** the service returns a `paused` state requiring booking approval
- **THEN** the TUI client displays a modal dialog or interactive buttons allowing the user to click "Approve" or "Reject".
- **WHEN** the user clicks "Approve"
- **THEN** the TUI client sends the resume payload to the service and updates the conversation state.

### Requirement: Immutable API Payload Models (REQ-CONC-IMMUTABLE)
The FastAPI application's incoming request models (Pydantic) SHALL be configured as frozen to ensure request state immutability.
#### Scenario: Prevent Request Mutation
- **WHEN** a request payload model is instantiated from incoming JSON
- **THEN** attempting to modify any of its fields programmatically raises a validation/type error.
