# Proposal: Cloud SQL Integration, TUI Client, and Immutability Enforcements

## Motivation
To transition the Mini-Concierge travel planner from a demo-level SQLite configuration to a production-ready Cloud Run architecture, we need to replace the local SQLite file database with Cloud SQL (PostgreSQL). We also want to keep local execution simple by falling back to SQLite when running locally.

Furthermore, we want to provide an interactive, terminal-based user interface (TUI) so users can easily test and manage agent booking requests and HITL approvals without manually crafting `curl` payloads. 

Finally, to enforce security and logical robustness, we want to make our API payload models immutable (frozen).

## Proposed Capabilities
*   **CAP-DB-CLOUDSQL**: Cloud Run service connects to Cloud SQL (PostgreSQL) using the Cloud SQL Python Connector with IAM database authentication. Fallback to SQLite locally.
*   **CAP-CLI-TUI**: An interactive terminal-based client (using the Textual framework) that connects to either a local or remote Mini-Concierge API instance to run planner queries and respond to approvals.
*   **CAP-MODEL-IMMUTABLE**: Pydantic input models for API requests are configured as frozen.
