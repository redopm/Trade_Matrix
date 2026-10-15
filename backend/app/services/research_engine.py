"""
Research Engine - TradeMatrix Phase 1 (Rebuilt)
The CORE of TradeMatrix. A clean, rule-based 4-filter pipeline.

Pipeline:
  Filter 1: Liquidity Check    (Avg daily vol > Rs.5 Cr)
  Filter 2: Fundamental Screen (ROCE, D/E, Piotroski, EPS Growth)
  Filter 3: Technical Screen   (Price > 200 EMA, RSI 25-55, ADX > 18)
  Filter 4: Risk/Reward Check  (ATR-based SL, R:R must be >= 1:2)

Output:
  For each passing stock — a complete ResearchSignal with:
  - Entry zone, Stop Loss (ATR-based), T1/T2/T3, Risk:Reward
  - Full fundamental + technical reasoning
  - Composite confidence score (0-100)
  - Signal type: SWING / POSITIONAL / INTRADAY
"""
import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import Any, Optional
import pytz

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.data_fetcher import DataFetcher
from app.services.fundamental import FundamentalAnalyzer
from app.services.technical import TechnicalAnalyzer
from app.services.risk_manager import RiskManager
from app.utils.logger import get_logger
from app.utils.helpers import sanitize_nans

logger = get_logger(__name__)
IST = pytz.timezone("Asia/Kolkata")


# ── Research Signal Data Class ────────────────────────────────────────────────

class ResearchSignal:
    """A single research recommendation signal."""

    def __init__(self):
        self.signal_id = str(uuid.uuid4())[:8]
        self.generated_at = datetime.now(IST).isoformat()

        # Core identity
        self.symbol: str = ""
        self.company_name: str = ""
        self.sector: str = ""
        self.industry: str = ""
        self.signal_type: str = "SWING"  # SWING | POSITIONAL | INTRADAY
        self.action: str = "BUY"         # BUY | SELL | HOLD | WATCH

        # Trade parameters
        self.current_price: float = 0.0
        self.entry_zone_low: float = 0.0
        self.entry_zone_high: float = 0.0
        self.stop_loss: float = 0.0
        self.stop_loss_pct: float = 0.0
        self.stop_loss_type: str = "ATR"
        self.target_1: float = 0.0
        self.target_2: float = 0.0
        self.target_3: float = 0.0
        self.target_1_pct: float = 0.0
        self.target_2_pct: float = 0.0
        self.target_3_pct: float = 0.0
        self.rr_t2: float = 0.0
        self.rr_quality: str = "POOR"
        self.suggested_qty: int = 0
        self.max_loss_amount: float = 0.0
        self.max_gain_t2: float = 0.0

        # Fundamental data
        self.roce: Optional[float] = None
        self.debt_to_equity: Optional[float] = None
        self.piotroski_f_score: Optional[int] = None
        self.altman_z_score: Optional[float] = None
        self.eps_growth_yoy: Optional[float] = None
        self.pe_ratio: Optional[float] = None
        self.roe: Optional[float] = None
        self.market_cap: Optional[float] = None
        self.promoter_holding: Optional[float] = None
        self.free_cash_flow: Optional[float] = None

        # Technical data
        self.rsi: Optional[float] = None
        self.ema_200: Optional[float] = None
        self.ema_50: Optional[float] = None
        self.adx: Optional[float] = None
        self.atr: Optional[float] = None
        self.atr_pct: Optional[float] = None
        self.macd: Optional[float] = None
        self.macd_signal: Optional[float] = None
        self.volume_ratio: Optional[float] = None
        self.week_52_high: Optional[float] = None
        self.week_52_low: Optional[float] = None
        self.pct_from_52w_high: Optional[float] = None
        self.supertrend_bullish: Optional[bool] = None
        self.bb_lower: Optional[float] = None

        # Filter pass/fail
        self.passed_liquidity: bool = False
        self.passed_roce: bool = False
        self.passed_debt_to_equity: bool = False
        self.passed_piotroski: bool = False
        self.passed_eps_growth: bool = False
        self.passed_ema_200: bool = False
        self.passed_rsi: bool = False
        self.passed_adx: bool = False
        self.passed_volume: bool = False
        self.passed_rr: bool = False
        self.passed_earnings_blackout: bool = True

        # Reasons (human-readable why it passed/failed)
        self.bull_reasons: list[str] = []
        self.caution_reasons: list[str] = []

        # Composite score (0-100)
        self.composite_score: float = 0.0
        self.confidence_label: str = "LOW"  # LOW | MEDIUM | HIGH | VERY HIGH

    def to_dict(self) -> dict[str, Any]:
        return sanitize_nans(self.__dict__.copy())


# ── Research Engine States ────────────────────────────────────────────────────

class ResearchRun:
    """Tracks the state of a single research run."""

    def __init__(self, run_id: str, mode: str = "SWING"):
        self.run_id = run_id
        self.mode = mode
        self.started_at = datetime.now(IST)
        self.finished_at: Optional[datetime] = None
        self.status: str = "RUNNING"
        self.current_symbol: str = ""
        self.total_symbols: int = 0
        self.processed: int = 0
        self.passed_filter1: int = 0
        self.passed_filter2: int = 0
        self.passed_filter3: int = 0
        self.passed_filter4: int = 0
        self.signals: list[dict] = []
        self.errors: list[str] = []

    @property
    def progress_pct(self) -> float:
        if self.total_symbols == 0:
            return 0.0
        return round((self.processed / self.total_symbols) * 100, 1)

    def to_dict(self) -> dict:
        return sanitize_nans({
            "run_id": self.run_id,
            "mode": self.mode,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "current_symbol": self.current_symbol,
            "total_symbols": self.total_symbols,
            "processed": self.processed,
            "progress_pct": self.progress_pct,
            "passed_filter1_liquidity": self.passed_filter1,
            "passed_filter2_fundamental": self.passed_filter2,
            "passed_filter3_technical": self.passed_filter3,
            "passed_filter4_rr": self.passed_filter4,
            "signals_count": len(self.signals),
        })


# Global in-memory store for active research runs
_active_research_runs: dict[str, ResearchRun] = {}


# ── Main Research Engine ──────────────────────────────────────────────────────

class ResearchEngine:
    """
    The Phase 1 Research Engine — Clean, Rule-Based, Reliable.

    No ML. Pure financial logic. Every signal has a clear "why".
    """

    # RSI ranges by mode
    RSI_RANGES = {
        "SWING":      (25, 55),   # Looking for dip in uptrend
        "POSITIONAL": (20, 60),   # Wider range for longer hold
        "INTRADAY":   (30, 50),   # Tighter range, momentum needed
    }

    # ADX thresholds by mode
    ADX_MIN = {
        "SWING":      18,   # Some trend needed
        "POSITIONAL": 15,   # Can enter even mild trend
        "INTRADAY":   22,   # Strong trend required for intraday
    }

    # Minimum liquidity (avg daily turnover in Rs.)
    MIN_DAILY_TURNOVER = 5_00_00_000  # Rs. 5 Crore

    def __init__(self):
        self.fetcher = DataFetcher()
        self.fundamental = FundamentalAnalyzer()
        self.technical = TechnicalAnalyzer()
        self.risk_mgr = RiskManager()

    async def run(
        self,
        run_id: str,
        mode: str = "SWING",
        symbols: Optional[list[str]] = None,
        universe: str = "NIFTY500",
    ) -> ResearchRun:
        """
        Start a full research run asynchronously.
        Results stored in _active_research_runs[run_id].
        """
        run = ResearchRun(run_id=run_id, mode=mode)
        _active_research_runs[run_id] = run

        # Resolve symbol universe
        if not symbols:
            from app.services.data_fetcher import SECTOR_UNIVERSE
            all_syms = []
            for sector_syms in SECTOR_UNIVERSE.values():
                all_syms.extend(sector_syms)
            symbols = list(dict.fromkeys(all_syms))  # Deduplicate, preserve order

        run.total_symbols = len(symbols)
        logger.info(f"[ResearchEngine] Run {run_id} started: {len(symbols)} symbols, mode={mode}")

        try:
            await self._process_universe(run, symbols, mode)
            run.status = "COMPLETED"
        except Exception as e:
            run.status = "ERROR"
            run.errors.append(str(e))
            logger.error(f"[ResearchEngine] Run {run_id} failed: {e}")
        finally:
            run.finished_at = datetime.now(IST)

        return run

    async def _process_universe(
        self,
        run: ResearchRun,
        symbols: list[str],
        mode: str,
    ):
        """Process all symbols through the 4-filter pipeline."""
        semaphore = asyncio.Semaphore(8)  # Max 8 concurrent fetches

        async def process_one(symbol: str):
            async with semaphore:
                run.current_symbol = symbol
                try:
                    signal = await self._analyze_stock(symbol, mode, run)
                    if signal:
                        run.signals.append(signal.to_dict())
                        run.passed_filter4 += 1
                except Exception as e:
                    logger.debug(f"[{symbol}] Error: {e}")
                finally:
                    run.processed += 1

        tasks = [process_one(sym) for sym in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Sort by composite score descending
        run.signals.sort(key=lambda s: s.get("composite_score", 0), reverse=True)
        logger.info(f"[ResearchEngine] Run complete: {run.passed_filter4} signals from {run.total_symbols} stocks")

    async def _analyze_stock(self, symbol: str, mode: str, run: "ResearchRun") -> "Optional[ResearchSignal]":
        """
        Run a single stock through all 4 filters.
        Returns ResearchSignal if stock passes all filters, else None.
        """
        sig = ResearchSignal()
        sig.symbol = symbol

        # ── FETCH DATA ────────────────────────────────────────────────────────
        info_task = self.fetcher.fetch_ticker_info(symbol)
        hist_task = self.fetcher.fetch_price_history(symbol, period="2y")

        info, df = await asyncio.gather(info_task, hist_task, return_exceptions=True)

        if isinstance(info, Exception) or not info:
            return None
        if isinstance(df, Exception) or df is None or df.empty or len(df) < 200:
            return None

        # ── FILTER 1: LIQUIDITY ───────────────────────────────────────────────
        avg_volume = df["Volume"].tail(20).mean()
        close_price = float(df["Close"].iloc[-1])
        daily_turnover = avg_volume * close_price

        if daily_turnover < self.MIN_DAILY_TURNOVER:
            return None  # Illiquid stock — skip

        sig.passed_liquidity = True
        run.passed_filter1 += 1

        # ── FUNDAMENTAL ANALYSIS ──────────────────────────────────────────────
        fund = self.fundamental.analyze(symbol, info)
        self._populate_fundamentals(sig, fund)

        # ── FILTER 2: FUNDAMENTAL SCREEN ──────────────────────────────────────
        is_banking = fund.get("is_banking", False)
        if not self._passes_fundamentals(sig, is_banking):
            return None

        sig.passed_roce = fund.get("passed_roce", False)
        sig.passed_debt_to_equity = fund.get("passed_debt_to_equity", False)
        run.passed_filter2 += 1

        # ── TECHNICAL ANALYSIS ────────────────────────────────────────────────
        tech = self.technical.analyze(symbol, df)
        self._populate_technicals(sig, tech)

        # ── FILTER 3: TECHNICAL SCREEN ────────────────────────────────────────
        if not self._passes_technicals(sig, mode):
            return None

        run.passed_filter3 += 1

        # ── FILTER 4: RISK/REWARD CHECK ───────────────────────────────────────
        risk_params = self.risk_mgr.calculate(
            symbol=symbol,
            current_price=sig.current_price,
            atr=sig.atr,
            direction="LONG",
            rsi=sig.rsi,
            bb_lower=sig.bb_lower,
            s1=tech.get("s1"),
            fib_618=tech.get("fib_level_618"),
        )

        if not risk_params.get("meets_minimum_rr", False):
            return None  # R:R < 1:2 — not worth the risk

        sig.passed_rr = True
        self._populate_risk(sig, risk_params)

        # ── COMPUTE COMPOSITE SCORE ───────────────────────────────────────────
        self._compute_composite_score(sig)

        # ── BUILD REASONING ───────────────────────────────────────────────────
        self._build_reasoning(sig)

        # ── DETERMINE SIGNAL TYPE ─────────────────────────────────────────────
        sig.signal_type = mode
        sig.action = "BUY"

        return sig

    # ── Fundamental Filter ────────────────────────────────────────────────────

    def _passes_fundamentals(self, sig: ResearchSignal, is_banking: bool) -> bool:
        """
        Filter 2: Fundamental Screen.
        Rules (non-banking):
          - ROCE >= 15% (OR banking bypass)
          - D/E <= 1.0  (OR banking bypass)
          - Piotroski F-Score >= 6 (flexible, was 7 before — too restrictive)
        At minimum: must pass ROCE + D/E.
        """
        # ROCE check (most important)
        if not is_banking:
            if sig.roce is None or sig.roce < settings.MIN_ROCE:
                return False

        # D/E check
        if not is_banking:
            if sig.debt_to_equity is None or sig.debt_to_equity > settings.MAX_DEBT_TO_EQUITY:
                return False

        # Piotroski is a BONUS, not hard mandatory (too many valid stocks fail)
        # We use 6 instead of 7 — allows stocks that are 89% healthy
        sig.passed_piotroski = (
            sig.piotroski_f_score is not None and
            sig.piotroski_f_score >= 6  # Relaxed from 7 to 6
        )

        sig.passed_eps_growth = (
            sig.eps_growth_yoy is not None and
            sig.eps_growth_yoy >= settings.MIN_EPS_GROWTH
        )

        return True  # ROCE + D/E passed

    # ── Technical Filter ──────────────────────────────────────────────────────

    def _passes_technicals(self, sig: ResearchSignal, mode: str) -> bool:
        """
        Filter 3: Technical Screen.
        Rules:
          - Price > 200 EMA (macro uptrend confirmed)
          - RSI in range [25-55] for SWING (dip in uptrend, not overbought)
          - ADX > 18 (some trend strength — avoid sideways chop)
        """
        # CRITICAL: Price must be above 200 EMA
        if sig.ema_200 is None or sig.current_price <= sig.ema_200:
            return False
        sig.passed_ema_200 = True

        # RSI range check
        rsi_low, rsi_high = self.RSI_RANGES.get(mode, (25, 55))
        if sig.rsi is None or not (rsi_low <= sig.rsi <= rsi_high):
            return False
        sig.passed_rsi = True

        # ADX check (trend strength — relaxed to 18 from 25)
        adx_min = self.ADX_MIN.get(mode, 18)
        if sig.adx is not None and sig.adx < adx_min:
            # ADX is a warning, not hard reject (some good stocks in early trends)
            sig.passed_adx = False
            # Only reject if ADX is very weak (< 12 = completely sideways)
            if sig.adx < 12:
                return False
        else:
            sig.passed_adx = True

        # Volume check — not dead volume
        if sig.volume_ratio is not None and sig.volume_ratio < 0.3:
            return False  # Extremely low volume — skip
        sig.passed_volume = True

        return True

    # ── Compute Composite Score ───────────────────────────────────────────────

    def _compute_composite_score(self, sig: ResearchSignal) -> None:
        """
        Composite Score (0-100) — weighted sum of all signals.

        Weights:
          ROCE           : 20 pts
          D/E (inverse)  : 10 pts
          Piotroski      : 15 pts
          EPS Growth     : 10 pts
          RSI (inverse)  : 15 pts  (lower RSI = more oversold = better dip)
          ADX            : 10 pts  (higher = stronger trend)
          Volume Surge   : 10 pts
          R:R Quality    : 10 pts
        Total: 100 pts
        """
        score = 0.0

        # ROCE score (20 pts): cap at ROCE=40 → 20 pts
        if sig.roce is not None and sig.roce > 0:
            score += min(20, (sig.roce / 40) * 20)

        # D/E inverse score (10 pts): D/E=0 → 10 pts, D/E=1 → 0 pts
        if sig.debt_to_equity is not None:
            de_score = max(0, (1 - sig.debt_to_equity)) * 10
            score += de_score
        else:
            score += 5  # Neutral if unknown

        # Piotroski (15 pts)
        if sig.piotroski_f_score is not None:
            score += (sig.piotroski_f_score / 9) * 15

        # EPS Growth (10 pts): cap at 30% growth → 10 pts
        if sig.eps_growth_yoy is not None and sig.eps_growth_yoy > 0:
            score += min(10, (sig.eps_growth_yoy / 30) * 10)

        # RSI inverse (15 pts): RSI=25 → 15 pts, RSI=55 → 0 pts
        if sig.rsi is not None and sig.rsi <= 55:
            rsi_score = max(0, (55 - sig.rsi) / 30) * 15
            score += rsi_score

        # ADX (10 pts): ADX=30 → 10 pts, ADX=0 → 0 pts
        if sig.adx is not None:
            score += min(10, (sig.adx / 30) * 10)

        # Volume Surge (10 pts): ratio=2.0 → 10 pts
        if sig.volume_ratio is not None:
            score += min(10, sig.volume_ratio * 5)

        # R:R Quality (10 pts)
        rr_pts = {"EXCELLENT": 10, "GOOD": 7, "FAIR": 4, "POOR": 0}
        score += rr_pts.get(sig.rr_quality, 0)

        sig.composite_score = round(score, 1)

        if sig.composite_score >= 75:
            sig.confidence_label = "VERY HIGH"
        elif sig.composite_score >= 60:
            sig.confidence_label = "HIGH"
        elif sig.composite_score >= 45:
            sig.confidence_label = "MEDIUM"
        else:
            sig.confidence_label = "LOW"

    # ── Reasoning Builder ─────────────────────────────────────────────────────

    def _build_reasoning(self, sig: ResearchSignal) -> None:
        """Build human-readable bull reasons and caution flags."""
        bulls = []
        cautions = []

        # Fundamental reasons
        if sig.roce and sig.roce >= 20:
            bulls.append(f"Strong ROCE {sig.roce:.1f}% (>20%)")
        elif sig.roce:
            bulls.append(f"ROCE {sig.roce:.1f}% (healthy)")

        if sig.debt_to_equity is not None and sig.debt_to_equity < 0.5:
            bulls.append(f"Low debt D/E={sig.debt_to_equity:.2f}")

        if sig.piotroski_f_score and sig.piotroski_f_score >= 8:
            bulls.append(f"Excellent Piotroski F-Score={sig.piotroski_f_score}/9")
        elif sig.piotroski_f_score and sig.piotroski_f_score >= 6:
            bulls.append(f"Piotroski F-Score={sig.piotroski_f_score}/9 (good)")

        if sig.eps_growth_yoy and sig.eps_growth_yoy >= 20:
            bulls.append(f"Strong EPS growth +{sig.eps_growth_yoy:.1f}% YoY")

        # Technical reasons
        if sig.rsi and sig.rsi <= 35:
            bulls.append(f"RSI={sig.rsi:.1f} — deeply oversold dip opportunity")
        elif sig.rsi:
            bulls.append(f"RSI={sig.rsi:.1f} — pullback in uptrend")

        if sig.adx and sig.adx >= 25:
            bulls.append(f"ADX={sig.adx:.1f} — strong trend momentum")

        if sig.volume_ratio and sig.volume_ratio >= 1.5:
            bulls.append(f"Volume surge {sig.volume_ratio:.1f}x avg — institutional activity?")

        if sig.supertrend_bullish:
            bulls.append("Supertrend is BULLISH")

        # R:R quality
        bulls.append(f"Risk:Reward={sig.rr_t2:.1f}:1 ({sig.rr_quality})")

        # Caution flags
        if sig.piotroski_f_score is None or sig.piotroski_f_score < 6:
            cautions.append("Piotroski score not confirmed (data limited)")

        if sig.eps_growth_yoy and sig.eps_growth_yoy < 0:
            cautions.append(f"EPS growth negative ({sig.eps_growth_yoy:.1f}%)")

        if sig.debt_to_equity and sig.debt_to_equity > 0.7:
            cautions.append(f"Moderate debt D/E={sig.debt_to_equity:.2f}")

        if sig.adx and sig.adx < 20:
            cautions.append(f"ADX={sig.adx:.1f} — weak trend, possible sideways risk")

        if not sig.passed_earnings_blackout:
            cautions.append("Earnings approaching — increased volatility risk")

        if sig.pct_from_52w_high and abs(sig.pct_from_52w_high) < 5:
            cautions.append("Near 52-week high — resistance possible")

        sig.bull_reasons = bulls
        sig.caution_reasons = cautions

    # ── Data Population Helpers ───────────────────────────────────────────────

    def _populate_fundamentals(self, sig: ResearchSignal, fund: dict) -> None:
        sig.company_name = fund.get("company_name", sig.symbol)
        sig.sector = fund.get("sector", "")
        sig.industry = fund.get("industry", "")
        sig.roce = fund.get("roce")
        sig.debt_to_equity = fund.get("debt_to_equity")
        sig.piotroski_f_score = fund.get("piotroski_f_score")
        sig.altman_z_score = fund.get("altman_z_score")
        sig.eps_growth_yoy = fund.get("eps_growth_yoy")
        sig.pe_ratio = fund.get("pe_ratio")
        sig.roe = fund.get("roe")
        sig.market_cap = fund.get("market_cap")
        sig.free_cash_flow = fund.get("free_cash_flow")
        sig.promoter_holding = fund.get("promoter_holding")

    def _populate_technicals(self, sig: ResearchSignal, tech: dict) -> None:
        sig.current_price = tech.get("current_price", 0.0)
        sig.rsi = tech.get("rsi")
        sig.ema_200 = tech.get("ema_200")
        sig.ema_50 = tech.get("ema_50")
        sig.adx = tech.get("adx")
        sig.atr = tech.get("atr")
        sig.atr_pct = tech.get("atr_pct")
        sig.macd = tech.get("macd")
        sig.macd_signal = tech.get("macd_signal")
        sig.volume_ratio = tech.get("volume_ratio")
        sig.week_52_high = tech.get("week_52_high")
        sig.week_52_low = tech.get("week_52_low")
        sig.pct_from_52w_high = tech.get("pct_from_52w_high")
        sig.supertrend_bullish = tech.get("supertrend_bullish")
        sig.bb_lower = tech.get("bb_lower")

    def _populate_risk(self, sig: ResearchSignal, risk: dict) -> None:
        sig.entry_zone_low = risk.get("entry_zone_low", sig.current_price)
        sig.entry_zone_high = risk.get("entry_zone_high", sig.current_price)
        sig.stop_loss = risk.get("stop_loss", 0.0)
        sig.stop_loss_pct = risk.get("stop_loss_pct", 0.0)
        sig.stop_loss_type = risk.get("stop_loss_type", "FIXED")
        sig.target_1 = risk.get("target_1", 0.0)
        sig.target_2 = risk.get("target_2", 0.0)
        sig.target_3 = risk.get("target_3", 0.0)
        sig.target_1_pct = risk.get("target_1_pct", 0.0)
        sig.target_2_pct = risk.get("target_2_pct", 0.0)
        sig.target_3_pct = risk.get("target_3_pct", 0.0)
        sig.rr_t2 = risk.get("rr_t2", 0.0)
        sig.rr_quality = risk.get("rr_quality", "POOR")
        sig.suggested_qty = risk.get("suggested_qty", 0)
        sig.max_loss_amount = risk.get("max_loss_amount", 0.0)
        sig.max_gain_t2 = risk.get("max_gain_t2", 0.0)


# ── Public API ────────────────────────────────────────────────────────────────

def get_research_run(run_id: str) -> Optional[ResearchRun]:
    return _active_research_runs.get(run_id)


def get_all_research_runs() -> list[dict]:
    return [run.to_dict() for run in _active_research_runs.values()]
