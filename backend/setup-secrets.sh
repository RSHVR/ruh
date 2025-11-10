#!/bin/bash

# Setup script for Google Secret Manager
# Run this ONCE to store your secrets securely

set -e

PROJECT_ID="ruh-backend"
ANTHROPIC_SECRET_NAME="anthropic-api-key"
API_KEY_SECRET_NAME="ruh-api-key"

echo "🔐 Setting up Google Secret Manager..."

# Enable Secret Manager API
echo "📋 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=${PROJECT_ID}

# Get project number
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")

# Create Anthropic API key secret
echo ""
echo "📝 Step 1: Anthropic API Key"
echo "Please paste your Anthropic API Key:"
read -s ANTHROPIC_KEY

echo ""
echo "Creating secret '${ANTHROPIC_SECRET_NAME}'..."
echo -n "${ANTHROPIC_KEY}" | gcloud secrets create ${ANTHROPIC_SECRET_NAME} \
  --data-file=- \
  --project=${PROJECT_ID}

echo "✅ Anthropic API key stored!"

# Generate custom API key for the ruh-api
echo ""
echo "📝 Step 2: Custom API Key"
echo "Generating a secure API key for your Chrome extension..."
CUSTOM_API_KEY="ruh_$(openssl rand -hex 32)"

echo "Creating secret '${API_KEY_SECRET_NAME}'..."
echo -n "${CUSTOM_API_KEY}" | gcloud secrets create ${API_KEY_SECRET_NAME} \
  --data-file=- \
  --project=${PROJECT_ID}

echo "✅ Custom API key generated and stored!"
echo ""
echo "🔑 Your Chrome Extension API Key (save this!):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "${CUSTOM_API_KEY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  IMPORTANT: Save this key! You'll need it in your Chrome extension."
echo ""

# Grant Cloud Run service account access to both secrets
echo "🔑 Granting access to Cloud Run..."
for SECRET in ${ANTHROPIC_SECRET_NAME} ${API_KEY_SECRET_NAME}; do
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${PROJECT_ID}

  # Grant Cloud Build service account access
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${PROJECT_ID}
done

echo ""
echo "✅ Secret Manager setup complete!"
echo ""
echo "Secrets created:"
echo "  - ${ANTHROPIC_SECRET_NAME} (Anthropic API key)"
echo "  - ${API_KEY_SECRET_NAME} (Custom API key for your extension)"
echo "Project: ${PROJECT_ID}"
echo ""
echo "You can now deploy using ./deploy.sh"
