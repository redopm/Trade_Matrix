import asyncio
import time
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.services.fyers_data_client import FyersDataClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/broker", tags=["broker"])

class AuthCodePayload(BaseModel):
    auth_code: str

# Singleton instance of client for the routes
fyers_client = FyersDataClient()

_cached_broker_status: Optional[Dict[str, Any]] = None
_cached_broker_timestamp: float = 0.0

def _sync_check_fyers() -> Dict[str, Any]:
    try:
        is_connected = fyers_client.connect()
        if is_connected:
            name = fyers_client.user_name or "Connected"
            return {"status": "connected", "broker": "fyers", "name": name}
    except Exception as e:
        logger.warning(f"Error checking Fyers status: {e}")
    return {"status": "disconnected", "broker": "fyers"}

@router.get("/status", response_model=Dict[str, Any])
async def get_broker_status():
    """Check if Fyers is connected with a valid token (cached for 30 seconds to prevent event loop bottlenecks)."""
    global _cached_broker_status, _cached_broker_timestamp
    now = time.time()
    if _cached_broker_status and (now - _cached_broker_timestamp < 30.0):
        return _cached_broker_status

    loop = asyncio.get_running_loop()
    status = await loop.run_in_executor(None, _sync_check_fyers)
    _cached_broker_status = status
    _cached_broker_timestamp = now
    return status

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
    global _cached_broker_status
    _cached_broker_status = None  # Invalidate cache
    success, err_msg = fyers_client.set_auth_code(payload.auth_code)
    
    if success:
        return {"status": "success", "message": "Fyers authenticated successfully"}
    else:
        detail_msg = err_msg if err_msg else "Invalid auth code or token generation failed"
        raise HTTPException(status_code=400, detail=detail_msg)
