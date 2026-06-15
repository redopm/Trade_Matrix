import os
import subprocess
from google.cloud import aiplatform

PROJECT_ID = "project-8cbf09d7-9540-44ff-a5f"
REGION = "asia-south1"
REPO_NAME = "tradematrix-repo"
IMAGE_NAME = "kronos-model"
IMAGE_URI = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/{REPO_NAME}/{IMAGE_NAME}:latest"

def run_cmd(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

print("1. Enabling required Google Cloud APIs...")
try:
    run_cmd(f"gcloud services enable artifactregistry.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com --project={PROJECT_ID}")
except subprocess.CalledProcessError:
    print("Warning: Failed to enable APIs. They might already be enabled or you lack permissions. Continuing...")

print("2. Creating Artifact Registry repository...")
try:
    run_cmd(f"gcloud artifacts repositories create {REPO_NAME} --repository-format=docker --location={REGION} --description=\"TradeMatrix Docker repository\" --project={PROJECT_ID}")
except subprocess.CalledProcessError:
    print("Repository might already exist. Continuing...")

print("3. Building and Pushing Docker image via Cloud Build...")
run_cmd(f"gcloud builds submit backend/ml/kronos_vertex --tag {IMAGE_URI} --project={PROJECT_ID}")

print("4. Initializing Vertex AI...")
aiplatform.init(project=PROJECT_ID, location=REGION)

print("5. Uploading Model to Registry...")
model = aiplatform.Model.upload(
    display_name="kronos_model",
    serving_container_image_uri=IMAGE_URI,
    serving_container_predict_route="/predict",
    serving_container_health_route="/health",
    serving_container_ports=[8080]
)
print(f"Model uploaded: {model.resource_name}")

print("6. Creating Endpoint...")
endpoint = aiplatform.Endpoint.create(display_name="kronos_endpoint")
print(f"Endpoint created: {endpoint.resource_name}")

print("7. Deploying Model to Endpoint (with T4 GPU and scale-to-zero)...")
model.deploy(
    endpoint=endpoint,
    machine_type="n1-standard-4",
    accelerator_type="NVIDIA_TESLA_T4",
    accelerator_count=1,
    min_replica_count=0,
    max_replica_count=1,
    sync=True
)
print("Deployment Complete!")
