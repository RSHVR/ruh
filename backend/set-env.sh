#!/bin/bash

# Script to set environment variables for Cloud Run service
# Run this AFTER deploy.sh to configure API keys and database

set -e

PROJECT_ID="ruh-backend"
SERVICE_NAME="ruh-api"
REGION="us-central1"

# Your environment variables
ANTHROPIC_API_KEY="***REMOVED***"
SUPABASE_URL="https://vslnwiugfuvquiaafxgh.supabase.co"
SUPABASE_KEY="your-supabase-anon-key"
DATABASE_URL="postgresql://postgres:password@localhost:5432/eject"

echo "🔐 Setting environment variables for ${SERVICE_NAME}..."

gcloud run services update ${SERVICE_NAME} \
  --region ${REGION} \
  --update-env-vars "\
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY},\
SUPABASE_URL=${SUPABASE_URL},\
SUPABASE_KEY=${SUPABASE_KEY},\
DATABASE_URL=${DATABASE_URL},\
REDIS_URL=redis://localhost:6379/0,\
CELERY_BROKER_URL=redis://localhost:6379/0,\
CELERY_RESULT_BACKEND=redis://localhost:6379/0,\
API_HOST=0.0.0.0,\
API_PORT=8080,\
DEBUG=false,\
ALLOWED_ORIGINS=*,\
LOG_LEVEL=INFO"

echo "✅ Environment variables set!"
echo ""
echo "Test the API:"
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "curl ${SERVICE_URL}/api/health"
