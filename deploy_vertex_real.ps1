$PROJECT_ID = "project-5a108f4e-6049-4655-9e2"
$REGION = "asia-south1"
$REPO_NAME = "tradematrix-repo"
$IMAGE_NAME = "kronos-model"
$IMAGE_URI = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/${IMAGE_NAME}:latest"

Write-Host "0. Setting active project to $PROJECT_ID..."
gcloud.cmd config set project $PROJECT_ID

Write-Host "1. Enabling required APIs..."
gcloud.cmd services enable artifactregistry.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com --project=$PROJECT_ID

Write-Host "2. Creating Artifact Registry repository..."
gcloud.cmd artifacts repositories create $REPO_NAME --repository-format=docker --location=$REGION --description="TradeMatrix Docker repository" --project=$PROJECT_ID

Write-Host "3. Building and Pushing Docker image via Cloud Build..."
gcloud.cmd builds submit backend/ml/kronos_vertex --tag $IMAGE_URI --project=$PROJECT_ID

Write-Host "4. Uploading Model to Vertex AI..."
gcloud.cmd ai models upload --region=$REGION --display-name=kronos_model --container-image-uri=$IMAGE_URI --container-predict-route=/predict --container-health-route=/health --container-ports=8080 --project=$PROJECT_ID

Write-Host "5. Creating Endpoint..."
gcloud.cmd ai endpoints create --region=$REGION --display-name=kronos_endpoint --project=$PROJECT_ID

Write-Host "6. Deploying Model to Endpoint (this takes 10-15 minutes)..."
$MODEL_ID = (gcloud.cmd ai models list --region=$REGION --project=$PROJECT_ID --filter="displayName=kronos_model" --format="value(name)" --limit=1)
$ENDPOINT_ID = (gcloud.cmd ai endpoints list --region=$REGION --project=$PROJECT_ID --filter="displayName=kronos_endpoint" --format="value(name)" --limit=1)

Write-Host "Deploying Model ID: $MODEL_ID to Endpoint ID: $ENDPOINT_ID with T4 GPU..."
gcloud.cmd ai endpoints deploy-model $ENDPOINT_ID --region=$REGION --project=$PROJECT_ID --model=$MODEL_ID --display-name=kronos_deployed --machine-type=n1-standard-4 --accelerator=type=nvidia-tesla-t4,count=1 --min-replica-count=0 --max-replica-count=1

Write-Host "Deployment Complete!"
