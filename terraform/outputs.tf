output "service_url" {
  value       = google_cloud_run_v2_service.agent_service.uri
  description = "The URL of the deployed service"
}

output "repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/agent"
  description = "The URL of the Artifact Registry repository"
}

