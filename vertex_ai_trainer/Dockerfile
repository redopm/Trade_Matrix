FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    timm==0.9.12 \
    mplfinance==0.9.0 \
    yfinance==0.2.37 \
    scikit-learn==1.4.1 \
    pandas==2.2.1 \
    google-cloud-storage==2.15.0 \
    Pillow==10.2.0

# Copy training script
COPY train_cnn.py .

# Entrypoint for Vertex AI
ENTRYPOINT ["python", "train_cnn.py"]
