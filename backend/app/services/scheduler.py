"""
APScheduler Background Jobs
Runs scheduled tasks:
  - 3:45 PM IST: Daily Alpha Screener run on Nifty 500
  - 9:20 AM IST: Update open paper trade P&L
"""
import asyncio
from datetime import datetime
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import AsyncSessionLocal
from app.utils.logger import get_logger

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
_scheduler: AsyncIOScheduler = None


async def _run_daily_screener() -> None:
    """Background job: Run Alpha Screener at 3:45 PM IST."""
    from app.services.screener import AlphaScreener
    logger.info(f"[Scheduler] Starting daily screener @ {datetime.now(IST).strftime('%H:%M IST')}")
    async with AsyncSessionLocal() as db:
        screener = AlphaScreener()
        run = await screener.run_screener(db)
        logger.info(
            f"[Scheduler] Daily screener done: {run.passed} signals | "
            f"Run ID: {run.run_id}"
        )


async def _update_paper_trades() -> None:
    """Background job: Update all open paper trades at 9:20 AM IST."""
    from app.services.paper_trading import PaperTradingEngine
    logger.info(f"[Scheduler] Updating paper trades @ {datetime.now(IST).strftime('%H:%M IST')}")
    async with AsyncSessionLocal() as db:
        engine = PaperTradingEngine()
        summary = await engine.update_open_trades(db)
        logger.info(f"[Scheduler] Trade update: {summary}")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=IST)

    # Daily screener at 3:45 PM IST (after NSE close at 3:30 PM)
    _scheduler.add_job(
        _run_daily_screener,
        CronTrigger(
            hour=settings.SCREENER_CRON_HOUR,
            minute=settings.SCREENER_CRON_MINUTE,
            timezone=IST,
        ),
        id="daily_screener",
        name="Daily Alpha Screener",
        replace_existing=True,
        misfire_grace_time=300,  # 5 min grace if server was down
    )

    # P&L update at 9:20 AM IST (20 min after NSE open at 9:00 AM)
    _scheduler.add_job(
        _update_paper_trades,
        CronTrigger(
            hour=settings.PNL_UPDATE_HOUR,
            minute=settings.PNL_UPDATE_MINUTE,
            timezone=IST,
        ),
        id="pnl_update",
        name="Paper Trade P&L Update",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info("Scheduler configured with 2 jobs")
    return _scheduler


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    return _scheduler


def get_scheduled_jobs() -> list[dict]:
    """Return info about all scheduled jobs."""
    if not _scheduler:
        return []
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return jobs
