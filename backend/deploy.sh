#!/bin/bash

# Simple deployment script for Cloud Run
set -e

PROJECT_ID="ruh-backend"
SERVICE_NAME="ruh-api"
REGION="us-central1"

echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run..."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo ""

# Set the project
gcloud config set project ${PROJECT_ID}

# Build and deploy in one command
echo "🏗️  Building and deploying..."
gcloud run deploy ${SERVICE_NAME} \
  --source . \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --set-env-vars "ANTHROPIC_API_KEY=***REMOVED***" \
  --set-env-vars "API_HOST=0.0.0.0" \
  --set-env-vars "API_PORT=8080" \
  --set-env-vars "DEBUG=false" \
  --set-env-vars "ALLOWED_ORIGINS=*" \
  --set-env-vars "LOG_LEVEL=INFO"

echo ""
echo "✅ Deployment complete!"
echo ""
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "🌐 Service URL: ${SERVICE_URL}"
echo "🏥 Health check: curl ${SERVICE_URL}/api/health"
