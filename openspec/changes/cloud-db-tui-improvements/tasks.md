# Tasks: Cloud SQL Integration, TUI Client, and Immutability Enforcements

## Requirements and DB Scaffolding
- [ ] Add `google-cloud-sql-connector[pg8000]` and `textual` to `requirements.txt`.
- [ ] Set `model_config = ConfigDict(frozen=True)` on `QueryRequest` and `ApprovalResponsePayload` in `app/main.py` to enforce immutability.
- [ ] Refactor `app/session.py` to establish connection using Google Cloud SQL Connector if `GOOGLE_CLOUD_PROJECT` and a Cloud SQL instance connection name is configured, otherwise fallback to SQLite.

## Cloud SQL Infrastructure
- [ ] Provision a Cloud SQL (PostgreSQL) instance and database in `terraform/main.tf` using standard GCP resources.
- [ ] Grant `roles/cloudsql.client` role to the Cloud Run Service Account (`agent_sa`) in `terraform/main.tf`.
- [ ] Pass the Cloud SQL connection name env variable to the Cloud Run service in `terraform/main.tf`.

## Interactive TUI Client
- [ ] Implement the interactive TUI application using `textual` in `app/tui.py`.
- [ ] Support parameterizing the service URL (default to `http://localhost:8000`).
- [ ] Implement query submit, loading indicator, chat log displaying history, and interactive confirm/reject modals for booking approvals.
- [ ] Add command description in `README.md` on how to launch the TUI client.

## Validation and Verification
- [ ] Verify local tests continue to pass (ensuring local SQLite fallback works).
- [ ] Run format checks, mypy checks, and vulture checks.
- [ ] Run local TUI query execution tests against a locally running API service.
