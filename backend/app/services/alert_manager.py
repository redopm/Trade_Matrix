import aiohttp
import urllib.parse
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class AlertManager:
    def __init__(self):
        self.enabled = settings.LIVE_ALERTS_ENABLED
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_signal_alert(self, signal: dict, chart_path: str = None) -> bool:
        """
        Sends a Telegram alert for a high-conviction signal.
        """
        if not self.enabled or not self.bot_token or not self.chat_id:
            logger.debug("Telegram alerts are disabled or missing config.")
            return False

        # Format message
        symbol = signal.get("symbol", "").replace(".NS", "")
        pattern = signal.get("pattern_name", "no_pattern")
        conf = signal.get("pattern_confidence", 0) * 100
        
        # Determine tags
        tags = "🚀 HIGHEST CONVICTION" if conf >= 80 and pattern != "no_pattern" else "💡 ALPHA SIGNAL"
        
        message = (
            f"{tags}\n\n"
            f"📈 **{symbol}**\n"
            f"• Price: ₹{signal.get('signal_price')}\n"
            f"• Pattern: {pattern.replace('_', ' ').title()} ({conf:.0f}%)\n"
            f"• ROCE: {signal.get('roce', 0):.1f}%\n"
            f"• RSI(14): {signal.get('rsi_14', 0):.1f}\n"
            f"• Target: ₹{signal.get('suggested_target', 0)}\n"
            f"• Stop Loss: ₹{signal.get('suggested_sl', 0)}\n\n"
            f"Composite Score: {signal.get('composite_score', 0):.1f}/100"
        )

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto" if chart_path else f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                if chart_path:
                    # Send with photo
                    data = aiohttp.FormData()
                    data.add_field("chat_id", self.chat_id)
                    data.add_field("caption", message)
                    data.add_field("parse_mode", "Markdown")
                    data.add_field("photo", open(chart_path, "rb"))
                    
                    async with session.post(url, data=data) as response:
                        result = await response.json()
                        if not result.get("ok"):
                            logger.error(f"Telegram error: {result}")
                            return False
                else:
                    # Send text only
                    payload = {
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                    async with session.post(url, json=payload) as response:
                        result = await response.json()
                        if not result.get("ok"):
                            logger.error(f"Telegram error: {result}")
                            return False
                            
            logger.info(f"Telegram alert sent for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    async def send_test_alert(self, bot_token: str, chat_id: str) -> bool:
        """Test the connection."""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "✅ TradeMatrix Telegram Alerts Configured Successfully!",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    return result.get("ok", False)
        except Exception:
            return False
