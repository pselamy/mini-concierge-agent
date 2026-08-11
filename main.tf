# main.tf
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  description = "The GCP Project ID"
}

variable "region" {
  type        = string
  description = "The region to deploy resources to"
  default     = "us-central1"
}

variable "image_tag" {
  type        = string
  description = "The tag of the image to deploy"
  default     = "latest"
}

# Enable required APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# Artifact Registry Repository to host the agent container image
resource "google_artifact_registry_repository" "repo" {
  depends_on    = [google_project_service.services]
  location      = var.region
  repository_id = "mini-concierge"
  description   = "Docker repository for Mini Concierge Agent"
  format        = "DOCKER"
}

# Custom Service Account for the Agent Service
resource "google_service_account" "agent_sa" {
  depends_on   = [google_project_service.services]
  account_id   = "mini-concierge-agent-sa"
  display_name = "Service Account for Mini Concierge Agent"
}

# Grant IAM roles to the Service Account
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Secret Manager Secret for Gemini API Key
resource "google_secret_manager_secret" "gemini_key" {
  depends_on = [google_project_service.services]
  secret_id  = "gemini-api-key"
  replication {
    auto {}
  }
}

# Grant Service Account access to the Secret
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  secret_id = google_secret_manager_secret.gemini_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Cloud Run Service for the FastAPI App
resource "google_cloud_run_v2_service" "agent_service" {
  depends_on = [
    google_project_service.services,
    google_artifact_registry_repository.repo
  ]
  name     = "mini-concierge-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/agent:${var.image_tag}"
      
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      
      # Inject Gemini API key from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# Outputs
output "service_url" {
  value       = google_cloud_run_v2_service.agent_service.uri
  description = "The URL of the deployed service"
}

output "repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/agent"
  description = "The URL of the Artifact Registry repository"
}
