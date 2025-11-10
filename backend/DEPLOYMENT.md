# Deployment Guide

## Automatic Deployment from Repository

This backend is configured for automatic deployment to Google Cloud Run using Cloud Build.

### Setup (One-time)

1. **Connect your repository to Cloud Build:**
   - Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers) in GCP Console
   - Click "Connect Repository"
   - Select your repository source (GitHub, GitLab, etc.)
   - Authenticate and select the `RSHVR/Eject` repository

2. **Create a Build Trigger:**
   - Name: `ruh-api-deploy`
   - Event: Push to a branch
   - Source: `^main$` (or your branch pattern)
   - Configuration: Cloud Build configuration file
   - Location: `backend/cloudbuild.yaml`

3. **Set required permissions:**
   ```bash
   PROJECT_ID="ruh-backend"
   PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud iam service-accounts add-iam-policy-binding \
     ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

### How It Works

When you push code to the connected branch:

1. Cloud Build triggers automatically
2. Builds Docker image from `backend/Dockerfile`
3. Pushes image to Container Registry
4. Deploys to Cloud Run using `backend/service.yaml` configuration
5. Service is available at: `https://ruh-api-<hash>-uc.a.run.app`

### Configuration Files

- **`cloudbuild.yaml`**: Defines build and deployment steps
- **`service.yaml`**: Cloud Run service configuration (env vars, resources, scaling)
- **`Dockerfile`**: Container image specification
- **`.gcloudignore`**: Files to exclude from builds

### Updating Environment Variables

Edit `service.yaml` and update the `env` section, then push to trigger a new deployment.

### Manual Deployment (if needed)

```bash
cd backend
gcloud builds submit --config cloudbuild.yaml
```
