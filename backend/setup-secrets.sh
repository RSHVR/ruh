#!/bin/bash

# Setup script for Google Secret Manager
# Handles both initial setup and adding missing secrets

set -e

PROJECT_ID="ruh-backend"
ANTHROPIC_SECRET_NAME="anthropic-api-key"
API_KEY_SECRET_NAME="ruh-api-key"
SUPABASE_SECRET_NAME="supabase-api-key"

echo "🔐 Setting up Google Secret Manager..."

# Enable Secret Manager API
echo "📋 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=${PROJECT_ID}

# Get project number
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")

# Check if Anthropic secret exists
echo ""
echo "📝 Step 1: Anthropic API Key"
if gcloud secrets describe ${ANTHROPIC_SECRET_NAME} --project=${PROJECT_ID} &>/dev/null; then
  echo "✅ Secret '${ANTHROPIC_SECRET_NAME}' already exists, skipping..."
else
  echo "Please paste your Anthropic API Key:"
  read -s ANTHROPIC_KEY

  echo ""
  echo "Creating secret '${ANTHROPIC_SECRET_NAME}'..."
  echo -n "${ANTHROPIC_KEY}" | gcloud secrets create ${ANTHROPIC_SECRET_NAME} \
    --data-file=- \
    --project=${PROJECT_ID}

  echo "✅ Anthropic API key stored!"
fi

# Generate custom API key for the ruh-api
echo ""
echo "📝 Step 2: Custom API Key"
if gcloud secrets describe ${API_KEY_SECRET_NAME} --project=${PROJECT_ID} &>/dev/null; then
  echo "✅ Secret '${API_KEY_SECRET_NAME}' already exists!"
  echo ""
  echo "To retrieve your existing API key, run:"
  echo "  gcloud secrets versions access latest --secret=${API_KEY_SECRET_NAME} --project=${PROJECT_ID}"
  echo ""
  echo "To generate a new key (will create a new version):"
  read -p "Generate new API key? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    CUSTOM_API_KEY="ruh_$(openssl rand -hex 32)"
    echo "Creating new version of '${API_KEY_SECRET_NAME}'..."
    echo -n "${CUSTOM_API_KEY}" | gcloud secrets versions add ${API_KEY_SECRET_NAME} \
      --data-file=- \
      --project=${PROJECT_ID}

    echo "✅ New API key generated!"
    echo ""
    echo "🔑 Your NEW Chrome Extension API Key (save this!):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "${CUSTOM_API_KEY}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
  fi
else
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
fi

# Check if Supabase secret exists
echo ""
echo "📝 Step 3: Supabase API Key"
if gcloud secrets describe ${SUPABASE_SECRET_NAME} --project=${PROJECT_ID} &>/dev/null; then
  echo "✅ Secret '${SUPABASE_SECRET_NAME}' already exists, skipping..."
else
  echo "Please paste your Supabase API Key (anon/public key):"
  echo "(Find it at: https://vslnwiugfuvquiaafxgh.supabase.co/project/vslnwiugfuvquiaafxgh/settings/api)"
  read -s SUPABASE_KEY

  echo ""
  echo "Creating secret '${SUPABASE_SECRET_NAME}'..."
  echo -n "${SUPABASE_KEY}" | gcloud secrets create ${SUPABASE_SECRET_NAME} \
    --data-file=- \
    --project=${PROJECT_ID}

  echo "✅ Supabase API key stored!"
fi

# Grant Cloud Run service account access to all secrets
echo "🔑 Granting access to Cloud Run..."
for SECRET in ${ANTHROPIC_SECRET_NAME} ${API_KEY_SECRET_NAME} ${SUPABASE_SECRET_NAME}; do
  # Grant Cloud Run service account access (ignore if already exists)
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${PROJECT_ID} 2>/dev/null || echo "  (Cloud Run access already granted for ${SECRET})"

  # Grant Cloud Build service account access (ignore if already exists)
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${PROJECT_ID} 2>/dev/null || echo "  (Cloud Build access already granted for ${SECRET})"
done

echo ""
echo "✅ Secret Manager setup complete!"
echo ""
echo "Secrets configured:"
echo "  - ${ANTHROPIC_SECRET_NAME} (Anthropic API key)"
echo "  - ${API_KEY_SECRET_NAME} (Custom API key for your extension)"
echo "  - ${SUPABASE_SECRET_NAME} (Supabase API key)"
echo "Project: ${PROJECT_ID}"
echo ""
echo "You can now deploy using ./deploy.sh"
