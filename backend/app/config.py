"""
TradeMatrix Configuration Module
Manages all application settings via Pydantic Settings (type-safe env variables).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "/app/.env", BASE_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "TradeMatrix"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # ── Phase 2: Pattern Recognition ──────────────────────────────────────────
    # Phase 2: Gemini Vision API & Vertex AI
    GEMINI_API_KEY: Optional[str] = None
    GCP_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"       # Fast + vision capable
    GEMINI_RATE_LIMIT: int = 14                   # Requests per minute (free tier: 15)

    # ── Phase 3: Fyers API Integration ─────────────────────────────────────────
    FYERS_CLIENT_ID: Optional[str] = None
    FYERS_APP_ID: Optional[str] = None
    FYERS_SECRET_ID: Optional[str] = None
    FYERS_TOTP_KEY: Optional[str] = None
    FYERS_PIN: Optional[str] = None
    FYERS_REDIRECT_URI: str = "http://127.0.0.1:8000/"

    # Chart Generation
    CHART_WINDOW_DAYS: int = 60                   # Days per chart window
    CHART_SLIDE_STEP: int = 10                    # Sliding window step
    CHART_WIDTH_PX: int = 800
    CHART_HEIGHT_PX: int = 600
    CHART_DPI: int = 100
    CHARTS_DIR: str = str(BASE_DIR / "data" / "charts")
    LABELS_FILE: str = str(BASE_DIR / "data" / "labels.jsonl")

    # Model
    MODEL_DIR: str = str(BASE_DIR / "backend" / "models")
    MODEL_PATH: str = str(BASE_DIR / "backend" / "models" / "expert_model_weights.pth")
    MODEL_METADATA_PATH: str = str(BASE_DIR / "backend" / "models" / "expert_model_meta.json")
    MIN_PATTERN_CONFIDENCE: float = 0.50          # Kaggle model ~68% acc, set lower to capture signals
    CONFLUENCE_CONFIDENCE: float = 0.52           # Phase1+Phase2 combo threshold

    # Training Universe
    PATTERN_UNIVERSE: str = "NIFTY200"            # NIFTY50 | NIFTY200 | NIFTY500
    TRAINING_PERIOD: str = "3y"                   # 3 years historical data

    # Patterns to detect — 28 total (19 Macro + 9 Candlestick)
    BULLISH_PATTERNS: list[str] = [
        "BUY (1)", # Expert Model
        # Macro — Reversal
        "double_bottom", "triple_bottom",
        "head_and_shoulders_bottom",
        "rounded_bottom",
        "cup_and_handle",
        # Macro — Continuation
        "ascending_triangle",
        "falling_wedge",
        "bull_flag", "bull_pennant",
        "bullish_rectangle",
        # Candlestick
        "cdl_hammer", "cdl_bullish_engulfing", "cdl_morning_star", "cdl_marubozu",
    ]
    BEARISH_PATTERNS: list[str] = [
        "SELL (2)", # Expert Model
        # Macro — Reversal
        "double_top", "triple_top",
        "head_and_shoulders_top",
        "rounded_top",
        # Macro — Continuation
        "descending_triangle",
        "rising_wedge",
        "bear_flag", "bear_pennant",
        "bearish_rectangle",
        # Candlestick
        "cdl_shooting_star", "cdl_bearish_engulfing", "cdl_evening_star",
    ]
    NEUTRAL_PATTERNS: list[str] = [
        "symmetrical_triangle", "cdl_doji", "cdl_spinning_top",
    ]

    # Feature Extraction
    PEAK_PROMINENCE_PCT: float = 0.03             # Min peak prominence (3% of range)
    PEAK_DISTANCE_DAYS: int = 5                   # Min days between peaks

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

    # Live Alerts (Phase 3)
    LIVE_ALERTS_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Fundamental Thresholds
    MIN_ROCE: float = 15.0                       # Minimum ROCE %
    MAX_DEBT_TO_EQUITY: float = 1.0              # Max D/E ratio
    MIN_PIOTROSKI_SCORE: int = 7                 # Min F-Score (0–9)
    MIN_PROMOTER_HOLDING: float = 50.0           # Min promoter holding %
    MIN_EPS_GROWTH: float = 15.0                 # Min YoY EPS growth %

    # Technical Thresholds
    RSI_OVERSOLD: float = 30.0                   # RSI oversold threshold
    RSI_OVERBOUGHT: float = 65.0                 # RSI overbought threshold (for SHORTs)
    RSI_PERIOD: int = 14                         # RSI period
    EMA_LONG_PERIOD: int = 200                   # Long-term EMA
    EMA_SHORT_PERIOD: int = 50                   # Short-term EMA
    ATR_PERIOD: int = 14                         # ATR period
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # SHORT Trading specific Thresholds
    SHORT_MIN_DEBT_TO_EQUITY: float = 0.5        # Minimum D/E ratio for a good short candidate
    SHORT_MAX_ROCE: float = 20.0                 # Max ROCE for a short candidate (weak business)
    SHORT_TARGET_PCT: float = 0.12               # 12% target for shorts

    # Scheduler (IST timezone = UTC+5:30)
    SCREENER_CRON_HOUR: int = 15                 # 3 PM IST → 9:30 AM UTC
    SCREENER_CRON_MINUTE: int = 45
    PNL_UPDATE_HOUR: int = 9                     # 9 AM IST → 3:30 AM UTC
    PNL_UPDATE_MINUTE: int = 20

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(BASE_DIR / "logs" / "tradematrix.log")

    @property
    def all_patterns(self) -> list[str]:
        return self.BULLISH_PATTERNS + self.BEARISH_PATTERNS

    @property
    def is_pattern_model_ready(self) -> bool:
        from pathlib import Path
        return Path(self.MODEL_PATH).exists()


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton - instantiated once per process."""
    return Settings()


settings = get_settings()
