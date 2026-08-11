#!/bin/bash
set -e

PROJECT_ID="pselamy-fde-sandbox-124598"
REGION="us-central1"
IMAGE_TAG="latest"

echo "Configuring gcloud project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}"

# Initialize OpenTofu using the GCS bucket created during bootstrap
echo "Initializing OpenTofu..."
cd terraform
tofu init -backend-config="bucket=${PROJECT_ID}-tfstate"

# Target the repo first to solve chicken-and-egg dependency
echo "Bootstrapping Artifact Registry Repository..."
tofu apply \
  -target=google_artifact_registry_repository.repo \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="image_tag=${IMAGE_TAG}" \
  -var="gemini_api_key=dummy" \
  -auto-approve

# Auth Docker to the registry
echo "Authenticating Docker..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build and Push image
cd ..
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/mini-concierge/agent:${IMAGE_TAG}"
echo "Building Docker image ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .
echo "Pushing Docker image..."
docker push "${IMAGE_NAME}"

# Run full apply
cd terraform
echo "Deploying Cloud Run service and Secret Manager..."
if [ -z "$GEMINI_API_KEY" ]; then
  read -sp "Enter Gemini API Key: " GEMINI_API_KEY
  echo ""
fi

tofu apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="image_tag=${IMAGE_TAG}" \
  -var="gemini_api_key=${GEMINI_API_KEY}" \
  -auto-approve

echo "Deployment complete!"

