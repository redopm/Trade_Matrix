"""
Fibonacci Retracement Service — Phase 4
Automatically detects Swing High/Low and calculates Fibonacci levels.

Key Functions:
  - find_swing_high_low(): ZigZag-based pivot detection (180-day lookback)
  - calculate_fib_levels(): Standard retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)
  - get_fib_analysis(): Full analysis — levels + nearest level + confluence flag
"""
from typing import Optional, Any
import pandas as pd
import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Standard Fibonacci Ratios
FIB_RATIOS = {
    "0.0":   0.0,
    "23.6":  0.236,
    "38.2":  0.382,
    "50.0":  0.500,
    "61.8":  0.618,   # ⭐ Golden Ratio — Strongest support/resistance
    "78.6":  0.786,
    "100.0": 1.000,
}

# Confluence tolerance: price within 2% of a Fib level = confluence
CONFLUENCE_TOLERANCE = 0.02

# Confluence score weights per level (higher = more significant level)
FIB_SCORE_WEIGHTS = {
    "61.8": 10.0,   # Golden Ratio — Strongest
    "50.0": 8.0,    # Midpoint — Very strong
    "38.2": 6.0,    # Common retracement
    "78.6": 5.0,    # Deep retracement
    "23.6": 3.0,    # Shallow retracement
    "0.0":  1.0,
    "100.0": 1.0,
}

LOOKBACK_DAYS = 180  # 6 months — Best for medium-term swing trading


def find_swing_high_low_with_direction(
    df: pd.DataFrame,
    lookback: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """
    Find the most significant Swing High and Swing Low in the last N days
    along with chronological impulse direction.

    is_uptrend_impulse=True when swing_low occurred BEFORE swing_high
    (a prior rally followed by pullback support).
    """
    if df is None or df.empty or len(df) < 20:
        return {"swing_high": None, "swing_low": None, "is_uptrend_impulse": True}

    window = df.tail(lookback).copy()
    highs = window["High"].values
    lows = window["Low"].values

    pivot_window = 5
    n = len(highs)

    pivot_highs: list[tuple[int, float]] = []
    pivot_lows: list[tuple[int, float]] = []

    for i in range(pivot_window, n - pivot_window):
        left_high = highs[i - pivot_window : i]
        right_high = highs[i + 1 : i + pivot_window + 1]
        left_low = lows[i - pivot_window : i]
        right_low = lows[i + 1 : i + pivot_window + 1]

        if highs[i] >= max(left_high) and highs[i] >= max(right_high):
            pivot_highs.append((i, float(highs[i])))

        if lows[i] <= min(left_low) and lows[i] <= min(right_low):
            pivot_lows.append((i, float(lows[i])))

    global_high_idx = int(np.argmax(highs))
    global_high_val = float(highs[global_high_idx])
    global_low_idx = int(np.argmin(lows))
    global_low_val = float(lows[global_low_idx])

    if pivot_highs:
        high_idx, swing_high = max(pivot_highs, key=lambda x: x[1])
        if global_high_val > swing_high:
            high_idx, swing_high = global_high_idx, global_high_val
    else:
        high_idx, swing_high = global_high_idx, global_high_val

    if pivot_lows:
        low_idx, swing_low = min(pivot_lows, key=lambda x: x[1])
        if global_low_val < swing_low:
            low_idx, swing_low = global_low_idx, global_low_val
    else:
        low_idx, swing_low = global_low_idx, global_low_val

    if swing_high <= swing_low:
        high_idx, swing_high = global_high_idx, global_high_val
        low_idx, swing_low = global_low_idx, global_low_val

    is_uptrend_impulse = bool(low_idx <= high_idx)

    return {
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "is_uptrend_impulse": is_uptrend_impulse,
    }


def find_swing_high_low(
    df: pd.DataFrame,
    lookback: int = LOOKBACK_DAYS,
) -> tuple[Optional[float], Optional[float]]:
    """
    Find the most significant Swing High and Swing Low in the last N days.
    """
    res = find_swing_high_low_with_direction(df, lookback=lookback)
    return res["swing_high"], res["swing_low"]


def calculate_fib_levels(
    swing_high: float,
    swing_low: float,
) -> dict[str, float]:
    """
    Calculate standard Fibonacci Retracement levels between a Swing High and Swing Low.

    Formula:
        Fib Level = Swing High - (ratio × (Swing High - Swing Low))

    This gives retracement from HIGH to LOW (bearish retracement = price falling).
    For LONG setups (price rising from low), levels represent support zones.

    Args:
        swing_high: The highest pivot price in the lookback window
        swing_low: The lowest pivot price in the lookback window

    Returns:
        Dict mapping label → price (e.g., {"61.8": 1234.5})
    """
    price_range = swing_high - swing_low
    if price_range <= 0:
        return {}

    levels = {}
    for label, ratio in FIB_RATIOS.items():
        # Retracement from high: High - ratio * range
        levels[label] = round(swing_high - (ratio * price_range), 2)

    return levels


def get_nearest_fib_level(
    current_price: float,
    fib_levels: dict[str, float],
    tolerance: float = CONFLUENCE_TOLERANCE,
) -> Optional[dict[str, Any]]:
    """
    Find which Fibonacci level the current price is closest to.

    Args:
        current_price: Latest close price of the stock
        fib_levels: Dict of {"61.8": 1234.5, ...}
        tolerance: Max % distance to qualify as "near" (default: 2%)

    Returns:
        Dict with level info if within tolerance, else None
        Example: {"level": "61.8", "price": 1234.5, "distance_pct": 0.8, "score": 10.0}
    """
    if not fib_levels or current_price <= 0:
        return None

    best_match = None
    best_distance = float("inf")

    for label, fib_price in fib_levels.items():
        if fib_price <= 0:
            continue
        distance_pct = abs((current_price - fib_price) / fib_price) * 100

        if distance_pct <= (tolerance * 100) and distance_pct < best_distance:
            best_distance = distance_pct
            best_match = {
                "level":        label,
                "price":        fib_price,
                "distance_pct": round(distance_pct, 2),
                "score":        FIB_SCORE_WEIGHTS.get(label, 1.0),
            }

    return best_match


def get_fib_analysis(
    df: pd.DataFrame,
    current_price: float,
    lookback: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """
    Main entry point: Full Fibonacci analysis for a stock.

    Steps:
      1. Find Swing High/Low from last N days
      2. Calculate all Fibonacci levels
      3. Check if current price is near any level (confluence)
      4. Return all data in a clean dict

    Args:
        df: OHLCV DataFrame
        current_price: Latest close price
        lookback: Days to look back for swing detection

    Returns:
        Dict with all fibonacci fields ready to be stored in database/signal
    """
    result: dict[str, Any] = {
        "fib_swing_high":       None,
        "fib_swing_low":        None,
        "fib_is_uptrend_impulse": True,
        "fib_level_0":          None,
        "fib_level_236":        None,
        "fib_level_382":        None,
        "fib_level_500":        None,
        "fib_level_618":        None,
        "fib_level_786":        None,
        "fib_level_100":        None,
        "fib_nearest_level":    None,  # e.g. "61.8"
        "fib_nearest_price":    None,
        "fib_confluence":       False,
        "fib_confluence_score": 0.0,
    }

    try:
        dir_info = find_swing_high_low_with_direction(df, lookback)
        swing_high = dir_info["swing_high"]
        swing_low = dir_info["swing_low"]
        if swing_high is None or swing_low is None:
            return result

        fib_levels = calculate_fib_levels(swing_high, swing_low)
        if not fib_levels:
            return result

        nearest = get_nearest_fib_level(current_price, fib_levels)

        result["fib_swing_high"]    = swing_high
        result["fib_swing_low"]     = swing_low
        result["fib_is_uptrend_impulse"] = dir_info["is_uptrend_impulse"]
        result["fib_level_0"]       = fib_levels.get("0.0")
        result["fib_level_236"]     = fib_levels.get("23.6")
        result["fib_level_382"]     = fib_levels.get("38.2")
        result["fib_level_500"]     = fib_levels.get("50.0")
        result["fib_level_618"]     = fib_levels.get("61.8")
        result["fib_level_786"]     = fib_levels.get("78.6")
        result["fib_level_100"]     = fib_levels.get("100.0")

        if nearest:
            result["fib_nearest_level"]    = nearest["level"]
            result["fib_nearest_price"]    = nearest["price"]
            result["fib_confluence"]       = True
            result["fib_confluence_score"] = nearest["score"]
            logger.debug(
                f"Fibonacci confluence: price ₹{current_price} near {nearest['level']}% "
                f"(₹{nearest['price']}, dist={nearest['distance_pct']}%)"
            )

    except Exception as e:
        logger.error(f"Fibonacci analysis failed: {e}")

    return result
