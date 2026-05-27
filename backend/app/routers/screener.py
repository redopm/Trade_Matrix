"""
Screener Router
POST /api/v1/screener/run       → Start a screener run (async)
GET  /api/v1/screener/run/{id}  → Get run status
GET  /api/v1/screener/results   → Get all signals (paginated, filterable)
GET  /api/v1/screener/signals/{id} → Single signal detail
WS   /api/v1/screener/ws/{id}   → Real-time run progress via WebSocket
"""
import asyncio
import uuid
import json
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, WebSocket
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.signal import ScreenerSignal
from app.services.screener import AlphaScreener, _active_runs
from app.utils.helpers import paginate
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/screener", tags=["Screener"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class RunScreenerRequest(BaseModel):
    symbols: Optional[list[str]] = None
    description: Optional[str] = None


class ScreenerRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class SignalOut(BaseModel):
    id: int
    symbol: str
    company_name: str
    sector: Optional[str]
    signal_date: str
    signal_price: float
    rsi_14: Optional[float]
    ema_200: Optional[float]
    roce: Optional[float]
    debt_to_equity: Optional[float]
    piotroski_f_score: Optional[int]
    suggested_entry: Optional[float]
    suggested_sl: Optional[float]
    suggested_target: Optional[float]
    risk_reward_ratio: Optional[float]
    passed_all: bool
    passed_roce: bool
    passed_debt_to_equity: bool
    passed_ema_200: bool
    passed_rsi: bool
    passed_piotroski: bool
    passed_earnings_blackout: bool
    composite_score: Optional[float]
    market_cap: Optional[float]
    atr_14: Optional[float]
    adx: Optional[float]
    is_traded: bool
    screener_run_id: Optional[str]

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=ScreenerRunResponse, status_code=202)
async def start_screener_run(
    request: RunScreenerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start an async screener run in the background.
    Returns immediately with a run_id for polling/websocket.
    """
    run_id = str(uuid.uuid4())

    async def run_screener_bg():
        """Background task wrapper."""
        from app.database import AsyncSessionLocal
        screener = AlphaScreener()
        async with AsyncSessionLocal() as bg_db:
            await screener.run_screener(
                db=bg_db,
                symbols=request.symbols,
                run_id=run_id,
            )

    background_tasks.add_task(run_screener_bg)
    logger.info(f"Screener run {run_id} started in background")

    return ScreenerRunResponse(
        run_id=run_id,
        status="STARTED",
        message=f"Screener run started. Track progress at /screener/run/{run_id}",
    )


@router.get("/run/{run_id}")
async def get_run_status(run_id: str):
    """Get the current status of a screener run."""
    run = _active_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run.to_dict()


@router.get("/runs")
async def list_runs():
    """List all screener runs (in-memory)."""
    return [run.to_dict() for run in _active_runs.values()]


@router.get("/results", response_model=dict)
async def get_screener_results(
    db: AsyncSession = Depends(get_db),
    passed_only: bool = Query(False, description="Return only stocks that passed all filters"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_score: Optional[float] = Query(None, description="Minimum composite score"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("composite_score", description="Sort field"),
    sort_desc: bool = Query(True),
):
    """
    Get paginated screener results with optional filters.
    """
    conditions = []

    if passed_only:
        conditions.append(ScreenerSignal.passed_all == True)
    if sector:
        conditions.append(ScreenerSignal.sector.ilike(f"%{sector}%"))
    if min_score is not None:
        conditions.append(ScreenerSignal.composite_score >= min_score)
    if date_from:
        conditions.append(ScreenerSignal.signal_date >= date_from)
    if date_to:
        conditions.append(ScreenerSignal.signal_date <= date_to)

    stmt = select(ScreenerSignal)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    # Sorting
    sort_col = getattr(ScreenerSignal, sort_by, ScreenerSignal.composite_score)
    stmt = stmt.order_by(desc(sort_col) if sort_desc else sort_col)

    result = await db.execute(stmt)
    signals = result.scalars().all()

    paginated = paginate([s.__dict__ for s in signals], page, page_size)

    # Compute summary stats
    all_signals = [s.__dict__ for s in signals]
    summary = {
        "total_screened": len(all_signals),
        "total_passed": sum(1 for s in all_signals if s.get("passed_all")),
        "pass_rate": round(
            sum(1 for s in all_signals if s.get("passed_all")) / max(len(all_signals), 1) * 100, 1
        ),
        "sectors": list({s.get("sector") for s in all_signals if s.get("sector")}),
    }

    return {**paginated, "summary": summary}


@router.get("/results/passed", response_model=list[SignalOut])
async def get_passed_signals(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Get the latest signals that passed all filters, sorted by score."""
    stmt = (
        select(ScreenerSignal)
        .where(ScreenerSignal.passed_all == True)
        .order_by(desc(ScreenerSignal.composite_score))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/signals/{signal_id}", response_model=SignalOut)
async def get_signal(signal_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single signal by ID."""
    result = await db.execute(
        select(ScreenerSignal).where(ScreenerSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.websocket("/ws/{run_id}")
async def screener_websocket(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time screener progress.
    Client connects and receives JSON updates as the screener processes each stock.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for run {run_id}")

    try:
        # Poll the run status until complete
        while True:
            run = _active_runs.get(run_id)
            if run:
                await websocket.send_json(run.to_dict())
                if run.status in ("COMPLETED", "FAILED"):
                    break
            else:
                await websocket.send_json({"run_id": run_id, "status": "NOT_FOUND"})
                break
            await asyncio.sleep(1.5)
    except Exception as e:
        logger.warning(f"WebSocket closed for {run_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
