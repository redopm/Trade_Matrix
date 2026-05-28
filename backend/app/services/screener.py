"""
Alpha Screener Engine — Phase 1 Core
Combines fundamental + technical analysis to find high-quality oversold dip opportunities.

Strategy Rules:
  Fundamental:
    A1. ROCE > 15% (skip for banking)
    A2. D/E < 1.0 (skip for banking)
    
  Technical:
    B1. Price > 200 EMA (macro trend UP)
    B2. RSI(14) < 30 (short-term oversold)
  
  Event Risk:
    C1. Not within ±3 days of earnings date
  
  Trade Parameters:
    Entry: Market open next day
    SL: max(5%, 2×ATR) below entry
    Target: RSI > 70 OR 12% profit
"""
import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import Any, Optional
import pytz

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.signal import ScreenerSignal
from app.services.data_fetcher import DataFetcher
from app.services.fundamental import FundamentalAnalyzer
from app.services.technical import TechnicalAnalyzer
from app.services.pattern_detector import PatternDetector
from app.services.alert_manager import AlertManager
from app.utils.logger import get_logger

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")


class ScreenerRun:
    """Tracks the state of a single screener run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.started_at = datetime.now(IST)
        self.finished_at: Optional[datetime] = None
        self.total_symbols = 0
        self.processed = 0
        self.passed = 0
        self.failed_data = 0
        self.failed_fundamental = 0
        self.failed_technical = 0
        self.failed_event_risk = 0
        self.signals: list[dict] = []
        self.status: str = "RUNNING"
        self.current_symbol: str = ""
        self.errors: list[str] = []

    @property
    def progress_pct(self) -> float:
        if self.total_symbols == 0:
            return 0.0
        return round((self.processed / self.total_symbols) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_symbols": self.total_symbols,
            "processed": self.processed,
            "progress_pct": self.progress_pct,
            "passed": self.passed,
            "failed_data": self.failed_data,
            "failed_fundamental": self.failed_fundamental,
            "failed_technical": self.failed_technical,
            "failed_event_risk": self.failed_event_risk,
            "current_symbol": self.current_symbol,
            "signals_count": len(self.signals),
        }


# Global registry of active runs (in-memory)
_active_runs: dict[str, ScreenerRun] = {}


class AlphaScreener:
    """
    The Phase 1 Alpha Screener Engine.
    
    Screens Nifty 500 stocks for:
    - Fundamentally strong companies (ROCE, D/E, Piotroski)
    - Currently in technical dip (Price > 200 EMA, RSI < 30)
    - No upcoming earnings risk (Event Risk Filter)
    """

    def __init__(self) -> None:
        self.fetcher = DataFetcher()
        self.fundamental = FundamentalAnalyzer()
        self.technical = TechnicalAnalyzer()
        self.pattern_detector = PatternDetector()
        self.alert_manager = AlertManager()
        self.cfg = settings

    async def run_screener(
        self,
        db: AsyncSession,
        symbols: Optional[list[str]] = None,
        run_id: Optional[str] = None,
        websocket_callback=None,
    ) -> ScreenerRun:
        """
        Execute the full Alpha Screener on the given symbols.
        
        Args:
            db: Database session for saving signals
            symbols: List of symbols (defaults to Nifty 500)
            run_id: Optional run ID for tracking
            websocket_callback: async callable for real-time progress
        
        Returns:
            ScreenerRun object with all results
        """
        if not run_id:
            run_id = str(uuid.uuid4())

        symbols = symbols or self.fetcher.get_nifty500_symbols()
        run = ScreenerRun(run_id)
        run.total_symbols = len(symbols)
        _active_runs[run_id] = run

        logger.info(f"[{run_id}] Starting Alpha Screener on {len(symbols)} symbols")

        try:
            for i, symbol in enumerate(symbols):
                run.current_symbol = symbol
                run.processed = i

                if websocket_callback:
                    await websocket_callback(run.to_dict())

                try:
                    signal = await self._screen_single(symbol, run_id)
                    if signal:
                        run.signals.append(signal)
                        if signal["passed_all"]:
                            run.passed += 1
                            logger.info(
                                f"[{run_id}] ✅ {symbol} PASSED | "
                                f"ROCE={signal.get('roce')} "
                                f"RSI={signal.get('rsi_14')} "
                                f"Score={signal.get('composite_score')} | "
                                f"Pattern: {signal.get('pattern_name')} ({signal.get('pattern_confidence', 0):.0%})"
                            )
                            
                            # Phase 3: Send Live Alerts for Confluence Signals
                            if signal.get("pattern_name") != "no_pattern" and signal.get("pattern_confidence", 0) >= 0.70:
                                asyncio.create_task(
                                    self.alert_manager.send_signal_alert(
                                        signal, chart_path=signal.get("chart_image_path")
                                    )
                                )
                        else:
                            self._update_failure_counts(run, signal)
                    else:
                        run.failed_data += 1

                except Exception as e:
                    logger.error(f"[{run_id}] Error screening {symbol}: {e}")
                    run.errors.append(f"{symbol}: {str(e)}")
                    run.failed_data += 1

            run.processed = len(symbols)
            run.status = "COMPLETED"
            run.finished_at = datetime.now(IST)

            # Save all signals to database
            await self._save_signals(db, run)

            logger.info(
                f"[{run_id}] Screener COMPLETE | "
                f"{run.passed}/{len(symbols)} passed | "
                f"Duration: {(run.finished_at - run.started_at).seconds}s"
            )

        except Exception as e:
            run.status = "FAILED"
            run.finished_at = datetime.now(IST)
            logger.error(f"[{run_id}] Screener FAILED: {e}")

        finally:
            if websocket_callback:
                await websocket_callback(run.to_dict())

        return run

    async def _screen_single(
        self, symbol: str, run_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Screen a single stock symbol.
        Returns signal dict (with passed_all flag) or None on data failure.
        """
        signal_date = date.today().strftime("%Y-%m-%d")

        # ── Step 1: Fetch Data ────────────────────────────────────────────────
        info_task = self.fetcher.fetch_ticker_info(symbol)
        history_task = self.fetcher.fetch_price_history(symbol)
        info, df = await asyncio.gather(info_task, history_task)

        if info is None or df is None or df.empty:
            logger.debug(f"[{run_id}] {symbol}: No data")
            return None

        # ── Step 2: Fundamental Analysis ──────────────────────────────────────
        fund = self.fundamental.analyze(symbol, info)

        # ── Step 3: Technical Analysis ────────────────────────────────────────
        tech = self.technical.analyze(symbol, df)
        if "error" in tech:
            logger.debug(f"[{run_id}] {symbol}: Technical error - {tech['error']}")

        # ── Step 4: Event Risk Filter ─────────────────────────────────────────
        earnings_dates = await self.fetcher.get_earnings_dates(symbol)
        passed_event_risk = self._check_event_risk(earnings_dates)

        # ── Step 5: Composite Scoring ─────────────────────────────────────────
        composite_score = self._compute_composite_score(fund, tech)

        # ── Step 6: Overall Pass/Fail ─────────────────────────────────────────
        passed_all = (
            fund.get("fundamentals_passed", False)
            and tech.get("technicals_passed", False)
            and passed_event_risk
        )

        current_price = tech.get("current_price") or fund.get("current_price", 0)

        # ── Step 6.5: Pattern Detection (Hybrid Mode) ─────────────────────────
        pattern_data = {}
        if passed_all:
            pattern_result = await self.pattern_detector.detect(
                symbol=symbol,
                df=df,
                phase1_passed=passed_all,
                generate_chart=True,
            )
            pattern_data = {
                "pattern_name": pattern_result.get("pattern_name", "no_pattern"),
                "pattern_confidence": pattern_result.get("confidence", 0.0),
                "chart_image_path": pattern_result.get("chart_path"),
            }

        signal = {
            "symbol": symbol,
            "company_name": fund.get("company_name", symbol),
            "sector": fund.get("sector"),
            "signal_date": signal_date,
            "screener_run_id": run_id,

            # Fundamentals
            "roce": fund.get("roce"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "pe_ratio": fund.get("pe_ratio"),
            "promoter_holding": fund.get("promoter_holding"),
            "piotroski_f_score": fund.get("piotroski_f_score"),
            "eps_growth_yoy": fund.get("eps_growth_yoy"),

            # Technicals
            "signal_price": current_price,
            "ema_200": tech.get("ema_200"),
            "ema_50": tech.get("ema_50"),
            "rsi_14": tech.get("rsi"),
            "atr_14": tech.get("atr"),
            "macd": tech.get("macd"),
            "macd_signal": tech.get("macd_signal"),
            "volume": tech.get("volume"),
            "avg_volume_20d": tech.get("avg_volume_20d"),
            "adx": tech.get("adx"),
            "supertrend_bullish": tech.get("supertrend_bullish"),

            # Trade Parameters
            "suggested_entry": current_price,
            "suggested_sl": tech.get("atr_stop_loss"),
            "suggested_sl_fixed": tech.get("fixed_stop_loss"),
            "suggested_target": tech.get("target_price"),
            "risk_reward_ratio": tech.get("risk_reward_ratio"),

            # Filter Results
            "passed_roce": fund.get("passed_roce", False),
            "passed_debt_to_equity": fund.get("passed_debt_to_equity", False),
            "passed_ema_200": tech.get("passed_ema_200", False),
            "passed_rsi": tech.get("passed_rsi_oversold", False),
            "passed_piotroski": fund.get("passed_piotroski", False),
            "passed_earnings_blackout": passed_event_risk,
            "passed_all": passed_all,

            # Phase 2 Pattern Data
            "pattern_name": pattern_data.get("pattern_name"),
            "pattern_confidence": pattern_data.get("pattern_confidence"),
            "chart_image_path": pattern_data.get("chart_image_path"),

            # Score
            "composite_score": composite_score,

            # Additional context
            "market_cap": fund.get("market_cap"),
            "week_52_high": tech.get("week_52_high"),
            "week_52_low": tech.get("week_52_low"),
            "pct_from_52w_high": tech.get("pct_from_52w_high"),
            "altman_z_score": fund.get("altman_z_score"),
            "bb_lower": tech.get("bb_lower"),
            "bb_width": tech.get("bb_width"),
            "volume_ratio": tech.get("volume_ratio"),
        }

        return signal

    def _check_event_risk(self, earnings_dates: list[datetime]) -> bool:
        """
        Event Risk Filter: Block trades within ±N days of earnings.
        Returns True if safe to trade (no upcoming earnings).
        """
        if not earnings_dates:
            return True

        today = date.today()
        blackout = timedelta(days=self.cfg.EARNINGS_BLACKOUT_DAYS)

        for earnings_date in earnings_dates:
            if hasattr(earnings_date, "date"):
                ed = earnings_date.date()
            else:
                ed = earnings_date

            if abs((ed - today).days) <= self.cfg.EARNINGS_BLACKOUT_DAYS:
                logger.debug(f"Event risk: earnings on {ed}, blocking trade")
                return False

        return True

    def _compute_composite_score(
        self,
        fund: dict[str, Any],
        tech: dict[str, Any],
    ) -> float:
        """
        Compute a weighted composite score (0–100) for ranking signals.
        
        Weights:
          - ROCE (25%): Higher is better, normalized to 0-1 at ROCE=40
          - D/E (15%): Lower is better
          - RSI (20%): More oversold = higher score (RSI=20 → score=1)
          - Piotroski (20%): 0-9 normalized
          - EPS Growth (10%): Higher is better
          - Volume Ratio (10%): Close to 1 = normal, > 1 = interest building
        """
        score = 0.0

        # ROCE (0–25 points)
        roce = fund.get("roce")
        if roce is not None and roce > 0:
            score += min(25.0, (roce / 40.0) * 25.0)

        # D/E (0–15 points, inverse)
        de = fund.get("debt_to_equity")
        if de is not None:
            de_score = max(0, (1.0 - de) * 15.0) if de <= 1.0 else 0
            score += de_score

        # RSI (0–20 points, inverse — more oversold = higher score)
        rsi = tech.get("rsi")
        if rsi is not None and rsi <= 30:
            rsi_score = ((30 - rsi) / 30) * 20.0
            score += rsi_score

        # Piotroski (0–20 points)
        f_score = fund.get("piotroski_f_score")
        if f_score is not None:
            score += (f_score / 9.0) * 20.0

        # EPS Growth (0–10 points)
        eps_growth = fund.get("eps_growth_yoy")
        if eps_growth is not None and eps_growth > 0:
            score += min(10.0, (eps_growth / 30.0) * 10.0)

        # Volume Ratio (0–10 points)
        vol_ratio = tech.get("volume_ratio")
        if vol_ratio is not None and vol_ratio >= 0.5:
            score += min(10.0, vol_ratio * 5.0)

        return round(score, 2)

    async def _save_signals(
        self, db: AsyncSession, run: ScreenerRun
    ) -> None:
        """Persist all screener signals to the database."""
        try:
            for signal_data in run.signals:
                signal = ScreenerSignal(**{
                    k: v for k, v in signal_data.items()
                    if hasattr(ScreenerSignal, k) and k not in ("id", "created_at", "updated_at")
                })
                db.add(signal)
            await db.commit()
            logger.info(f"Saved {len(run.signals)} signals to database")
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")
            await db.rollback()

    @staticmethod
    def _update_failure_counts(run: ScreenerRun, signal: dict) -> None:
        """Update failure counters based on which filters failed."""
        if not signal.get("passed_roce") or not signal.get("passed_debt_to_equity"):
            run.failed_fundamental += 1
        elif not signal.get("passed_ema_200") or not signal.get("passed_rsi"):
            run.failed_technical += 1
        elif not signal.get("passed_earnings_blackout"):
            run.failed_event_risk += 1

    @staticmethod
    def get_active_run(run_id: str) -> Optional[ScreenerRun]:
        return _active_runs.get(run_id)

    @staticmethod
    def get_all_runs() -> list[ScreenerRun]:
        return list(_active_runs.values())
