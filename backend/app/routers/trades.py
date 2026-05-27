"""
Paper Trades Router
POST /api/v1/trades/             → Create trade from signal
GET  /api/v1/trades/             → List all trades (paginated)
GET  /api/v1/trades/{id}         → Single trade detail
PUT  /api/v1/trades/{id}/close   → Close a trade manually
POST /api/v1/trades/update-all   → Update all open trades (P&L check)
GET  /api/v1/trades/stats        → Portfolio statistics
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus
from app.models.signal import ScreenerSignal
from app.services.paper_trading import PaperTradingEngine
from app.utils.helpers import paginate
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/trades", tags=["Paper Trades"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class CreateTradeRequest(BaseModel):
    signal_id: int
    capital: Optional[float] = None
    notes: Optional[str] = None


class CloseTradeRequest(BaseModel):
    exit_price: Optional[float] = None
    notes: Optional[str] = None


class TradeOut(BaseModel):
    id: int
    symbol: str
    company_name: str
    sector: Optional[str]
    direction: str
    entry_date: str
    entry_price: float
    quantity: int
    invested_amount: float
    stop_loss: float
    stop_loss_fixed: float
    target_price: float
    atr_at_entry: Optional[float]
    risk_reward_ratio: Optional[float]
    rsi_at_entry: Optional[float]
    roce_at_entry: Optional[float]
    piotroski_at_entry: Optional[int]
    current_price: Optional[float]
    current_rsi: Optional[float]
    unrealized_pnl: Optional[float]
    unrealized_pnl_pct: Optional[float]
    highest_price: Optional[float]
    days_in_trade: Optional[int]
    exit_date: Optional[str]
    exit_price: Optional[float]
    exit_reason: Optional[str]
    realized_pnl: Optional[float]
    realized_pnl_pct: Optional[float]
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=TradeOut, status_code=201)
async def create_trade(
    request: CreateTradeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new paper trade from a screener signal."""
    result = await db.execute(
        select(ScreenerSignal).where(ScreenerSignal.id == request.signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {request.signal_id} not found")
    if not signal.passed_all:
        raise HTTPException(
            status_code=422,
            detail="Cannot trade a signal that did not pass all filters"
        )
    if signal.is_traded:
        raise HTTPException(
            status_code=409,
            detail=f"Signal {request.signal_id} already has an associated trade"
        )

    engine = PaperTradingEngine()
    trade = await engine.enter_trade(db, signal, request.capital, request.notes)
    return trade


@router.get("/", response_model=dict)
async def list_trades(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, CLOSED_SL, etc.)"),
    symbol: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all paper trades with optional filters."""
    conditions = []
    if status:
        try:
            trade_status = TradeStatus(status)
            conditions.append(PaperTrade.status == trade_status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if symbol:
        conditions.append(PaperTrade.symbol.ilike(f"%{symbol}%"))

    stmt = select(PaperTrade).order_by(desc(PaperTrade.entry_date))
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    trades = result.scalars().all()

    return paginate([t.__dict__ for t in trades], page, page_size)


@router.get("/open", response_model=list[TradeOut])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    """Get all currently open trades."""
    result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.status == TradeStatus.OPEN)
        .order_by(desc(PaperTrade.entry_date))
    )
    return result.scalars().all()


@router.get("/stats")
async def get_portfolio_stats(db: AsyncSession = Depends(get_db)):
    """Get portfolio-level statistics."""
    engine = PaperTradingEngine()
    stats = await engine.get_portfolio_stats(db)
    return stats


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single trade by ID."""
    result = await db.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.put("/{trade_id}/close", response_model=TradeOut)
async def close_trade(
    trade_id: int,
    request: CloseTradeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually close an open trade."""
    engine = PaperTradingEngine()
    trade = await engine.close_trade_manual(
        db, trade_id, request.exit_price, request.notes
    )
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"Trade {trade_id} not found or not open"
        )
    return trade


@router.post("/update-all")
async def update_all_trades(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a P&L update for all open trades.
    Runs in background and checks exit conditions.
    """
    async def update_bg():
        from app.database import AsyncSessionLocal
        engine = PaperTradingEngine()
        async with AsyncSessionLocal() as bg_db:
            summary = await engine.update_open_trades(bg_db)
            logger.info(f"Background P&L update complete: {summary}")

    background_tasks.add_task(update_bg)
    return {"message": "P&L update started in background"}
