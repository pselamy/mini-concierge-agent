# Design: Cloud SQL Integration, TUI Client, and Immutability Enforcements

## Technical Architecture

### 1. Database Backend (Cloud SQL vs. SQLite)
We will leverage SQLAlchemy's engine creator to dynamically choose the connection backend:
*   **Production**: Cloud SQL PostgreSQL. We'll use the Google Cloud SQL Python Connector with IAM database authentication. The database credentials/passwords do not need to be stored or managed. The connection username is the Cloud Run Service Account email.
*   **Local Fallback**: If the environment variable `INSTANCE_CONNECTION_NAME` is not present, the session service will instantiate a SQLite engine (`sqlite:///data/sessions.db`). This keeps local development decoupled from GCP Cloud SQL.

### 2. Interactive TUI Client (Textual)
We will use the **Textual** framework to create a terminal-based chat client:
*   `app/tui.py` runs a Textual application containing:
    *   An input query field.
    *   A scrollable scroll log area (conversation panel).
    *   An interactive modal popup when a booking requires approval, displaying the approval hint and offering "Approve" (Green) and "Reject" (Red) buttons.
*   The TUI uses `httpx.AsyncClient` to perform async HTTP POST queries to the parameterized Mini-Concierge API service URL.

### 3. API Payload Immutability
We will configure Pydantic's `frozen=True` setting on request/response schema models:
*   Prevents mutation of payloads post-initialization.
*   Prevents accidental state tampering in FastAPI route handlers or background tasks.

## Infrastructure changes (Terraform)
*   **API Enablements**: Enable `sqladmin.googleapis.com` (Cloud SQL Admin API).
*   **Cloud SQL Instance & DB**: Define `google_sql_database_instance` (PostgreSQL 15, tier `db-f1-micro` to minimize costs, `cloudsql.iam_authentication` flag set to `on`).
*   **IAM DB User**: Create `google_sql_user` mapping the Cloud Run service account email as a `CLOUD_IAM_SERVICE_ACCOUNT` user.
*   **IAM Permissions**: Grant `roles/cloudsql.client` to the service account.
*   **Service Configuration**: Inject env variables `INSTANCE_CONNECTION_NAME` and `DB_NAME` into the Cloud Run container.
