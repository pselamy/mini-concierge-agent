# Delta Specification: Agent Enhancements

## ADDED Requirements

### Requirement: PII Redaction (REQ-CONC-PII)
The service SHALL globally redact PII (specifically email addresses and phone numbers) from all structured logs, messages, and metadata.
#### Scenario: Redact PII in Log Output
- **WHEN** a log record is processed containing an email address like "user@example.com" or a phone number like "555-0199"
- **THEN** the log record message and extra fields are sanitized, replacing them with "[REDACTED_EMAIL]" and "[REDACTED_PHONE]" respectively.

### Requirement: Safety Settings (REQ-CONC-SAFE)
The agent SHALL configure safety settings blocking Hate Speech, Harassment, Sexual Content, and Dangerous Content at standard thresholds.
#### Scenario: Verify Safety Filters Configuration
- **WHEN** the agent initialization config is constructed
- **THEN** the safety settings block list is configured and applied to the Gemini model runs.

### Requirement: OpenTelemetry Tracing (REQ-CONC-OTEL)
The service SHALL instrument runtime operations with OpenTelemetry tracing.
#### Scenario: Generate OpenTelemetry Traces
- **WHEN** requests are processed by the FastAPI application
- **THEN** OpenTelemetry spans are generated and exported.
