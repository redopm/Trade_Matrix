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

class ScreenerConfig(BaseModel):
    min_roce: float
    max_debt_to_equity: float
    rsi_oversold: float
    target_profit_pct: float
    atr_sl_multiplier: float
    short_max_roce: float
    short_min_debt_to_equity: float
    rsi_overbought: float
    short_target_pct: float
    default_capital: float

@router.get("/screener")
async def get_screener_settings():
    return {
        "min_roce": settings.MIN_ROCE,
        "max_debt_to_equity": settings.MAX_DEBT_TO_EQUITY,
        "rsi_oversold": settings.RSI_OVERSOLD,
        "target_profit_pct": settings.TARGET_PROFIT_PCT,
        "atr_sl_multiplier": settings.ATR_SL_MULTIPLIER,
        "short_max_roce": settings.SHORT_MAX_ROCE,
        "short_min_debt_to_equity": settings.SHORT_MIN_DEBT_TO_EQUITY,
        "rsi_overbought": settings.RSI_OVERBOUGHT,
        "short_target_pct": settings.SHORT_TARGET_PCT,
        "default_capital": settings.DEFAULT_CAPITAL,
    }

@router.post("/screener")
async def update_screener_settings(config: ScreenerConfig):
    # Update in memory
    settings.MIN_ROCE = config.min_roce
    settings.MAX_DEBT_TO_EQUITY = config.max_debt_to_equity
    settings.RSI_OVERSOLD = config.rsi_oversold
    settings.TARGET_PROFIT_PCT = config.target_profit_pct
    settings.ATR_SL_MULTIPLIER = config.atr_sl_multiplier
    settings.SHORT_MAX_ROCE = config.short_max_roce
    settings.SHORT_MIN_DEBT_TO_EQUITY = config.short_min_debt_to_equity
    settings.RSI_OVERBOUGHT = config.rsi_overbought
    settings.SHORT_TARGET_PCT = config.short_target_pct
    settings.DEFAULT_CAPITAL = config.default_capital

    # Update .env file
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        content = env_path.read_text()
        
        # Keys to update mapping
        updates = {
            "MIN_ROCE": config.min_roce,
            "MAX_DEBT_TO_EQUITY": config.max_debt_to_equity,
            "RSI_OVERSOLD": config.rsi_oversold,
            "TARGET_PROFIT_PCT": config.target_profit_pct,
            "ATR_SL_MULTIPLIER": config.atr_sl_multiplier,
            "SHORT_MAX_ROCE": config.short_max_roce,
            "SHORT_MIN_DEBT_TO_EQUITY": config.short_min_debt_to_equity,
            "RSI_OVERBOUGHT": config.rsi_overbought,
            "SHORT_TARGET_PCT": config.short_target_pct,
            "DEFAULT_CAPITAL": config.default_capital,
        }

        new_lines = []
        found_keys = set()
        
        for line in content.splitlines():
            updated = False
            for key, val in updates.items():
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={val}")
                    found_keys.add(key)
                    updated = True
                    break
            if not updated:
                new_lines.append(line)
                
        # Append missing keys
        for key, val in updates.items():
            if key not in found_keys:
                new_lines.append(f"{key}={val}")

        env_path.write_text("\n".join(new_lines) + "\n")

    return {"status": "success", "message": "Screener rules saved successfully."}
