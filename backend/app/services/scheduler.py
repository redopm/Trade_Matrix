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


async def _run_daily_ohlcv_sync() -> None:
    """Background job: Append today's daily candles across Nifty 500 + Indices at 3:38 PM IST."""
    from app.services.daily_history_store import DailyHistoryStore
    logger.info(f"[Scheduler] Starting daily Nifty 500 EOD OHLCV sync @ {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        res = await DailyHistoryStore.sync_full_universe(force_full=False)
        logger.info(
            f"[Scheduler] Daily OHLCV sync done: {res.get('stored_symbols')} symbols, "
            f"{res.get('total_daily_candles')} candles ({res.get('db_size_mb')} MB)"
        )
    except Exception as e:
        logger.error(f"[Scheduler] Daily OHLCV sync error: {e}")


async def _run_daily_prediction_audit() -> None:
    """Background job: Compare past Aladdin predictions vs today's actual candles at 3:42 PM IST."""
    from app.services.prediction_ledger import PredictionLedger
    try:
        res = await asyncio.to_thread(PredictionLedger.evaluate_all_pending_predictions)
        logger.info(
            f"[Scheduler] Prediction Audit done: evaluated={res.get('evaluated_now')}, "
            f"global_hit_rate={res.get('direction_hit_rate_pct')}%"
        )
    except Exception as e:
        logger.warning(f"[Scheduler] Daily prediction audit error: {e}")


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
    """Background job: Monitor open paper trades every 5 min during NSE market hours & run EOD cohort MTM."""
    from app.services.paper_trading import PaperTradingEngine
    from app.services.forward_test import ForwardTestEngine

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return
    total_mins = now_ist.hour * 60 + now_ist.minute
    if total_mins < (9 * 60 + 15) or total_mins > (15 * 60 + 45):
        return

    logger.info(f"[Scheduler] Updating paper trades @ {now_ist.strftime('%H:%M IST')}")
    async with AsyncSessionLocal() as db:
        engine = PaperTradingEngine()
        summary = await engine.update_open_trades(db)
        logger.info(f"[Scheduler] Trade update: {summary}")

        if now_ist.hour == 15 and 30 <= now_ist.minute <= 45:
            try:
                mtm_res = await ForwardTestEngine.update_and_evaluate_cohorts(db)
                logger.info(f"[Scheduler] Daily Forward Cohort MTM updated: {mtm_res}")
            except Exception as e_mtm:
                logger.warning(f"[Scheduler] Cohort MTM update failed: {e_mtm}")

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
    """Background job: Run or catch up Forward Validation monthly cohort freeze (Protocol v2.1.2)."""
    from app.services.forward_test import ForwardTestEngine

    logger.info(f"[Scheduler] Checking Forward Test monthly cohort status @ {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        async with AsyncSessionLocal() as db:
            res = await ForwardTestEngine.check_and_freeze_monthly_cohort_if_due(db)
            if res:
                logger.info(
                    f"[Scheduler] Forward Cohort frozen: {res.get('batch_id')} | "
                    f"Type={res.get('cohort_type')} | Regime={res.get('regime')} | "
                    f"Universe={res.get('eligible_universe_count')}"
                )
    except Exception as e:
        logger.error(f"[Scheduler] Forward Test monthly freeze check failed: {e}")


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


async def _run_enterprise_watchdog_job(phase: str = "EOD") -> None:
    """Enterprise pre-market & EOD health watchdog: self-heals gaps & refreshes pattern stats in background logs."""
    import asyncio
    import sys
    from app.config import _BACKEND_DIR
    from app.services.daily_history_store import DailyHistoryStore

    logger.info(f"[Watchdog Job] Running {phase} Enterprise Watchdog @ {datetime.now(IST).strftime('%H:%M IST')}")
    try:
        report = await asyncio.to_thread(DailyHistoryStore.run_enterprise_watchdog, True)
        if phase == "EOD":
            try:
                if str(_BACKEND_DIR) not in sys.path:
                    sys.path.insert(0, str(_BACKEND_DIR))
                from advanced_dataset_generator import run_empirical_pattern_benchmark
                await asyncio.to_thread(run_empirical_pattern_benchmark, 80, 5)
                report["ai_calibration"]["empirical_stats_ready"] = True
            except Exception as exc:
                logger.warning(f"[Watchdog Job] EOD empirical pattern refresh skipped: {exc}")

        ds = report.get("data_store") or {}
        infra = report.get("infrastructure") or {}
        broker = report.get("broker") or {}

        logger.info(
            f"[Watchdog Job] {phase} status={report.get('overall_status')} | "
            f"Broker={broker.get('connected')} | Store={ds.get('stored_symbols')}/{ds.get('target_universe_size')} "
            f"(20Y={ds.get('deep_10_20y_symbols')}) | DiskFree={infra.get('disk_free_gb')}GB"
        )
    except Exception as e:
        logger.error(f"[Watchdog Job] Failed ({phase}): {e}")


async def check_forward_test_catchup_on_startup() -> None:
    """Executes on application startup to catch up any missed monthly freeze if server was offline."""
    await _run_forward_test_monthly_cohort()


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=IST)

    # Daily Nifty 500 + Indices EOD OHLCV append at 3:38 PM IST (Mon-Fri, before screener)
    _scheduler.add_job(
        _run_daily_ohlcv_sync,
        CronTrigger(
            day_of_week="mon-fri",
            hour=15,
            minute=38,
            timezone=IST,
        ),
        id="daily_ohlcv_eod_sync",
        name="Daily Nifty 500 EOD Data Store Sync (15:38 IST)",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Closed-loop Prediction vs Actual Candle verification at 3:42 PM IST (Mon-Fri)
    _scheduler.add_job(
        _run_daily_prediction_audit,
        CronTrigger(
            day_of_week="mon-fri",
            hour=15,
            minute=42,
            timezone=IST,
        ),
        id="daily_prediction_audit",
        name="Daily Aladdin Prediction Accuracy Audit (15:42 IST)",
        replace_existing=True,
        misfire_grace_time=1800,
    )

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

    # Intraday SL / Target / P&L monitoring every 5 minutes (9:15 AM - 3:45 PM IST, Mon-Fri)
    _scheduler.add_job(
        _update_paper_trades,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="*/5",
            timezone=IST,
        ),
        id="pnl_update",
        name="Intraday Paper Trade SL/Target Monitor (5m)",
        replace_existing=True,
        misfire_grace_time=120,
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

    # Enterprise Pre-Market Watchdog at 9:05 AM IST (Mon-Fri)
    _scheduler.add_job(
        _run_enterprise_watchdog_job,
        args=["PRE_MARKET"],
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=9,
            minute=5,
            timezone=IST,
        ),
        id="enterprise_premarket_watchdog",
        name="Enterprise Pre-Market Health Watchdog (09:05 IST)",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # Enterprise Post-Market Watchdog + 20Y Empirical Pattern Refresh at 3:52 PM IST (Mon-Fri)
    _scheduler.add_job(
        _run_enterprise_watchdog_job,
        args=["EOD"],
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=15,
            minute=52,
            timezone=IST,
        ),
        id="enterprise_eod_watchdog",
        name="Enterprise EOD Health Watchdog & Pattern Refresh (15:52 IST)",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    logger.info("Scheduler configured with 9 jobs (OHLCV Sync, Prediction Audit, Watchdogs, Screener & Auto-Login)")
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
