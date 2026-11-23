"""
The Aladdin Brain API Router
Endpoints:
  GET  /api/v1/aladdin/diagnose/{symbol} → Full 5-pillar unified intelligence diagnostic
  POST /api/v1/aladdin/deploy            → 1-click deploy diagnosed setup into live paper trading
  GET  /api/v1/aladdin/popular           → Curated leaders for instant lookup
"""
from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus, TradeDirection
from app.services.aladdin_brain import AladdinBrainEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/aladdin", tags=["Aladdin Brain (Universal Stock Intelligence)"])


class DeployAladdinTradeRequest(BaseModel):
    symbol: str
    company_name: str
    sector: Optional[str] = "General"
    entry_price: float
    stop_loss: float
    target_price: float
    quantity: int
    capital: Optional[float] = None
    notes: Optional[str] = None


@router.get("/diagnose/{symbol}")
async def diagnose_stock(
    symbol: str,
    force_refresh: bool = Query(False, description="Bypass in-memory cache and fetch fresh data"),
):
    """
    Execute 5-Pillar Omniscient Diagnostic on any stock.
    Returns:
      - Current Market Phase (Accumulation, Markup, Distribution, Capitulation)
      - Predictive Target 1, Target 2, Dynamic ATR Stop Loss
      - 5-Pillar breakdown (Geometry, Technical, Fundamental, F&O Smart Money, Macro)
      - Weighted Conviction Score (0 to 100%) & Verdict
    """
    clean_sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    if not clean_sym:
        raise HTTPException(status_code=400, detail="Invalid symbol provided.")

    engine = AladdinBrainEngine()
    result = await engine.diagnose_stock(clean_sym, force_refresh=force_refresh)

    if result.get("error"):
        return result

    return result


@router.post("/deploy", status_code=201)
async def deploy_aladdin_trade(
    req: DeployAladdinTradeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    1-Click deploy an Aladdin-diagnosed high conviction setup directly into Paper Trading.
    Immediately tracked with live tick updates & dynamic trailing stop loss.
    """
    clean_sym = req.symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    invested = round(req.entry_price * req.quantity, 2)

    # ── Strict Rigid Capital Enforcement ──
    from app.config import settings
    from sqlalchemy import select
    stmt_open = select(PaperTrade).where(PaperTrade.status == TradeStatus.OPEN)
    res_open = await db.execute(stmt_open)
    open_trades = res_open.scalars().all()

    stmt_closed = select(PaperTrade).where(PaperTrade.status != TradeStatus.OPEN)
    res_closed = await db.execute(stmt_closed)
    closed_trades = res_closed.scalars().all()

    realized_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
    total_invested_currently = sum(t.invested_amount for t in open_trades)
    total_capital = req.capital or settings.DEFAULT_CAPITAL
    available_cash = total_capital + realized_pnl - total_invested_currently

    if available_cash <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Rigid Fund Limit: Paper portfolio has ₹0 available cash (Total pool: ₹{total_capital:,.2f}, Invested: ₹{total_invested_currently:,.2f}). Close an open trade before opening a new position."
        )

    if invested > available_cash:
        raise HTTPException(
            status_code=400,
            detail=f"Rigid Fund Limit: Trade requires ₹{invested:,.2f}, but only ₹{available_cash:,.2f} available cash remains in the ₹{total_capital:,.2f} pool."
        )

    trade = PaperTrade(
        symbol=clean_sym,
        company_name=req.company_name,
        sector=req.sector,
        direction=TradeDirection.LONG,
        entry_date=date.today().strftime("%Y-%m-%d"),
        entry_price=req.entry_price,
        quantity=req.quantity,
        invested_amount=invested,
        stop_loss=req.stop_loss,
        stop_loss_fixed=req.stop_loss,
        target_price=req.target_price,
        current_price=req.entry_price,
        highest_price=req.entry_price,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0,
        days_in_trade=0,
        status=TradeStatus.OPEN,
        notes=req.notes or f"Aladdin Brain Execution: SL ₹{req.stop_loss:.2f} | Target ₹{req.target_price:.2f}",
    )

    db.add(trade)
    await db.commit()
    await db.refresh(trade)

    t_dict = trade.__dict__.copy()
    t_dict.pop("_sa_instance_state", None)

    logger.info(f"Aladdin: Deployed trade #{trade.id} for {clean_sym} ({req.quantity} qty @ ₹{req.entry_price})")
    return {
        "success": True,
        "message": f"Successfully opened paper trade #{trade.id} for {clean_sym}!",
        "trade": t_dict,
    }


@router.get("/popular")
async def get_popular_symbols():
    """Curated list of high-liquidity market leaders for 1-click Aladdin analysis."""
    return [
        {"symbol": "RELIANCE", "name": "Reliance Industries", "sector": "Energy"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank", "sector": "Financial Services"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank", "sector": "Financial Services"},
        {"symbol": "TCS", "name": "Tata Consultancy Services", "sector": "Technology"},
        {"symbol": "INFY", "name": "Infosys", "sector": "Technology"},
        {"symbol": "TATAMOTORS", "name": "Tata Motors", "sector": "Automobile"},
        {"symbol": "SBIN", "name": "State Bank of India", "sector": "Financial Services"},
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel", "sector": "Telecom"},
        {"symbol": "LT", "name": "Larsen & Toubro", "sector": "Construction"},
        {"symbol": "ITC", "name": "ITC Limited", "sector": "Consumer Goods"},
    ]


@router.get("/backtest")
async def get_aladdin_backtest_report():
    """
    Returns official multi-year institutional portfolio backtest scorecard.
    """
    import json
    from pathlib import Path
    from app.config import BASE_DIR, _BACKEND_DIR

    for report_path in (
        Path(_BACKEND_DIR) / "models" / "aladdin_backtest_report.json",
        Path(BASE_DIR) / "backend" / "models" / "aladdin_backtest_report.json",
    ):
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {
        "error": "Backtest report not found. Run backtest_aladdin_model.py first."
    }


@router.get("/stress-test")
async def get_aladdin_stress_test_report():
    """
    Returns deep institutional stress testing and Monte Carlo analysis.
    """
    import json
    from pathlib import Path
    from app.config import BASE_DIR, _BACKEND_DIR

    for report_path in (
        Path(_BACKEND_DIR) / "models" / "aladdin_stress_test_report.json",
        Path(BASE_DIR) / "backend" / "models" / "aladdin_stress_test_report.json",
    ):
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {
        "error": "Stress test report not found. Run stress_test_and_harden.py first."
    }


@router.get("/forecast/{symbol}")
async def get_aladdin_forecast(symbol: str):
    """
    Returns 15-day trajectory forecast, ±1 SD probability cone, 3-way directional odds,
    and walk-forward Predicted vs Actual Candle accuracy ledger for the symbol.
    """
    import asyncio
    from app.services.prediction_ledger import PredictionLedger

    clean_sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    if not clean_sym:
        raise HTTPException(status_code=400, detail="Invalid symbol provided.")

    engine = AladdinBrainEngine()
    diagnosis = await engine.diagnose_stock(clean_sym)
    forecast = await asyncio.to_thread(
        PredictionLedger.generate_forecast_and_audit,
        clean_sym,
        None if diagnosis.get("error") else diagnosis,
    )
    return forecast


@router.get("/predictions/stats")
async def get_prediction_accuracy_stats():
    """Returns global Closed-Loop Prediction vs Actual Candle accuracy stats across all evaluated stocks."""
    from app.services.prediction_ledger import PredictionLedger
    return PredictionLedger.get_global_prediction_stats()


@router.post("/predictions/evaluate")
async def evaluate_pending_predictions():
    """Evaluates all PENDING Aladdin predictions against newly closed actual daily candles and updates self-learning feedback."""
    import asyncio
    from app.services.prediction_ledger import PredictionLedger
    return await asyncio.to_thread(PredictionLedger.evaluate_all_pending_predictions)


@router.get("/patterns/empirical-stats")
async def get_empirical_pattern_stats():
    """Return 5Y outcome-verified empirical win rates across chart and candlestick patterns."""
    import asyncio
    import sys
    from app.config import _BACKEND_DIR
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))
    from advanced_dataset_generator import get_cached_or_run_empirical_stats
    return await asyncio.to_thread(get_cached_or_run_empirical_stats, 80)


@router.post("/patterns/scan-empirical")
async def run_empirical_pattern_scan(
    max_symbols: int = Query(80, ge=20, le=120, description="Number of Nifty stocks to scan safely within memory budget"),
    years: int = Query(5, ge=2, le=10, description="Lookback years in SQLite daily OHLCV store"),
):
    """Run fresh walk-forward outcome-verified empirical pattern benchmark over local 20Y SQLite history."""
    import asyncio
    import sys
    from app.config import _BACKEND_DIR
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))
    from advanced_dataset_generator import run_empirical_pattern_benchmark
    return await asyncio.to_thread(run_empirical_pattern_benchmark, max_symbols, years)
