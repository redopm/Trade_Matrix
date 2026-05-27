"""
Structured logging using Loguru.
Provides a consistent logger with correlation IDs and file rotation.
"""
import sys
from pathlib import Path
from loguru import logger

from app.config import settings, BASE_DIR

# ── Remove default handler ────────────────────────────────────────────────────
logger.remove()

# ── Console handler (colored, development-friendly) ───────────────────────────
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# ── File handler (JSON-style, production-ready) ───────────────────────────────
log_dir = BASE_DIR / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logger.add(
    str(log_dir / "tradematrix.log"),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    enqueue=True,  # Thread-safe
)

# ── Screener-specific log ─────────────────────────────────────────────────────
logger.add(
    str(log_dir / "screener.log"),
    level="INFO",
    filter=lambda record: "screener" in record["name"].lower(),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    rotation="5 MB",
    retention="60 days",
)


def get_logger(name: str):
    """Get a named logger instance."""
    return logger.bind(name=name)
