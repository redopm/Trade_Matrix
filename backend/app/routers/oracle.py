"""
The Aladdin Brain — Oracle API Router
Endpoints:
  GET  /api/v1/oracle/diagnose/{symbol} → Full 5-pillar unified intelligence diagnostic
  POST /api/v1/oracle/deploy            → 1-click deploy diagnosed setup into live paper trading
  GET  /api/v1/oracle/popular           → Curated leaders for instant lookup
"""
from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus, TradeDirection
from app.services.stock_oracle import StockOracleEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/oracle", tags=["Stock Oracle (The Aladdin Brain)"])


class DeployOracleTradeRequest(BaseModel):
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

    engine = StockOracleEngine()
    result = await engine.diagnose_stock(clean_sym, force_refresh=force_refresh)

    if result.get("error"):
        # Return structured error with status 404 or 422
        return result

    return result


@router.post("/deploy", status_code=201)
async def deploy_oracle_trade(
    req: DeployOracleTradeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    1-Click deploy an Oracle-diagnosed high conviction setup directly into Paper Trading.
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
        notes=req.notes or f"Aladdin Oracle Execution: SL ₹{req.stop_loss:.2f} | Target ₹{req.target_price:.2f}",
    )

    db.add(trade)
    await db.commit()
    await db.refresh(trade)

    t_dict = trade.__dict__.copy()
    t_dict.pop("_sa_instance_state", None)

    logger.info(f"Oracle: Deployed trade #{trade.id} for {clean_sym} ({req.quantity} qty @ ₹{req.entry_price})")
    return {
        "success": True,
        "message": f"Successfully opened paper trade #{trade.id} for {clean_sym}!",
        "trade": t_dict,
    }


@router.get("/popular")
async def get_popular_symbols():
    """Curated list of high-liquidity market leaders for 1-click Oracle analysis."""
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
