from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from app.config import settings, BASE_DIR

router = APIRouter(prefix="/settings", tags=["Settings"])

class TelegramConfig(BaseModel):
    enabled: bool
    bot_token: str
    chat_id: str

@router.get("/telegram")
async def get_telegram_settings():
    return {
        "enabled": settings.LIVE_ALERTS_ENABLED,
        "bot_token": settings.TELEGRAM_BOT_TOKEN,
        "chat_id": settings.TELEGRAM_CHAT_ID,
    }

@router.post("/telegram")
async def update_telegram_settings(config: TelegramConfig):
    # Update in memory
    settings.LIVE_ALERTS_ENABLED = config.enabled
    settings.TELEGRAM_BOT_TOKEN = config.bot_token
    settings.TELEGRAM_CHAT_ID = config.chat_id

    # Update .env file
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        content = env_path.read_text()
        
        # Replace or append
        new_lines = []
        for line in content.splitlines():
            if line.startswith("LIVE_ALERTS_ENABLED="):
                new_lines.append(f"LIVE_ALERTS_ENABLED={str(config.enabled).lower()}")
            elif line.startswith("TELEGRAM_BOT_TOKEN="):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={config.bot_token}")
            elif line.startswith("TELEGRAM_CHAT_ID="):
                new_lines.append(f"TELEGRAM_CHAT_ID={config.chat_id}")
            else:
                new_lines.append(line)
                
        # If not present, append
        if not any(line.startswith("LIVE_ALERTS_ENABLED=") for line in new_lines):
            new_lines.append(f"LIVE_ALERTS_ENABLED={str(config.enabled).lower()}")
        if not any(line.startswith("TELEGRAM_BOT_TOKEN=") for line in new_lines):
            new_lines.append(f"TELEGRAM_BOT_TOKEN={config.bot_token}")
        if not any(line.startswith("TELEGRAM_CHAT_ID=") for line in new_lines):
            new_lines.append(f"TELEGRAM_CHAT_ID={config.chat_id}")

        env_path.write_text("\n".join(new_lines) + "\n")

    return {"status": "success", "message": "Settings saved successfully."}

@router.post("/telegram/test")
async def test_telegram_alert(config: TelegramConfig):
    from app.services.alert_manager import AlertManager
    mgr = AlertManager()
    success = await mgr.send_test_alert(config.bot_token, config.chat_id)
    if success:
        return {"status": "success", "message": "Test alert sent successfully!"}
    else:
        raise HTTPException(status_code=400, detail="Failed to send test alert. Check token and chat ID.")
