"""
Feature Extractor Service — Phase 2
Extracts 23 geometric features from OHLCV price data for pattern classification.

These features replace image-based CNN inference at production time:
- No GPU required
- Microsecond inference speed
- Fully interpretable
- Works on raw OHLCV without any image generation

Feature Categories:
  1. Peak/Trough Structure (8 features)
  2. Trendline Geometry (5 features)
  3. Volume Confirmation (4 features)
  4. Momentum State (3 features)
  5. Pattern Metrics (3 features)
"""
from typing import Any, Optional
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, argrelextrema
from scipy.stats import linregress

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """
    Extracts 23 geometric features from a price window.
    
    These features are used both for:
    1. Training the XGBoost model (alongside Gemini labels)
    2. Real-time inference (no image needed)
    """

    FEATURE_NAMES = [
        # Peak/Trough structure
        "n_peaks", "n_troughs",
        "peak_height_mean", "peak_height_std",
        "trough_depth_mean", "trough_depth_std",
        "peak_symmetry_score", "trough_symmetry_score",
        # Trendline geometry
        "upper_trendline_slope", "lower_trendline_slope",
        "trendline_convergence",
        "neckline_level_pct", "neckline_slope",
        # Volume confirmation
        "volume_at_breakout_ratio", "volume_trend_slope",
        "volume_peak_alignment", "obv_slope",
        # Momentum state
        "rsi_at_window_end", "rsi_trend_slope",
        "macd_crossovers_count",
        # Pattern metrics
        "price_range_pct", "recovery_from_low_pct",
        "pattern_compactness",
    ]

    def __init__(self) -> None:
        self.cfg = settings

    def extract(
        self, df: pd.DataFrame, window_days: Optional[int] = None
    ) -> Optional[dict[str, float]]:
        """
        Extract all 23 features from a price DataFrame window.

        Args:
            df: OHLCV DataFrame (should be 30-90 days)
            window_days: Force window size (uses last N days)

        Returns:
            Dict of {feature_name: value} or None on failure
        """
        if df is None or df.empty:
            return None

        try:
            window = df.tail(window_days or self.cfg.CHART_WINDOW_DAYS).copy()
            if len(window) < 20:
                return None

            close = window["Close"].values
            high = window["High"].values
            low = window["Low"].values
            volume = window["Volume"].values
            n = len(close)

            # Normalize price to [0, 1] for slope comparisons
            price_min, price_max = close.min(), close.max()
            price_range = price_max - price_min
            if price_range < 1e-6:
                return None

            close_norm = (close - price_min) / price_range

            features = {}

            # ── 1. Peak/Trough Structure ──────────────────────────────────────
            peaks_idx, troughs_idx = self._find_peaks_troughs(close)

            features["n_peaks"] = float(len(peaks_idx))
            features["n_troughs"] = float(len(troughs_idx))

            peak_heights = close[peaks_idx] if len(peaks_idx) else np.array([close[-1]])
            trough_depths = close[troughs_idx] if len(troughs_idx) else np.array([close[0]])

            features["peak_height_mean"] = float(np.mean(peak_heights) / price_max)
            features["peak_height_std"] = float(np.std(peak_heights) / price_range + 1e-8)
            features["trough_depth_mean"] = float(np.mean(trough_depths) / price_max)
            features["trough_depth_std"] = float(np.std(trough_depths) / price_range + 1e-8)

            # Symmetry: ratio of left vs right height (for Double Bottom/Top)
            features["peak_symmetry_score"] = self._symmetry_score(peak_heights)
            features["trough_symmetry_score"] = self._symmetry_score(trough_depths)

            # ── 2. Trendline Geometry ─────────────────────────────────────────
            # Fit lines through peaks (resistance) and troughs (support)
            upper_slope = self._trendline_slope(peaks_idx, close[peaks_idx], n)
            lower_slope = self._trendline_slope(troughs_idx, close[troughs_idx], n)

            features["upper_trendline_slope"] = upper_slope
            features["lower_trendline_slope"] = lower_slope
            # Convergence: if upper going down and lower going up → triangle
            features["trendline_convergence"] = float(upper_slope - lower_slope)

            # Neckline: the resistance level that price needs to break
            neckline = float(np.percentile(high, 75))
            features["neckline_level_pct"] = float((neckline - price_min) / price_range)
            # Neckline slope over last 20 days
            last_20_high = high[-20:]
            if len(last_20_high) >= 5:
                nl_slope, _, _, _, _ = linregress(range(len(last_20_high)), last_20_high)
                features["neckline_slope"] = float(nl_slope / price_range)
            else:
                features["neckline_slope"] = 0.0

            # ── 3. Volume Confirmation ────────────────────────────────────────
            avg_vol = np.mean(volume) + 1e-8
            # Volume on last 5 bars vs average (breakout confirmation)
            breakout_vol = np.mean(volume[-5:]) / avg_vol
            features["volume_at_breakout_ratio"] = float(min(breakout_vol, 5.0))

            # Volume trend: is it increasing or decreasing?
            if len(volume) >= 10:
                vol_slope, _, _, _, _ = linregress(range(len(volume)), volume)
                features["volume_trend_slope"] = float(np.clip(vol_slope / avg_vol, -2, 2))
            else:
                features["volume_trend_slope"] = 0.0

            # Volume at troughs vs peaks (for reversal confirmation)
            vol_at_troughs = np.mean(volume[troughs_idx]) if len(troughs_idx) else avg_vol
            vol_at_peaks = np.mean(volume[peaks_idx]) if len(peaks_idx) else avg_vol
            features["volume_peak_alignment"] = float(
                vol_at_troughs / (vol_at_peaks + 1e-8)
            )

            # OBV trend slope
            obv = self._compute_obv(close, volume)
            if len(obv) >= 5:
                obv_slope, _, _, _, _ = linregress(range(len(obv)), obv)
                features["obv_slope"] = float(np.clip(obv_slope / (avg_vol + 1e-8), -2, 2))
            else:
                features["obv_slope"] = 0.0

            # ── 4. Momentum State ─────────────────────────────────────────────
            rsi = self._compute_rsi(close, 14)
            features["rsi_at_window_end"] = float(rsi[-1]) / 100.0

            if len(rsi) >= 10:
                rsi_slope, _, _, _, _ = linregress(range(len(rsi)), rsi)
                features["rsi_trend_slope"] = float(np.clip(rsi_slope, -5, 5))
            else:
                features["rsi_trend_slope"] = 0.0

            # MACD crossovers (signal × direction changes)
            features["macd_crossovers_count"] = float(
                self._count_macd_crossovers(close)
            )

            # ── 5. Pattern Metrics ────────────────────────────────────────────
            features["price_range_pct"] = float(price_range / price_min * 100)

            # Recovery: how much has price recovered from lowest point
            lowest_idx = np.argmin(close)
            recovery = (close[-1] - close[lowest_idx]) / (price_range + 1e-8)
            features["recovery_from_low_pct"] = float(max(0.0, recovery))

            # Pattern compactness: width-to-height ratio
            pattern_width = n
            features["pattern_compactness"] = float(pattern_width / (price_range / price_min * 100 + 1e-8))

            return features

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def features_to_vector(self, features: dict[str, float]) -> Optional[np.ndarray]:
        """Convert feature dict to ordered numpy array for ML model."""
        if not features:
            return None
        try:
            return np.array([
                features.get(name, 0.0) for name in self.FEATURE_NAMES
            ], dtype=np.float32)
        except Exception:
            return None

    def _find_peaks_troughs(
        self, close: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Find significant peaks and troughs using scipy."""
        price_range = close.max() - close.min()
        prominence = max(price_range * self.cfg.PEAK_PROMINENCE_PCT, 1.0)

        peaks_idx, _ = find_peaks(
            close,
            prominence=prominence,
            distance=self.cfg.PEAK_DISTANCE_DAYS,
        )
        troughs_idx, _ = find_peaks(
            -close,
            prominence=prominence,
            distance=self.cfg.PEAK_DISTANCE_DAYS,
        )
        return peaks_idx, troughs_idx

    @staticmethod
    def _symmetry_score(heights: np.ndarray) -> float:
        """
        Score how symmetric peaks/troughs are (key for Double Bottom/Top).
        1.0 = perfect symmetry, 0.0 = very asymmetric
        """
        if len(heights) < 2:
            return 0.5
        if len(heights) == 2:
            ratio = min(heights) / (max(heights) + 1e-8)
            return float(ratio)
        # For 3+ points (H&S): check if outer = inner pattern
        if len(heights) == 3:
            left, mid, right = heights[0], heights[1], heights[2]
            shoulder_sym = min(left, right) / (max(left, right) + 1e-8)
            return float(shoulder_sym * 0.8 + 0.2)  # Weighted
        return float(1.0 - np.std(heights) / (np.mean(heights) + 1e-8))

    @staticmethod
    def _trendline_slope(
        indices: np.ndarray, prices: np.ndarray, total_n: int
    ) -> float:
        """Fit a trendline through peaks or troughs and return normalized slope."""
        if len(indices) < 2:
            return 0.0
        try:
            slope, _, _, _, _ = linregress(indices, prices)
            return float(np.clip(slope / (prices.mean() + 1e-8), -0.5, 0.5))
        except Exception:
            return 0.0

    @staticmethod
    def _compute_obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """On-Balance Volume."""
        obv = np.zeros(len(close))
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv[i] = obv[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]
        return obv

    @staticmethod
    def _compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """RSI computation (pure numpy)."""
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.convolve(gain, np.ones(period) / period, mode="valid")
        avg_loss = np.convolve(loss, np.ones(period) / period, mode="valid")
        rs = avg_gain / (avg_loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))
        # Pad to original length
        rsi = np.concatenate([np.full(period, 50.0), rsi])
        return rsi[:len(close)]

    @staticmethod
    def _count_macd_crossovers(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> int:
        """Count MACD line crossovers with signal line."""
        if len(close) < slow + signal:
            return 0
        ema_fast = pd.Series(close).ewm(span=fast).mean().values
        ema_slow = pd.Series(close).ewm(span=slow).mean().values
        macd_line = ema_fast - ema_slow
        signal_line = pd.Series(macd_line).ewm(span=signal).mean().values
        diff = macd_line - signal_line
        crossovers = np.sum(np.diff(np.sign(diff)) != 0)
        return int(crossovers)
