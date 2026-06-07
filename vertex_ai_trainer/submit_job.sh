#!/bin/bash
# TradeMatrix Vertex AI Job Submitter
# Usage: ./submit_job.sh

PROJECT_ID="project-8cbf09d7-9540-44ff-a5f"
BUCKET_NAME="tradematrix-ai-bucket-8cbf09d7"
REPO_NAME="tradematrix-repo"
IMAGE_URI="asia-south1-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/cnn-trainer:v1"

echo "========================================="
echo " Submitting Vertex AI Training Job..."
echo " Project: $PROJECT_ID"
echo " Bucket: $BUCKET_NAME"
echo "========================================="

# 1. Ensure Artifact Registry exists
echo "[1/3] Checking Artifact Registry..."
gcloud.cmd artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=asia-south1 \
    --project=$PROJECT_ID || true

# 2. Build and Push the Docker Image via Cloud Build
echo "[2/3] Building Docker image in Cloud Build..."
gcloud.cmd builds submit --tag $IMAGE_URI --project $PROJECT_ID

# 3. Create Custom Training Job in Vertex AI
echo "[3/3] Submitting Custom Training Job..."
gcloud.cmd ai custom-jobs create \
  --region=asia-south1 \
  --project=$PROJECT_ID \
  --display-name=tradematrix-cnn-training-job \
  --worker-pool-spec=machine-type=n1-standard-4,replica-count=1,accelerator-type=NVIDIA_TESLA_T4,accelerator-count=1,container-image-uri=$IMAGE_URI \
  --args="--bucket=$BUCKET_NAME"

echo "Job submitted successfully! Check GCP Console for progress."
