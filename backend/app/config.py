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
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # ── Phase 2: Pattern Recognition ──────────────────────────────────────────
    # Gemini Vision API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"       # Fast + vision capable
    GEMINI_RATE_LIMIT: int = 14                   # Requests per minute (free tier: 15)

    # Chart Generation
    CHART_WINDOW_DAYS: int = 60                   # Days per chart window
    CHART_SLIDE_STEP: int = 10                    # Sliding window step
    CHART_WIDTH_PX: int = 800
    CHART_HEIGHT_PX: int = 600
    CHART_DPI: int = 100
    CHARTS_DIR: str = str(BASE_DIR / "data" / "charts")
    LABELS_FILE: str = str(BASE_DIR / "data" / "labels.jsonl")

    # Model
    MODEL_DIR: str = str(BASE_DIR / "models")
    MODEL_PATH: str = str(BASE_DIR / "models" / "pattern_classifier.pkl")
    MODEL_METADATA_PATH: str = str(BASE_DIR / "models" / "model_metadata.json")
    MIN_PATTERN_CONFIDENCE: float = 0.75          # Min confidence to report pattern
    CONFLUENCE_CONFIDENCE: float = 0.80           # Min for confluence signal

    # Training Universe
    PATTERN_UNIVERSE: str = "NIFTY200"            # NIFTY50 | NIFTY200 | NIFTY500
    TRAINING_PERIOD: str = "3y"                   # 3 years historical data

    # Patterns to detect (8 total)
    BULLISH_PATTERNS: list[str] = [
        "double_bottom", "hs_bottom", "bull_flag",
        "cup_handle", "ascending_triangle"
    ]
    BEARISH_PATTERNS: list[str] = [
        "double_top", "bear_flag", "descending_triangle"
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
