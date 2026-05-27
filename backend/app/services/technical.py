"""
Technical Analysis Service
Computes all technical indicators using pandas-ta:
- EMA (200, 50)
- RSI (14)
- ATR (14) for dynamic SL
- MACD
- Bollinger Bands
- Volume analysis (VWAP proxy, OBV, 20D avg volume)
- Supertrend
- ADX
"""
from typing import Optional, Any
import pandas as pd
import pandas_ta as ta
import numpy as np

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    """
    Computes all technical indicators from OHLCV DataFrame.
    
    Usage:
        analyzer = TechnicalAnalyzer()
        result = analyzer.analyze(symbol, df)
    """

    def __init__(self) -> None:
        self.cfg = settings

    def analyze(
        self, symbol: str, df: pd.DataFrame
    ) -> dict[str, Any]:
        """
        Main entry point: compute all technical indicators.
        
        Args:
            symbol: Stock ticker
            df: OHLCV DataFrame with columns: Open, High, Low, Close, Volume
        
        Returns:
            Dict with all indicator values and filter pass/fail flags
        """
        if df is None or df.empty or len(df) < 200:
            return self._insufficient_data(symbol, df)

        try:
            df = df.copy()
            df = self._compute_indicators(df)

            # Get latest values (most recent candle)
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) >= 2 else latest

            result = self._extract_latest(symbol, df, latest, prev)
            result.update(self._evaluate_filters(result))

            return result

        except Exception as e:
            logger.error(f"Technical analysis failed for {symbol}: {e}")
            return self._insufficient_data(symbol, df)

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all technical indicators and add as new columns."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # ── Trend ─────────────────────────────────────────────────────────────
        df["EMA_200"] = ta.ema(close, length=200)
        df["EMA_50"] = ta.ema(close, length=50)
        df["EMA_20"] = ta.ema(close, length=20)
        df["SMA_200"] = ta.sma(close, length=200)

        # ── Momentum ──────────────────────────────────────────────────────────
        df["RSI"] = ta.rsi(close, length=self.cfg.RSI_PERIOD)
        
        # MACD
        macd_df = ta.macd(
            close,
            fast=self.cfg.MACD_FAST,
            slow=self.cfg.MACD_SLOW,
            signal=self.cfg.MACD_SIGNAL,
        )
        if macd_df is not None and not macd_df.empty:
            df["MACD"] = macd_df.iloc[:, 0]
            df["MACD_SIGNAL"] = macd_df.iloc[:, 2]
            df["MACD_HIST"] = macd_df.iloc[:, 1]

        # Stochastic
        stoch = ta.stoch(high, low, close)
        if stoch is not None and not stoch.empty:
            df["STOCH_K"] = stoch.iloc[:, 0]
            df["STOCH_D"] = stoch.iloc[:, 1]

        # ── Volatility ────────────────────────────────────────────────────────
        df["ATR"] = ta.atr(high, low, close, length=self.cfg.ATR_PERIOD)
        
        # Bollinger Bands
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and not bb.empty:
            df["BB_UPPER"] = bb.iloc[:, 0]
            df["BB_MID"] = bb.iloc[:, 1]
            df["BB_LOWER"] = bb.iloc[:, 2]
            df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"]

        # ── Volume ────────────────────────────────────────────────────────────
        df["OBV"] = ta.obv(close, volume)
        df["VOL_MA_20"] = ta.sma(volume, length=20)
        df["VOL_RATIO"] = volume / df["VOL_MA_20"]

        # ── Trend Strength ────────────────────────────────────────────────────
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            df["ADX"] = adx_df.iloc[:, 0]
            df["DI_PLUS"] = adx_df.iloc[:, 1]
            df["DI_MINUS"] = adx_df.iloc[:, 2]

        # ── Supertrend ────────────────────────────────────────────────────────
        st = ta.supertrend(high, low, close, length=10, multiplier=3)
        if st is not None and not st.empty:
            df["SUPERTREND"] = st.iloc[:, 0]
            df["SUPERTREND_DIR"] = st.iloc[:, 1]  # 1 = bullish, -1 = bearish

        # ── Pivot Points (Weekly) ─────────────────────────────────────────────
        # Simple daily pivot
        df["PIVOT"] = (high + low + close) / 3
        df["R1"] = 2 * df["PIVOT"] - low
        df["S1"] = 2 * df["PIVOT"] - high

        # ── Price Position ────────────────────────────────────────────────────
        df["PCT_FROM_52W_HIGH"] = (close / close.rolling(252).max() - 1) * 100
        df["PCT_FROM_52W_LOW"] = (close / close.rolling(252).min() - 1) * 100

        return df

    def _extract_latest(
        self,
        symbol: str,
        df: pd.DataFrame,
        latest: pd.Series,
        prev: pd.Series,
    ) -> dict[str, Any]:
        """Extract the most recent indicator values."""

        def safe(val) -> Optional[float]:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            return round(float(val), 4)

        close = float(latest["Close"])
        atr = safe(latest.get("ATR"))

        # ATR-based stop loss: entry - 2×ATR
        atr_sl = None
        atr_sl_pct = None
        if atr:
            atr_sl = round(close - (self.cfg.ATR_SL_MULTIPLIER * atr), 2)
            atr_sl_pct = round((atr_sl / close - 1) * 100, 2)

        # Fixed 5% stop loss
        fixed_sl = round(close * (1 - self.cfg.FIXED_SL_PCT), 2)

        # Take the more conservative (higher) SL
        effective_sl = max(atr_sl, fixed_sl) if atr_sl else fixed_sl
        target = round(close * (1 + self.cfg.TARGET_PROFIT_PCT), 2)

        # Risk-Reward ratio
        risk = close - effective_sl
        reward = target - close
        rr_ratio = round(reward / risk, 2) if risk > 0 else None

        return {
            "symbol": symbol,
            # Price
            "current_price": close,
            "open": safe(latest.get("Open")),
            "high": safe(latest.get("High")),
            "low": safe(latest.get("Low")),
            "volume": safe(latest.get("Volume")),
            # Trend
            "ema_200": safe(latest.get("EMA_200")),
            "ema_50": safe(latest.get("EMA_50")),
            "ema_20": safe(latest.get("EMA_20")),
            "sma_200": safe(latest.get("SMA_200")),
            "price_vs_ema200_pct": round((close / float(latest["EMA_200"]) - 1) * 100, 2)
            if latest.get("EMA_200") and not np.isnan(latest["EMA_200"])
            else None,
            # Momentum
            "rsi": safe(latest.get("RSI")),
            "rsi_prev": safe(prev.get("RSI")),
            "macd": safe(latest.get("MACD")),
            "macd_signal": safe(latest.get("MACD_SIGNAL")),
            "macd_hist": safe(latest.get("MACD_HIST")),
            "stoch_k": safe(latest.get("STOCH_K")),
            "stoch_d": safe(latest.get("STOCH_D")),
            # Volatility
            "atr": atr,
            "atr_pct": round((atr / close) * 100, 2) if atr else None,
            "bb_upper": safe(latest.get("BB_UPPER")),
            "bb_mid": safe(latest.get("BB_MID")),
            "bb_lower": safe(latest.get("BB_LOWER")),
            "bb_width": safe(latest.get("BB_WIDTH")),
            # Volume
            "obv": safe(latest.get("OBV")),
            "avg_volume_20d": safe(latest.get("VOL_MA_20")),
            "volume_ratio": safe(latest.get("VOL_RATIO")),
            # Trend Strength
            "adx": safe(latest.get("ADX")),
            "di_plus": safe(latest.get("DI_PLUS")),
            "di_minus": safe(latest.get("DI_MINUS")),
            # Supertrend
            "supertrend": safe(latest.get("SUPERTREND")),
            "supertrend_bullish": (
                latest.get("SUPERTREND_DIR") == 1.0
                if latest.get("SUPERTREND_DIR") is not None
                else None
            ),
            # 52-week
            "pct_from_52w_high": safe(latest.get("PCT_FROM_52W_HIGH")),
            "pct_from_52w_low": safe(latest.get("PCT_FROM_52W_LOW")),
            "week_52_high": round(float(df["High"].rolling(252).max().iloc[-1]), 2),
            "week_52_low": round(float(df["Low"].rolling(252).min().iloc[-1]), 2),
            # Trade Parameters
            "atr_stop_loss": atr_sl,
            "fixed_stop_loss": fixed_sl,
            "effective_stop_loss": effective_sl,
            "target_price": target,
            "risk_reward_ratio": rr_ratio,
            # Data quality
            "data_points": len(df),
            "latest_candle_date": str(df.index[-1].date()),
        }

    def _evaluate_filters(self, data: dict[str, Any]) -> dict[str, Any]:
        """Evaluate technical filter conditions."""
        filters = {}

        close = data.get("current_price", 0)
        ema_200 = data.get("ema_200")
        rsi = data.get("rsi")
        adx = data.get("adx")
        volume_ratio = data.get("volume_ratio")

        # Core Alpha Screener filter: Price > 200 EMA
        filters["passed_ema_200"] = (
            ema_200 is not None and close > 0 and close > ema_200
        )

        # Core Alpha Screener filter: RSI < 30 (oversold)
        filters["passed_rsi_oversold"] = (
            rsi is not None and rsi <= self.cfg.RSI_OVERSOLD
        )

        # Additional quality filters
        filters["passed_adx"] = (
            adx is None or adx >= 20  # Some trend strength required
        )

        filters["passed_volume"] = (
            volume_ratio is None or volume_ratio >= 0.5  # Not dead volume
        )

        # RSI exit signal (for existing positions)
        filters["rsi_overbought"] = (
            rsi is not None and rsi >= self.cfg.TARGET_RSI_OVERBOUGHT
        )

        # Technical filters combined
        filters["technicals_passed"] = (
            filters["passed_ema_200"] and filters["passed_rsi_oversold"]
        )

        return filters

    def get_chart_data(
        self,
        df: pd.DataFrame,
        days: int = 180,
    ) -> list[dict[str, Any]]:
        """
        Convert OHLCV DataFrame to chart-ready JSON format.
        Returns last N days of data.
        """
        if df is None or df.empty:
            return []

        df = df.tail(days).copy()
        df["EMA_50"] = ta.ema(df["Close"], length=50)
        df["EMA_200"] = ta.ema(df["Close"], length=200)
        df["RSI"] = ta.rsi(df["Close"], length=14)

        records = []
        for idx, row in df.iterrows():
            record = {
                "date": str(idx.date()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if not np.isnan(row["Volume"]) else 0,
            }
            for col in ["EMA_50", "EMA_200", "RSI"]:
                val = row.get(col)
                if val is not None and not np.isnan(float(val)):
                    record[col.lower()] = round(float(val), 2)
                else:
                    record[col.lower()] = None
            records.append(record)

        return records

    @staticmethod
    def _insufficient_data(
        symbol: str, df: Optional[pd.DataFrame]
    ) -> dict[str, Any]:
        n = len(df) if df is not None else 0
        return {
            "symbol": symbol,
            "error": f"Insufficient data (only {n} candles, need 200+)",
            "technicals_passed": False,
            "passed_ema_200": False,
            "passed_rsi_oversold": False,
            "data_points": n,
        }
