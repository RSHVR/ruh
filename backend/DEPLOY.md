# Deployment Guide

## 🔐 Prerequisites: Setup Secret Manager (Required - One-time)

**IMPORTANT**: Before deploying, you must store your Anthropic API key securely in Google Secret Manager.

Run the setup script from the backend directory:
```bash
cd ~/Eject/backend
chmod +x setup-secrets.sh
./setup-secrets.sh
```

This script will:
1. Enable Secret Manager API
2. Prompt you to enter your Anthropic API key (securely)
3. Store it in Secret Manager
4. Grant necessary permissions to Cloud Run and Cloud Build

**You only need to do this once.** After this, your API key is never hardcoded in code or config files.

---

## Option 1: Manual Deployment (Immediate)

Run the deployment script from the backend directory:
```bash
cd ~/Eject/backend
./deploy.sh
```

## Option 2: Continuous Deployment (Automatic on Push)

### Setup Cloud Build Trigger (One-time setup)

1. **Enable Cloud Build API** (if not already enabled):
   ```bash
   gcloud services enable cloudbuild.googleapis.com --project=ruh-backend
   ```

2. **Grant Cloud Build permissions to deploy to Cloud Run**:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe ruh-backend --format="value(projectNumber)")

   # Grant Cloud Run Admin role
   gcloud projects add-iam-policy-binding ruh-backend \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/run.admin"

   # Grant Service Account User role
   gcloud iam service-accounts add-iam-policy-binding \
     ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

3. **Connect your GitHub repository**:
   - Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=ruh-backend)
   - Click **"CREATE TRIGGER"**
   - Name: `deploy-ruh-api`
   - Event: **Push to a branch**
   - Source: Click **"CONNECT NEW REPOSITORY"**
     - Select **GitHub (Cloud Build GitHub App)**
     - Authenticate with GitHub
     - Select repository: `RSHVR/Eject`
   - Branch: `^main$` or `^master$` (or your preferred branch pattern)
   - Configuration: **Cloud Build configuration file**
   - Location: `backend/cloudbuild.yaml`
   - Click **"CREATE"**

4. **Test the trigger**:
   - Make any commit and push to your main branch
   - Go to [Cloud Build History](https://console.cloud.google.com/cloud-build/builds?project=ruh-backend)
   - You should see your build running automatically

### How it works:
- Every push to your configured branch triggers Cloud Build
- Cloud Build runs `cloudbuild.yaml` which deploys to Cloud Run
- New version is automatically deployed within 3-5 minutes

## Service Information

- **Service Name**: ruh-api
- **Region**: us-central1
- **Current URL**: https://ruh-api-nlxvekfjuq-uc.a.run.app
- **Health Check**: https://ruh-api-nlxvekfjuq-uc.a.run.app/api/health

## Updating Environment Variables

**Regular environment variables**: Edit `deploy.sh` or `cloudbuild.yaml` and redeploy.

**API Key**: Update the secret in Secret Manager:
```bash
echo -n "NEW_API_KEY" | gcloud secrets versions add anthropic-api-key \
  --data-file=- \
  --project=ruh-backend
```

Then redeploy - Cloud Run will automatically use the new version.
