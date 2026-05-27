"""
Dashboard Router
GET /api/v1/dashboard/summary     → High-level portfolio + screener stats
GET /api/v1/dashboard/pnl-chart   → Historical P&L chart data
GET /api/v1/dashboard/heatmap     → Sector-wise performance heatmap
GET /api/v1/dashboard/scheduler   → Scheduler job status
"""
from datetime import date, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus
from app.models.signal import ScreenerSignal
from app.services.paper_trading import PaperTradingEngine
from app.services.scheduler import get_scheduled_jobs
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Get the main dashboard summary:
    - Portfolio stats (P&L, open trades, win rate)
    - Recent screener signals
    - Scheduler status
    """
    engine = PaperTradingEngine()
    portfolio_stats = await engine.get_portfolio_stats(db)

    # Latest screener run stats
    stmt = (
        select(ScreenerSignal)
        .order_by(ScreenerSignal.id.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    recent_signals = result.scalars().all()

    latest_run_id = None
    latest_run_date = None
    if recent_signals:
        latest_run_id = recent_signals[0].screener_run_id
        latest_run_date = recent_signals[0].signal_date

    screener_stats = {
        "latest_run_id": latest_run_id,
        "latest_run_date": latest_run_date,
        "total_signals_today": sum(
            1 for s in recent_signals if s.signal_date == str(date.today())
        ),
        "passed_today": sum(
            1 for s in recent_signals
            if s.signal_date == str(date.today()) and s.passed_all
        ),
    }

    # Top signals by score
    top_signals = sorted(
        [s for s in recent_signals if s.passed_all],
        key=lambda x: x.composite_score or 0,
        reverse=True,
    )[:5]

    top_signals_data = [
        {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "signal_price": s.signal_price,
            "rsi_14": s.rsi_14,
            "roce": s.roce,
            "composite_score": s.composite_score,
            "suggested_sl": s.suggested_sl,
            "suggested_target": s.suggested_target,
            "risk_reward_ratio": s.risk_reward_ratio,
        }
        for s in top_signals
    ]

    return {
        "portfolio": portfolio_stats,
        "screener": screener_stats,
        "top_signals": top_signals_data,
        "scheduler_jobs": get_scheduled_jobs(),
        "config": {
            "capital": settings.DEFAULT_CAPITAL,
            "position_size_pct": settings.DEFAULT_POSITION_SIZE_PCT * 100,
            "universe": settings.SCREENER_UNIVERSE,
        },
    }


@router.get("/pnl-chart")
async def get_pnl_chart(
    db: AsyncSession = Depends(get_db),
    days: int = 30,
):
    """
    Get cumulative P&L chart data for the past N days.
    Returns daily data points for charting.
    """
    start_date = str(date.today() - timedelta(days=days))

    stmt = select(PaperTrade).where(
        PaperTrade.entry_date >= start_date
    ).order_by(PaperTrade.entry_date)

    result = await db.execute(stmt)
    trades = result.scalars().all()

    # Aggregate by date
    daily_pnl: dict[str, float] = defaultdict(float)
    for trade in trades:
        if trade.realized_pnl is not None and trade.exit_date:
            daily_pnl[trade.exit_date] += trade.realized_pnl

    # Build cumulative series
    all_dates = []
    current = date.today() - timedelta(days=days)
    while current <= date.today():
        all_dates.append(str(current))
        current += timedelta(days=1)

    cumulative = 0.0
    chart_data = []
    for d in all_dates:
        cumulative += daily_pnl.get(d, 0.0)
        chart_data.append({
            "date": d,
            "daily_pnl": round(daily_pnl.get(d, 0.0), 2),
            "cumulative_pnl": round(cumulative, 2),
        })

    return {
        "days": days,
        "total_pnl": round(cumulative, 2),
        "data": chart_data,
    }


@router.get("/heatmap")
async def get_sector_heatmap(db: AsyncSession = Depends(get_db)):
    """
    Sector-wise performance heatmap.
    Returns sector → {trade_count, avg_pnl_pct, win_rate}
    """
    result = await db.execute(select(PaperTrade))
    trades = result.scalars().all()

    sector_data: dict[str, list] = defaultdict(list)
    for trade in trades:
        sector = trade.sector or "Unknown"
        pnl_pct = trade.realized_pnl_pct or trade.unrealized_pnl_pct or 0
        sector_data[sector].append(pnl_pct)

    heatmap = []
    for sector, pnls in sector_data.items():
        wins = sum(1 for p in pnls if p > 0)
        heatmap.append({
            "sector": sector,
            "trade_count": len(pnls),
            "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0,
            "win_rate": round(wins / len(pnls) * 100, 1) if pnls else 0,
            "total_pnl_pct": round(sum(pnls), 2),
        })

    return sorted(heatmap, key=lambda x: x["avg_pnl_pct"], reverse=True)


@router.get("/recent-signals")
async def get_recent_signals(
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
):
    """Get the most recent passed signals."""
    stmt = (
        select(ScreenerSignal)
        .where(ScreenerSignal.passed_all == True)
        .order_by(ScreenerSignal.id.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    signals = result.scalars().all()
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "signal_date": s.signal_date,
            "signal_price": s.signal_price,
            "rsi_14": s.rsi_14,
            "roce": s.roce,
            "composite_score": s.composite_score,
            "risk_reward_ratio": s.risk_reward_ratio,
            "is_traded": s.is_traded,
        }
        for s in signals
    ]
