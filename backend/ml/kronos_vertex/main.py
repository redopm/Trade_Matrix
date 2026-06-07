import os
import sys
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)

# Append current directory to path to find the model package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from model.kronos import Kronos, KronosTokenizer, KronosPredictor

app = FastAPI()

# Global predictor instance
predictor = None

@app.on_event("startup")
async def load_model():
    global predictor
    try:
        logging.info("Downloading/Loading Kronos Tokenizer...")
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        
        logging.info("Downloading/Loading Kronos Model...")
        model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        
        logging.info("Initializing Predictor...")
        predictor = KronosPredictor(model, tokenizer, max_context=512)
        logging.info(f"Model loaded successfully on device: {predictor.device}")
    except Exception as e:
        logging.error(f"Error loading model: {str(e)}")

@app.get("/health")
async def health():
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {"status": "healthy"}

@app.post("/predict")
async def predict(request: Request):
    """
    Vertex AI Predict endpoint.
    Expects JSON:
    {
      "instances": [
         {
            "historical_data": [ {"open":..., "high":..., "low":..., "close":..., "volume":..., "amount":..., "timestamps": "..."} ],
            "pred_len": 120,
            "future_timestamps": ["...", "..."]
         }
      ]
    }
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not ready")
        
    try:
        body = await request.json()
        instances = body.get("instances", [])
        
        if not instances:
            return {"predictions": []}
        
        predictions = []
        for instance in instances:
            hist_data = instance.get("historical_data", [])
            pred_len = instance.get("pred_len", 5)
            future_timestamps = instance.get("future_timestamps", [])
            
            df = pd.DataFrame(hist_data)
            df['timestamps'] = pd.to_datetime(df['timestamps'])
            
            x_df = df[['open', 'high', 'low', 'close', 'volume', 'amount']]
            x_timestamp = df['timestamps']
            y_timestamp = pd.to_datetime(future_timestamps)
            
            pred_df = predictor.predict(
                df=x_df,
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=pred_len,
                T=1.0,
                top_p=0.9,
                sample_count=1,
                verbose=False
            )
            
            # Convert prediction df back to list of dicts
            pred_records = pred_df.reset_index().rename(columns={"index": "timestamps"}).to_dict(orient="records")
            # Convert timestamps to strings for JSON
            for r in pred_records:
                if 'timestamps' in r:
                    r['timestamps'] = str(r['timestamps'])
                    
            predictions.append(pred_records)
            
        return {"predictions": predictions}
    except Exception as e:
        logging.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AIP_HTTP_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
