"""
Research Router - TradeMatrix Phase 1
Clean API endpoints for the research engine.

Endpoints:
  POST /api/v1/research/run           - Start a research run
  GET  /api/v1/research/run/{id}      - Get run status
  GET  /api/v1/research/signals       - Get all signals from last run
  GET  /api/v1/research/runs          - List all runs
  POST /api/v1/research/analyze/{sym} - Quick single stock analysis
  WS   /api/v1/research/ws/{id}       - Real-time progress
"""
import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.services.research_engine import ResearchEngine, get_research_run, get_all_research_runs
from app.services.data_fetcher import DataFetcher
from app.services.fundamental import FundamentalAnalyzer
from app.services.technical import TechnicalAnalyzer
from app.services.risk_manager import RiskManager
from app.utils.logger import get_logger
from app.utils.helpers import sanitize_nans

logger = get_logger(__name__)
router = APIRouter(prefix="/research", tags=["Research Engine"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class StartResearchRequest(BaseModel):
    mode: str = "SWING"          # SWING | POSITIONAL | INTRADAY
    universe: str = "NIFTY500"  # NIFTY50 | NIFTY200 | NIFTY500
    symbols: Optional[list[str]] = None  # Override with specific symbols


# ── Start Research Run ────────────────────────────────────────────────────────

@router.post("/run")
async def start_research_run(
    req: StartResearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a new research run asynchronously.
    Returns run_id immediately; poll /run/{id} for status.
    """
    if req.mode not in ("SWING", "POSITIONAL", "INTRADAY"):
        raise HTTPException(400, detail="mode must be SWING, POSITIONAL, or INTRADAY")

    run_id = str(uuid.uuid4())
    engine = ResearchEngine()

    async def _run():
        await engine.run(
            run_id=run_id,
            mode=req.mode,
            symbols=req.symbols,
            universe=req.universe,
        )

    background_tasks.add_task(_run)

    return {
        "run_id": run_id,
        "status": "STARTED",
        "message": f"Research run started in {req.mode} mode for {req.universe}. Poll /run/{run_id} for progress.",
    }


# ── Get Run Status ────────────────────────────────────────────────────────────

@router.get("/run/{run_id}")
async def get_run_status(run_id: str):
    """Get status and progress of a research run."""
    run = get_research_run(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run {run_id} not found")
    return sanitize_nans(run.to_dict())


# ── Get Signals from a Run ────────────────────────────────────────────────────

@router.get("/signals/{run_id}")
async def get_run_signals(
    run_id: str,
    min_score: float = 0.0,
    min_rr: float = 0.0,
    sector: Optional[str] = None,
    limit: int = 50,
):
    """Get research signals from a specific run, with filters."""
    run = get_research_run(run_id)
    if not run:
        raise HTTPException(404, detail=f"Run {run_id} not found")

    signals = run.signals

    # Apply filters
    if min_score > 0:
        signals = [s for s in signals if s.get("composite_score", 0) >= min_score]
    if min_rr > 0:
        signals = [s for s in signals if s.get("rr_t2", 0) >= min_rr]
    if sector:
        signals = [s for s in signals if sector.lower() in (s.get("sector") or "").lower()]

    return sanitize_nans({
        "run_id": run_id,
        "status": run.status,
        "total_signals": len(run.signals),
        "filtered_signals": len(signals),
        "signals": signals[:limit],
    })


# ── List All Runs ─────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs():
    """List all research runs."""
    return sanitize_nans({"runs": get_all_research_runs()})


# ── Quick Single Stock Analysis ───────────────────────────────────────────────

@router.post("/analyze/{symbol}")
async def analyze_single_stock(symbol: str, mode: str = "SWING"):
    """
    Quick analysis of a single stock.
    Returns full signal card with entry, SL, targets, reasons.
    Great for: "Bhai RELIANCE mein buy karna chahiye kya abhi?"
    """
    fetcher = DataFetcher()
    fund_analyzer = FundamentalAnalyzer()
    tech_analyzer = TechnicalAnalyzer()
    risk_mgr = RiskManager()

    # Normalize symbol
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = f"{symbol}.NS"

    # Fetch data concurrently
    info_task = fetcher.fetch_ticker_info(symbol)
    hist_task = fetcher.fetch_price_history(symbol, period="2y")
    info, df = await asyncio.gather(info_task, hist_task, return_exceptions=True)

    if isinstance(info, Exception) or not info:
        raise HTTPException(404, detail=f"Could not fetch data for {symbol}. Check if ticker is valid.")
    if isinstance(df, Exception) or df is None or df.empty or len(df) < 200:
        raise HTTPException(400, detail=f"Insufficient historical data for {symbol} (need 200+ days)")

    # Analyze
    fund = fund_analyzer.analyze(symbol, info)
    tech = tech_analyzer.analyze(symbol, df)

    current_price = tech.get("current_price", 0)
    atr = tech.get("atr")

    # Risk calculation
    risk_params = risk_mgr.calculate(
        symbol=symbol,
        current_price=current_price,
        atr=atr,
        direction="LONG",
        rsi=tech.get("rsi"),
        bb_lower=tech.get("bb_lower"),
        s1=tech.get("s1"),
        fib_618=tech.get("fib_level_618"),
    )

    # Determine recommendation
    is_banking = fund.get("is_banking", False)
    passed_roce = is_banking or (fund.get("roce") and fund.get("roce") >= settings_roce())
    passed_de = is_banking or (fund.get("debt_to_equity") is not None and fund.get("debt_to_equity") <= 1.0)
    passed_ema = tech.get("current_price", 0) > (tech.get("ema_200") or 0)
    rsi_val = tech.get("rsi") or 999

    rsi_ranges = {"SWING": (25, 55), "POSITIONAL": (20, 60), "INTRADAY": (30, 50)}
    rsi_low, rsi_high = rsi_ranges.get(mode, (25, 55))
    passed_rsi = rsi_low <= rsi_val <= rsi_high
    passed_rr = risk_params.get("meets_minimum_rr", False)

    all_passed = passed_roce and passed_de and passed_ema and passed_rsi and passed_rr

    # Build simple signal verdict
    if all_passed:
        verdict = "BUY"
        verdict_reason = "All filters passed — Good setup!"
    elif passed_ema and passed_rsi:
        verdict = "WATCH"
        verdict_reason = "Technical setup good but fundamentals need review"
    else:
        verdict = "SKIP"
        verdict_reason = "Does not meet entry criteria right now"

    return sanitize_nans({
        "symbol": symbol,
        "company_name": fund.get("company_name", symbol),
        "sector": fund.get("sector", ""),
        "mode": mode,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        # Price
        "current_price": current_price,
        # Trade Parameters
        **risk_params,
        # Fundamental Snapshot
        "fundamental": {
            "roce": fund.get("roce"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "piotroski_f_score": fund.get("piotroski_f_score"),
            "eps_growth_yoy": fund.get("eps_growth_yoy"),
            "pe_ratio": fund.get("pe_ratio"),
            "roe": fund.get("roe"),
            "market_cap": fund.get("market_cap"),
            "altman_z_score": fund.get("altman_z_score"),
            "passed_roce": passed_roce,
            "passed_debt_to_equity": passed_de,
        },
        # Technical Snapshot
        "technical": {
            "rsi": tech.get("rsi"),
            "ema_200": tech.get("ema_200"),
            "ema_50": tech.get("ema_50"),
            "adx": tech.get("adx"),
            "atr": atr,
            "atr_pct": tech.get("atr_pct"),
            "volume_ratio": tech.get("volume_ratio"),
            "macd": tech.get("macd"),
            "macd_signal": tech.get("macd_signal"),
            "week_52_high": tech.get("week_52_high"),
            "week_52_low": tech.get("week_52_low"),
            "pct_from_52w_high": tech.get("pct_from_52w_high"),
            "supertrend_bullish": tech.get("supertrend_bullish"),
            "passed_ema_200": passed_ema,
            "passed_rsi": passed_rsi,
        },
        # Filter Summary
        "filters": {
            "passed_roce": passed_roce,
            "passed_debt_to_equity": passed_de,
            "passed_ema_200": passed_ema,
            "passed_rsi": passed_rsi,
            "passed_rr": passed_rr,
            "all_passed": all_passed,
        },
    })


def settings_roce():
    from app.config import settings
    return settings.MIN_ROCE


# ── WebSocket Progress Stream ─────────────────────────────────────────────────

@router.websocket("/ws/{run_id}")
async def research_progress_ws(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time research run progress."""
    await websocket.accept()

    try:
        while True:
            run = get_research_run(run_id)
            if not run:
                await websocket.send_json({"error": f"Run {run_id} not found"})
                break

            await websocket.send_json(run.to_dict())

            if run.status in ("COMPLETED", "ERROR"):
                break

            await asyncio.sleep(1.0)  # Update every 1 second

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for research run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
