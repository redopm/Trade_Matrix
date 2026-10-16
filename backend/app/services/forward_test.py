"""
Forward Validation Engine (Protocol v2.1)
Institutional Pre-Registered Empirical Trial Implementation

Dual-Ledger Architecture:
- Ledger A (Primary Shadow Research): Fixed 90-Day, Fractional %-per-rupee, Zero SL/TP truncation.
- Ledger B (Secondary Live Execution Desk): Integer shares, ₹25k slots, Dynamic ATR SL, 12% Target.

Evaluates Tool Top 10 against a 1,000-basket Monte Carlo random distribution from Nifty 100.
"""
import asyncio
import json
import numpy as np
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.trade import PaperTrade, TradeStatus, ForwardBatch, UniverseScoreSnapshot
from app.services.aladdin_brain import AladdinBrainEngine
from app.services.market_regime import MarketRegimeDetector
from app.services.data_fetcher import DataFetcher
from app.utils.nse_calendar import NSETradingCalendar
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Frozen Statutory Equity Delivery Friction Schedule (Discount Broker Standard)
# STT: 0.20% round-trip | Stamp: 0.015% | Exch+SEBI: 0.006% | GST: 0.001% | DP: 0.063% | Slippage: 0.10%
FROZEN_DELIVERY_FRICTION_PCT: float = 0.00385  # 0.385%
SCORING_FORMULA_VERSION: str = "ALADDIN_V2_5PILLAR"

# All files that directly define the stock scoring algorithm (excludes forward_test.py harness)
SCORING_CRITICAL_CODE_FILES: List[str] = [
    "backend/app/services/aladdin_brain.py",
    "backend/app/services/technical.py",
    "backend/app/services/fundamental.py",
    "backend/app/services/fibonacci.py",
    "backend/app/services/market_regime.py",
    "backend/app/services/data_fetcher.py",
]

# Model weight artifacts that directly drive the ML conviction pillar
SCORING_WEIGHTS_FILES: List[str] = [
    "backend/models/aladdin_classifier.pkl",
    "backend/models/aladdin_regressor.pkl",
    "backend/models/aladdin_feature_names.json",
    "backend/models/expert_model_weights.pth",
]

# Pre-registered Nifty 100 Eligible Universe (Top liquid, high-turnover blue chips)
NIFTY100_ELIGIBLE_UNIVERSE: List[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "INFY", "ITC", "SBIN",
    "LT", "HINDUNILVR", "BAJFINANCE", "M&M", "HCLTECH", "KOTAKBANK", "SUNPHARMA",
    "MARUTI", "AXISBANK", "TITAN", "ULTRACEMCO", "NTPC", "POWERGRID", "ONGC",
    "TATAMOTORS", "ADANIENT", "TATASTEEL", "COALINDIA", "BAJAJFINSV", "JSWSTEEL",
    "ASIANPAINT", "GRASIM", "TECHM", "LTIM", "ADANIPORTS", "WIPRO", "HINDALCO",
    "NESTLEIND", "BPCL", "HEROMOTOCO", "INDUSINDBK", "CIPLA", "APOLLOHOSP", "DIVISLAB",
    "EICHERMOT", "BRITANNIA", "TATACONSUM", "DRREDDY", "SHRIRAMFIN", "SBILIFE", "HDFCLIFE",
    "BEL", "HAL", "PERSISTENT", "TRENT", "DIXON", "KAYNES", "BSE", "MCX",
    "FEDERALBNK", "POLYCAB", "CUMMINSIND", "SIEMENS", "ABB", "VOLTAS", "CHOLAFIN",
    "MUTHOOTFIN", "TVSMOTOR", "BAJAJ-AUTO", "AMBUJACEM", "ACC", "DLF", "LODHA",
    "GODREJCP", "DABUR", "MARICO", "COLPAL", "PIDILITIND", "BERGEPAINT", "HAVELLES",
    "ASTRAL", "SUPREMEIND", "TORNTPHARM", "MANAPPURAM", "CANBK", "PNB", "BANKBARODA",
    "IDFCFIRSTB", "AUBANK", "MAXHEALTH", "LUPIN", "ALKEM", "AUROPHARMA", "ZYDUSLIFE",
    "PIIND", "UPL", "COROMANDEL", "SRF", "DEEPAKNTR", "NAVINFLUOR", "PAGEIND"
]


class ForwardTestEngine:
    """
    Core empirical trial engine for Pre-Registered Forward Protocol v2.1.
    """

    @staticmethod
    def get_scoring_weights_hash() -> str:
        """Computes SHA256 content hash of active model weights to detect any silent retraining."""
        h = hashlib.sha256()
        found_any = False
        for p_str in SCORING_WEIGHTS_FILES:
            p = Path(p_str)
            if p.exists():
                h.update(p.read_bytes())
                found_any = True
        return h.hexdigest()[:8] if found_any else "NOWEIGHTS"

    @staticmethod
    def get_scoring_git_hash(enforce_clean: bool = True) -> str:
        """
        Extract exact git commit SHA and weights fingerprint for audit tracking.
        Enforces a clean git working tree on scoring-critical files only,
        preventing accidental refusal due to unrelated workspace files (notes, scratch scripts, docs).
        Harness files like forward_test.py are excluded so harness display tweaks do not alter scoring fingerprint.
        """
        try:
            if enforce_clean:
                status_res = subprocess.run(
                    ["git", "status", "--porcelain", "--"] + SCORING_CRITICAL_CODE_FILES,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                dirty_lines = [line.strip() for line in status_res.stdout.splitlines() if line.strip()]
                if dirty_lines:
                    raise RuntimeError(
                        f"Cohort freeze rejected: Scoring logic has uncommitted modifications ({len(dirty_lines)} files):\n"
                        + "\n".join(dirty_lines)
                        + "\nProtocol v2.1.1 requires scoring code changes to be committed before freezing an empirical cohort."
                    )

            # Get the commit hash that last touched any scoring file
            res = subprocess.run(
                ["git", "log", "-1", "--format=%h", "--"] + SCORING_CRITICAL_CODE_FILES,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            scoring_hash = res.stdout.strip()
            if not scoring_hash:
                head_res = subprocess.run(
                    ["git", "rev-parse", "--short=7", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5
                )
                scoring_hash = head_res.stdout.strip()

            weights_hash = ForwardTestEngine.get_scoring_weights_hash()
            return f"{scoring_hash}+{weights_hash}"
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Failed retrieving scoring git hash: {e}")
            raise RuntimeError(f"Scoring git commit hash could not be retrieved: {e}")

    @staticmethod
    def calculate_delivery_friction(entry_price: float, exit_price: float, qty: int) -> float:
        """
        Calculates exact statutory delivery friction for a round-trip equity trade.
        Returns friction in INR.
        """
        turnover = (entry_price + exit_price) * qty
        stt = turnover * 0.0010              # 0.10% buy + 0.10% sell = 0.20% on turnover
        stamp = (entry_price * qty) * 0.00015 # 0.015% on buy turnover
        exchange_turnover = turnover * 0.0000307 # ~0.003%
        gst = exchange_turnover * 0.18
        dp_charges = 15.93                   # Flat per scrip on sell
        slippage = turnover * 0.0005         # 0.05% entry + 0.05% exit = 0.10%
        return round(stt + stamp + exchange_turnover + gst + dp_charges + slippage, 2)

    @classmethod
    async def freeze_cohort(
        cls,
        db: AsyncSession,
        cohort_type: str = "PRIMARY", # 'PILOT' or 'PRIMARY'
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an immutable cohort freeze at T=0.
        
        1. Snapshots Nifty 50 base price and market regime.
        2. Scores all eligible Nifty 100 stocks.
        3. Records Ledger A (Primary Shadow: full universe snapshot).
        4. Selects Tool Top 10.
        5. Deploys Ledger B (Secondary Live: 10 paper trades @ ₹25k slot).
        6. Commits ForwardBatch metadata.
        """
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        git_hash = cls.get_scoring_git_hash()
        seed = int(date_str)

        # 1. Macro Regime & Nifty 50 Base Level
        regime_data = await MarketRegimeDetector.get_current_regime()
        nifty_price = float(regime_data.get("nifty_price") or 25000.0)
        nifty_ema200 = float(regime_data.get("nifty_ema200") or 24500.0)
        regime_tag = "DEFENSIVE" if (nifty_price < nifty_ema200) else "BULLISH"

        if not batch_id:
            batch_id = f"COHORT_{'0_PILOT' if cohort_type == 'PILOT' else '1'}_{date_str}_{regime_tag}"

        # 2. Check if batch already exists
        existing_batch = await db.execute(select(ForwardBatch).where(ForwardBatch.batch_id == batch_id))
        if existing_batch.scalar_one_or_none():
            raise ValueError(f"Cohort '{batch_id}' has already been frozen. Modification is strictly prohibited.")

        logger.info(f"Initiating Forward Cohort Freeze: {batch_id} (Type: {cohort_type}, Regime: {regime_tag})")

        # 3. Score Full Eligible Universe (Nifty 100)
        brain = AladdinBrainEngine()
        as_of_date = now.date()
        universe_scores = []
        for sym in NIFTY100_ELIGIBLE_UNIVERSE:
            try:
                diag = await brain.diagnose_stock(sym, force_refresh=True, as_of_date=as_of_date)
                if not diag.get("error") and diag.get("current_price"):
                    universe_scores.append({
                        "symbol": sym,
                        "company_name": diag.get("company_name") or sym,
                        "sector": diag.get("sector") or "General",
                        "composite_score": float(diag.get("composite_score") or 50.0),
                        "current_price": float(diag.get("current_price")),
                        "stop_loss": float(diag.get("stop_loss") or (diag.get("current_price") * 0.95)),
                        "target_price": float(diag.get("target_1") or (diag.get("current_price") * 1.12)),
                        "atr": float(diag.get("atr_at_entry") or 0.0),
                    })
            except Exception as e:
                logger.warning(f"ForwardTestEngine: Failed scoring {sym}: {e}")

        if len(universe_scores) < 10:
            raise RuntimeError(f"Insufficient universe scored ({len(universe_scores)} stocks). Market data stream required.")

        # Sort universe by composite score descending
        universe_scores.sort(key=lambda x: x["composite_score"], reverse=True)
        top10_symbols = {x["symbol"] for x in universe_scores[:10]}

        # 4. Insert Ledger A: Full Universe Score Snapshot
        snapshot_records = []
        for stock in universe_scores:
            is_top = stock["symbol"] in top10_symbols
            rec = UniverseScoreSnapshot(
                batch_id=batch_id,
                symbol=stock["symbol"],
                company_name=stock["company_name"],
                sector=stock["sector"],
                composite_score=stock["composite_score"],
                is_top10=is_top,
                entry_price=stock["current_price"],
                notes=f"Frozen at T=0. Score: {stock['composite_score']:.1f}%"
            )
            db.add(rec)
            snapshot_records.append(rec)

        # 5. Insert Ledger B: Secondary Live Paper Execution Desk (Tool Top 10 @ ₹25k slots)
        slot_capital = settings.FORWARD_TEST_SLOT_CAPITAL # ₹25,000
        forward_pool = getattr(settings, "FORWARD_TEST_CAPITAL_POOL", 1_000_000.0)
        
        # Check active live forward test capital
        active_fwd_stmt = select(func.sum(PaperTrade.invested_amount)).where(
            and_(PaperTrade.batch_id.isnot(None), PaperTrade.status == TradeStatus.OPEN)
        )
        res_cap = await db.execute(active_fwd_stmt)
        active_fwd_allocated = float(res_cap.scalar() or 0.0)
        available_fwd_capital = forward_pool - active_fwd_allocated

        fetcher = DataFetcher()
        live_trades = []
        for stock in universe_scores[:10]:
            p = stock["current_price"]
            try:
                live_p = await asyncio.wait_for(fetcher.fetch_current_price(stock["symbol"]), timeout=2.0)
                if live_p and live_p > 0:
                    p = live_p
            except Exception:
                pass
            qty = max(1, int(slot_capital / p))
            invested = round(qty * p, 2)
            friction = round(invested * FROZEN_DELIVERY_FRICTION_PCT, 2)

            # Strict ring-fenced capital check for Ledger B
            if available_fwd_capital < invested:
                logger.warning(
                    f"[FORWARD_LEDGER_B_REJECT] Trade for {stock['symbol']} rejected: "
                    f"Forward Test capital pool (₹{forward_pool:,.2f}) exhausted. "
                    f"Available: ₹{available_fwd_capital:,.2f}, Required: ₹{invested:,.2f}."
                )
                continue

            available_fwd_capital -= invested
            trade = PaperTrade(
                batch_id=batch_id,
                experiment_arm="TOOL_TOP10",
                regime_tag=regime_tag,
                symbol=stock["symbol"],
                company_name=stock["company_name"],
                sector=stock["sector"],
                entry_date=now.strftime("%Y-%m-%d"),
                entry_price=p,
                quantity=qty,
                invested_amount=invested,
                stop_loss=stock["stop_loss"],
                stop_loss_fixed=round(p * 0.95, 2),
                target_price=stock["target_price"],
                atr_at_entry=stock.get("atr") or 0.0,
                nifty_entry_price=nifty_price,
                friction_cost=FROZEN_DELIVERY_FRICTION_PCT,
                status=TradeStatus.OPEN,
                notes=f"Protocol v2.1.1 Cohort {cohort_type} | Aladdin Top 10 Rank | Score: {stock['composite_score']:.1f}%"
            )
            db.add(trade)
            live_trades.append(trade)

        # 6. Calculate Score Distribution & Sector Exposure
        scores_arr = [s["composite_score"] for s in universe_scores]
        score_dist = {
            "min": round(float(np.min(scores_arr)), 2),
            "max": round(float(np.max(scores_arr)), 2),
            "mean": round(float(np.mean(scores_arr)), 2),
            "median": round(float(np.median(scores_arr)), 2),
            "std": round(float(np.std(scores_arr)), 2),
            "top10_threshold": round(float(universe_scores[9]["composite_score"]), 2),
        }

        top10_sectors = dict(Counter(s["sector"] for s in universe_scores[:10]))
        universe_sectors = dict(Counter(s["sector"] for s in universe_scores))
        defensive_sectors = {"Technology", "Healthcare", "Consumer Defensive", "Utilities"}
        defensive_count = sum(top10_sectors.get(sec, 0) for sec in defensive_sectors)
        
        sector_exp = {
            "top10_sector_counts": top10_sectors,
            "universe_sector_counts": universe_sectors,
            "defensive_stocks_in_top10": defensive_count,
            "defensive_weight_pct": round((defensive_count / 10.0) * 100.0, 1),
        }

        # 7. Insert ForwardBatch Metadata Record
        batch_meta = ForwardBatch(
            batch_id=batch_id,
            created_at=now,
            cohort_type=cohort_type,
            status="ACTIVE",
            regime=regime_tag,
            nifty_base_price=nifty_price,
            scoring_git_hash=git_hash,
            scoring_formula_version=SCORING_FORMULA_VERSION,
            random_seed=seed,
            eligible_universe_count=len(universe_scores),
            tool_stock_count=10,
            control_basket_count=1000,
            slot_capital_inr=slot_capital,
            total_allocated_inr=sum(t.invested_amount for t in live_trades),
            sector_exposure=json.dumps(sector_exp),
            score_distribution=json.dumps(score_dist),
        )
        db.add(batch_meta)
        await db.commit()

        logger.info(
            f"Cohort {batch_id} successfully frozen! "
            f"Ledger A: {len(universe_scores)} snapshot stocks (Mean score: {score_dist['mean']}%, Top10 defensive weight: {sector_exp['defensive_weight_pct']}%). "
            f"Ledger B: {len(live_trades)} live trades deployed (Total invested: ₹{batch_meta.total_allocated_inr:,.2f})."
        )

        return {
            "batch_id": batch_id,
            "cohort_type": cohort_type,
            "status": "ACTIVE",
            "regime": regime_tag,
            "nifty_base_price": nifty_price,
            "scoring_git_hash": git_hash,
            "random_seed": seed,
            "eligible_universe_count": len(universe_scores),
            "tool_top10": [
                {
                    "rank": i + 1,
                    "symbol": s["symbol"],
                    "score": s["composite_score"],
                    "price": s["current_price"],
                    "qty": max(1, int(slot_capital / s["current_price"]))
                }
                for i, s in enumerate(universe_scores[:10])
            ],
            "total_invested_inr": batch_meta.total_allocated_inr,
            "frozen_at": now.strftime("%Y-%m-%d %H:%M:%S IST")
        }

    @classmethod
    def run_1000_monte_carlo_baskets(
        cls,
        universe_symbols: List[str],
        returns_map: Dict[str, float],
        tool_top10_symbols: List[str],
        seed: int,
        k_baskets: int = 1000,
        basket_size: int = 10,
        friction_pct: float = FROZEN_DELIVERY_FRICTION_PCT
    ) -> Dict[str, Any]:
        """
        Pure offline simulation of 1,000 pseudo-random 10-stock equal-weight baskets.
        - Primary Delta: Tool Net Return minus Universe Equal-Weight Exact Net Return.
        - Monte Carlo Distribution: Evaluates Control Mean, Std, and Empirical Percentile/p-value.
        """
        rng = np.random.RandomState(seed)
        eligible = [s for s in universe_symbols if s in returns_map]
        if len(eligible) < basket_size:
            raise ValueError(f"Insufficient returns data: only {len(eligible)} eligible stocks available.")

        # Tool 10 Equal-Weighted Net Return
        tool_rets = [returns_map[s] for s in tool_top10_symbols if s in returns_map]
        tool_gross = float(np.mean(tool_rets)) if tool_rets else 0.0
        tool_net = tool_gross - (friction_pct * 100.0)

        # Exact Universe Equal-Weighted Return (Primary Deterministic Benchmark)
        universe_gross = float(np.mean([returns_map[s] for s in eligible]))
        universe_net = universe_gross - (friction_pct * 100.0)
        exact_delta = round(tool_net - universe_net, 4)

        # 1,000 Random Baskets Net Returns
        basket_net_returns = []
        for _ in range(k_baskets):
            chosen = rng.choice(eligible, size=basket_size, replace=False)
            gross = float(np.mean([returns_map[s] for s in chosen]))
            net = gross - (friction_pct * 100.0)
            basket_net_returns.append(net)

        basket_net_returns = np.array(basket_net_returns)
        control_mean = float(np.mean(basket_net_returns))
        control_std = float(np.std(basket_net_returns))

        # Empirical p-value: Fraction of random baskets that beat or matched the Tool basket
        beat_count = int(np.sum(basket_net_returns >= tool_net))
        p_val = round(beat_count / k_baskets, 4)
        percentile = round((1.0 - p_val) * 100.0, 2)

        return {
            "tool_top10_net_return_pct": round(tool_net, 4),
            "universe_exact_net_return_pct": round(universe_net, 4),
            "control_mean_net_return_pct": round(control_mean, 4),
            "control_std_pct": round(control_std, 4),
            "delta_excess_return_pct": exact_delta,
            "empirical_p_value": p_val,
            "tool_percentile_rank": percentile,
            "k_baskets": k_baskets,
            "seed": seed
        }

    @classmethod
    def run_sector_matched_baskets(
        cls,
        universe_symbols: List[str],
        returns_map: Dict[str, float],
        stock_to_sector: Dict[str, str],
        tool_top10_symbols: List[str],
        seed: int,
        k_baskets: int = 1000,
        friction_pct: float = FROZEN_DELIVERY_FRICTION_PCT
    ) -> Dict[str, Any]:
        """
        Secondary Diagnostic (Control 2): 1,000 Sector-Matched Random Baskets.
        Matches the exact sector quota of Tool Top 10 (e.g. 2 IT, 3 Pharma, etc.)
        to decompose alpha into:
        - Sector Allocation Effect = SectorMatched_Mean - Universe_Mean
        - Within-Sector Selection Skill = Tool_Net - SectorMatched_Mean
        """
        rng = np.random.RandomState(seed + 999)
        tool_sectors = [stock_to_sector.get(s, "General") for s in tool_top10_symbols]
        sector_counts = Counter(tool_sectors)
        
        # Group eligible stocks by sector
        sector_buckets: Dict[str, List[str]] = {}
        for s in universe_symbols:
            if s in returns_map:
                sec = stock_to_sector.get(s, "General")
                sector_buckets.setdefault(sec, []).append(s)

        tool_rets = [returns_map[s] for s in tool_top10_symbols if s in returns_map]
        tool_net = (float(np.mean(tool_rets)) if tool_rets else 0.0) - (friction_pct * 100.0)

        basket_returns = []
        for _ in range(k_baskets):
            chosen = []
            for sec, count in sector_counts.items():
                pool = sector_buckets.get(sec, [])
                if len(pool) >= count:
                    chosen.extend(rng.choice(pool, size=count, replace=False))
                else:
                    chosen.extend(pool)
                    needed = count - len(pool)
                    other_pool = [x for x in universe_symbols if x in returns_map and x not in chosen]
                    if other_pool:
                        chosen.extend(rng.choice(other_pool, size=min(needed, len(other_pool)), replace=False))
            gross = float(np.mean([returns_map[s] for s in chosen])) if chosen else 0.0
            net = gross - (friction_pct * 100.0)
            basket_returns.append(net)

        control2_mean = float(np.mean(basket_returns)) if basket_returns else 0.0
        control2_std = float(np.std(basket_returns)) if basket_returns else 0.0
        selection_alpha = round(tool_net - control2_mean, 4)

        return {
            "control2_sector_matched_mean_pct": round(control2_mean, 4),
            "control2_std_pct": round(control2_std, 4),
            "within_sector_selection_alpha_pct": selection_alpha,
            "k_baskets": k_baskets,
            "seed": seed + 999
        }

    @classmethod
    def calculate_spearman_rho(
        cls,
        scores: List[float],
        returns: List[float]
    ) -> float:
        """
        Calculates Spearman's rank correlation coefficient (rho) between scores and forward returns.
        """
        if len(scores) < 5 or len(scores) != len(returns):
            return 0.0

        scores_arr = np.array(scores)
        returns_arr = np.array(returns)

        # Rank data
        rank_s = np.argsort(np.argsort(scores_arr))
        rank_r = np.argsort(np.argsort(returns_arr))

        n = len(scores)
        d_sq = np.sum((rank_s - rank_r) ** 2)
        rho = 1.0 - (6.0 * d_sq) / (n * (n**2 - 1))
        return round(float(rho), 4)

    @classmethod
    async def get_protocol_scorecard(cls, db: AsyncSession) -> Dict[str, Any]:
        """
        Computes the unified pre-registered forward scorecard across all completed cohorts.
        Applies between-cohort standard error SE = s / sqrt(K).
        """
        # Fetch all batches
        stmt = select(ForwardBatch).order_by(ForwardBatch.created_at)
        res = await db.execute(stmt)
        batches = res.scalars().all()

        pilot_batches = [b for b in batches if b.cohort_type == "PILOT"]
        primary_batches = [b for b in batches if b.cohort_type == "PRIMARY"]
        completed_primary = [b for b in primary_batches if b.status == "COMPLETED"]

        k_completed = len(completed_primary)
        k_target = 9

        deltas = [b.delta_excess_return_pct for b in completed_primary if b.delta_excess_return_pct is not None]
        rhos = [b.spearman_rho for b in completed_primary if b.spearman_rho is not None]

        mean_delta = float(np.mean(deltas)) if deltas else 0.0
        std_delta = float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 5.0
        se_delta = round(std_delta / np.sqrt(max(1, len(deltas))), 4) if deltas else 1.67

        # 95% Confidence Interval across cohorts
        t_crit = 2.306 if len(deltas) >= 9 else (2.776 if len(deltas) >= 5 else 3.182)
        ci_lower = round(mean_delta - (t_crit * se_delta), 4)
        ci_upper = round(mean_delta + (t_crit * se_delta), 4)

        # Decision Hurdle Status (Protocol v2.1.1: Single Criterion CI_lower > 0 with 1.0% Economic Floor)
        if k_completed < k_target:
            decision = f"IN_PROGRESS ({k_completed} of {k_target} completed cohorts)"
            decision_color = "blue"
            decision_desc = f"Empirical forward trial active. Pre-registered sunset evaluated strictly after all {k_target} cohorts complete."
        else:
            if ci_lower > 0.0 and mean_delta >= 1.0:
                decision = "PASS (suggestive): ALGORITHMIC EDGE SUGGESTED UNDER OVERLAPPING COHORT ASSUMPTIONS"
                decision_color = "emerald"
                decision_desc = (
                    f"Suggestive algorithmic edge detected: 95% CI lower bound (+{ci_lower:.2f}%) strictly cleared 0.0%, "
                    f"and mean excess return (+{mean_delta:.2f}%) cleared economic floor (>=1.0% per 90d). "
                    f"Caveat: Due to 90-day cohort overlap, observations are not strictly independent; "
                    f"do not allocate large institutional capital solely based on this forward trial."
                )
            elif mean_delta <= 0.0:
                decision = "SUNSET: ZERO EMPIRICAL ALPHA (SYSTEM RETIRED)"
                decision_color = "rose"
                decision_desc = "Tool basket does not beat universe equal-weight mean. Stock-selection engine permanently decommissioned."
            else:
                decision = "INCONCLUSIVE: STATISTICALLY NOISY"
                decision_color = "amber"
                decision_desc = f"Mean Alpha was positive (+{mean_delta:.2f}%), but CI lower bound ({ci_lower:.2f}%) did not clear 0.0%."

        return {
            "protocol_version": "v2.1.1 (Dual-Ledger Pre-Registered)",
            "deadline": "2027-10-16",
            "scoring_formula": SCORING_FORMULA_VERSION,
            "target_cohorts_k": k_target,
            "completed_cohorts_k": k_completed,
            "active_batches_count": len([b for b in batches if b.status == "ACTIVE"]),
            "unified_primary_metric": {
                "metric_name": "Tool Top 10 Net Return minus Universe Equal-Weight Exact Net Return",
                "mean_delta_pct": round(mean_delta, 2),
                "cross_cohort_se_pct": round(se_delta, 2),
                "confidence_interval_95": [ci_lower, ci_upper],
                "assumed_sd_reference_pct": 5.0,
                "min_detectable_edge_pct": 3.85,
                "annualized_equivalent_pct": round(mean_delta * 4.0, 2),
            },
            "secondary_diagnostics": {
                "mean_spearman_rho": round(float(np.mean(rhos)), 3) if rhos else 0.0,
                "frozen_delivery_friction_pct": FROZEN_DELIVERY_FRICTION_PCT * 100.0,
                "benchmark": "Nifty 50 TRI",
                "control_2": "1,000 Sector-Matched Random Baskets",
            },
            "decision_rule": {
                "status": decision,
                "color": decision_color,
                "explanation": decision_desc
            },
            "batches_ledger": [
                {
                    "batch_id": b.batch_id,
                    "cohort_type": b.cohort_type,
                    "status": b.status,
                    "regime": b.regime,
                    "created_at": b.created_at.strftime("%Y-%m-%d") if hasattr(b.created_at, "strftime") else str(b.created_at)[:10],
                    "nifty_base": b.nifty_base_price,
                    "tool_net_return_pct": b.tool_avg_return_pct,
                    "control_mean_pct": b.control_mean_return_pct,
                    "delta_alpha_pct": b.delta_excess_return_pct,
                    "percentile_rank": b.monte_carlo_percentile,
                    "sector_exposure": json.loads(b.sector_exposure) if getattr(b, "sector_exposure", None) else None,
                    "score_distribution": json.loads(b.score_distribution) if getattr(b, "score_distribution", None) else None,
                }
                for b in batches
            ]
        }

    @classmethod
    async def check_and_freeze_monthly_cohort_if_due(
        cls, db: AsyncSession, target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Automated monthly freeze and missed-run catchup logic.
        1. Checks current year and month.
        2. Determines first trading day of the month using NSETradingCalendar.
        3. If today >= first trading day of the month:
           - Checks if a PRIMARY cohort already exists for this YYYYMM.
           - If not, triggers freeze_cohort and logs audit info.
        """
        now = datetime.now()
        today = target_date if target_date is not None else now.date()

        # Cohort 1 starts in November 2026 (Cohort 0 was October Pilot)
        if today < date(2026, 11, 1):
            return None

        first_trading_day = NSETradingCalendar.get_first_trading_day_of_month(today.year, today.month)
        if today < first_trading_day:
            return None

        cohort_num = (today.year - 2026) * 12 + (today.month - 11) + 1
        if cohort_num < 1 or cohort_num > 9:
            return None

        month_prefix = f"COHORT_{cohort_num}_{today.strftime('%Y%m')}"
        stmt = select(ForwardBatch).where(ForwardBatch.batch_id.like(f"{month_prefix}%"))
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return None

        is_catchup = (today > first_trading_day)
        cohort_type = "CATCHUP_LATE" if is_catchup else "PRIMARY"

        if is_catchup:
            logger.warning(
                f"[FORWARD_TEST_SCHEDULER] Catch-up freeze detected on {today} (First trading day was {first_trading_day}). "
                f"Cohort {cohort_num} tagged as '{cohort_type}' (quarantined from primary statistical inference to prevent lookahead/timing distortion)."
            )
        else:
            logger.info(
                f"[FORWARD_TEST_SCHEDULER] Freezing On-Time Primary Cohort {cohort_num} on {today} (First trading day: {first_trading_day})."
            )

        regime_data = await MarketRegimeDetector.get_current_regime()
        nifty_price = float(regime_data.get("nifty_price") or 25000.0)
        nifty_ema200 = float(regime_data.get("nifty_ema200") or 24500.0)
        regime_tag = "DEFENSIVE" if (nifty_price < nifty_ema200) else "BULLISH"
        
        type_suffix = "LATE" if is_catchup else "PRIMARY"
        batch_id = f"{month_prefix}_{today.strftime('%Y%m%d')}_{type_suffix}_{regime_tag}"
        freeze_res = await cls.freeze_cohort(db, cohort_type=cohort_type, batch_id=batch_id)
        return freeze_res
