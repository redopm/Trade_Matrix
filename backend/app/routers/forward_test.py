"""
Forward Validation Router (Protocol v2.1)
REST Endpoints for Cohort Freeze, Monte Carlo Bootstrap Evaluation, and Scorecard
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.trade import ForwardBatch, UniverseScoreSnapshot, PaperTrade
from app.services.forward_test import ForwardTestEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/forward-test", tags=["Forward Validation Protocol v2.1"])


@router.post("/freeze-cohort", response_model=Dict[str, Any], status_code=201)
async def freeze_cohort(
    cohort_type: str = Query("PRIMARY", description="'PILOT' for today's verification run, or 'PRIMARY' for monthly cohorts"),
    batch_id: Optional[str] = Query(None, description="Optional custom batch identifier"),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a pre-registered immutable cohort freeze at T=0.
    Creates Ledger A (Full Universe Snapshot) and Ledger B (Live Execution Desk).
    """
    try:
        res = await ForwardTestEngine.freeze_cohort(db, cohort_type=cohort_type, batch_id=batch_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error freezing forward cohort: {e}")
        raise HTTPException(status_code=500, detail=f"Cohort freeze failed: {e}")


@router.get("/scorecard", response_model=Dict[str, Any])
async def get_forward_scorecard(db: AsyncSession = Depends(get_db)):
    """
    Returns the unified pre-registered scorecard across completed cohorts.
    Evaluates Tool Top 10 vs 1,000 Random Baskets with cross-cohort Confidence Interval.
    """
    try:
        scorecard = await ForwardTestEngine.get_protocol_scorecard(db)
        return scorecard
    except Exception as e:
        logger.error(f"Error generating forward scorecard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohorts", response_model=List[Dict[str, Any]])
async def get_all_cohorts(db: AsyncSession = Depends(get_db)):
    """Returns all frozen cohorts."""
    stmt = select(ForwardBatch).order_by(ForwardBatch.created_at)
    res = await db.execute(stmt)
    batches = res.scalars().all()
    return [
        {
            "batch_id": b.batch_id,
            "cohort_type": b.cohort_type,
            "status": b.status,
            "regime": b.regime,
            "created_at": b.created_at.isoformat() if hasattr(b.created_at, "isoformat") else str(b.created_at),
            "nifty_base_price": b.nifty_base_price,
            "scoring_git_hash": b.scoring_git_hash,
            "scoring_formula_version": b.scoring_formula_version,
            "random_seed": b.random_seed,
            "eligible_universe_count": b.eligible_universe_count,
            "tool_stock_count": b.tool_stock_count,
            "slot_capital_inr": b.slot_capital_inr,
            "total_allocated_inr": b.total_allocated_inr,
            "tool_avg_return_pct": b.tool_avg_return_pct,
            "control_mean_return_pct": b.control_mean_return_pct,
            "delta_excess_return_pct": b.delta_excess_return_pct,
            "monte_carlo_percentile": b.monte_carlo_percentile,
            "spearman_rho": b.spearman_rho,
        }
        for b in batches
    ]


@router.get("/snapshot/{batch_id}", response_model=List[Dict[str, Any]])
async def get_universe_snapshot(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Returns the full 100-stock score snapshot for a specific cohort (Ledger A)."""
    stmt = select(UniverseScoreSnapshot).where(UniverseScoreSnapshot.batch_id == batch_id).order_by(UniverseScoreSnapshot.composite_score.desc())
    res = await db.execute(stmt)
    snaps = res.scalars().all()
    if not snaps:
        raise HTTPException(status_code=404, detail=f"No snapshot found for cohort '{batch_id}'")
    return [
        {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "composite_score": s.composite_score,
            "is_top10": s.is_top10,
            "entry_price": s.entry_price,
            "day90_price": s.day90_price,
            "day90_return_pct": s.day90_return_pct,
        }
        for s in snaps
    ]
