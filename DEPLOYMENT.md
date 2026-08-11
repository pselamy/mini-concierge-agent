# Deployment Guide

This guide explains how to deploy the Mini-Concierge Agent to Google Cloud Run using OpenTofu and GitHub Actions.

## Prerequisites

### 1. Google Cloud Project
You need a Google Cloud Project with billing enabled.

### 2. Gemini API Key
Obtain a Gemini API key from Google AI Studio.

### 3. Setup Secret Manager
Before deploying, you must create a secret in Secret Manager called `gemini-api-key` in your project and store your API key in it.
You can do this via the GCP Console or using `gcloud`:
```bash
# Create the secret
gcloud secrets create gemini-api-key --replication-policy="automatic"

# Add your API key as a version
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
```

### 4. Setup OpenTofu State Bucket
Create a Google Cloud Storage (GCS) bucket to store the OpenTofu state file. This bucket name will be needed in GitHub secrets.
```bash
gsutil mb -l us-central1 gs://YOUR_STATE_BUCKET_NAME
```

### 5. Authentication Setup
You can authenticate GitHub Actions to Google Cloud using either **Workload Identity Federation** (recommended) or a **Service Account Key**.

#### Option A: Workload Identity Federation (WIF) - Recommended
Set up WIF in your GCP project to trust your GitHub repository. Follow the [Google Cloud WIF Guide](https://github.com/google-github-actions/auth#preferred-direct-workload-identity-federation).
You will get a Workload Identity Provider string (looks like `projects/123456/locations/global/workloadIdentityPools/my-pool/providers/my-provider`) and you must grant the pool access to act as your deployment service account.

#### Option B: Service Account Key (Legacy)
Create a Service Account with the following roles:
- `roles/run.admin` (Cloud Run Administrator)
- `roles/iam.serviceAccountUser` (to act as the agent runtime service account)
- `roles/artifactregistry.admin` (to manage container images)
- `roles/secretmanager.viewer` and `roles/secretmanager.secretAccessor` (to manage access to the gemini key)
- `roles/serviceusage.serviceController` (to enable APIs)
- `roles/storage.admin` (to read/write the OpenTofu state bucket)

Create and download a JSON key for this service account.

---

## GitHub Repository Secrets Configuration

Configure the following secrets in your GitHub repository (**Settings > Secrets and variables > Actions**):

| Secret Name | Description | Example |
| :--- | :--- | :--- |
| `GCP_PROJECT_ID` | **Required**. Your Google Cloud Project ID. | `my-concierge-project` |
| `GCP_REGION` | *Optional*. The region to deploy to. Defaults to `us-central1`. | `us-central1` |
| `GCP_TF_STATE_BUCKET` | **Required**. The GCS bucket name you created in step 4. | `my-tofu-state-bucket` |
| `GCP_REPOSITORY` | *Optional*. The Artifact Registry repo name. Defaults to `mini-concierge`. | `mini-concierge` |

### If using Workload Identity Federation (Option A):
| Secret Name | Description | Example |
| :--- | :--- | :--- |
| `GCP_WIF_PROVIDER` | The Workload Identity Provider string. | `projects/.../providers/...` |
| `GCP_WIF_SA` | The email of the service account to assume. | `deployer@project.iam.gserviceaccount.com` |

### If using Service Account Key (Option B):
| Secret Name | Description | Example |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | The entire content of the Service Account JSON key file. | `{ "type": "service_account", ... }` |

---

## Deployment

Once the prerequisites are set up and secrets are configured, any push to the `main` branch will trigger the **CD** workflow, which will:
1. Run the CI test suite (insisting on 95% test coverage).
2. Build and push the agent Docker image to your Artifact Registry.
3. Run `tofu apply` to update/deploy the Cloud Run service.

