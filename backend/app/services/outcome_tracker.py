"""
Outcome Tracker — Self-Learning Phase
Evaluates past signals to determine if they were WINNER, LOSER, or NEUTRAL.
Criteria: Target hit before SL = WINNER. SL hit before Target = LOSER.
"""
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import ScreenerSignal
from app.services.data_fetcher import DataFetcher
from app.utils.logger import get_logger

logger = get_logger(__name__)

class OutcomeTracker:
    def __init__(self):
        self.fetcher = DataFetcher()

    async def track_outcomes(self, db: AsyncSession, days_back: int = 45) -> dict:
        """
        Evaluate PENDING signals generated in the last `days_back` days.
        """
        logger.info("Starting Outcome Tracker...")
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        # Fetch PENDING signals that have all required trading parameters
        stmt = select(ScreenerSignal).where(
            ScreenerSignal.outcome == "PENDING",
            ScreenerSignal.signal_date >= cutoff_date,
            ScreenerSignal.suggested_target.is_not(None),
            ScreenerSignal.suggested_sl.is_not(None)
        )
        result = await db.execute(stmt)
        signals = result.scalars().all()
        
        logger.info(f"Found {len(signals)} PENDING signals to evaluate.")
        
        stats = {"WINNER": 0, "LOSER": 0, "NEUTRAL": 0, "TOTAL": len(signals)}
        
        for sig in signals:
            try:
                # Fetch recent history (2 months ensures we cover up to 45 days back)
                df = await self.fetcher.fetch_price_history(sig.symbol, period="2mo")
                if df is None or df.empty:
                    continue
                
                # Filter data to only include days AFTER the signal date
                df_post = df[df.index > pd.to_datetime(sig.signal_date)]
                
                if df_post.empty:
                    continue
                
                outcome = "NEUTRAL"
                outcome_date = None
                outcome_price = None
                
                # Iterate day by day to see what hits first
                for date, row in df_post.iterrows():
                    high = row['High']
                    low = row['Low']
                    
                    if sig.direction == "LONG":
                        if low <= sig.suggested_sl:
                            outcome = "LOSER"
                            outcome_date = date.strftime("%Y-%m-%d")
                            outcome_price = sig.suggested_sl
                            break
                        elif high >= sig.suggested_target:
                            outcome = "WINNER"
                            outcome_date = date.strftime("%Y-%m-%d")
                            outcome_price = sig.suggested_target
                            break
                            
                    elif sig.direction == "SHORT":
                        if high >= sig.suggested_sl:
                            outcome = "LOSER"
                            outcome_date = date.strftime("%Y-%m-%d")
                            outcome_price = sig.suggested_sl
                            break
                        elif low <= sig.suggested_target:
                            outcome = "WINNER"
                            outcome_date = date.strftime("%Y-%m-%d")
                            outcome_price = sig.suggested_target
                            break
                
                # Check 30-day expiry for NEUTRAL
                if outcome == "NEUTRAL":
                    days_elapsed = (datetime.now() - datetime.strptime(sig.signal_date, "%Y-%m-%d")).days
                    if days_elapsed >= 30:
                        # Force outcome after 30 days
                        outcome = "NEUTRAL"
                        outcome_date = datetime.now().strftime("%Y-%m-%d")
                    else:
                        continue # Still PENDING, give it more time
                
                # Update DB
                sig.outcome = outcome
                if outcome_date:
                    sig.outcome_date = outcome_date
                    sig.outcome_price = outcome_price
                    sig.days_to_outcome = (datetime.strptime(outcome_date, "%Y-%m-%d") - datetime.strptime(sig.signal_date, "%Y-%m-%d")).days
                
                stats[outcome] += 1
                db.add(sig)
                
            except Exception as e:
                logger.error(f"Error evaluating outcome for {sig.symbol}: {e}")
                
        await db.commit()
        logger.info(f"Outcome Tracker Finished: {stats}")
        return stats

    async def get_pattern_performance(self, db: AsyncSession) -> list[dict]:
        """
        Aggregate win rates for all patterns based on outcomes.
        """
        stmt = select(
            ScreenerSignal.pattern_name,
            ScreenerSignal.direction,
            ScreenerSignal.outcome
        ).where(
            ScreenerSignal.pattern_name.is_not(None),
            ScreenerSignal.pattern_name != "no_pattern",
            ScreenerSignal.outcome != "PENDING"
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        perf = {}
        for pattern, direction, outcome in rows:
            key = f"{pattern}_{direction}"
            if key not in perf:
                perf[key] = {"pattern": pattern, "direction": direction, "total": 0, "winners": 0, "losers": 0, "neutral": 0}
            
            perf[key]["total"] += 1
            if outcome == "WINNER":
                perf[key]["winners"] += 1
            elif outcome == "LOSER":
                perf[key]["losers"] += 1
            else:
                perf[key]["neutral"] += 1
                
        # Calculate win rate and status
        final_stats = []
        for v in perf.values():
            active_trades = v["winners"] + v["losers"]
            win_rate = (v["winners"] / active_trades) if active_trades > 0 else 0
            
            status = "Need More Data"
            if active_trades >= 5:
                if win_rate >= 0.60:
                    status = "🟢 Strong"
                elif win_rate < 0.40:
                    status = "🔴 Weak — Auto-tightening"
                else:
                    status = "🟡 Average"
            
            v["win_rate"] = round(win_rate * 100, 1)
            v["status"] = status
            final_stats.append(v)
            
        return sorted(final_stats, key=lambda x: x["total"], reverse=True)
