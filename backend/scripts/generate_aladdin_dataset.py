"""
The Aladdin Brain — Institutional Dataset Generator
===================================================
Pulls 5 years (2020-2026) of historical market data across 50 top liquid
Nifty constituents + Nifty 50 Macro index.

Constructs 35+ rolling technical, geometric, volatility, and macro features
with ZERO lookahead bias, and labels every trade candidate using
López de Prado's Triple Barrier Method:
  - Upper Barrier: +6.0% Profit Target
  - Lower Barrier: -3.0% Stop Loss
  - Time Barrier:  15 Trading Days

Output:
  - backend/models/aladdin_training_data.parquet
  - backend/models/aladdin_training_summary.json
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Top 50 liquid Nifty constituents across all major sectors
NIFTY_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "HINDUNILVR.NS", "AXISBANK.NS",
    "KOTAKBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
    "BAJFINANCE.NS", "TATASTEEL.NS", "HCLTECH.NS", "M&M.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS", "BAJAJFINSV.NS", "NESTLEIND.NS",
    "TECHM.NS", "GRASIM.NS", "ONGC.NS", "JSWSTEEL.NS", "HINDALCO.NS",
    "CIPLA.NS", "INDUSINDBK.NS", "ADANIENT.NS", "ADANIPORTS.NS", "DIVISLAB.NS",
    "COALINDIA.NS", "BAJAJ-AUTO.NS", "DRREDDY.NS", "EICHERMOT.NS", "BRITANNIA.NS",
    "APOLLOHOSP.NS", "HEROMOTOCO.NS", "TATACONSUM.NS", "SBILIFE.NS", "PIDILITIND.NS",
    "HAVELLS.NS", "FEDERALBNK.NS", "BEL.NS", "VEDL.NS", "SIEMENS.NS"
]

BENCHMARK_SYMBOL = "^NSEI"
START_DATE = "2020-01-01"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"
OUTPUT_PARQUET = OUTPUT_DIR / "aladdin_training_data.parquet"
OUTPUT_CSV = OUTPUT_DIR / "aladdin_training_data.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "aladdin_training_summary.json"


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close_prev = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return atr


def fetch_benchmark(start_date: str) -> pd.DataFrame:
    print(f"Fetching Macro Benchmark: {BENCHMARK_SYMBOL} (Nifty 50)...")
    ticker = yf.Ticker(BENCHMARK_SYMBOL)
    df = ticker.history(start=start_date, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    # Precompute Macro Indicators
    df["nifty_ema_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["nifty_ema_200"] = df["Close"].ewm(span=200, adjust=False).mean()
    df["nifty_dist_ema_50"] = (df["Close"] - df["nifty_ema_50"]) / df["nifty_ema_50"] * 100.0
    df["nifty_dist_ema_200"] = (df["Close"] - df["nifty_ema_200"]) / df["nifty_ema_200"] * 100.0
    df["nifty_rsi_14"] = compute_rsi(df["Close"], 14)
    df["nifty_ret_20"] = df["Close"].pct_change(20) * 100.0
    df["nifty_bull_regime"] = ((df["Close"] > df["nifty_ema_50"]) & (df["nifty_ema_50"] > df["nifty_ema_200"])).astype(float)
    print(f"Benchmark ready: {len(df)} candles.")
    return df


def engineer_features_and_labels(df: pd.DataFrame, benchmark_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Computes strictly causal features on day t, and Triple Barrier label forward t+1 to t+15.
    """
    if len(df) < 260:
        return pd.DataFrame()

    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    o = df["Open"]
    v = df["Volume"]

    # 1. EMAs & Distances
    ema_9 = c.ewm(span=9, adjust=False).mean()
    ema_20 = c.ewm(span=20, adjust=False).mean()
    ema_50 = c.ewm(span=50, adjust=False).mean()
    ema_200 = c.ewm(span=200, adjust=False).mean()

    dist_ema_20 = (c - ema_20) / ema_20 * 100.0
    dist_ema_50 = (c - ema_50) / ema_50 * 100.0
    dist_ema_200 = (c - ema_200) / ema_200 * 100.0
    ema_20_slope_5 = (ema_20 - ema_20.shift(5)) / ema_20.shift(5) * 100.0
    ema_50_slope_5 = (ema_50 - ema_50.shift(5)) / ema_50.shift(5) * 100.0
    ema_alignment = ((ema_20 > ema_50) & (ema_50 > ema_200)).astype(float) - ((ema_20 < ema_50) & (ema_50 < ema_200)).astype(float)

    # 2. RSI & Oscillators
    rsi_14 = compute_rsi(c, 14)
    rsi_slope_5 = rsi_14 - rsi_14.shift(5)
    rsi_oversold = (rsi_14 < 35.0).astype(float)
    rsi_overbought = (rsi_14 > 70.0).astype(float)

    # 3. MACD
    ema_12 = c.ewm(span=12, adjust=False).mean()
    ema_26 = c.ewm(span=26, adjust=False).mean()
    macd_line = (ema_12 - ema_26) / c * 100.0
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    macd_hist_slope_3 = macd_hist - macd_hist.shift(3)

    # 4. Volatility & Bollinger Bands
    atr_14 = compute_atr(df, 14)
    atr_pct = atr_14 / c * 100.0
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_upper = bb_mid + (2.0 * bb_std)
    bb_lower = bb_mid - (2.0 * bb_std)
    bb_width = (bb_upper - bb_lower) / (bb_mid + 1e-9) * 100.0
    bb_pos = (c - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # 5. Volume Dynamics
    vol_sma_20 = v.rolling(20).mean()
    vol_sma_50 = v.rolling(50).mean()
    vol_ratio_20 = v / (vol_sma_20 + 1e-9)
    vol_ratio_50 = v / (vol_sma_50 + 1e-9)
    vol_change_5 = (v - v.shift(5)) / (v.shift(5) + 1e-9)

    # 6. Trailing Geometry & Fibonacci Retracements
    high_52w = h.rolling(252).max()
    low_52w = l.rolling(252).min()
    dist_52w_high = (c - high_52w) / high_52w * 100.0
    dist_52w_low = (c - low_52w) / low_52w * 100.0

    swing_high_60 = h.rolling(60).max()
    swing_low_60 = l.rolling(60).min()
    dist_swing_high = (c - swing_high_60) / swing_high_60 * 100.0
    dist_swing_low = (c - swing_low_60) / swing_low_60 * 100.0

    fib_range = swing_high_60 - swing_low_60 + 1e-9
    fib_retrace_ratio = (swing_high_60 - c) / fib_range
    # Proximity to key Fib levels (50% and 61.8%)
    dist_fib_50 = (fib_retrace_ratio - 0.50).abs()
    dist_fib_618 = (fib_retrace_ratio - 0.618).abs()

    # 7. Candlestick Anatomy
    candle_range = h - l + 1e-9
    candle_body_ratio = (c - o).abs() / candle_range
    upper_wick_ratio = (h - np.maximum(o, c)) / candle_range
    lower_wick_ratio = (np.minimum(o, c) - l) / candle_range
    is_bullish_candle = (c > o).astype(float)

    # 8. Momentum returns
    ret_5d = c.pct_change(5) * 100.0
    ret_20d = c.pct_change(20) * 100.0

    # Build features dataframe
    feat = pd.DataFrame(index=df.index)
    feat["symbol"] = symbol
    feat["close"] = c
    feat["dist_ema_20"] = dist_ema_20
    feat["dist_ema_50"] = dist_ema_50
    feat["dist_ema_200"] = dist_ema_200
    feat["ema_20_slope_5"] = ema_20_slope_5
    feat["ema_50_slope_5"] = ema_50_slope_5
    feat["ema_alignment"] = ema_alignment
    feat["rsi_14"] = rsi_14
    feat["rsi_slope_5"] = rsi_slope_5
    feat["rsi_oversold"] = rsi_oversold
    feat["rsi_overbought"] = rsi_overbought
    feat["macd_line"] = macd_line
    feat["macd_signal"] = macd_signal
    feat["macd_hist"] = macd_hist
    feat["macd_hist_slope_3"] = macd_hist_slope_3
    feat["atr_pct"] = atr_pct
    feat["bb_width"] = bb_width
    feat["bb_pos"] = bb_pos
    feat["vol_ratio_20"] = vol_ratio_20
    feat["vol_ratio_50"] = vol_ratio_50
    feat["vol_change_5"] = vol_change_5
    feat["dist_52w_high"] = dist_52w_high
    feat["dist_52w_low"] = dist_52w_low
    feat["dist_swing_high"] = dist_swing_high
    feat["dist_swing_low"] = dist_swing_low
    feat["fib_retrace_ratio"] = fib_retrace_ratio
    feat["dist_fib_50"] = dist_fib_50
    feat["dist_fib_618"] = dist_fib_618
    feat["candle_body_ratio"] = candle_body_ratio
    feat["upper_wick_ratio"] = upper_wick_ratio
    feat["lower_wick_ratio"] = lower_wick_ratio
    feat["is_bullish_candle"] = is_bullish_candle
    feat["ret_5d"] = ret_5d
    feat["ret_20d"] = ret_20d

    # 9. Macro Alignment (Join with Benchmark)
    # Join on date index
    feat = feat.join(benchmark_df[[
        "nifty_dist_ema_50", "nifty_dist_ema_200", 
        "nifty_rsi_14", "nifty_ret_20", "nifty_bull_regime"
    ]], how="left")
    feat["nifty_dist_ema_50"] = feat["nifty_dist_ema_50"].ffill().bfill()
    feat["nifty_dist_ema_200"] = feat["nifty_dist_ema_200"].ffill().bfill()
    feat["nifty_rsi_14"] = feat["nifty_rsi_14"].ffill().bfill()
    feat["nifty_bull_regime"] = feat["nifty_bull_regime"].ffill().bfill()
    feat["rel_strength_nifty_20"] = feat["ret_20d"] - feat["nifty_ret_20"].ffill().bfill()

    # Drop the temporary nifty_ret_20 column
    feat.drop(columns=["nifty_ret_20"], inplace=True)

    # ── 10. TRIPLE BARRIER LABELING (López de Prado) ───────────────────────────
    # Target: +6.0% Profit Barrier
    # Stop:   -3.0% Stop Loss Barrier
    # Horizon: 15 trading days
    tp_mult = 1.060
    sl_mult = 0.970
    horizon = 15

    n = len(df)
    labels = np.full(n, np.nan)
    max_forward_rets = np.full(n, np.nan)
    min_forward_rets = np.full(n, np.nan)
    final_rets = np.full(n, np.nan)

    highs_arr = h.values
    lows_arr = l.values
    closes_arr = c.values

    # Start after 252 days warmup to ensure 52w high and 200 EMA are completely mature
    for i in range(252, n - horizon):
        entry_price = closes_arr[i]
        if np.isnan(entry_price) or entry_price <= 0:
            continue

        tp_price = entry_price * tp_mult
        sl_price = entry_price * sl_mult

        window_highs = highs_arr[i + 1 : i + 1 + horizon]
        window_lows = lows_arr[i + 1 : i + 1 + horizon]
        window_closes = closes_arr[i + 1 : i + 1 + horizon]

        max_forward_rets[i] = ((window_highs.max() - entry_price) / entry_price) * 100.0
        min_forward_rets[i] = ((window_lows.min() - entry_price) / entry_price) * 100.0
        final_rets[i] = ((window_closes[-1] - entry_price) / entry_price) * 100.0

        # Scan day by day in the 15-day window to see which barrier is hit first
        hit_tp_day = None
        hit_sl_day = None

        for d in range(horizon):
            if window_highs[d] >= tp_price and hit_tp_day is None:
                hit_tp_day = d
            if window_lows[d] <= sl_price and hit_sl_day is None:
                hit_sl_day = d

        if hit_tp_day is not None and hit_sl_day is None:
            labels[i] = 1.0  # Take profit hit cleanly
        elif hit_sl_day is not None and hit_tp_day is None:
            labels[i] = 0.0  # Stop loss hit cleanly
        elif hit_tp_day is not None and hit_sl_day is not None:
            if hit_tp_day < hit_sl_day:
                labels[i] = 1.0  # Hit TP before SL
            elif hit_sl_day < hit_tp_day:
                labels[i] = 0.0  # Hit SL before TP
            else:
                # Both breached on same day: conservative quant rule assigns Loss
                labels[i] = 0.0
        else:
            # Neither hit within 15 days (Time barrier expired)
            # Conservative rule: Require positive net gain of at least +1.5% to count as Win
            if final_rets[i] >= 1.5:
                labels[i] = 1.0
            else:
                labels[i] = 0.0

    feat["label"] = labels
    feat["max_forward_ret"] = max_forward_rets
    feat["min_forward_ret"] = min_forward_rets
    feat["final_ret"] = final_rets

    # Drop unlabelled rows (warmup period and last 15 days horizon)
    feat.dropna(subset=["label"], inplace=True)
    feat["label"] = feat["label"].astype(int)

    return feat


def main():
    print("=" * 70)
    print("[ALADDIN AI] INSTITUTIONAL DATASET GENERATOR")
    print(f"Horizon: 5 Years (Start: {START_DATE}) | Constituents: {len(NIFTY_SYMBOLS)}")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch Benchmark
    benchmark_df = fetch_benchmark(START_DATE)

    # 2. Iterate through constituents
    all_dfs = []
    success_count = 0
    total_symbols = len(NIFTY_SYMBOLS)

    try:
        for idx, sym in enumerate(NIFTY_SYMBOLS, 1):
            clean_name = sym.replace(".NS", "")
            print(f"[{idx:02d}/{total_symbols:02d}] Fetching & engineering {clean_name}...", end=" ", flush=True)
            try:
                ticker = yf.Ticker(sym)
                stock_df = ticker.history(start=START_DATE, auto_adjust=False)
                if isinstance(stock_df.columns, pd.MultiIndex):
                    stock_df.columns = stock_df.columns.get_level_values(0)
                stock_df = stock_df[["Open", "High", "Low", "Close", "Volume"]].dropna()

                if len(stock_df) < 300:
                    print(f"[SKIP] (only {len(stock_df)} candles)")
                    continue

                processed_df = engineer_features_and_labels(stock_df, benchmark_df, clean_name)
                if not processed_df.empty:
                    all_dfs.append(processed_df)
                    success_count += 1
                    wins = (processed_df["label"] == 1).sum()
                    losses = (processed_df["label"] == 0).sum()
                    print(f"[OK] {len(processed_df)} rows (Wins: {wins}, Losses: {losses})")
                else:
                    print("[SKIP] Empty feature set")
            except Exception as e:
                print(f"[ERROR] {e}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[INFO] Run interrupted, saving collected data so far...")

    if not all_dfs:
        print("[FATAL] No data collected.")
        sys.exit(1)

    print("\nMerging and validating dataset...")
    full_dataset = pd.concat(all_dfs, axis=0)
    full_dataset.sort_index(inplace=True)

    total_rows = len(full_dataset)
    total_wins = int((full_dataset["label"] == 1).sum())
    total_losses = int((full_dataset["label"] == 0).sum())
    win_pct = round((total_wins / total_rows) * 100.0, 2)

    print("-" * 70)
    print("DATASET SUMMARY:")
    print(f"* Total Validated Samples : {total_rows:,}")
    print(f"* Total Features Engineered: {len(full_dataset.columns) - 5}")
    print(f"* Class 1 (Wins / +6% TP)  : {total_wins:,} ({win_pct}%)")
    print(f"* Class 0 (Loss / -3% SL)  : {total_losses:,} ({round(100 - win_pct, 2)}%)")
    print(f"* Date Range               : {full_dataset.index.min().strftime('%Y-%m-%d')} to {full_dataset.index.max().strftime('%Y-%m-%d')}")
    print("-" * 70)

    # Save to Parquet and CSV
    print(f"Saving to {OUTPUT_PARQUET}...")
    full_dataset.to_parquet(OUTPUT_PARQUET, index=True)

    print(f"Saving to {OUTPUT_CSV}...")
    full_dataset.to_csv(OUTPUT_CSV, index=True)

    # Save summary metadata
    feature_cols = [c for c in full_dataset.columns if c not in ["symbol", "close", "label", "max_forward_ret", "min_forward_ret", "final_ret"]]
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_rows": total_rows,
        "total_symbols": success_count,
        "date_range": [full_dataset.index.min().strftime('%Y-%m-%d'), full_dataset.index.max().strftime('%Y-%m-%d')],
        "class_distribution": {
            "wins": total_wins,
            "losses": total_losses,
            "win_rate_pct": win_pct
        },
        "feature_count": len(feature_cols),
        "feature_columns": feature_cols,
        "target_rules": {
            "upper_barrier_pct": 6.0,
            "lower_barrier_pct": -3.0,
            "time_barrier_days": 15
        }
    }
    with open(OUTPUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2)

    print("[DONE] Dataset Generation Complete!")


if __name__ == "__main__":
    main()
