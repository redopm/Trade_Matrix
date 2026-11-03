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

async def _run_weekly_self_learning() -> None:
    """Background job: Run Weekly Self-Learning (Outcomes + Gemini) on Saturday 6 AM IST."""
    from app.services.outcome_tracker import OutcomeTracker
    from app.services.gemini_feedback import GeminiFeedbackLoop
    logger.info(f"[Scheduler] Starting Weekly Self-Learning @ {datetime.now(IST).strftime('%H:%M IST')}")
    async with AsyncSessionLocal() as db:
        tracker = OutcomeTracker()
        stats = await tracker.track_outcomes(db, days_back=45)
        logger.info(f"[Scheduler] Outcomes processed: {stats}")
        
        perf = await tracker.get_pattern_performance(db)
        if perf:
            feedback = GeminiFeedbackLoop()
            new_config = await feedback.run_feedback_loop(perf)
            logger.info(f"[Scheduler] Feedback generated: {bool(new_config)}")


async def _run_forward_test_monthly_cohort() -> None:
    """Background job: Run or catch up Forward Validation monthly cohort freeze (Protocol v2.1.1)."""
    from app.services.forward_test import ForwardTestEngine
    from app.services.alert_manager import AlertManager

    logger.info(f"[Scheduler] Checking Forward Test monthly cohort status @ {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        async with AsyncSessionLocal() as db:
            res = await ForwardTestEngine.check_and_freeze_monthly_cohort_if_due(db)
            if res:
                logger.info(f"[Scheduler] Forward Cohort successfully frozen: {res.get('batch_id')}")
                try:
                    alert_mgr = AlertManager()
                    await alert_mgr.send_message(
                        f"🎯 **[TradeMatrix] Forward Cohort Frozen**\n\n"
                        f"• Batch: `{res.get('batch_id')}`\n"
                        f"• Cohort Type: `{res.get('cohort_type')}`\n"
                        f"• Market Regime: `{res.get('regime')}`\n"
                        f"• Scored Universe: `{res.get('eligible_universe_count')}` scrips\n"
                        f"• Capital Deployed: ₹{res.get('total_invested_inr', 0):,.2f}"
                    )
                except Exception as alert_err:
                    logger.warning(f"Could not dispatch success alert to Telegram: {alert_err}")
    except Exception as e:
        err_msg = f"🚨 **[TradeMatrix ALERT] Forward Test Freeze Failed**\n\nError: `{e}`"
        logger.error(f"[Scheduler ALERT] Forward Test monthly freeze check failed: {e}")
        try:
            alert_mgr = AlertManager()
            await alert_mgr.send_message(err_msg)
        except Exception as alert_err:
            logger.warning(f"Could not dispatch failure alert to Telegram: {alert_err}")


async def _run_daily_heartbeat() -> None:
    """Daily Telegram Heartbeat at 09:45 AM IST."""
    try:
        from app.services.alert_manager import AlertManager
        from app.services.fyers_data_client import FyersDataClient
        fyers = FyersDataClient()
        fyers_status = "Connected (" + (fyers.user_name or "OK") + ")" if fyers.is_connected() else "Disconnected"
        alert_mgr = AlertManager()
        await alert_mgr.send_message(
            f"💓 **[TradeMatrix Heartbeat] System Operational**\n\n"
            f"• Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            f"• Broker (Fyers): {fyers_status}\n"
            f"• Environment: Production (tradematrix-vm)\n"
            f"• Scheduler: Running 6 jobs\n"
            f"• Uptime: Healthy"
        )
        logger.info("[Scheduler] Daily Telegram Heartbeat dispatched successfully.")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to dispatch daily heartbeat: {e}")


async def _run_fyers_daily_login() -> None:
    """Daily Fyers TOTP Auto-Login at 6:45 AM IST to keep session active 24x7."""
    try:
        from app.services.fyers_data_client import FyersDataClient
        client = FyersDataClient()
        success = client.connect(force=True)
        if success:
            logger.info(f"Daily Fyers 24x7 Auto-Login successful for: {client.user_name}")
        else:
            logger.error("Daily Fyers 24x7 Auto-Login failed")
    except Exception as e:
        logger.error(f"Error during scheduled Fyers auto-login: {e}")


async def check_forward_test_catchup_on_startup() -> None:
    """Executes on application startup to catch up any missed monthly freeze if server was offline."""
    await _run_forward_test_monthly_cohort()


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

    # Weekly Self-Learning on Saturday 6:00 AM IST
    _scheduler.add_job(
        _run_weekly_self_learning,
        CronTrigger(
            day_of_week="sat",
            hour=6,
            minute=0,
            timezone=IST,
        ),
        id="weekly_self_learning",
        name="Weekly Self-Learning Feedback",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Forward Test Monthly Cohort Check (Runs every weekday morning at 9:30 AM IST)
    _scheduler.add_job(
        _run_forward_test_monthly_cohort,
        CronTrigger(
            day_of_week="mon-fri",
            hour=9,
            minute=30,
            timezone=IST,
        ),
        id="forward_test_monthly_freeze",
        name="Forward Test Monthly Cohort Freeze (Protocol v2.1.1)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily Fyers 24x7 Auto-Login at 6:45 AM IST (after 6:30 AM broker token reset)
    _scheduler.add_job(
        _run_fyers_daily_login,
        CronTrigger(
            hour=6,
            minute=45,
            timezone=IST,
        ),
        id="fyers_daily_autologin",
        name="Daily Fyers TOTP Auto-Login (24x7 Session)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily Telegram Heartbeat at 09:45 AM IST (after market open)
    _scheduler.add_job(
        _run_daily_heartbeat,
        CronTrigger(
            hour=9,
            minute=45,
            timezone=IST,
        ),
        id="daily_heartbeat",
        name="Daily Telegram Heartbeat (09:45 AM IST)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    logger.info("Scheduler configured with 6 jobs (including Forward Test, Fyers Auto-Login & Heartbeat)")
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
