"""
TradeMatrix FastAPI Application
Main entrypoint with:
  - CORS middleware
  - Database initialization on startup
  - APScheduler registration
  - Health check endpoint
  - API documentation
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import screener, trades, stocks, dashboard
from app.services.scheduler import create_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION} starting up")
    logger.info(f"  Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Start background scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    yield  # Application is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("TradeMatrix shutting down...")
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="TradeMatrix API",
    description="""
## TradeMatrix: Personal Algo-Trading Control Center

Phase 1 — The Alpha Screener API

### Features
- **Alpha Screener**: Screen Nifty 500 stocks using fundamental + technical filters
- **Paper Trading**: Track simulated trades with ATR-based risk management
- **Real-time Progress**: WebSocket-based screener progress updates
- **Sector Intelligence**: Banking/NBFC specific rules, sector heatmaps

### Strategy Rules
**Fundamental:**
- ROCE > 15% (Return on Capital Employed)
- D/E < 1.0 (Debt to Equity ratio)
- Piotroski F-Score ≥ 7 (Financial strength score)

**Technical:**  
- Price > 200 EMA (Macro trend must be UP)
- RSI(14) < 30 (Short-term oversold dip)

**Risk Management:**
- SL: max(5%, 2×ATR) below entry
- Target: RSI > 70 OR 12% fixed profit
- Event Risk: Block ±3 days around earnings
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Log request timing for performance monitoring."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{duration:.2f}ms"
    if duration > 2000:
        logger.warning(f"Slow request: {request.method} {request.url.path} → {duration:.0f}ms")
    return response


# ── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "path": str(request.url.path),
        },
    )


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
async def root():
    """API root — redirect to docs."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ── Include Routers ───────────────────────────────────────────────────────────

API_PREFIX = settings.API_V1_PREFIX

app.include_router(screener.router, prefix=API_PREFIX)
app.include_router(trades.router, prefix=API_PREFIX)
app.include_router(stocks.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)

logger.info(f"API routes registered at prefix: {API_PREFIX}")
