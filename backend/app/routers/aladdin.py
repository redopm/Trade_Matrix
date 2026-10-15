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
    invested = req.entry_price * req.quantity

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
    Returns official 5.7-year institutional portfolio backtest scorecard:
    1-Year CAGR (27.17%), 1-Month CAGR (2.02%), Net Return (+294.85%),
    Max Drawdown (11.56%), Sharpe Ratio (1.82), Win Rate (49.9%), and Year-by-Year breakdown.
    """
    import json
    from pathlib import Path
    from app.config import BASE_DIR

    report_path = Path(BASE_DIR) / "backend" / "models" / "aladdin_backtest_report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "error": "Backtest report not found. Run backtest_aladdin_model.py first."
    }


@router.get("/stress-test")
async def get_aladdin_stress_test_report():
    """
    Returns deep institutional stress testing and Monte Carlo analysis:
    - 1,000 Monte Carlo bootstrap simulations (Ruin Risk, Worst 5% luck CAGR, VaR Drawdown)
    - Slippage & transaction friction tests (0.05% to 0.30%)
    - Alpha diversification across 50 top Nifty stocks
    - Consecutive streak and max drawdown recovery statistics
    """
    import json
    from pathlib import Path
    from app.config import BASE_DIR

    report_path = Path(BASE_DIR) / "backend" / "models" / "aladdin_stress_test_report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "error": "Stress test report not found. Run stress_test_and_harden.py first."
    }
