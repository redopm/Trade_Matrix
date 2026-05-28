"""
TradeMatrix Phase 2 — Full Training Script
Run directly: python run_training.py

This script:
1. Downloads OHLCV data for Top 50 Nifty stocks (Day 1 quota-safe)
2. Generates 60-day sliding window chart images (mplfinance dark theme)
3. Labels each chart with Gemini 2.5 Flash Vision
4. Extracts 23 geometric features per window
5. Trains XGBoost classifier (5-fold CV)
6. Saves model to models/pattern_classifier.pkl
7. Prints full accuracy report

Free tier: ~14 req/min, ~1400 req/day
Estimated: Top 50 stocks = ~300-500 windows = ~35-45 min
"""

import asyncio
import sys
import json
import time
import os
import random
import io
from pathlib import Path
from datetime import datetime, date

# ── Setup paths ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Load .env manually before importing settings
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")

print("=" * 65)
print("  TradeMatrix Phase 2 — Pattern Recognition Training")
print(f"  Model: gemini-2.5-flash | Started: {datetime.now().strftime('%H:%M:%S')}")
print("=" * 65)

# ── Imports ───────────────────────────────────────────────────────────────────
from app.config import get_settings
settings = get_settings()

print(f"  Gemini API Key: {'✓ SET (' + settings.GEMINI_API_KEY[:8] + '...)' if settings.GEMINI_API_KEY else '✗ NOT SET'}")
print(f"  Model: {settings.GEMINI_MODEL}")
print(f"  Charts dir: {settings.CHARTS_DIR}")
print(f"  Labels file: {settings.LABELS_FILE}")
print(f"  Model path: {settings.MODEL_PATH}")
print()

# ── Training Universe: Top 50 Nifty for Day 1 ────────────────────────────────
# Chosen for liquidity, data quality, pattern frequency
TOP_50_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "BAJFINANCE.NS", "TITAN.NS", "WIPRO.NS", "NTPC.NS", "POWERGRID.NS",
    "ULTRACEMCO.NS", "NESTLEIND.NS", "TECHM.NS", "HCLTECH.NS", "BAJAJFINSV.NS",
    "COALINDIA.NS", "GRASIM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "HINDALCO.NS",
    "DIVISLAB.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS", "BAJAJ-AUTO.NS",
    "HEROMOTOCO.NS", "BRITANNIA.NS", "TATACONSUM.NS", "BPCL.NS", "IOC.NS",
    "INDUSINDBK.NS", "PIDILITIND.NS", "SIEMENS.NS", "DLF.NS", "GODREJCP.NS",
    "DABUR.NS", "COLPAL.NS", "MARICO.NS", "HAVELLS.NS", "POLYCAB.NS",
]

# ── Initialize services ───────────────────────────────────────────────────────
from app.services.chart_generator import ChartGenerator
from app.services.feature_extractor import FeatureExtractor
from app.services.model_trainer import PatternModelTrainer

chart_gen = ChartGenerator()
extractor = FeatureExtractor()
trainer = PatternModelTrainer()

# ── Gemini Vision Labeler (inline, optimized) ─────────────────────────────────
from google import genai
from google.genai import types
from PIL import Image

if settings.GCP_PROJECT_ID:
    gemini_client = genai.Client(
        vertexai=True,
        project=settings.GCP_PROJECT_ID,
        location="us-central1"
    )
else:
    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

PATTERN_PROMPT = """You are an expert NSE technical analyst. Analyze this 60-day candlestick chart.

EMA lines: Yellow=EMA200, Blue=EMA50. Volume shown at bottom.

Identify the SINGLE best classical chart pattern visible:

BULLISH: double_bottom, hs_bottom, bull_flag, cup_handle, ascending_triangle
BEARISH: double_top, bear_flag, descending_triangle
NONE: no_pattern

Rules:
- Only label if ≥65% confident
- Volume confirmation increases confidence
- Be strict: poor setups = no_pattern

Respond ONLY in JSON:
{
  "pattern_name": "<one of the 9 options>",
  "confidence": <0-100 integer>,
  "is_bullish": <true/false/null>,
  "reasoning": "<1-2 sentences>"
}"""

# Quota tracking
QUOTA_FILE = Path(settings.LABELS_FILE).parent / "gemini_quota.json"
REQUEST_INTERVAL = 60.0 / 300  # Paid tier: 300 req/min
_last_request_time = 0.0
_quota_exhausted = False

def get_quota_today():
    today = str(date.today())
    try:
        if QUOTA_FILE.exists():
            d = json.loads(QUOTA_FILE.read_text())
            if d.get("date") == today:
                return d.get("count", 0)
    except:
        pass
    return 0

def increment_quota():
    today = str(date.today())
    count = get_quota_today() + 1
    try:
        QUOTA_FILE.write_text(json.dumps({"date": today, "count": count}))
    except:
        pass
    return count

async def rate_limit():
    global _last_request_time
    now = time.monotonic()
    wait = REQUEST_INTERVAL - (now - _last_request_time)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_request_time = time.monotonic()

async def label_with_gemini(symbol, img_bytes, window_start, window_end, retries=4):
    global _quota_exhausted
    if _quota_exhausted:
        return None

    used = get_quota_today()
    if used >= 1500000:
        print(f"\n  ⚠ Daily quota reached ({used}/1500000). Stopping Gemini labeling.")
        _quota_exhausted = True
        return None

    await rate_limit()

    for attempt in range(retries):
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[PATTERN_PROMPT, img],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=256,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
            )

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            data = json.loads(raw)
            count = increment_quota()

            return {
                "pattern_name": data.get("pattern_name", "no_pattern"),
                "confidence": float(data.get("confidence", 0)) / 100.0,
                "is_bullish": data.get("is_bullish"),
                "reasoning": data.get("reasoning", ""),
                "label_source": "gemini",
            }

        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                if "day" in err.lower():
                    print(f"\n  ✗ Daily quota exhausted!")
                    _quota_exhausted = True
                    return None
                backoff = 65 * (2 ** attempt) + random.uniform(0, 5)
                print(f"\n  ⚠ Rate limit hit. Waiting {backoff:.0f}s (attempt {attempt+1}/{retries})...")
                await asyncio.sleep(backoff)
            else:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                else:
                    print(f"\n  ✗ Gemini error for {symbol}: {err[:80]}")
                    return None

    return None

def label_with_rules(features):
    """Fallback rule-based labeler when Gemini unavailable."""
    if not features:
        return {"pattern_name": "no_pattern", "confidence": 0.5, "is_bullish": None, "label_source": "rule_based"}

    n_peaks = features.get("n_peaks", 0)
    n_troughs = features.get("n_troughs", 0)
    trough_sym = features.get("trough_symmetry_score", 0)
    peak_sym = features.get("peak_symmetry_score", 0)
    upper_slope = features.get("upper_trendline_slope", 0)
    lower_slope = features.get("lower_trendline_slope", 0)
    recovery = features.get("recovery_from_low_pct", 0)
    obv_slope = features.get("obv_slope", 0)
    vol_breakout = features.get("volume_at_breakout_ratio", 1.0)
    vol_trend = features.get("volume_trend_slope", 0)

    if n_troughs >= 2 and trough_sym > 0.85 and recovery > 0.5 and obv_slope > 0:
        return {"pattern_name": "double_bottom", "confidence": min(0.5 + trough_sym * 0.3 + recovery * 0.2, 0.90), "is_bullish": True, "label_source": "rule_based"}
    if n_peaks >= 2 and peak_sym > 0.85 and recovery < 0.3 and obv_slope < 0:
        return {"pattern_name": "double_top", "confidence": min(0.5 + peak_sym * 0.3, 0.88), "is_bullish": False, "label_source": "rule_based"}
    if n_troughs >= 3 and trough_sym > 0.75 and obv_slope > 0:
        return {"pattern_name": "hs_bottom", "confidence": min(0.5 + trough_sym * 0.25, 0.85), "is_bullish": True, "label_source": "rule_based"}
    if abs(upper_slope) < 0.005 and lower_slope > 0.003 and vol_breakout > 1.2:
        return {"pattern_name": "ascending_triangle", "confidence": 0.75, "is_bullish": True, "label_source": "rule_based"}
    if abs(lower_slope) < 0.005 and upper_slope < -0.003 and vol_breakout > 1.2:
        return {"pattern_name": "descending_triangle", "confidence": 0.73, "is_bullish": False, "label_source": "rule_based"}
    if lower_slope > 0.01 and upper_slope < 0 and upper_slope > -0.01 and vol_trend < 0:
        return {"pattern_name": "bull_flag", "confidence": 0.70, "is_bullish": True, "label_source": "rule_based"}
    if upper_slope < -0.01 and lower_slope > 0 and lower_slope < 0.01 and vol_trend < 0:
        return {"pattern_name": "bear_flag", "confidence": 0.68, "is_bullish": False, "label_source": "rule_based"}
    if recovery > 0.7 and n_troughs >= 1 and obv_slope > 0:
        return {"pattern_name": "cup_handle", "confidence": min(0.55 + recovery * 0.2, 0.78), "is_bullish": True, "label_source": "rule_based"}

    return {"pattern_name": "no_pattern", "confidence": 0.85, "is_bullish": None, "label_source": "rule_based"}


# ── Data download ─────────────────────────────────────────────────────────────
def download_stock_data(symbol):
    import yfinance as yf
    try:
        df = yf.download(symbol, period="3y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 100:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        for std in ["Open", "High", "Low", "Close", "Volume"]:
            for c in df.columns:
                if c.lower() == std.lower() and c != std:
                    df.rename(columns={c: std}, inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception as e:
        return None


def generate_windows(df, window=60, step=15):
    """Generate sliding windows. step=15 balances coverage vs speed."""
    windows = []
    if len(df) < window:
        return windows
    dates = df.index
    i = window
    while i <= len(df):
        w_df = df.iloc[i - window:i]
        windows.append((
            str(dates[i - window].date()),
            str(dates[i - 1].date()),
            w_df
        ))
        i += step
    return windows


# ── Load existing labels (resume support) ─────────────────────────────────────
labels_file = Path(settings.LABELS_FILE)
labels_file.parent.mkdir(parents=True, exist_ok=True)
Path(settings.CHARTS_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.MODEL_DIR).mkdir(parents=True, exist_ok=True)

existing_labels = set()
all_labels = []
if labels_file.exists():
    with open(labels_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    l = json.loads(line)
                    key = f"{l.get('symbol')}_{l.get('window_end')}"
                    existing_labels.add(key)
                    all_labels.append(l)
                except:
                    pass

print(f"  Resuming from {len(all_labels)} existing labels")
print(f"  Gemini quota used today: {get_quota_today()}/1400")
print()


# ── Main async training pipeline ──────────────────────────────────────────────
async def run_pipeline():
    global all_labels

    total_stocks = len(TOP_50_SYMBOLS)
    labeled_new = 0
    skipped = 0
    failed_download = 0

    print(f"{'─'*65}")
    print(f"  STAGE 1: Downloading data for {total_stocks} stocks")
    print(f"{'─'*65}")

    stock_data = {}
    for i, sym in enumerate(TOP_50_SYMBOLS):
        print(f"  [{i+1:2d}/{total_stocks}] {sym:<20}", end="", flush=True)
        df = download_stock_data(sym)
        if df is not None and len(df) >= 80:
            stock_data[sym] = df
            print(f"  ✓ {len(df)} days")
        else:
            failed_download += 1
            print(f"  ✗ No data")
        await asyncio.sleep(0.3)  # Polite yfinance rate limit

    print(f"\n  Downloaded: {len(stock_data)}/{total_stocks} stocks")

    # Count total windows
    total_windows = sum(len(generate_windows(df)) for df in stock_data.values())
    new_windows = total_windows - len(existing_labels)
    print(f"  Total windows: {total_windows} | New to label: {new_windows}")
    print(f"  Estimated time at 14 req/min: ~{new_windows // 14 + 1} min")
    print()

    print(f"{'─'*65}")
    print(f"  STAGE 2: Gemini Vision Labeling (gemini-2.5-flash)")
    print(f"{'─'*65}")

    for stock_idx, (sym, df) in enumerate(stock_data.items()):
        windows = generate_windows(df)
        sym_clean = sym.replace(".NS", "")
        new_count = sum(1 for _, w_end, _ in windows if f"{sym}_{w_end}" not in existing_labels)

        print(f"\n  [{stock_idx+1:2d}/{len(stock_data)}] {sym_clean:<12} ({len(windows)} windows, {new_count} new)", flush=True)

        for w_start, w_end, df_w in windows:
            key = f"{sym}_{w_end}"
            if key in existing_labels:
                skipped += 1
                print(".", end="", flush=True)
                continue

            # Generate chart image
            _, img_bytes = chart_gen.generate_chart(sym, df, window_start=w_start, window_end=w_end, save=False)
            if not img_bytes:
                print("x", end="", flush=True)
                continue

            # Extract features
            features = extractor.extract(df_w)

            # Label with Gemini (or fallback)
            if _quota_exhausted or not img_bytes:
                label_result = label_with_rules(features)
            else:
                label_result = await label_with_gemini(sym, img_bytes, w_start, w_end)
                if label_result is None:
                    label_result = label_with_rules(features)

            if not label_result:
                continue

            # Build full label record
            full_label = {
                "symbol": sym,
                "window_start": w_start,
                "window_end": w_end,
                "created_at": datetime.now().isoformat(),
                "features": features,
                **label_result,
            }

            # Save label
            with open(labels_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(full_label, default=str) + "\n")

            all_labels.append(full_label)
            existing_labels.add(key)
            labeled_new += 1

            # Progress indicator
            src_icon = "G" if label_result.get("label_source") == "gemini" else "R"
            pname = label_result.get("pattern_name", "?")
            conf = label_result.get("confidence", 0)

            if pname != "no_pattern":
                print(f"\n    [{src_icon}] {w_end}: {pname} ({conf:.0%})", end="", flush=True)
            else:
                print("·", end="", flush=True)

    print(f"\n\n  Labeling complete!")
    print(f"  New labels: {labeled_new} | Skipped (existing): {skipped}")
    print(f"  Total labels: {len(all_labels)}")
    print(f"  Gemini quota used today: {get_quota_today()}/1400")

    # ── Pattern distribution ──────────────────────────────────────────────────
    from collections import Counter
    patterns = Counter(l.get("pattern_name") for l in all_labels)
    sources = Counter(l.get("label_source") for l in all_labels)

    print(f"\n  Pattern distribution:")
    for p, c in sorted(patterns.items(), key=lambda x: -x[1]):
        bar = "█" * min(c // 3, 25)
        print(f"    {p:<25} {c:>4}  {bar}")

    print(f"\n  Label sources: {dict(sources)}")

    # ── Stage 3: Train XGBoost ────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  STAGE 3: Training XGBoost Classifier")
    print(f"{'─'*65}")

    if len(all_labels) < 30:
        print(f"  ✗ Too few labels ({len(all_labels)}). Need 30+. Exiting.")
        return

    print(f"  Training on {len(all_labels)} total labels...")
    result = trainer.train(labels_override=all_labels, min_samples_per_class=3)

    if not result.get("success"):
        print(f"  ✗ Training failed: {result.get('error')}")
        return

    # ── Results ───────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  ✅  TRAINING COMPLETE!")
    print(f"{'='*65}")
    print(f"  CV Accuracy:     {result.get('cv_accuracy', 0):.2%}")
    print(f"  Train Accuracy:  {result.get('train_accuracy', 0):.2%}")
    print(f"  CV Std Dev:      ±{result.get('cv_std', 0):.2%}")
    print(f"  Classes:         {result.get('n_classes')} patterns")
    print(f"  Training Samples:{result.get('n_samples')}")
    print(f"  Model saved:     {settings.MODEL_PATH}")
    print()

    print(f"  Classes: {result.get('classes')}")
    print()

    print(f"  Top 5 Predictive Features:")
    for feat, imp in (result.get("top_features") or [])[:5]:
        bar = "█" * int(imp * 200)
        print(f"    {feat:<30} {imp:.4f}  {bar}")

    print()
    print(f"  Classification Report:")
    report = result.get("classification_report", {})
    print(f"  {'Pattern':<25} {'Precision':>9} {'Recall':>7} {'F1':>7} {'Support':>8}")
    print(f"  {'─'*25} {'─'*9} {'─'*7} {'─'*7} {'─'*8}")
    for cls, metrics in report.items():
        if isinstance(metrics, dict) and cls not in ["accuracy", "macro avg", "weighted avg"]:
            print(f"  {cls:<25} {metrics.get('precision',0):>9.2f} {metrics.get('recall',0):>7.2f} {metrics.get('f1-score',0):>7.2f} {int(metrics.get('support',0)):>8}")

    print()
    print(f"  Model ready! Use it via:")
    print(f"    GET http://localhost:8000/api/v1/patterns/detect/RELIANCE")
    print(f"    GET http://localhost:3000/patterns  (Frontend)")
    print(f"{'='*65}\n")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_pipeline())
