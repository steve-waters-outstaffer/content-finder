#!/bin/bash

# Deployment script for the Content Finder backend on Cloud Run
# This script is designed to be run from within the backend directory.
set -e

# --- Configuration ---
PROJECT_ID="content-finder-4bf70"
SERVICE_NAME="content-finder-backend"
REGION="australia-southeast1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"
ACCOUNT_EMAIL="steve.waters@outstaffer.com"

echo "🚀 Starting self-contained deployment for Content Finder backend..."

# --- Load Secrets ---
# Load environment variables from the .env file in the current directory
if [ -f ".env" ]; then
    export $(cat .env | grep -v '#' | xargs)
    echo "📋 Loaded environment variables from .env"
else
    echo "❌ .env file not found! Please ensure it exists in the backend directory."
    exit 1
fi

# --- Authentication and Project Setup ---
echo "🔐 Setting Google account to $ACCOUNT_EMAIL..."
gcloud config set account $ACCOUNT_EMAIL
gcloud config set project $PROJECT_ID

# --- Build & Push Docker Image ---
echo "🔨 Building Docker image from the current directory..."
# This builds the image using the Dockerfile in the current directory
docker build -t $IMAGE_NAME .

echo "📤 Pushing image to Google Container Registry..."
gcloud auth configure-docker
docker push $IMAGE_NAME

# --- Deploy to Cloud Run ---
echo "☁️ Deploying to Cloud Run..."
# This command deploys the image you just pushed.
# The --set-env-vars flag reads the variables we exported from the .env file
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}" \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --set-env-vars "TAVILY_API_KEY=${TAVILY_API_KEY}"

# --- Finalize ---
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo "✅ Deployment complete!"
echo "🌐 Service URL: ${SERVICE_URL}"