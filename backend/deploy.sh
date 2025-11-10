#!/bin/bash

# Deployment script for ruh backend to Google Cloud Run
# Run this from Google Cloud Shell

set -e

PROJECT_ID="ruh-backend"
SERVICE_NAME="ruh-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "🚀 Deploying ruh backend to Cloud Run..."
echo "Project: ${PROJECT_ID}"
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo ""

# Set the project
echo "📋 Setting project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs (if not already enabled)
echo "🔌 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Build and push the Docker image using Cloud Build
echo "🏗️  Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}

# Deploy to Cloud Run
echo "🚢 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
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
  --set-env-vars "DATABASE_URL=postgresql://placeholder:placeholder@localhost:5432/eject" \
  --set-env-vars "SUPABASE_URL=https://vslnwiugfuvquiaafxgh.supabase.co" \
  --set-env-vars "SUPABASE_KEY=" \
  --set-env-vars "REDIS_URL=redis://localhost:6379/0" \
  --set-env-vars "CELERY_BROKER_URL=redis://localhost:6379/0" \
  --set-env-vars "CELERY_RESULT_BACKEND=redis://localhost:6379/0" \
  --set-env-vars "API_HOST=0.0.0.0" \
  --set-env-vars "API_PORT=8080" \
  --set-env-vars "DEBUG=false" \
  --set-env-vars "ALLOWED_ORIGINS=*" \
  --set-env-vars "LOG_LEVEL=INFO"

# Get the service URL
echo ""
echo "✅ Deployment complete!"
echo ""
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "🌐 Service URL: ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "1. Set environment variables (ANTHROPIC_API_KEY, DATABASE_URL, etc.)"
echo "2. Test the health endpoint: curl ${SERVICE_URL}/api/health"
echo "3. Update extension to use: ${SERVICE_URL}"
