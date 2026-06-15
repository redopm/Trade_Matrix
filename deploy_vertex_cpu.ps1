$PROJECT_ID = "project-8cbf09d7-9540-44ff-a5f"
$REGION = "asia-south1"

$MODEL_ID = (gcloud.cmd ai models list --region=$REGION --project=$PROJECT_ID --filter="displayName=kronos_model" --format="value(name)" --limit=1)
$ENDPOINT_ID = (gcloud.cmd ai endpoints list --region=$REGION --project=$PROJECT_ID --filter="displayName=kronos_endpoint" --format="value(name)" --limit=1)

Write-Host "Deploying Model ID: $MODEL_ID to Endpoint ID: $ENDPOINT_ID on CPU..."
gcloud.cmd ai endpoints deploy-model $ENDPOINT_ID --region=$REGION --project=$PROJECT_ID --model=$MODEL_ID --display-name=kronos_deployed_cpu --machine-type=n1-standard-4 --min-replica-count=1 --max-replica-count=1

Write-Host "Deployment Complete!"
