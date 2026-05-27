"""
TradeMatrix Configuration Module
Manages all application settings via Pydantic Settings (type-safe env variables).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "TradeMatrix"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/database/tradematrix.db"
    DATABASE_ECHO: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]

    # Screener Settings
    SCREENER_UNIVERSE: str = "NIFTY500"          # Stock universe to screen
    MAX_CONCURRENT_FETCHES: int = 10             # Rate limiting for yfinance
    FETCH_DELAY_SECONDS: float = 0.3             # Delay between API calls
    DATA_PERIOD: str = "2y"                      # Historical data period
    DATA_INTERVAL: str = "1d"                    # Candle interval

    # Paper Trading Defaults
    DEFAULT_CAPITAL: float = 100_000.0           # ₹1 Lakh default capital
    DEFAULT_POSITION_SIZE_PCT: float = 0.10      # 10% per trade
    FIXED_SL_PCT: float = 0.05                   # 5% hard stop loss
    ATR_SL_MULTIPLIER: float = 2.0               # 2×ATR for dynamic SL
    TARGET_RSI_OVERBOUGHT: float = 70.0          # RSI exit threshold
    TARGET_PROFIT_PCT: float = 0.12              # 12% fixed target
    EARNINGS_BLACKOUT_DAYS: int = 3              # ±3 days event risk block

    # Fundamental Thresholds
    MIN_ROCE: float = 15.0                       # Minimum ROCE %
    MAX_DEBT_TO_EQUITY: float = 1.0              # Max D/E ratio
    MIN_PIOTROSKI_SCORE: int = 7                 # Min F-Score (0–9)
    MIN_PROMOTER_HOLDING: float = 50.0           # Min promoter holding %
    MIN_EPS_GROWTH: float = 15.0                 # Min YoY EPS growth %

    # Technical Thresholds
    RSI_OVERSOLD: float = 30.0                   # RSI oversold threshold
    RSI_PERIOD: int = 14                         # RSI period
    EMA_LONG_PERIOD: int = 200                   # Long-term EMA
    EMA_SHORT_PERIOD: int = 50                   # Short-term EMA
    ATR_PERIOD: int = 14                         # ATR period
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # Scheduler (IST timezone = UTC+5:30)
    SCREENER_CRON_HOUR: int = 15                 # 3 PM IST → 9:30 AM UTC
    SCREENER_CRON_MINUTE: int = 45
    PNL_UPDATE_HOUR: int = 9                     # 9 AM IST → 3:30 AM UTC
    PNL_UPDATE_MINUTE: int = 20

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(BASE_DIR / "logs" / "tradematrix.log")


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton - instantiated once per process."""
    return Settings()


settings = get_settings()
