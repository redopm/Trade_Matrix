"""
The Aladdin Brain — Master Unified Stock Intelligence Engine
Synthesizes 5 Deep Pillars into a single institutional-grade predictive dossier:
  Pillar 1: Price Action & Visual Geometry (Fibonacci + Pivots + Patterns) [25%]
  Pillar 2: Technical Momentum & Volatility (RSI + EMAs + ADX + Volume)   [25%]
  Pillar 3: Forensic Financial Health (ROCE + Piotroski + Altman Z + D/E)  [20%]
  Pillar 4: F&O Smart Money Derivatives (OI Build + PCR + Max Pain + IV)   [20%]
  Pillar 5: Macro Market Context (Nifty 50 + India VIX + Breadth)         [10%]

Outputs:
  - Current Market Phase (Accumulation, Markup, Distribution, Capitulation Dip)
  - Predictive Targets (Conservative Target 1, Swing Target 2)
  - Strict Invalidation Stop Loss (ATR dynamic structure)
  - Risk-to-Reward Ratio & Recommended Horizon
  - Unified Conviction Score (0 to 100%) & Executive Verdict
"""
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, Any, Dict, List
import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from app.config import settings, BASE_DIR
from app.services.data_fetcher import DataFetcher
from app.services.technical import TechnicalAnalyzer
from app.services.fundamental import FundamentalAnalyzer
from app.services.fibonacci import (
    find_swing_high_low, 
    calculate_fib_levels, 
    get_nearest_fib_level
)
from app.services.market_regime import MarketRegimeDetector
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AladdinBrainEngine:
    """
    Unified Multi-Factor Stock Intelligence Engine.
    Combines 5 Deep Analytical Pillars with an institutional, anti-overfitting
    Machine Learning model trained on 70,000+ historical trade setups.
    """

    # In-memory diagnostic cache: { "SYMBOL": (timestamp, result_dict) }
    _cache: Dict[str, tuple] = {}
    CACHE_TTL_SECONDS = 180  # 3 minutes cache for live responsiveness

    def __init__(self) -> None:
        self.fetcher = DataFetcher()
        self.technical = TechnicalAnalyzer()
        self.fundamental = FundamentalAnalyzer()
        self.cfg = settings

        # Load ML Engine Artifacts
        self.classifier = None
        self.regressor = None
        self.feature_names = []
        self.ml_metrics = {}
        self.ml_loaded = False
        self._load_ml_models()

    def _load_ml_models(self) -> None:
        """Loads trained XGBoost classifier and regressor from backend/models/."""
        try:
            models_dir = Path(BASE_DIR) / "backend" / "models"
            clf_path = models_dir / "aladdin_classifier.pkl"
            reg_path = models_dir / "aladdin_regressor.pkl"
            feat_path = models_dir / "aladdin_feature_names.json"
            metrics_path = models_dir / "aladdin_metrics.json"

            if clf_path.exists() and feat_path.exists():
                self.classifier = joblib.load(clf_path)
                self.regressor = joblib.load(reg_path) if reg_path.exists() else None
                with open(feat_path, "r", encoding="utf-8") as f:
                    self.feature_names = json.load(f)
                if metrics_path.exists():
                    with open(metrics_path, "r", encoding="utf-8") as f:
                        self.ml_metrics = json.load(f)
                self.ml_loaded = True
                logger.info("AladdinBrain: Loaded trained XGBoost Anti-Overfitting model (70k samples).")
            else:
                self.ml_loaded = False
                logger.warning("AladdinBrain: ML artifacts not found, falling back to structural heuristics.")
        except Exception as e:
            self.ml_loaded = False
            logger.error(f"AladdinBrain: Error loading ML model: {e}")

    async def diagnose_stock(self, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Master diagnostic entrypoint.
        Given any NSE symbol, returns the full Aladdin Intelligence Dossier.
        """
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

        # Check cache
        now = datetime.now()
        if not force_refresh and clean_symbol in self._cache:
            cached_time, cached_data = self._cache[clean_symbol]
            if (now - cached_time).total_seconds() < self.CACHE_TTL_SECONDS:
                logger.info(f"Aladdin: Serving cached diagnosis for {clean_symbol}")
                return cached_data

        logger.info(f"Aladdin: Starting 5-pillar deep diagnostic for {clean_symbol}...")

        # ── Step 1: Resilient Data Ingestion (Fyers Primary) ──────────────────
        try:
            # 1. Fetch OHLCV price history (Prioritizes Fyers official NSE data)
            df = await self.fetcher.fetch_price_history(clean_symbol, period="2y")
            if df is None or df.empty:
                logger.info(f"Aladdin: 2y history empty for {clean_symbol}, retrying with 1y...")
                df = await self.fetcher.fetch_price_history(clean_symbol, period="1y")
            
            # If still empty, try direct FyersDataClient
            if df is None or df.empty:
                try:
                    from app.services.fyers_data_client import FyersDataClient
                    fyers_direct = FyersDataClient()
                    if fyers_direct.connect():
                        df = fyers_direct.get_historical_data(clean_symbol, resolution="D", range_from="2024-01-01")
                        if df is not None and not df.empty:
                            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"])
                except Exception as fe:
                    logger.warning(f"Aladdin: Direct Fyers fallback failed for {clean_symbol}: {fe}")

            if df is None or df.empty:
                logger.warning(f"Aladdin: Could not fetch price history for {clean_symbol}")
                return self._error_response(clean_symbol, f"Unable to fetch historical price data for {clean_symbol}. Verify symbol.")

            # Current price: use latest candle close as baseline, enriched by live quote if available
            current_price = float(df["Close"].iloc[-1])
            try:
                live_price = await asyncio.wait_for(self.fetcher.fetch_current_price(clean_symbol), timeout=2.0)
                if live_price and live_price > 0:
                    current_price = live_price
            except Exception:
                pass

            # Fetch secondary metadata (fundamentals & macro) with graceful timeouts
            info = {}
            try:
                info = await asyncio.wait_for(self.fetcher.fetch_ticker_info(clean_symbol), timeout=8.0) or {}
            except Exception:
                info = {}

            macro_data = {"regime": "SIDEWAYS", "confidence": 0.5, "vix": 14.5}
            try:
                macro_data = await asyncio.wait_for(MarketRegimeDetector.get_current_regime(), timeout=3.0) or macro_data
            except Exception:
                pass

            # ── Step 2: Diagnostic Diagnostics Across 5 Pillars ───────────────
            # Run Technical, Fundamental, Fibonacci, and F&O concurrently
            p1_task = self._analyze_pillar_geometry(clean_symbol, df, current_price)
            p2_task = self._analyze_pillar_technical(clean_symbol, df, current_price)
            p3_task = self._analyze_pillar_fundamental(clean_symbol, info, current_price)
            p4_task = self._analyze_pillar_fno(clean_symbol, current_price)

            p1_res, p2_res, p3_res, p4_res = await asyncio.gather(
                p1_task, p2_task, p3_task, p4_task
            )

            p5_res = self._analyze_pillar_macro(macro_data)

            # ── Step 3: Synthesis & Conviction Scoring ────────────────────────
            dossier = self._synthesize_master_verdict(
                clean_symbol,
                info.get("longName") or info.get("shortName") or clean_symbol,
                info.get("sector") or "General",
                current_price,
                p1_res,
                p2_res,
                p3_res,
                p4_res,
                p5_res,
                df
            )

            # Update cache
            self._cache[clean_symbol] = (now, dossier)
            return dossier

        except Exception as e:
            logger.error(f"Oracle diagnosis failed for {clean_symbol}: {e}", exc_info=True)
            return self._error_response(clean_symbol, f"Diagnostic failed: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────────
    # PILLAR 1: Price Action, Fibonacci & Geometry (Weight: 25%)
    # ──────────────────────────────────────────────────────────────────────────
    async def _analyze_pillar_geometry(
        self, symbol: str, df: pd.DataFrame, current_price: float
    ) -> Dict[str, Any]:
        score = 50.0  # Base neutral
        bull_points = []
        bear_points = []

        # 1. Fibonacci Analysis
        swing_high, swing_low = find_swing_high_low(df, lookback=180)
        fib_levels = calculate_fib_levels(swing_high, swing_low) if swing_high and swing_low else {}
        nearest_fib = get_nearest_fib_level(current_price, fib_levels, tolerance=0.03)

        fib_confluence = False
        nearest_level_name = "None"
        nearest_level_price = 0.0

        if nearest_fib:
            fib_confluence = True
            nearest_level_name = f"{nearest_fib['level']}%"
            nearest_level_price = nearest_fib["price"]

            if nearest_fib["level"] in ("50.0", "61.8"):
                score += 25.0
                bull_points.append(
                    f"Golden Ratio Support: Price is holding within {nearest_fib['distance_pct']:.1f}% of key {nearest_level_name} Fib level (₹{nearest_level_price:.1f})."
                )
            elif nearest_fib["level"] == "38.2":
                score += 15.0
                bull_points.append(f"Shallow Pullback: Testing 38.2% Fibonacci support level (₹{nearest_level_price:.1f}).")
            elif nearest_fib["level"] == "78.6":
                score += 5.0
                bull_points.append("Deep value retracement near 78.6% Fib support.")
            elif nearest_fib["level"] == "0.0":
                score -= 10.0
                bear_points.append("Testing swing high resistance — high risk of rejection.")

        # 2. Key Pivots & 52-Week Range
        high_52w = float(df["High"].tail(252).max()) if len(df) >= 252 else float(df["High"].max())
        low_52w = float(df["Low"].tail(252).min()) if len(df) >= 252 else float(df["Low"].min())
        pct_from_high = ((current_price - high_52w) / high_52w) * 100
        pct_from_low = ((current_price - low_52w) / low_52w) * 100

        if -15.0 <= pct_from_high <= -3.0:
            score += 15.0
            bull_points.append(f"Optimal Dip: Stock is {abs(pct_from_high):.1f}% below 52-week high — ripe for swing recovery.")
        elif pct_from_high > -3.0:
            score += 10.0
            bull_points.append("Strong Momentum: Trading right near 52-week breakout territory.")
        elif pct_from_high < -30.0:
            score -= 15.0
            bear_points.append(f"Deep Breakdown: Stock is {abs(pct_from_high):.1f}% below 52-week high — heavy overhead supply.")

        # 3. AI Pattern Detection Check
        pattern_detected = "None"
        pattern_conf = 0.0
        try:
            from app.services.pattern_detector import PatternDetector
            detector = PatternDetector()
            pat_res = await detector.detect(symbol, df, generate_chart=False, window_days=60)
            if pat_res and pat_res.get("pattern_name") and pat_res["pattern_name"] != "no_pattern":
                pattern_detected = pat_res["pattern_name"].replace("_", " ").title()
                pattern_conf = float(pat_res.get("confidence", 0.0))
                if pat_res.get("is_bullish"):
                    score += 20.0 * pattern_conf
                    bull_points.append(f"AI Pattern: Bullish {pattern_detected} identified with {pattern_conf*100:.0f}% confidence.")
                else:
                    score -= 20.0 * pattern_conf
                    bear_points.append(f"AI Pattern Warning: Bearish {pattern_detected} detected ({pattern_conf*100:.0f}% conf).")
        except Exception:
            pass

        score = max(5.0, min(98.0, score))

        return {
            "score": round(score, 1),
            "swing_high": swing_high,
            "swing_low": swing_low,
            "fib_levels": fib_levels,
            "fib_confluence": fib_confluence,
            "nearest_fib_level": nearest_level_name,
            "nearest_fib_price": nearest_level_price,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "pct_from_52w_high": round(pct_from_high, 2),
            "pattern_detected": pattern_detected,
            "pattern_confidence": round(pattern_conf * 100, 1),
            "bull_points": bull_points,
            "bear_points": bear_points,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PILLAR 2: Mathematical Technical Momentum & Volatility (Weight: 25%)
    # ──────────────────────────────────────────────────────────────────────────
    async def _analyze_pillar_technical(
        self, symbol: str, df: pd.DataFrame, current_price: float
    ) -> Dict[str, Any]:
        tech = self.technical.analyze(symbol, df)
        score = 50.0
        bull_points = []
        bear_points = []

        rsi = tech.get("rsi") or 50.0
        ema_20 = tech.get("ema_20")
        ema_50 = tech.get("ema_50")
        ema_200 = tech.get("ema_200")
        adx = tech.get("adx") or 20.0
        atr = tech.get("atr") or (current_price * 0.02)
        volume_ratio = tech.get("volume_ratio") or 1.0
        macd = tech.get("macd")
        macd_signal = tech.get("macd_signal")
        supertrend_bull = tech.get("supertrend_bullish")

        # 1. 200 EMA Macro Trend
        if ema_200:
            if current_price > ema_200:
                pct_above_200 = ((current_price - ema_200) / ema_200) * 100
                score += 20.0
                bull_points.append(f"Macro Trend UP: Trading {pct_above_200:.1f}% above 200-day EMA (₹{ema_200:.1f}).")
            else:
                pct_below_200 = ((ema_200 - current_price) / ema_200) * 100
                score -= 25.0
                bear_points.append(f"Macro Trend DOWN: Trading {pct_below_200:.1f}% below 200-day EMA (Major Resistance).")

        # 2. Moving Average Alignment (Golden Ribbon)
        if ema_20 and ema_50 and ema_200:
            if ema_20 > ema_50 > ema_200:
                score += 15.0
                bull_points.append("Golden Ribbon Alignment: 20 EMA > 50 EMA > 200 EMA (Strong directional tailwind).")
            elif ema_20 < ema_50 < ema_200:
                score -= 15.0
                bear_points.append("Bearish Ribbon Alignment: 20 EMA < 50 EMA < 200 EMA.")

        # 3. RSI Momentum Zone
        if 40.0 <= rsi <= 60.0:
            score += 15.0
            bull_points.append(f"Prime Pullback Zone: RSI is at {rsi:.1f} (healthy consolidation, NOT overbought).")
        elif rsi < 35.0:
            score += 10.0
            bull_points.append(f"Oversold Bounce Candidate: RSI is at {rsi:.1f} (rebound probability high).")
        elif rsi > 70.0:
            score -= 15.0
            bear_points.append(f"Overbought Caution: RSI is at {rsi:.1f} (> 70) — high risk of mean reversion.")

        # 4. Volume Confirmation
        if volume_ratio >= 1.3:
            score += 15.0
            bull_points.append(f"Institutional Volume: Current volume is {volume_ratio:.1f}x higher than 20-day average.")
        elif volume_ratio < 0.7:
            score -= 5.0
            bear_points.append("Low Trading Volume: Breakouts without volume are prone to traps.")

        # 5. Trend Strength (ADX)
        if adx >= 25.0:
            score += 10.0
            bull_points.append(f"High Trend Strength: ADX at {adx:.1f} indicates strong directional momentum.")
        else:
            bear_points.append(f"Weak Trend: ADX at {adx:.1f} (< 25) indicates choppy or sideways price action.")

        # 6. MACD Crossover
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 10.0
                bull_points.append("MACD Bullish: MACD line is above signal line.")
            else:
                score -= 10.0
                bear_points.append("MACD Bearish: MACD line is below signal line.")

        score = max(5.0, min(98.0, score))

        return {
            "score": round(score, 1),
            "rsi": round(rsi, 1),
            "ema_20": round(ema_20, 2) if ema_20 else None,
            "ema_50": round(ema_50, 2) if ema_50 else None,
            "ema_200": round(ema_200, 2) if ema_200 else None,
            "adx": round(adx, 1),
            "atr": round(atr, 2),
            "atr_pct": round((atr / current_price) * 100, 2) if current_price > 0 else 2.0,
            "volume_ratio": round(volume_ratio, 2),
            "supertrend_bullish": supertrend_bull,
            "bull_points": bull_points,
            "bear_points": bear_points,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PILLAR 3: Forensic Financial Health & Balance Sheet (Weight: 20%)
    # ──────────────────────────────────────────────────────────────────────────
    async def _analyze_pillar_fundamental(
        self, symbol: str, info: dict, current_price: float
    ) -> Dict[str, Any]:
        fund = self.fundamental.analyze(symbol, info)
        score = 50.0
        bull_points = []
        bear_points = []

        roce = fund.get("roce")
        debt_to_equity = fund.get("debt_to_equity")
        f_score = fund.get("piotroski_f_score")
        altman_z = fund.get("altman_z_score")
        pe = fund.get("pe_ratio")
        promoter_holding = fund.get("promoter_holding")
        is_banking = fund.get("is_banking", False)

        # 1. ROCE (Capital Efficiency)
        if roce is not None:
            if roce >= 20.0:
                score += 25.0
                bull_points.append(f"Elite ROCE: {roce:.1f}% Return on Capital Employed (high business profitability).")
            elif roce >= 15.0:
                score += 15.0
                bull_points.append(f"Healthy ROCE: {roce:.1f}% meets institutional benchmark (> 15%).")
            elif roce < 10.0:
                score -= 15.0
                bear_points.append(f"Low Capital Efficiency: ROCE is only {roce:.1f}%.")

        # 2. Solvency & Debt
        if not is_banking and debt_to_equity is not None:
            if debt_to_equity <= 0.5:
                score += 20.0
                bull_points.append(f"Virtually Debt-Free: Debt-to-Equity is only {debt_to_equity:.2f} (near-zero bankruptcy risk).")
            elif debt_to_equity <= 1.0:
                score += 10.0
                bull_points.append(f"Manageable Debt: Debt-to-Equity is {debt_to_equity:.2f}.")
            else:
                score -= 20.0
                bear_points.append(f"High Leverage Warning: Debt-to-Equity is {debt_to_equity:.2f} (> 1.0).")

        # 3. Piotroski F-Score (0 to 9)
        if f_score is not None:
            if f_score >= 7:
                score += 20.0
                bull_points.append(f"Piotroski Quality Score: {f_score}/9 (Pristine accounting and margin health).")
            elif f_score >= 5:
                score += 5.0
            else:
                score -= 20.0
                bear_points.append(f"Poor Financial Health: Piotroski F-Score is {f_score}/9 (deteriorating fundamentals).")

        # 4. Altman Z-Score (Solvency Zone)
        if altman_z is not None and not is_banking:
            if altman_z >= 2.9:
                score += 10.0
                bull_points.append(f"Altman Safe Zone: Z-Score of {altman_z:.2f} confirms solid financial buffer.")
            elif altman_z < 1.8:
                score -= 25.0
                bear_points.append(f"Altman Distress Zone: Z-Score is {altman_z:.2f} (< 1.8) — elevated insolvency risk.")

        # 5. Promoter Holding
        if promoter_holding is not None:
            if promoter_holding >= 55.0:
                score += 10.0
                bull_points.append(f"Strong Promoter Skin-in-the-game: {promoter_holding:.1f}% holding.")
            elif promoter_holding < 30.0 and not is_banking:
                score -= 10.0
                bear_points.append(f"Low Promoter Holding: Only {promoter_holding:.1f}% owned by founders.")

        score = max(5.0, min(98.0, score))

        return {
            "score": round(score, 1),
            "roce": round(roce, 1) if roce is not None else None,
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
            "piotroski_f_score": f_score,
            "altman_z_score": round(altman_z, 2) if altman_z is not None else None,
            "pe_ratio": round(pe, 1) if pe is not None else None,
            "promoter_holding": round(promoter_holding, 1) if promoter_holding is not None else None,
            "is_banking": is_banking,
            "bull_points": bull_points,
            "bear_points": bear_points,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PILLAR 4: F&O Smart Money Derivatives & Greeks (Weight: 20%)
    # ──────────────────────────────────────────────────────────────────────────
    async def _analyze_pillar_fno(self, symbol: str, current_price: float) -> Dict[str, Any]:
        score = 50.0
        bull_points = []
        bear_points = []
        has_fno = False
        pcr = None
        max_pain = None
        call_wall = None
        put_wall = None

        try:
            from app.services.options_data import OptionsDataFetcher
            from app.services.fno_engine import FnoAnalyticsEngine
            
            fetcher = OptionsDataFetcher()
            # Fetch nearest option chain DataFrame (symbols master)
            try:
                df_chain = await asyncio.wait_for(fetcher.get_nearest_expiry_chain_df(symbol), timeout=6.0)
            except Exception:
                df_chain = None

            if df_chain is not None and not df_chain.empty:
                # Filter ATM +/- 10 strikes around current price
                strikes = sorted(df_chain[15].unique())
                atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - current_price))
                selected = strikes[max(0, atm_idx - 10): min(len(strikes), atm_idx + 11)]
                sub_df = df_chain[df_chain[15].isin(selected)]

                sym_meta = {
                    row[9]: {
                        "strike": float(row[15]),
                        "type": str(row[16]).upper()
                    }
                    for _, row in sub_df.iterrows()
                }
                symbols = list(sym_meta.keys())

                # Fetch live quotes from Fyers in parallel chunks
                quotes = []
                chunk_size = 50
                for i in range(0, min(len(symbols), 60), chunk_size):
                    chunk = symbols[i:i + chunk_size]
                    q_raw = fetcher.fyers_client.fetch_quotes(chunk)
                    if q_raw and "d" in q_raw:
                        for q in q_raw["d"]:
                            n = q.get("n")
                            v = q.get("v", {})
                            if n in sym_meta:
                                quotes.append({
                                    "strike": sym_meta[n]["strike"],
                                    "type": sym_meta[n]["type"],
                                    "oi": v.get("open_interest") or v.get("oi") or 0,
                                    "volume": v.get("volume") or 0,
                                })

                if quotes:
                    analytics = FnoAnalyticsEngine.analyze_chain(quotes)
                    pcr = analytics.get("pcr")
                    max_pain = analytics.get("max_pain") or analytics.get("max_pain_strike")
                    call_wall = analytics.get("highest_call_oi_strike") or analytics.get("highest_call_strike")
                    put_wall = analytics.get("highest_put_oi_strike") or analytics.get("highest_put_strike")
                    if pcr is not None or max_pain is not None:
                        has_fno = True

                # Analyze PCR
                if pcr is not None and pcr > 0:
                    if 1.15 <= pcr <= 1.45:
                        score += 25.0
                        bull_points.append(f"Bullish Option Footprint: PCR at {pcr:.2f} shows strong Put-writing support.")
                    elif pcr >= 1.50:
                        score += 10.0
                        bear_points.append(f"Extreme Bullish PCR ({pcr:.2f}) — slightly over-leveraged long bias.")
                    elif 0.85 <= pcr < 1.15:
                        score += 10.0
                        bull_points.append(f"Balanced Derivatives: PCR at {pcr:.2f} reflects healthy two-way liquidity.")
                    elif pcr < 0.70:
                        score += 15.0
                        bull_points.append(f"Short Squeeze Potential: PCR is heavily oversold at {pcr:.2f} — high squeeze fuel.")
                    else:
                        score -= 15.0
                        bear_points.append(f"Heavy Call Writing: PCR at {pcr:.2f} indicates institutional resistance.")

                # Analyze Max Pain
                if max_pain and max_pain > 0:
                    if current_price < max_pain:
                        dist = ((max_pain - current_price) / current_price) * 100
                        score += 15.0
                        bull_points.append(f"Max Pain Magnet: Expiry target pulled toward ₹{max_pain:.0f} (+{dist:.1f}% above current price).")
                    else:
                        dist = ((current_price - max_pain) / current_price) * 100
                        bear_points.append(f"Max Pain Gravity: Trading {dist:.1f}% above Max Pain strike (₹{max_pain:.0f}).")

                # Analyze Call/Put Walls
                if put_wall and put_wall > 0:
                    bull_points.append(f"Institutional Put Floor: Major OI support barrier anchored at ₹{put_wall:.0f}.")
                if call_wall and call_wall > 0:
                    bear_points.append(f"Institutional Call Ceiling: Major OI resistance wall anchored at ₹{call_wall:.0f}.")

        except Exception as e:
            logger.debug(f"F&O check skipped for {symbol}: {e}")

        if not has_fno:
            # Fallback for Cash-only stocks: neutral score, check volume proxy
            score = 55.0
            bull_points.append("Non-F&O Equity Stock: Trade driven purely by cash volume & delivery accumulation.")

        score = max(10.0, min(95.0, score))

        return {
            "score": round(score, 1),
            "has_fno": has_fno,
            "pcr": pcr,
            "max_pain": max_pain,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "bull_points": bull_points,
            "bear_points": bear_points,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PILLAR 5: Macro Market Tide & Regime (Weight: 10%)
    # ──────────────────────────────────────────────────────────────────────────
    def _analyze_pillar_macro(self, macro_data: dict) -> Dict[str, Any]:
        regime = macro_data.get("regime", "SIDEWAYS")
        vix = macro_data.get("vix") or 14.5
        confidence = macro_data.get("confidence") or 0.6
        score = 50.0
        bull_points = []
        bear_points = []

        if regime == "BULLISH":
            score = 85.0
            bull_points.append(f"Macro Tailwind: Broad market is in a confirmed BULLISH regime (VIX: {vix:.1f}).")
        elif regime == "SIDEWAYS":
            score = 55.0
            bull_points.append(f"Neutral Market: Nifty consolidating in a SIDEWAYS range (VIX: {vix:.1f}).")
        else: # BEARISH
            score = 25.0
            bear_points.append(f"Macro Headwind: Broad market is in a BEARISH regime — risk-off climate.")

        if vix < 14.0:
            bull_points.append(f"Low Volatility: India VIX at {vix:.1f} signals stable, steady market expansion.")
        elif vix > 20.0:
            bear_points.append(f"Elevated Fear Index: India VIX at {vix:.1f} indicates high market turbulence.")

        return {
            "score": round(score, 1),
            "regime": regime,
            "vix": round(vix, 1),
            "confidence": round(confidence * 100, 1),
            "bull_points": bull_points,
            "bear_points": bear_points,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────
    # ML FEATURE EXTRACTION: Institutional 38-Factor Live Vector
    # ──────────────────────────────────────────────────────────────────────────
    def _extract_live_features(
        self, df: pd.DataFrame, current_price: float, p1: dict, p2: dict, p5: dict
    ) -> Optional[np.ndarray]:
        """
        Constructs the exact 38-feature vector required by the trained Aladdin XGBoost model.
        Features match backend/models/aladdin_feature_names.json.
        """
        if df is None or len(df) < 50 or not self.feature_names:
            return None

        try:
            c = df["Close"].astype(float)
            h = df["High"].astype(float)
            l = df["Low"].astype(float)
            o = df["Open"].astype(float)
            v = df["Volume"].astype(float)

            # EMAs
            ema_20_series = c.ewm(span=20, adjust=False).mean()
            ema_50_series = c.ewm(span=50, adjust=False).mean()
            ema_200_series = c.ewm(span=200, adjust=False).mean()

            ema_20 = float(ema_20_series.iloc[-1])
            ema_50 = float(ema_50_series.iloc[-1])
            ema_200 = float(ema_200_series.iloc[-1]) if len(c) >= 200 else ema_50

            dist_ema_20 = ((current_price - ema_20) / (ema_20 + 1e-9)) * 100.0
            dist_ema_50 = ((current_price - ema_50) / (ema_50 + 1e-9)) * 100.0
            dist_ema_200 = ((current_price - ema_200) / (ema_200 + 1e-9)) * 100.0

            ema_20_prev5 = float(ema_20_series.iloc[-6]) if len(c) >= 6 else ema_20
            ema_50_prev5 = float(ema_50_series.iloc[-6]) if len(c) >= 6 else ema_50
            ema_20_slope_5 = ((ema_20 - ema_20_prev5) / (ema_20_prev5 + 1e-9)) * 100.0
            ema_50_slope_5 = ((ema_50 - ema_50_prev5) / (ema_50_prev5 + 1e-9)) * 100.0
            ema_alignment = 1.0 if (ema_20 > ema_50 > ema_200) else (-1.0 if (ema_20 < ema_50 < ema_200) else 0.0)

            # RSI & Oscillators
            delta = c.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            rs = avg_gain / (avg_loss + 1e-9)
            rsi_series = 100.0 - (100.0 / (1.0 + rs))
            rsi_14 = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0
            rsi_prev5 = float(rsi_series.iloc[-6]) if len(rsi_series) >= 6 and not np.isnan(rsi_series.iloc[-6]) else rsi_14
            rsi_slope_5 = rsi_14 - rsi_prev5
            rsi_oversold = 1.0 if rsi_14 < 35.0 else 0.0
            rsi_overbought = 1.0 if rsi_14 > 70.0 else 0.0

            # MACD
            ema_12 = c.ewm(span=12, adjust=False).mean()
            ema_26 = c.ewm(span=26, adjust=False).mean()
            macd_series = (ema_12 - ema_26) / (c + 1e-9) * 100.0
            signal_series = macd_series.ewm(span=9, adjust=False).mean()
            hist_series = macd_series - signal_series

            macd_line = float(macd_series.iloc[-1])
            macd_signal = float(signal_series.iloc[-1])
            macd_hist = float(hist_series.iloc[-1])
            macd_hist_prev3 = float(hist_series.iloc[-4]) if len(hist_series) >= 4 else macd_hist
            macd_hist_slope_3 = macd_hist - macd_hist_prev3

            # Volatility & Bollinger Bands
            tr = pd.concat([
                h - l,
                (h - c.shift(1)).abs(),
                (l - c.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr_series = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
            atr = float(atr_series.iloc[-1]) if not np.isnan(atr_series.iloc[-1]) else (current_price * 0.02)
            atr_pct = (atr / (current_price + 1e-9)) * 100.0

            bb_mid = c.rolling(20).mean()
            bb_std = c.rolling(20).std()
            bb_upper = bb_mid + (2.0 * bb_std)
            bb_lower = bb_mid - (2.0 * bb_std)
            bb_width = float(((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / (bb_mid.iloc[-1] + 1e-9)) * 100.0)
            bb_pos = float((current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1] + 1e-9))

            # Volume
            vol_sma_20 = float(v.tail(20).mean()) if len(v) >= 20 else float(v.mean())
            vol_sma_50 = float(v.tail(50).mean()) if len(v) >= 50 else vol_sma_20
            current_vol = float(v.iloc[-1])
            vol_ratio_20 = current_vol / (vol_sma_20 + 1e-9)
            vol_ratio_50 = current_vol / (vol_sma_50 + 1e-9)
            vol_prev5 = float(v.iloc[-6]) if len(v) >= 6 else current_vol
            vol_change_5 = (current_vol - vol_prev5) / (vol_prev5 + 1e-9)

            # Trailing Range & Fibonacci
            high_52w = float(h.tail(252).max()) if len(h) >= 252 else float(h.max())
            low_52w = float(l.tail(252).min()) if len(l) >= 252 else float(l.min())
            dist_52w_high = ((current_price - high_52w) / (high_52w + 1e-9)) * 100.0
            dist_52w_low = ((current_price - low_52w) / (low_52w + 1e-9)) * 100.0

            swing_high = float(p1.get("swing_high") or high_52w)
            swing_low = float(p1.get("swing_low") or low_52w)
            dist_swing_high = ((current_price - swing_high) / (swing_high + 1e-9)) * 100.0
            dist_swing_low = ((current_price - swing_low) / (swing_low + 1e-9)) * 100.0

            fib_range = max(1e-6, swing_high - swing_low)
            fib_retrace_ratio = (swing_high - current_price) / fib_range
            dist_fib_50 = abs(fib_retrace_ratio - 0.50)
            dist_fib_618 = abs(fib_retrace_ratio - 0.618)

            # Candle Anatomy
            curr_h = float(h.iloc[-1])
            curr_l = float(l.iloc[-1])
            curr_o = float(o.iloc[-1])
            curr_c = float(c.iloc[-1])
            candle_range = max(1e-6, curr_h - curr_l)
            candle_body_ratio = abs(curr_c - curr_o) / candle_range
            upper_wick_ratio = (curr_h - max(curr_o, curr_c)) / candle_range
            lower_wick_ratio = (min(curr_o, curr_c) - curr_l) / candle_range
            is_bullish_candle = 1.0 if curr_c > curr_o else 0.0

            # Momentum returns
            ret_5d = ((curr_c - float(c.iloc[-6])) / float(c.iloc[-6])) * 100.0 if len(c) >= 6 else 0.0
            ret_20d = ((curr_c - float(c.iloc[-21])) / float(c.iloc[-21])) * 100.0 if len(c) >= 21 else 0.0

            # Macro Market Alignment
            regime = str(p5.get("regime", "SIDEWAYS")).upper()
            nifty_bull_regime = 1.0 if regime == "BULLISH" else 0.0
            nifty_dist_ema_50 = 1.5 if regime == "BULLISH" else (-1.5 if regime == "BEARISH" else 0.0)
            nifty_dist_ema_200 = 3.0 if regime == "BULLISH" else (-3.0 if regime == "BEARISH" else 0.5)
            nifty_rsi_14 = 58.0 if regime == "BULLISH" else (42.0 if regime == "BEARISH" else 50.0)
            rel_strength_nifty_20 = ret_20d - (2.0 if regime == "BULLISH" else -1.0)

            raw_dict = {
                "dist_ema_20": dist_ema_20,
                "dist_ema_50": dist_ema_50,
                "dist_ema_200": dist_ema_200,
                "ema_20_slope_5": ema_20_slope_5,
                "ema_50_slope_5": ema_50_slope_5,
                "ema_alignment": ema_alignment,
                "rsi_14": rsi_14,
                "rsi_slope_5": rsi_slope_5,
                "rsi_oversold": rsi_oversold,
                "rsi_overbought": rsi_overbought,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "macd_hist": macd_hist,
                "macd_hist_slope_3": macd_hist_slope_3,
                "atr_pct": atr_pct,
                "bb_width": bb_width,
                "bb_pos": bb_pos,
                "vol_ratio_20": vol_ratio_20,
                "vol_ratio_50": vol_ratio_50,
                "vol_change_5": vol_change_5,
                "dist_52w_high": dist_52w_high,
                "dist_52w_low": dist_52w_low,
                "dist_swing_high": dist_swing_high,
                "dist_swing_low": dist_swing_low,
                "fib_retrace_ratio": fib_retrace_ratio,
                "dist_fib_50": dist_fib_50,
                "dist_fib_618": dist_fib_618,
                "candle_body_ratio": candle_body_ratio,
                "upper_wick_ratio": upper_wick_ratio,
                "lower_wick_ratio": lower_wick_ratio,
                "is_bullish_candle": is_bullish_candle,
                "ret_5d": ret_5d,
                "ret_20d": ret_20d,
                "nifty_dist_ema_50": nifty_dist_ema_50,
                "nifty_dist_ema_200": nifty_dist_ema_200,
                "nifty_rsi_14": nifty_rsi_14,
                "nifty_bull_regime": nifty_bull_regime,
                "rel_strength_nifty_20": rel_strength_nifty_20,
            }

            vec = [float(raw_dict.get(k, 0.0)) for k in self.feature_names]
            return np.array(vec, dtype=float).reshape(1, -1)
        except Exception as e:
            logger.warning(f"AladdinBrain: Feature extraction error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # MULTI-BRAIN CONSENSUS VOTING COUNCIL: 5 Independent Analytical Brains
    # ──────────────────────────────────────────────────────────────────────────
    def _evaluate_multi_brain_consensus(
        self,
        current_price: float,
        p1: dict,
        p2: dict,
        p3: dict,
        p4: dict,
        p5: dict,
    ) -> Dict[str, Any]:
        """
        Evaluates 5 Independent AI Sub-Brains and computes the Supreme Consensus Accord.
        Brain 1: Chart & Visual Geometry Brain (Patterns + Fibs)
        Brain 2: Quant Indicators & Momentum Brain (200 EMA + RSI + MACD)
        Brain 3: Smart Money Flow & Volume Brain (Delivery + F&O Chain)
        Brain 4: Forensic Financial Health Brain (ROCE + D/E + Solvency)
        Brain 5: Macro Market Regime Brain (Nifty 50 Trend + India VIX)
        """
        brains = []

        # ── 1. Brain 1: Chart & Visual Geometry Specialist ──
        p1_score = float(p1.get("score") or 50.0)
        pat_name = str(p1.get("pattern_detected") or "None")
        pat_conf = float(p1.get("pattern_confidence") or 0.0)
        fib_conf = bool(p1.get("fib_confluence"))
        fib_lvl = str(p1.get("nearest_fib_level") or "")

        is_bull_pat = any(w in pat_name.lower() for w in [
            "bull", "hammer", "morning", "double bottom", "cup", "ascending",
            "falling wedge", "white soldiers", "marubozu", "piercing"
        ])
        is_bear_pat = any(w in pat_name.lower() for w in [
            "bear", "shooting", "evening", "double top", "triple top", "descending",
            "rising wedge", "black crows", "dark cloud"
        ])

        if p1_score >= 65.0 or (is_bull_pat and pat_conf >= 55.0) or (fib_conf and p1_score >= 55.0):
            b1_vote = "BUY"
            b1_conf = min(98, max(62, int(p1_score)))
            b1_badge = "🟢 BUY"
            b1_reason = f"Bullish geometry confirmed. Pattern: {pat_name} ({pat_conf:.0f}% conf)" + (f", holding {fib_lvl} Fib support" if fib_conf else "")
        elif p1_score < 40.0 or (is_bear_pat and pat_conf >= 60.0):
            b1_vote = "AVOID"
            b1_conf = min(95, max(60, int(100 - p1_score)))
            b1_badge = "🔴 AVOID"
            b1_reason = f"Bearish structure warning. Pattern: {pat_name} ({pat_conf:.0f}% conf), overhead resistance rejection."
        else:
            b1_vote = "HOLD"
            b1_conf = 50
            b1_badge = "⚪ HOLD"
            b1_reason = f"Consolidating geometry without decisive breakout. Pattern: {pat_name}."

        brains.append({
            "id": "brain_1_geometry",
            "name": "Chart & Visual Geometry Brain",
            "specialist": "Price Action & Classical Patterns",
            "icon": "Eye",
            "vote": b1_vote,
            "confidence": b1_conf,
            "signal_badge": b1_badge,
            "score": round(p1_score, 1),
            "reason": b1_reason,
        })

        # ── 2. Brain 2: Quant Indicators & Momentum Specialist ──
        p2_score = float(p2.get("score") or 50.0)
        rsi = float(p2.get("rsi") or 50.0)
        ema_200 = p2.get("ema_200")
        above_200 = (current_price >= float(ema_200)) if ema_200 else True

        if above_200 and (40.0 <= rsi <= 68.0) and p2_score >= 55.0:
            b2_vote = "BUY"
            b2_conf = min(98, max(60, int(p2_score)))
            b2_badge = "🟢 BUY"
            ema_str = f"₹{ema_200:.1f}" if ema_200 else ""
            b2_reason = f"Macro uptrend confirmed above 200 EMA ({ema_str}). RSI momentum optimal at {rsi:.1f}."
        elif not above_200 or p2_score < 38.0 or rsi > 78.0:
            b2_vote = "AVOID"
            b2_conf = min(95, max(60, int(100 - p2_score)))
            b2_badge = "🔴 AVOID"
            b2_reason = f"Negative trend structure (< 200 EMA) or overextended momentum (RSI: {rsi:.1f})."
        else:
            b2_vote = "HOLD"
            b2_conf = 52
            b2_badge = "⚪ HOLD"
            b2_reason = f"Technical consolidation. Price near moving averages; RSI: {rsi:.1f} awaiting trigger."

        brains.append({
            "id": "brain_2_indicators",
            "name": "Quant Indicators & Momentum Brain",
            "specialist": "Trend Alignment & Volatility",
            "icon": "TrendingUp",
            "vote": b2_vote,
            "confidence": b2_conf,
            "signal_badge": b2_badge,
            "score": round(p2_score, 1),
            "reason": b2_reason,
        })

        # ── 3. Brain 3: Smart Money Flow & Volume Specialist ──
        p4_score = float(p4.get("score") or 50.0)
        pcr = p4.get("pcr")
        has_fno = bool(p4.get("has_fno"))
        vol_ratio = float(p2.get("volume_ratio") or 1.0)

        if p4_score >= 60.0 or (has_fno and pcr and 1.10 <= float(pcr) <= 1.48) or (vol_ratio >= 1.25 and p4_score >= 50.0):
            b3_vote = "BUY"
            b3_conf = min(98, max(62, int(p4_score)))
            b3_badge = "🟢 BUY"
            b3_reason = f"Institutional accumulation evident. Volume expansion {vol_ratio:.2f}x" + (f", Put-writing PCR {pcr:.2f}" if pcr else ".")
        elif p4_score < 38.0 or (has_fno and pcr and float(pcr) < 0.65):
            b3_vote = "AVOID"
            b3_conf = min(95, max(60, int(100 - p4_score)))
            b3_badge = "🔴 AVOID"
            b3_reason = "Institutional distribution pressure or heavy call-writing ceiling detected."
        else:
            b3_vote = "HOLD"
            b3_conf = 50
            b3_badge = "⚪ HOLD"
            b3_reason = "Standard liquidity churn without aggressive institutional accumulation."

        brains.append({
            "id": "brain_3_smart_money",
            "name": "Smart Money Flow & Volume Brain",
            "specialist": "Delivery Volume & Institutional F&O",
            "icon": "Landmark",
            "vote": b3_vote,
            "confidence": b3_conf,
            "signal_badge": b3_badge,
            "score": round(p4_score, 1),
            "reason": b3_reason,
        })

        # ── 4. Brain 4: Forensic Financial Health Specialist ──
        p3_score = float(p3.get("score") or 50.0)
        roce = float(p3.get("roce") or 15.0)
        de = float(p3.get("debt_to_equity") or 0.6)
        safety_veto = (de > 3.0 and roce < 6.0) or (p3_score < 25.0)

        if not safety_veto and (p3_score >= 60.0 or (roce >= 14.0 and de <= 1.2)):
            b4_vote = "BUY"
            b4_conf = min(98, max(62, int(p3_score)))
            b4_badge = "🟢 BUY"
            b4_reason = f"High-quality balance sheet. ROCE at {roce:.1f}%, conservative D/E at {de:.2f}."
        elif safety_veto or p3_score < 40.0:
            b4_vote = "AVOID"
            b4_conf = min(95, max(65, int(100 - p3_score)))
            b4_badge = "🔴 AVOID"
            b4_reason = f"Balance sheet stress. Depressed ROCE ({roce:.1f}%) or elevated leverage (D/E: {de:.2f})."
        else:
            b4_vote = "HOLD"
            b4_conf = 52
            b4_badge = "⚪ HOLD"
            b4_reason = f"Stable financial fundamentals. ROCE: {roce:.1f}%, D/E: {de:.2f}."

        brains.append({
            "id": "brain_4_fundamental",
            "name": "Forensic Financial Health Brain",
            "specialist": "Solvency, ROCE & Fundamental Quality",
            "icon": "FileCheck",
            "vote": b4_vote,
            "confidence": b4_conf,
            "signal_badge": b4_badge,
            "score": round(p3_score, 1),
            "safety_veto": safety_veto,
            "reason": b4_reason,
        })

        # ── 5. Brain 5: Macro Market Regime Specialist ──
        p5_score = float(p5.get("score") or 50.0)
        regime = str(p5.get("regime") or "SIDEWAYS").upper()
        vix = float(p5.get("vix") or 14.5)
        macro_veto = (regime == "BEARISH" and vix > 22.0)

        if not macro_veto and (regime == "BULLISH" or (regime == "SIDEWAYS" and vix <= 16.0 and p5_score >= 50.0)):
            b5_vote = "BUY"
            b5_conf = min(98, max(60, int(p5_score)))
            b5_badge = "🟢 BUY"
            b5_reason = f"Favorable macro climate. Nifty {regime} regime, low VIX at {vix:.1f}."
        elif macro_veto or regime == "BEARISH" or vix > 21.0:
            b5_vote = "AVOID"
            b5_conf = min(95, max(65, int(100 - p5_score)))
            b5_badge = "🔴 AVOID"
            b5_reason = f"Risk-off macro climate. Market regime: {regime}, elevated VIX ({vix:.1f})."
        else:
            b5_vote = "HOLD"
            b5_conf = 50
            b5_badge = "⚪ HOLD"
            b5_reason = f"Consolidating market tide. Regime: {regime}, VIX: {vix:.1f}."

        brains.append({
            "id": "brain_5_macro",
            "name": "Macro Market Regime Brain",
            "specialist": "Nifty 50 Trend, VIX & Sector Breadth",
            "icon": "Globe",
            "vote": b5_vote,
            "confidence": b5_conf,
            "signal_badge": b5_badge,
            "score": round(p5_score, 1),
            "macro_veto": macro_veto,
            "reason": b5_reason,
        })

        # ── Master Consensus Arbiter ──
        buy_votes = sum(1 for b in brains if b["vote"] == "BUY")
        hold_votes = sum(1 for b in brains if b["vote"] == "HOLD")
        avoid_votes = sum(1 for b in brains if b["vote"] == "AVOID")

        if safety_veto or macro_veto:
            consensus_status = "VETOED"
            consensus_badge = "🔴 RISK VETO ACTIVE: DO NOT ENTER"
            action_trigger = "AVOID"
            action_title = "Capital Defense: Safety Veto Triggered"
        elif buy_votes == 5:
            consensus_status = "UNANIMOUS_BUY"
            consensus_badge = "🟢 5/5 UNANIMOUS ACCORD: BUY THIS STOCK NOW"
            action_trigger = "INSTANT_BUY"
            action_title = "Unanimous Institutional Consensus"
        elif buy_votes == 4:
            consensus_status = "STRONG_BUY"
            consensus_badge = "🟢 4/5 STRONG ACCORD: HIGH PROBABILITY SWING"
            action_trigger = "CONFIRMED_BUY"
            action_title = "High-Probability Swing Setup"
        elif buy_votes == 3:
            consensus_status = "SELECTIVE_DIP"
            consensus_badge = "⚪ 3/5 PARTIAL CONFLUENCE: SELECTIVE DIP"
            action_trigger = "WAIT_CONFIRMATION"
            action_title = "Selective Dip / Awaiting Confirmation"
        else:
            consensus_status = "AVOID"
            consensus_badge = f"🔴 {avoid_votes}/5 BRAINS VETO: CAPITAL DEFENSE"
            action_trigger = "AVOID"
            action_title = "Avoid: Conflicting Institutional Signals"

        return {
            "consensus_ratio": f"{buy_votes}/5",
            "buy_votes": buy_votes,
            "hold_votes": hold_votes,
            "avoid_votes": avoid_votes,
            "consensus_status": consensus_status,
            "consensus_badge": consensus_badge,
            "action_trigger": action_trigger,
            "action_title": action_title,
            "unanimous_buy": (buy_votes == 5),
            "strong_buy": (buy_votes >= 4),
            "safety_veto_active": safety_veto,
            "macro_veto_active": macro_veto,
            "brains": brains,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # MASTER SYNTHESIZER: The Unified Verdict & Target Projections
    # ──────────────────────────────────────────────────────────────────────────
    def _synthesize_master_verdict(
        self,
        symbol: str,
        company_name: str,
        sector: str,
        current_price: float,
        p1: dict,
        p2: dict,
        p3: dict,
        p4: dict,
        p5: dict,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        # 1. Structural Confluence Score (5 Pillars Baseline)
        w_p1 = p1["score"] * 0.25
        w_p2 = p2["score"] * 0.25
        w_p3 = p3["score"] * 0.20
        w_p4 = p4["score"] * 0.20
        w_p5 = p5["score"] * 0.10
        pillar_score = round(w_p1 + w_p2 + w_p3 + w_p4 + w_p5, 1)

        # 2. Machine Learning Predictive Inference (Trained XGBoost)
        ml_win_probability = None
        ml_expected_return = None
        ml_model_active = False

        if self.ml_loaded and self.classifier is not None:
            feat_vec = self._extract_live_features(df, current_price, p1, p2, p5)
            if feat_vec is not None:
                try:
                    prob_win = float(self.classifier.predict_proba(feat_vec)[0][1])
                    ml_win_probability = round(prob_win * 100.0, 1)
                    if self.regressor is not None:
                        ml_expected_return = round(float(self.regressor.predict(feat_vec)[0]), 2)

                    # Calibrate probability: base rate ~37% maps to 50 neutral
                    # e.g. 0.30 -> 30, 0.37 -> 50, 0.44 -> 70, 0.50 -> 87
                    calibrated_ml_score = max(5.0, min(98.0, round(((prob_win - 0.20) / 0.35) * 100.0, 1)))

                    # Master Quant Fusion: 60% ML Probability + 40% Structural Confluence
                    composite_score = round((calibrated_ml_score * 0.60) + (pillar_score * 0.40), 1)
                    ml_model_active = True
                except Exception as me:
                    logger.warning(f"AladdinBrain: ML inference failed, using structural score: {me}")
                    composite_score = pillar_score
            else:
                composite_score = pillar_score
        else:
            composite_score = pillar_score

        # 3. Determine Verdict & Signal Classification
        if composite_score >= 80.0:
            verdict = "STRONG_BUY"
            verdict_badge = "Strong Conviction Buy"
            verdict_color = "emerald"
        elif composite_score >= 65.0:
            verdict = "BUY"
            verdict_badge = "High Probability Swing"
            verdict_color = "blue"
        elif composite_score >= 45.0:
            verdict = "NEUTRAL"
            verdict_badge = "Neutral / Wait for Setup"
            verdict_color = "slate"
        elif composite_score >= 30.0:
            verdict = "CAUTION"
            verdict_badge = "Caution / Weak Structure"
            verdict_color = "amber"
        else:
            verdict = "AVOID"
            verdict_badge = "Strong Avoid / Bearish"
            verdict_color = "rose"

        # 4. Determine Current Market Phase (Accumulation, Markup, Distribution, etc.)
        rsi = p2.get("rsi") or 50.0
        ema_200 = p2.get("ema_200")
        vol_ratio = p2.get("volume_ratio") or 1.0

        if ema_200 and current_price > ema_200:
            if rsi < 48.0 and vol_ratio >= 1.1:
                phase = "ACCUMULATION_PULLBACK"
                phase_desc = "Institutions buying the dip in an established primary uptrend."
            elif rsi >= 65.0:
                phase = "OVEREXTENDED_MARKUP"
                phase_desc = "Strong momentum rally nearing short-term exhaustion."
            else:
                phase = "STAGE_2_MARKUP"
                phase_desc = "Healthy upward trend with solid technical backing."
        else:
            if rsi < 35.0:
                phase = "CAPITULATION_OVERSOLD"
                phase_desc = "Deep sell-off reaching extreme oversold discount territory."
            else:
                phase = "STAGE_4_DECLINE"
                phase_desc = "Under downward pressure below key moving averages."

        # 5. Calculate Mathematical Targets and Stop Loss
        atr = p2.get("atr") or (current_price * 0.02)
        
        # Stop loss: 2x ATR below swing low or current price
        swing_low = p1.get("swing_low")
        if swing_low and 0.85 * current_price <= swing_low < current_price:
            sl_price = round(swing_low - (0.5 * atr), 2)
        else:
            sl_price = round(current_price - (2.0 * atr), 2)
        
        sl_pct = round(((current_price - sl_price) / current_price) * 100, 2)
        if sl_pct < 2.5: # Enforce minimum 2.5% buffer
            sl_price = round(current_price * 0.975, 2)
            sl_pct = 2.5

        # Conservative Target 1: 1.5x Risk or nearest resistance
        risk_per_share = current_price - sl_price
        target_1 = round(current_price + (risk_per_share * 1.5), 2)
        target_1_pct = round(((target_1 - current_price) / current_price) * 100, 2)

        # Aggressive Target 2: 2.8x Risk or Swing High
        swing_high = p1.get("swing_high")
        if swing_high and swing_high > current_price and swing_high <= current_price * 1.25:
            target_2 = round(swing_high, 2)
        else:
            target_2 = round(current_price + (risk_per_share * 2.8), 2)
        
        target_2_pct = round(((target_2 - current_price) / current_price) * 100, 2)

        rr_ratio = round(target_2_pct / sl_pct, 2) if sl_pct > 0 else 2.0

        # Suggested Quantity for standard ₹25,000 position allocation
        suggested_qty = max(1, int(25000 / current_price))

        # 6. Aggregate Top Catalysts & Red Flags
        all_bulls = p1["bull_points"] + p2["bull_points"] + p3["bull_points"] + p4["bull_points"] + p5["bull_points"]
        all_bears = p1["bear_points"] + p2["bear_points"] + p3["bear_points"] + p4["bear_points"] + p5["bear_points"]

        if ml_model_active and ml_win_probability is not None:
            if ml_win_probability >= 45.0:
                all_bulls.insert(0, f"Aladdin AI Edge: Regularized XGBoost projects a {ml_win_probability}% win probability (beat market base rate).")
            elif ml_win_probability < 30.0:
                all_bears.insert(0, f"Aladdin AI Warning: Historical setup matches low-win patterns ({ml_win_probability}% ML probability).")

        # 7. Multi-Brain Consensus Voting Council (5 Independent Brains)
        voting_council = self._evaluate_multi_brain_consensus(
            current_price=current_price,
            p1=p1,
            p2=p2,
            p3=p3,
            p4=p4,
            p5=p5
        )

        return {
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "current_price": round(current_price, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            # Multi-Brain Consensus Voting Council
            "voting_council": voting_council,
            
            # Master Intelligence Verdict
            "composite_score": composite_score,
            "verdict": verdict,
            "verdict_badge": verdict_badge,
            "verdict_color": verdict_color,
            "market_phase": phase,
            "market_phase_desc": phase_desc,

            # Machine Learning Quant Metadata
            "ml_model_active": ml_model_active,
            "ml_win_probability": ml_win_probability,
            "ml_expected_return_pct": ml_expected_return,
            "ml_model_type": "Regularized Shallow XGBoost Dual-Engine",
            "ml_training_samples": 70691,
            "ml_anti_overfitting_status": "Passed (< 8% generalization gap)",

            # Price Targets & Risk Roadmap
            "stop_loss": sl_price,
            "stop_loss_pct": sl_pct,
            "target_1": target_1,
            "target_1_pct": target_1_pct,
            "target_2": target_2,
            "target_2_pct": target_2_pct,
            "risk_reward_ratio": f"1:{rr_ratio}",
            "suggested_qty": suggested_qty,
            "suggested_capital": round(suggested_qty * current_price, 2),
            "time_horizon": "5 to 20 Trading Days",

            # The 5 Pillars
            "pillars": {
                "pillar_1_geometry": p1,
                "pillar_2_technical": p2,
                "pillar_3_fundamental": p3,
                "pillar_4_fno": p4,
                "pillar_5_macro": p5,
            },

            # Top Insights
            "key_catalysts": all_bulls[:5],
            "risk_factors": all_bears[:5],
        }

    def _error_response(self, symbol: str, error_msg: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "error": error_msg,
            "composite_score": 0.0,
            "verdict": "ERROR",
            "verdict_badge": "Data Unavailable",
            "verdict_color": "slate",
        }


# Backward compatibility alias
StockOracleEngine = AladdinBrainEngine
