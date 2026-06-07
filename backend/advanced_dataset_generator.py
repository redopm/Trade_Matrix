"""
TradeMatrix - Advanced Dataset Generator v2
===========================================
Scans top Nifty stocks (3 years data) and generates training labels for
ALL popular chart patterns using pure mathematical/geometric detection.

MACRO CHART PATTERNS (19 types):
  Reversal:    Double Top, Double Bottom, Triple Top, Triple Bottom,
               Head & Shoulders (Top + Bottom), Rounded Top, Rounded Bottom
  Continuation: Ascending Triangle, Descending Triangle, Symmetrical Triangle,
                Rising Wedge, Falling Wedge,
                Bull Flag, Bear Flag, Bull Pennant, Bear Pennant,
                Cup & Handle, Bullish Rectangle, Bearish Rectangle

CANDLESTICK PATTERNS (9 types):
  Doji, Hammer, Shooting Star, Marubozu, Bullish/Bearish Engulfing,
  Morning Star, Evening Star, Spinning Top
"""

import os
import json
import random
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.signal import argrelextrema
from scipy.stats import linregress
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ─── Nifty 50 + Mid-Cap symbols ───────────────────────────────────────────────
SYMBOLS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "ITC.NS","SBIN.NS","BHARTIARTL.NS","LT.NS","HINDUNILVR.NS",
    "AXISBANK.NS","KOTAKBANK.NS","ASIANPAINT.NS","MARUTI.NS",
    "SUNPHARMA.NS","TITAN.NS","BAJFINANCE.NS","TATASTEEL.NS",
    "HCLTECH.NS","M&M.NS","WIPRO.NS","ULTRACEMCO.NS","POWERGRID.NS",
    "NTPC.NS","BAJAJFINSV.NS","NESTLEIND.NS","TECHM.NS","GRASIM.NS",
    "ONGC.NS","JSWSTEEL.NS","HINDALCO.NS","CIPLA.NS","INDUSINDBK.NS",
    "ADANIENT.NS","ADANIPORTS.NS","DIVISLAB.NS","COALINDIA.NS",
    "BAJAJ-AUTO.NS","DRREDDY.NS","EICHERMOT.NS","BRITANNIA.NS",
    "APOLLOHOSP.NS","HEROMOTOCO.NS","TATACONSUM.NS","HDFCLIFE.NS",
    "SBILIFE.NS","PIDILITIND.NS","HAVELLS.NS","DABUR.NS","BERGER.NS",
    "MCDOWELL-N.NS","COLPAL.NS","MARICO.NS","GODREJCP.NS","AMBUJACEM.NS",
    "SHREECEM.NS","GLAND.NS","LALPATHLAB.NS","METROPOLIS.NS",
    "ZYDUSLIFE.NS","TORNTPHARM.NS","AUROPHARMA.NS","LUPIN.NS",
    "BIOCON.NS","BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS",
    "MUTHOOTFIN.NS","CHOLAFIN.NS","MANAPPURAM.NS","PFC.NS","RECLTD.NS",
    "SAIL.NS","NMDC.NS","VEDL.NS","NATIONALUM.NS","MOIL.NS",
    "CUMMINSIND.NS","ABB.NS","BHEL.NS","SIEMENS.NS","THERMAX.NS",
    "CONCOR.NS","TATACOMM.NS","HFCL.NS","IRCTC.NS","DELHIVERY.NS",
]

LABELS_OUT = "data/advanced_labels.jsonl"
SUMMARY_OUT = "data/classes_summary.json"
MAX_PER_CLASS = 500     # Balanced cap per pattern class
PEAK_ORDER = 5          # Sensitivity of peak/trough detection


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_peaks_troughs(prices, order=PEAK_ORDER):
    peaks   = argrelextrema(prices, np.greater_equal, order=order)[0]
    troughs = argrelextrema(prices, np.less_equal,    order=order)[0]
    return peaks, troughs

def slope_of(x_arr, y_arr):
    """Returns linear regression slope over x_arr, y_arr."""
    if len(x_arr) < 2:
        return 0.0
    slope, _, _, _, _ = linregress(x_arr, y_arr)
    return slope

def pct_diff(a, b):
    """Percentage difference between two values."""
    if a == 0:
        return 0.0
    return abs(a - b) / a

def make_label(sym, df, start_idx, end_idx, name, is_bullish, confidence=0.92):
    """Helper to build a label dict."""
    return {
        "symbol":       sym,
        "pattern_name": name,
        "window_start": df.index[start_idx].strftime("%Y-%m-%d"),
        "window_end":   df.index[end_idx].strftime("%Y-%m-%d"),
        "confidence":   confidence,
        "is_bullish":   bool(is_bullish) if is_bullish is not None else None,
        "label_source": "algorithmic",
        "created_at":   datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER A — CANDLESTICK PATTERNS  (9 types)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_candlestick_patterns(df, sym):
    labels = []
    O = df['Open'].values
    C = df['Close'].values
    H = df['High'].values
    L = df['Low'].values

    body       = np.abs(C - O)
    rng        = np.where((H - L) == 0, 0.001, H - L)
    upper_wick = H - np.maximum(O, C)
    lower_wick = np.minimum(O, C) - L

    W = 10   # candlestick window

    for i in range(3, len(df)):
        b, r, u, d = body[i], rng[i], upper_wick[i], lower_wick[i]
        o, c = O[i], C[i]

        # 1. DOJI
        if b < 0.08 * r:
            labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                     'cdl_doji', None, 0.93))

        # 2. SPINNING TOP  (small body, both wicks present)
        if 0.08*r <= b <= 0.3*r and u > 0.2*r and d > 0.2*r:
            labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                     'cdl_spinning_top', None, 0.90))

        # 3. HAMMER  (small body at top, long lower wick, after downtrend)
        if b > 0.05*r and d > 2*b and u < 0.15*r:
            labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                     'cdl_hammer', True, 0.93))

        # 4. SHOOTING STAR  (small body at bottom, long upper wick)
        if b > 0.05*r and u > 2*b and d < 0.15*r:
            labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                     'cdl_shooting_star', False, 0.93))

        # 5. MARUBOZU  (huge body, almost no wicks)
        if b > 0.80*r and u < 0.05*r and d < 0.05*r:
            labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                     'cdl_marubozu', c > o, 0.95))

        # 6 & 7. BULLISH / BEARISH ENGULFING
        if i >= 1:
            p_o, p_c = O[i-1], C[i-1]
            p_b = body[i-1]
            if p_b > 0 and b > p_b:
                if p_c < p_o and c > o and c >= p_o and o <= p_c:
                    labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                             'cdl_bullish_engulfing', True, 0.95))
                elif p_c > p_o and c < o and c <= p_o and o >= p_c:
                    labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                             'cdl_bearish_engulfing', False, 0.95))

        # 8 & 9. MORNING STAR / EVENING STAR  (3-candle)
        if i >= 2:
            p2_o, p2_c, p2_b = O[i-2], C[i-2], body[i-2]
            p1_b = body[i-1]
            if p2_b > 0 and p1_b < 0.35*p2_b and b > 0.5*p2_b:
                # Morning Star: bearish → star → bullish
                if p2_c < p2_o and c > o:
                    labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                             'cdl_morning_star', True, 0.95))
                # Evening Star: bullish → star → bearish
                elif p2_c > p2_o and c < o:
                    labels.append(make_label(sym, df, max(0,i-W), min(len(df)-1,i+1),
                                             'cdl_evening_star', False, 0.95))

    return labels


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER B — MACRO CHART PATTERNS  (19 types)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_macro_patterns(df, sym):
    labels  = []
    prices  = df['Close'].values
    volumes = df['Volume'].values
    n       = len(prices)

    peaks, troughs = get_peaks_troughs(prices)

    # ── 1. DOUBLE TOP ──────────────────────────────────────────────────────────
    for i in range(len(peaks)-1):
        p1, p2 = peaks[i], peaks[i+1]
        gap = p2 - p1
        if 10 <= gap <= 60 and pct_diff(prices[p1], prices[p2]) < 0.025:
            s = max(0, p1-5); e = min(n-1, p2+8)
            labels.append(make_label(sym, df, s, e, 'double_top', False, 0.92))

    # ── 2. DOUBLE BOTTOM ───────────────────────────────────────────────────────
    for i in range(len(troughs)-1):
        t1, t2 = troughs[i], troughs[i+1]
        gap = t2 - t1
        if 10 <= gap <= 60 and pct_diff(prices[t1], prices[t2]) < 0.025:
            s = max(0, t1-5); e = min(n-1, t2+8)
            labels.append(make_label(sym, df, s, e, 'double_bottom', True, 0.92))

    # ── 3. TRIPLE TOP ──────────────────────────────────────────────────────────
    for i in range(len(peaks)-2):
        p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
        if (pct_diff(prices[p1], prices[p2]) < 0.025 and
                pct_diff(prices[p2], prices[p3]) < 0.025 and
                p3 - p1 <= 90):
            s = max(0, p1-5); e = min(n-1, p3+8)
            labels.append(make_label(sym, df, s, e, 'triple_top', False, 0.93))

    # ── 4. TRIPLE BOTTOM ───────────────────────────────────────────────────────
    for i in range(len(troughs)-2):
        t1, t2, t3 = troughs[i], troughs[i+1], troughs[i+2]
        if (pct_diff(prices[t1], prices[t2]) < 0.025 and
                pct_diff(prices[t2], prices[t3]) < 0.025 and
                t3 - t1 <= 90):
            s = max(0, t1-5); e = min(n-1, t3+8)
            labels.append(make_label(sym, df, s, e, 'triple_bottom', True, 0.93))

    # ── 5. HEAD & SHOULDERS TOP ────────────────────────────────────────────────
    for i in range(len(peaks)-2):
        p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
        if (prices[p2] > prices[p1] and prices[p2] > prices[p3] and
                pct_diff(prices[p1], prices[p3]) < 0.04 and
                p3 - p1 <= 100):
            s = max(0, p1-5); e = min(n-1, p3+8)
            labels.append(make_label(sym, df, s, e, 'head_and_shoulders_top', False, 0.93))

    # ── 6. HEAD & SHOULDERS BOTTOM (INVERSE) ──────────────────────────────────
    for i in range(len(troughs)-2):
        t1, t2, t3 = troughs[i], troughs[i+1], troughs[i+2]
        if (prices[t2] < prices[t1] and prices[t2] < prices[t3] and
                pct_diff(prices[t1], prices[t3]) < 0.04 and
                t3 - t1 <= 100):
            s = max(0, t1-5); e = min(n-1, t3+8)
            labels.append(make_label(sym, df, s, e, 'head_and_shoulders_bottom', True, 0.93))

    # ── 7. ROUNDED TOP (Saucer Top) ───────────────────────────────────────────
    # Price forms an arc — peaks in the middle, falling on both sides
    W = 40
    for start in range(0, n - W, W // 2):
        end = min(n-1, start + W)
        seg = prices[start:end]
        mid = len(seg) // 2
        if (seg[mid] == max(seg) and            # peak is in the middle third
                start + mid//2 < start + mid < end - mid//2 and
                pct_diff(seg[0], seg[-1]) < 0.04):
            labels.append(make_label(sym, df, start, end, 'rounded_top', False, 0.88))

    # ── 8. ROUNDED BOTTOM (Saucer / Cup base) ─────────────────────────────────
    W = 40
    for start in range(0, n - W, W // 2):
        end = min(n-1, start + W)
        seg = prices[start:end]
        mid = len(seg) // 2
        if (seg[mid] == min(seg) and
                pct_diff(seg[0], seg[-1]) < 0.04):
            labels.append(make_label(sym, df, start, end, 'rounded_bottom', True, 0.88))

    # ── TRENDLINE-BASED PATTERNS  ──────────────────────────────────────────────
    # We scan rolling windows; fit upper & lower trendlines via peaks/troughs
    WIN_SIZES = [25, 35, 45, 60]

    for W in WIN_SIZES:
        for start in range(0, n - W, W // 3):
            end = min(n-1, start + W)
            seg = prices[start:end]
            seg_vol = volumes[start:end]

            local_peaks, local_troughs = get_peaks_troughs(seg, order=3)
            if len(local_peaks) < 2 or len(local_troughs) < 2:
                continue

            # Slopes of upper (peaks) and lower (troughs) trendlines
            upper_slope = slope_of(local_peaks, seg[local_peaks])
            lower_slope = slope_of(local_troughs, seg[local_troughs])

            upper_start = seg[local_peaks[0]]
            lower_start = seg[local_troughs[0]]
            upper_end   = seg[local_peaks[-1]]
            lower_end   = seg[local_troughs[-1]]

            pct_up = pct_diff(upper_start, upper_end)
            pct_lo = pct_diff(lower_start, lower_end)

            slope_conv = abs(upper_slope - lower_slope)   # convergence

            # ── 9. ASCENDING TRIANGLE ──────────────────────────────────────────
            # Flat resistance top + rising support bottom
            if pct_up < 0.015 and lower_slope > 0.05 and slope_conv > 0.03:
                labels.append(make_label(sym, df, start, end,
                                         'ascending_triangle', True, 0.91))

            # ── 10. DESCENDING TRIANGLE ────────────────────────────────────────
            # Falling resistance top + flat support bottom
            if pct_lo < 0.015 and upper_slope < -0.05 and slope_conv > 0.03:
                labels.append(make_label(sym, df, start, end,
                                         'descending_triangle', False, 0.91))

            # ── 11. SYMMETRICAL TRIANGLE ───────────────────────────────────────
            # Both sides converging (falling top, rising bottom)
            if upper_slope < -0.02 and lower_slope > 0.02 and slope_conv > 0.02:
                labels.append(make_label(sym, df, start, end,
                                         'symmetrical_triangle', None, 0.88))

            # ── 12. RISING WEDGE (Bearish) ─────────────────────────────────────
            # Both top and bottom rising but converging — bearish reversal
            if upper_slope > 0.02 and lower_slope > 0.02 and lower_slope > upper_slope:
                labels.append(make_label(sym, df, start, end,
                                         'rising_wedge', False, 0.90))

            # ── 13. FALLING WEDGE (Bullish) ────────────────────────────────────
            # Both top and bottom falling but converging — bullish reversal
            if upper_slope < -0.02 and lower_slope < -0.02 and upper_slope < lower_slope:
                labels.append(make_label(sym, df, start, end,
                                         'falling_wedge', True, 0.90))

            # ── 14 & 15. BULL FLAG / BEAR FLAG ────────────────────────────────
            # Flag = sharp directional pole THEN tight parallel channel
            # Pole: first 1/3 of window; Flag: last 2/3
            pole_end = start + W // 3
            flag_seg = prices[pole_end:end]
            pole_seg = prices[start:pole_end]

            if len(pole_seg) >= 5 and len(flag_seg) >= 8:
                pole_move_pct = (pole_seg[-1] - pole_seg[0]) / pole_seg[0]
                flag_range_pct = (max(flag_seg) - min(flag_seg)) / min(flag_seg)

                # Bull Flag: pole is a sharp rally (+7%) + flag is tight (<3%)
                if pole_move_pct > 0.07 and flag_range_pct < 0.03:
                    flag_slope = slope_of(np.arange(len(flag_seg)), flag_seg)
                    if flag_slope <= 0:   # flag drifts slightly downward
                        labels.append(make_label(sym, df, start, end,
                                                 'bull_flag', True, 0.92))

                # Bear Flag: pole is a sharp decline (-7%) + flag is tight (<3%)
                if pole_move_pct < -0.07 and flag_range_pct < 0.03:
                    flag_slope = slope_of(np.arange(len(flag_seg)), flag_seg)
                    if flag_slope >= 0:   # flag drifts slightly upward
                        labels.append(make_label(sym, df, start, end,
                                                 'bear_flag', False, 0.92))

            # ── 16 & 17. BULL PENNANT / BEAR PENNANT ──────────────────────────
            # Pennant = sharp pole + symmetrical triangle consolidation
            if len(pole_seg) >= 5 and len(flag_seg) >= 8:
                pole_move_pct = (pole_seg[-1] - pole_seg[0]) / pole_seg[0]
                pk, tr = get_peaks_troughs(flag_seg, order=2)
                if len(pk) >= 2 and len(tr) >= 2:
                    pennant_upper_slope = slope_of(pk, flag_seg[pk])
                    pennant_lower_slope = slope_of(tr, flag_seg[tr])
                    pennant_conv = pennant_lower_slope > 0 and pennant_upper_slope < 0

                    if pole_move_pct > 0.07 and pennant_conv:
                        labels.append(make_label(sym, df, start, end,
                                                 'bull_pennant', True, 0.91))

                    if pole_move_pct < -0.07 and pennant_conv:
                        labels.append(make_label(sym, df, start, end,
                                                 'bear_pennant', False, 0.91))

            # ── 18. BULLISH RECTANGLE (Support / Resistance channel) ───────────
            # Price bounces in a horizontal box before breakout up
            if (pct_up < 0.02 and pct_lo < 0.02 and
                    abs(upper_slope) < 0.02 and abs(lower_slope) < 0.02):
                if prices[end] > prices[start]:
                    labels.append(make_label(sym, df, start, end,
                                             'bullish_rectangle', True, 0.88))
                else:
                    labels.append(make_label(sym, df, start, end,
                                             'bearish_rectangle', False, 0.88))

    # ── 19. CUP & HANDLE ──────────────────────────────────────────────────────
    # Cup = rounded bottom (U-shape) + Handle = small pullback (~5-15%)
    CUP_W = 50
    for start in range(0, n - CUP_W - 10, CUP_W // 2):
        cup_end = start + CUP_W
        if cup_end >= n:
            break
        cup = prices[start:cup_end]
        cup_min_idx = int(np.argmin(cup))
        # Cup rim should be roughly equal on both sides
        left_rim  = cup[0]
        right_rim = cup[-1]
        cup_floor = cup[cup_min_idx]

        depth_pct  = (left_rim - cup_floor) / left_rim if left_rim > 0 else 0
        rim_sym    = pct_diff(left_rim, right_rim)

        if (0.07 <= depth_pct <= 0.35 and
                rim_sym < 0.04 and
                cup_min_idx > CUP_W // 4 and
                cup_min_idx < 3 * CUP_W // 4):

            # Look for handle: small pullback after cup (next 5–15 days)
            handle_start = cup_end
            handle_end   = min(n-1, cup_end + 15)
            if handle_end > handle_start + 4:
                handle = prices[handle_start:handle_end]
                handle_pullback = (right_rim - min(handle)) / right_rim
                if 0.03 <= handle_pullback <= 0.15:
                    labels.append(make_label(sym, df, start, handle_end,
                                             'cup_and_handle', True, 0.93))

    return labels


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def process_symbol(sym):
    try:
        df = yf.download(sym, period="5y", progress=False)
        if df is None or df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df[['Open','High','Low','Close','Volume']].dropna()
        if len(df) < 100:
            return []

        result  = detect_candlestick_patterns(df, sym)
        result += detect_macro_patterns(df, sym)
        return result
    except Exception as e:
        print(f"  [ERROR] {sym}: {e}")
        return []


def main():
    os.makedirs("data", exist_ok=True)

    all_labels = []
    total = len(SYMBOLS)
    print(f"\n[START] Scanning {total} stocks x 5 years for ALL chart patterns...\n")

    for idx, sym in enumerate(SYMBOLS, 1):
        print(f"  [{idx:>2}/{total}] {sym}", end=" ", flush=True)
        lbls = process_symbol(sym)
        all_labels.extend(lbls)
        print(f"-> {len(lbls)} patterns found")

    print(f"\n[DONE] Total raw patterns detected: {len(all_labels)}")

    # ── Balance ────────────────────────────────────────────────────────────────
    pattern_groups = defaultdict(list)
    for lbl in all_labels:
        pattern_groups[lbl['pattern_name']].append(lbl)

    print(f"[DONE] Distinct pattern classes    : {len(pattern_groups)}\n")
    print("Pattern-wise count (before balancing):")
    for pname, items in sorted(pattern_groups.items(), key=lambda x: -len(x[1])):
        bar = "#" * (len(items) // 20)
        print(f"  {pname:<35} {len(items):>5}  {bar}")

    balanced = []
    for pname, items in pattern_groups.items():
        if len(items) > MAX_PER_CLASS:
            items = random.sample(items, MAX_PER_CLASS)
        # Normalise is_bullish to native bool
        for lbl in items:
            if lbl.get('is_bullish') is not None:
                lbl['is_bullish'] = bool(lbl['is_bullish'])
        balanced.extend(items)

    random.shuffle(balanced)

    with open(LABELS_OUT, "w") as f:
        for lbl in balanced:
            f.write(json.dumps(lbl) + "\n")

    classes = sorted(pattern_groups.keys())
    with open(SUMMARY_OUT, "w") as f:
        json.dump({"total_classes": len(classes), "classes": classes}, f, indent=2)

    print(f"\n" + "-"*55)
    print(f"[SAVED] {len(balanced):,} balanced labels -> {LABELS_OUT}")
    print(f"[SAVED] Class summary          -> {SUMMARY_OUT}")
    print(f"\nPattern classes included ({len(classes)} total):")
    for c in classes:
        print(f"  - {c}")
    print(f"\n[NEXT] Upload '{LABELS_OUT}' to Google Colab and Run All!")


if __name__ == "__main__":
    main()
