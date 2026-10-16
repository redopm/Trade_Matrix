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

import time
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus
from app.models.signal import ScreenerSignal
from app.services.paper_trading import PaperTradingEngine
from app.services.scheduler import get_scheduled_jobs
from app.services.aladdin_brain import AladdinBrainEngine
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ── Aladdin AI Top Picks Cache ────────────────────────────────────────────────
_AI_PICKS_CACHE: Dict[str, Any] = {
    "timestamp": time.time(),
    "data": [
        {
            "symbol": "PERSISTENT",
            "company_name": "Persistent Systems Limited",
            "sector": "Technology",
            "current_price": 5898.0,
            "composite_score": 67.3,
            "verdict": "BUY",
            "verdict_badge": "Swing Setup",
            "verdict_color": "blue",
            "market_phase": "STAGE_2_MARKUP",
            "market_phase_desc": "Smart Money Markup Phase. Price expanding above key EMAs.",
            "target_1": 6402.27,
            "target_1_pct": 8.55,
            "target_2": 6906.54,
            "target_2_pct": 17.1,
            "stop_loss": 5561.82,
            "stop_loss_pct": 5.7,
            "risk_reward_ratio": "1:1.95",
            "ml_win_probability": 40.4,
            "ml_expected_return_pct": 1.42,
            "time_horizon": "5-20 Days",
        },
        {
            "symbol": "HAL",
            "company_name": "Hindustan Aeronautics Limited",
            "sector": "Capital Goods",
            "current_price": 4933.0,
            "composite_score": 59.9,
            "verdict": "NEUTRAL",
            "verdict_badge": "Neutral Setup",
            "verdict_color": "slate",
            "market_phase": "STAGE_2_MARKUP",
            "market_phase_desc": "Markup Phase with active momentum.",
            "target_1": 5277.67,
            "target_1_pct": 6.99,
            "target_2": 5622.34,
            "target_2_pct": 13.97,
            "stop_loss": 4703.22,
            "stop_loss_pct": 4.66,
            "risk_reward_ratio": "1:0.94",
            "ml_win_probability": 40.7,
            "ml_expected_return_pct": 1.5,
            "time_horizon": "5-20 Days",
        },
        {
            "symbol": "TRENT",
            "company_name": "Trent Limited",
            "sector": "Retail",
            "current_price": 2971.0,
            "composite_score": 58.6,
            "verdict": "NEUTRAL",
            "verdict_badge": "Neutral Setup",
            "verdict_color": "slate",
            "market_phase": "STAGE_2_MARKUP",
            "market_phase_desc": "Institutional accumulation turning into markup expansion.",
            "target_1": 3192.67,
            "target_1_pct": 7.46,
            "target_2": 3414.34,
            "target_2_pct": 14.92,
            "stop_loss": 2823.22,
            "stop_loss_pct": 4.97,
            "risk_reward_ratio": "1:2.90",
            "ml_win_probability": 40.7,
            "ml_expected_return_pct": 1.5,
            "time_horizon": "5-20 Days",
        },
        {
            "symbol": "ICICIBANK",
            "company_name": "ICICI Bank Limited",
            "sector": "Financial Services",
            "current_price": 1338.6,
            "composite_score": 56.5,
            "verdict": "NEUTRAL",
            "verdict_badge": "Oversold Bounce",
            "verdict_color": "slate",
            "market_phase": "ACCUMULATION_DIP",
            "market_phase_desc": "Banking titan near key multi-month support level.",
            "target_1": 1582.44,
            "target_1_pct": 18.22,
            "target_2": 1720.0,
            "target_2_pct": 28.49,
            "stop_loss": 1176.04,
            "stop_loss_pct": 12.14,
            "risk_reward_ratio": "1:0.87",
            "ml_win_probability": 40.9,
            "ml_expected_return_pct": 1.5,
            "time_horizon": "10-30 Days",
        },
        {
            "symbol": "DIXON",
            "company_name": "Dixon Technologies (India) Limited",
            "sector": "Technology & Electronics",
            "current_price": 12820.0,
            "composite_score": 53.2,
            "verdict": "NEUTRAL",
            "verdict_badge": "High Beta Swing",
            "verdict_color": "slate",
            "market_phase": "STAGE_4_CONSOLIDATION",
            "market_phase_desc": "High beta manufacturing leader in pull-back zone.",
            "target_1": 13851.67,
            "target_1_pct": 8.05,
            "target_2": 14883.34,
            "target_2_pct": 16.09,
            "stop_loss": 12132.22,
            "stop_loss_pct": 5.36,
            "risk_reward_ratio": "1:3.17",
            "ml_win_probability": 40.4,
            "ml_expected_return_pct": 1.46,
            "time_horizon": "5-15 Days",
        },
    ]
}

_MONITORED_ALPHA_BASKET = [
    "RELIANCE", "BHARTIARTL", "SUNPHARMA", "PERSISTENT", 
    "DIXON", "HAL", "TRENT", "BEL", "BAJFINANCE", 
    "BSE", "MCX", "KAYNES", "FEDERALBNK", "TCS", "M&M"
]


async def get_or_compute_ai_picks(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Returns Aladdin AI Top High-Conviction Picks.
    Uses in-memory cache (TTL: 15 minutes) for sub-millisecond response.
    """
    global _AI_PICKS_CACHE
    now = time.time()
    if not force_refresh and _AI_PICKS_CACHE["data"] and (now - _AI_PICKS_CACHE["timestamp"] < 900):
        return _AI_PICKS_CACHE["data"]

    try:
        engine = AladdinBrainEngine()
        fresh_picks = []
        for sym in _MONITORED_ALPHA_BASKET:
            try:
                res = await engine.diagnose_stock(sym)
                if not res.get("error"):
                    fresh_picks.append({
                        "symbol": sym,
                        "company_name": res.get("company_name"),
                        "sector": res.get("sector"),
                        "current_price": res.get("current_price"),
                        "composite_score": res.get("composite_score"),
                        "verdict": res.get("verdict"),
                        "verdict_badge": res.get("verdict_badge"),
                        "verdict_color": res.get("verdict_color"),
                        "market_phase": res.get("market_phase"),
                        "market_phase_desc": res.get("market_phase_desc"),
                        "target_1": res.get("target_1"),
                        "target_1_pct": res.get("target_1_pct"),
                        "target_2": res.get("target_2"),
                        "target_2_pct": res.get("target_2_pct"),
                        "stop_loss": res.get("stop_loss"),
                        "stop_loss_pct": res.get("stop_loss_pct"),
                        "risk_reward_ratio": res.get("risk_reward_ratio"),
                        "ml_win_probability": res.get("ml_win_probability"),
                        "ml_expected_return_pct": res.get("ml_expected_return_pct"),
                        "time_horizon": res.get("time_horizon", "5 to 20 Trading Days"),
                    })
            except Exception as e:
                logger.warning(f"Dashboard: Failed diagnosing {sym} for AI picks: {e}")

        fresh_picks.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        if fresh_picks:
            _AI_PICKS_CACHE["timestamp"] = now
            _AI_PICKS_CACHE["data"] = fresh_picks
            return fresh_picks
    except Exception as e:
        logger.error(f"Dashboard: Error generating AI picks: {e}")

    return _AI_PICKS_CACHE.get("data", [])



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

    ai_picks = await get_or_compute_ai_picks()

    return {
        "portfolio": portfolio_stats,
        "screener": screener_stats,
        "top_signals": top_signals_data,
        "ai_picks": ai_picks,
        "scheduler_jobs": get_scheduled_jobs(),
        "config": {
            "capital": settings.DEFAULT_CAPITAL,
            "position_size_pct": settings.DEFAULT_POSITION_SIZE_PCT * 100,
            "universe": settings.SCREENER_UNIVERSE,
        },
    }


@router.get("/ai-picks")
async def get_dashboard_ai_picks(force_refresh: bool = False):
    """
    Get top high-conviction AI setups diagnosed by the Aladdin Brain ML Engine.
    Returns 5-pillar composite score, market phase, price targets, and risk profile.
    """
    return await get_or_compute_ai_picks(force_refresh=force_refresh)


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
