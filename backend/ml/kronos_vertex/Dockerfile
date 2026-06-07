FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies (CUDA versions if run on GPU instance in Vertex AI)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121

COPY . .

# Run the FastAPI server on Vertex AI port
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${AIP_HTTP_PORT:-8080}"]
