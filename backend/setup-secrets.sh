#!/bin/bash

# Setup script for Google Secret Manager
# Run this ONCE to store your API key securely

set -e

PROJECT_ID="ruh-backend"
SECRET_NAME="anthropic-api-key"

echo "🔐 Setting up Google Secret Manager..."

# Enable Secret Manager API
echo "📋 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=${PROJECT_ID}

# Create the secret (you'll be prompted to paste your API key)
echo ""
echo "Please paste your Anthropic API Key:"
read -s API_KEY

echo ""
echo "Creating secret '${SECRET_NAME}'..."
echo -n "${API_KEY}" | gcloud secrets create ${SECRET_NAME} \
  --data-file=- \
  --project=${PROJECT_ID}

echo ""
echo "✅ Secret created successfully!"
echo ""
echo "🔑 Granting access to Cloud Run..."

# Get project number
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")

# Grant Cloud Run service account access to the secret
gcloud secrets add-iam-policy-binding ${SECRET_NAME} \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT_ID}

# Grant Cloud Build service account access to the secret
gcloud secrets add-iam-policy-binding ${SECRET_NAME} \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=${PROJECT_ID}

echo ""
echo "✅ Secret Manager setup complete!"
echo ""
echo "Secret name: ${SECRET_NAME}"
echo "Project: ${PROJECT_ID}"
echo ""
echo "You can now deploy using ./deploy.sh"
