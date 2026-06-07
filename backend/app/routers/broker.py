from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any

from app.services.fyers_data_client import FyersDataClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/broker", tags=["broker"])

class AuthCodePayload(BaseModel):
    auth_code: str

# Singleton instance of client for the routes
fyers_client = FyersDataClient()

@router.get("/status", response_model=Dict[str, Any])
async def get_broker_status():
    """Check if Fyers is connected with a valid token."""
    is_connected = fyers_client.connect()
    
    if is_connected:
        profile = fyers_client.fyers.get_profile()
        name = profile.get("data", {}).get("name", "Unknown")
        return {"status": "connected", "broker": "fyers", "name": name}
    
    return {"status": "disconnected", "broker": "fyers"}

@router.get("/auth-url", response_model=Dict[str, str])
async def get_auth_url():
    """Get the Fyers login URL."""
    try:
        url = fyers_client.get_auth_url()
        return {"auth_url": url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth", response_model=Dict[str, str])
async def set_auth_code(payload: AuthCodePayload):
    """Submit the auth code from the frontend to generate the token."""
    success = fyers_client.set_auth_code(payload.auth_code)
    
    if success:
        return {"status": "success", "message": "Fyers authenticated successfully"}
    else:
        raise HTTPException(status_code=400, detail="Invalid auth code or token generation failed")
