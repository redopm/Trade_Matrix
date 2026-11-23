"""
Aladdin Prediction Ledger & Closed-Loop Verification Engine.

Provides:
1. 15-day Forward Price Trajectory + Directional Probabilities (Bullish / Sideways / Bearish)
   + ±1 SD Probability Cone derived from trend drift, RSI/EMA regime, and ATR/HV volatility.
2. Walk-forward historical checkpoints (T-30..T-5 trading days) evaluated strictly without
   lookahead against actual subsequent 5-day candle closes.
3. Persistent SQLite ledger (`aladdin_predictions` inside daily_ohlcv_store.db) tracking
   PENDING vs VERIFIED predictions (direction_hit, band_hit, mae_pct, accuracy_pct).
4. Closed-loop JSONL feedback export (`data/verified_prediction_feedback.jsonl`) for future ML retraining.
"""
import json
import math
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pytz

from app.config import _BACKEND_DIR
from app.services.daily_history_store import STORE_DB_PATH, DB_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
FEEDBACK_JSONL_PATH = Path(_BACKEND_DIR) / "data" / "verified_prediction_feedback.jsonl"


class PredictionLedger:
    _lock = threading.RLock()
    _initialized = False

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(STORE_DB_PATH), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @classmethod
    def _ensure_schema(cls) -> None:
        if cls._initialized and STORE_DB_PATH.exists():
            return
        with cls._lock:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            conn = cls._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS aladdin_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        pred_date TEXT NOT NULL,
                        horizon_days INTEGER DEFAULT 5,
                        base_price REAL NOT NULL,
                        predicted_direction TEXT NOT NULL,
                        conviction_score REAL NOT NULL,
                        ml_win_prob REAL,
                        predicted_price_5d REAL NOT NULL,
                        predicted_price_15d REAL NOT NULL,
                        upper_band_5d REAL NOT NULL,
                        lower_band_5d REAL NOT NULL,
                        target_1 REAL,
                        stop_loss REAL,
                        actual_price_5d REAL,
                        actual_return_5d_pct REAL,
                        predicted_return_5d_pct REAL,
                        direction_hit INTEGER,
                        band_hit INTEGER,
                        accuracy_pct REAL,
                        mae_pct REAL,
                        status TEXT DEFAULT 'PENDING',
                        evaluated_at TEXT,
                        UNIQUE(symbol, pred_date)
                    );
                    CREATE INDEX IF NOT EXISTS ix_aladdin_pred_sym_date
                        ON aladdin_predictions (symbol, pred_date);
                    CREATE INDEX IF NOT EXISTS ix_aladdin_pred_status
                        ON aladdin_predictions (status);
                    """
                )
                conn.commit()
                cls._initialized = True
            finally:
                conn.close()

    @staticmethod
    def _compute_point_projection(
        closes: pd.Series,
        highs: pd.Series,
        lows: pd.Series,
        diagnosis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute strictly causal directional bias, expected 5D/15D price & ±1SD cone at end of series."""
        spot = float(closes.iloc[-1])
        ema20 = float(closes.ewm(span=min(20, len(closes)), adjust=False).mean().iloc[-1])
        ema50 = float(closes.ewm(span=min(50, len(closes)), adjust=False).mean().iloc[-1])

        delta = closes.diff()
        gain = delta.clip(lower=0.0).ewm(com=13, adjust=False).mean()
        loss = (-delta.clip(upper=0.0)).ewm(com=13, adjust=False).mean()
        rs = float(gain.iloc[-1]) / max(float(loss.iloc[-1]), 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # True 20-day daily return volatility
        log_ret = np.log(closes / closes.shift(1)).dropna()
        daily_vol = float(log_ret.iloc[-20:].std()) if len(log_ret) >= 5 else 0.015
        daily_vol = max(0.006, min(0.05, daily_vol))

        # Causal conviction proxy (uses diagnosis if predicting live day)
        if diagnosis is not None:
            conviction = float(diagnosis.get("composite_score") or 55.0)
            ml_prob = diagnosis.get("ml_win_probability")
            ml_ret_15d = diagnosis.get("ml_expected_return_pct")
        else:
            score = 50.0
            score += 12.0 if spot > ema20 else -12.0
            score += 10.0 if ema20 > ema50 else -10.0
            if 50 <= rsi <= 68:
                score += 8.0
            elif rsi < 38:
                score += 4.0  # oversold bounce potential
            elif rsi > 75:
                score -= 5.0
            conviction = max(15.0, min(92.0, score))
            ml_prob = None
            ml_ret_15d = None

        # Directional probabilities (sum = 100%)
        bull_raw = 33.0 + (conviction - 50.0) * 0.85
        if ml_prob is not None:
            bull_raw = 0.6 * bull_raw + 0.4 * max(20.0, min(80.0, float(ml_prob) * 1.25))
        bull_prob = round(max(12.0, min(78.0, bull_raw)), 1)
        bear_raw = 33.0 + (50.0 - conviction) * 0.78
        bear_prob = round(max(10.0, min(75.0, bear_raw)), 1)
        side_prob = round(max(8.0, 100.0 - bull_prob - bear_prob), 1)
        # Re-normalize strictly to 100.0
        total_p = bull_prob + side_prob + bear_prob
        bull_prob = round((bull_prob / total_p) * 100.0, 1)
        bear_prob = round((bear_prob / total_p) * 100.0, 1)
        side_prob = round(100.0 - bull_prob - bear_prob, 1)

        if bull_prob >= bear_prob + 8.0 and conviction >= 54.0:
            pred_dir = "BULLISH"
        elif bear_prob >= bull_prob + 8.0 or conviction <= 44.0:
            pred_dir = "BEARISH"
        else:
            pred_dir = "SIDEWAYS"

        # Expected 15D drift anchored cautiously to volatility & conviction
        if ml_ret_15d is not None:
            expected_15d_ret_pct = max(-12.0, min(14.0, float(ml_ret_15d) * 0.65 + (conviction - 52.0) * 0.12))
        else:
            expected_15d_ret_pct = max(-10.0, min(12.0, (conviction - 50.0) * 0.16))

        expected_5d_ret_pct = expected_15d_ret_pct * (5.0 / 15.0)
        pred_5d = round(spot * (1.0 + expected_5d_ret_pct / 100.0), 2)
        pred_15d = round(spot * (1.0 + expected_15d_ret_pct / 100.0), 2)

        sd_5d = spot * daily_vol * math.sqrt(5.0)
        upper_5d = round(pred_5d + sd_5d, 2)
        lower_5d = round(max(0.05, pred_5d - sd_5d), 2)

        return {
            "spot": round(spot, 2),
            "ema_20": round(ema20, 2),
            "ema_50": round(ema50, 2),
            "rsi_14": round(rsi, 2),
            "daily_vol": daily_vol,
            "daily_vol_pct": round(daily_vol * 100.0, 2),
            "conviction": round(conviction, 1),
            "ml_win_prob": float(ml_prob) if ml_prob is not None else None,
            "predicted_direction": pred_dir,
            "probabilities": {
                "bullish_pct": bull_prob,
                "sideways_pct": side_prob,
                "bearish_pct": bear_prob,
            },
            "expected_5d_price": pred_5d,
            "expected_15d_price": pred_15d,
            "expected_5d_return_pct": round(expected_5d_ret_pct, 2),
            "expected_15d_return_pct": round(expected_15d_ret_pct, 2),
            "upper_5d": upper_5d,
            "lower_5d": lower_5d,
        }

    @staticmethod
    def _evaluate_record_metrics(
        base_price: float,
        pred_price_5d: float,
        upper_5d: float,
        lower_5d: float,
        pred_dir: str,
        actual_5d: float,
    ) -> Dict[str, Any]:
        actual_ret = ((actual_5d - base_price) / max(base_price, 1e-6)) * 100.0
        pred_ret = ((pred_price_5d - base_price) / max(base_price, 1e-6)) * 100.0
        mae_pct = abs(actual_5d - pred_price_5d) / max(actual_5d, 1e-6) * 100.0

        if pred_dir == "BULLISH":
            dir_hit = 1 if actual_ret > -0.35 else 0
        elif pred_dir == "BEARISH":
            dir_hit = 1 if actual_ret < 0.35 else 0
        else:
            # Sideways hit if stock stayed inside expected ±1SD band or <2.5% move
            dir_hit = 1 if abs(actual_ret) <= 2.5 or (lower_5d <= actual_5d <= upper_5d) else 0

        band_hit = 1 if (lower_5d <= actual_5d <= upper_5d) else 0
        accuracy_pct = round(max(0.0, min(100.0, 100.0 - mae_pct * 8.0)), 1)
        status = "VERIFIED_HIT" if dir_hit == 1 else "VERIFIED_MISS"
        return {
            "actual_price_5d": round(actual_5d, 2),
            "actual_return_5d_pct": round(actual_ret, 2),
            "predicted_return_5d_pct": round(pred_ret, 2),
            "direction_hit": dir_hit,
            "band_hit": band_hit,
            "mae_pct": round(mae_pct, 2),
            "accuracy_pct": accuracy_pct,
            "status": status,
        }

    @classmethod
    def _append_feedback_jsonl(cls, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            FEEDBACK_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing_keys = set()
            if FEEDBACK_JSONL_PATH.exists():
                with open(FEEDBACK_JSONL_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            obj = json.loads(line)
                            existing_keys.add((obj.get("symbol"), obj.get("pred_date")))
                        except Exception:
                            pass
            with open(FEEDBACK_JSONL_PATH, "a", encoding="utf-8") as f:
                for r in rows:
                    key = (r.get("symbol"), r.get("pred_date"))
                    if key not in existing_keys:
                        f.write(json.dumps(r) + "\n")
                        existing_keys.add(key)
        except Exception as e:
            logger.warning(f"Could not write prediction feedback JSONL: {e}")

    @classmethod
    def generate_forecast_and_audit(cls, symbol: str, diagnosis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generates 15-day trajectory forecast + confidence cone AND runs walk-forward
        Predicted vs Actual candle verification on the last 30 trading days.
        """
        cls._ensure_schema()
        clean_sym = symbol.upper().strip().replace(".NS", "").replace(".BO", "").replace("NSE:", "").replace("-EQ", "")

        from app.services.fyers_data_client import FyersDataClient
        fc = FyersDataClient()
        r_from = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        df = fc.get_historical_data(clean_sym, "D", range_from=r_from)
        if df is None or df.empty or len(df) < 25:
            return {"error": f"Insufficient daily candles in local store for {clean_sym} forecast."}

        closes = pd.Series(df["Close"].astype(float).values, index=df.index)
        highs = pd.Series(df["High"].astype(float).values, index=df.index)
        lows = pd.Series(df["Low"].astype(float).values, index=df.index)
        ema20_s = closes.ewm(span=20, adjust=False).mean()
        ema50_s = closes.ewm(span=50, adjust=False).mean()

        # Live day projection
        live_proj = cls._compute_point_projection(closes, highs, lows, diagnosis=diagnosis)
        latest_dt_str = df.index[-1].strftime("%Y-%m-%d")
        now_iso = datetime.now(IST).isoformat()

        # Save today's PENDING prediction if not already logged today
        with cls._lock:
            conn = cls._connect()
            try:
                pred_ret_5d = live_proj["expected_5d_return_pct"]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO aladdin_predictions
                    (symbol, pred_date, horizon_days, base_price, predicted_direction,
                     conviction_score, ml_win_prob, predicted_price_5d, predicted_price_15d,
                     upper_band_5d, lower_band_5d, target_1, stop_loss, predicted_return_5d_pct, status)
                    VALUES (?, ?, 5, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                    """,
                    (
                        clean_sym,
                        latest_dt_str,
                        live_proj["spot"],
                        live_proj["predicted_direction"],
                        live_proj["conviction"],
                        live_proj["ml_win_prob"],
                        live_proj["expected_5d_price"],
                        live_proj["expected_15d_price"],
                        live_proj["upper_5d"],
                        live_proj["lower_5d"],
                        float(diagnosis.get("target_1")) if diagnosis and diagnosis.get("target_1") else None,
                        float(diagnosis.get("stop_loss")) if diagnosis and diagnosis.get("stop_loss") else None,
                        pred_ret_5d,
                    ),
                )

                # Walk-forward historical checkpoints (causal predictions at T-35, T-30, T-25, T-20, T-15, T-10, T-5)
                past_pred_by_target_date: Dict[str, float] = {}
                newly_verified_feedback: List[Dict[str, Any]] = []
                n_bars = len(df)
                for offset in [35, 30, 25, 20, 15, 10, 5]:
                    t_idx = n_bars - 1 - offset
                    if t_idx < 30 or (t_idx + 5) >= n_bars:
                        continue
                    ckpt_date = df.index[t_idx].strftime("%Y-%m-%d")
                    tgt_date = df.index[t_idx + 5].strftime("%Y-%m-%d")
                    c_sub = closes.iloc[: t_idx + 1]
                    h_sub = highs.iloc[: t_idx + 1]
                    l_sub = lows.iloc[: t_idx + 1]
                    proj = cls._compute_point_projection(c_sub, h_sub, l_sub, diagnosis=None)
                    actual_5d = float(closes.iloc[t_idx + 5])
                    ev = cls._evaluate_record_metrics(
                        proj["spot"],
                        proj["expected_5d_price"],
                        proj["upper_5d"],
                        proj["lower_5d"],
                        proj["predicted_direction"],
                        actual_5d,
                    )
                    past_pred_by_target_date[tgt_date] = proj["expected_5d_price"]

                    existing = conn.execute(
                        "SELECT status FROM aladdin_predictions WHERE symbol = ? AND pred_date = ?",
                        (clean_sym, ckpt_date),
                    ).fetchone()
                    if not existing or existing[0] == "PENDING":
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO aladdin_predictions
                            (symbol, pred_date, horizon_days, base_price, predicted_direction,
                             conviction_score, ml_win_prob, predicted_price_5d, predicted_price_15d,
                             upper_band_5d, lower_band_5d, actual_price_5d, actual_return_5d_pct,
                             predicted_return_5d_pct, direction_hit, band_hit, accuracy_pct, mae_pct,
                             status, evaluated_at)
                            VALUES (?, ?, 5, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                clean_sym,
                                ckpt_date,
                                proj["spot"],
                                proj["predicted_direction"],
                                proj["conviction"],
                                None,
                                proj["expected_5d_price"],
                                proj["expected_15d_price"],
                                proj["upper_5d"],
                                proj["lower_5d"],
                                ev["actual_price_5d"],
                                ev["actual_return_5d_pct"],
                                ev["predicted_return_5d_pct"],
                                ev["direction_hit"],
                                ev["band_hit"],
                                ev["accuracy_pct"],
                                ev["mae_pct"],
                                ev["status"],
                                now_iso,
                            ),
                        )
                        newly_verified_feedback.append(
                            {
                                "symbol": clean_sym,
                                "pred_date": ckpt_date,
                                "conviction_score": proj["conviction"],
                                "predicted_direction": proj["predicted_direction"],
                                "predicted_return_5d_pct": ev["predicted_return_5d_pct"],
                                "actual_return_5d_pct": ev["actual_return_5d_pct"],
                                "direction_hit": ev["direction_hit"],
                                "band_hit": ev["band_hit"],
                                "evaluated_at": now_iso,
                            }
                        )

                # Also update any earlier real PENDING predictions for this symbol once 5 bars elapsed
                pending_rows = conn.execute(
                    """
                    SELECT id, pred_date, base_price, predicted_price_5d, upper_band_5d, lower_band_5d, predicted_direction
                    FROM aladdin_predictions
                    WHERE symbol = ? AND status = 'PENDING' AND pred_date < ?
                    """,
                    (clean_sym, latest_dt_str),
                ).fetchall()
                date_to_pos = {idx.strftime("%Y-%m-%d"): pos for pos, idx in enumerate(df.index)}
                for row_id, p_date, base_p, p_5d, u_5d, l_5d, p_dir in pending_rows:
                    pos = date_to_pos.get(p_date)
                    if pos is not None and (pos + 5) < n_bars:
                        act_5d = float(closes.iloc[pos + 5])
                        ev = cls._evaluate_record_metrics(base_p, p_5d, u_5d, l_5d, p_dir, act_5d)
                        conn.execute(
                            """
                            UPDATE aladdin_predictions
                            SET actual_price_5d = ?, actual_return_5d_pct = ?, predicted_return_5d_pct = ?,
                                direction_hit = ?, band_hit = ?, accuracy_pct = ?, mae_pct = ?,
                                status = ?, evaluated_at = ?
                            WHERE id = ?
                            """,
                            (
                                ev["actual_price_5d"],
                                ev["actual_return_5d_pct"],
                                ev["predicted_return_5d_pct"],
                                ev["direction_hit"],
                                ev["band_hit"],
                                ev["accuracy_pct"],
                                ev["mae_pct"],
                                ev["status"],
                                now_iso,
                                row_id,
                            ),
                        )

                conn.commit()
                cls._append_feedback_jsonl(newly_verified_feedback)

                audit_rows = conn.execute(
                    """
                    SELECT pred_date, base_price, predicted_direction, conviction_score,
                           predicted_price_5d, actual_price_5d, predicted_return_5d_pct,
                           actual_return_5d_pct, direction_hit, band_hit, accuracy_pct, mae_pct, status
                    FROM aladdin_predictions
                    WHERE symbol = ?
                    ORDER BY pred_date DESC
                    LIMIT 12
                    """,
                    (clean_sym,),
                ).fetchall()
            finally:
                conn.close()

        # Build unified Chart Series (Last 60 actual days + Next 15 forecast days)
        chart_series: List[Dict[str, Any]] = []
        hist_slice = df.iloc[-60:]
        ema20_slice = ema20_s.iloc[-60:]
        ema50_slice = ema50_s.iloc[-60:]

        for i in range(len(hist_slice)):
            d_str = hist_slice.index[i].strftime("%Y-%m-%d")
            act_c = round(float(hist_slice["Close"].iloc[i]), 2)
            chart_series.append(
                {
                    "date": d_str,
                    "actual_close": act_c,
                    "ema_20": round(float(ema20_slice.iloc[i]), 2),
                    "ema_50": round(float(ema50_slice.iloc[i]), 2),
                    "past_predicted_close": past_pred_by_target_date.get(d_str),
                    "expected_close": act_c if i == len(hist_slice) - 1 else None,
                    "upper_1sd": act_c if i == len(hist_slice) - 1 else None,
                    "lower_1sd": act_c if i == len(hist_slice) - 1 else None,
                    "is_forecast": False,
                }
            )

        future_dates = pd.bdate_range(start=df.index[-1] + pd.Timedelta(days=1), periods=15)
        spot_now = live_proj["spot"]
        vol = live_proj["daily_vol"]
        ret_15d = live_proj["expected_15d_return_pct"] / 100.0
        for step_idx, fd in enumerate(future_dates, start=1):
            frac = step_idx / 15.0
            exp_c = round(spot_now * (1.0 + ret_15d * frac), 2)
            sd_step = spot_now * vol * math.sqrt(step_idx)
            chart_series.append(
                {
                    "date": fd.strftime("%Y-%m-%d"),
                    "actual_close": None,
                    "ema_20": None,
                    "ema_50": None,
                    "past_predicted_close": None,
                    "expected_close": exp_c,
                    "upper_1sd": round(exp_c + sd_step, 2),
                    "lower_1sd": round(max(0.05, exp_c - sd_step), 2),
                    "is_forecast": True,
                }
            )

        audit_history = [
            {
                "pred_date": r[0],
                "base_price": r[1],
                "predicted_direction": r[2],
                "conviction_score": r[3],
                "predicted_price_5d": r[4],
                "actual_price_5d": r[5],
                "predicted_return_5d_pct": r[6],
                "actual_return_5d_pct": r[7],
                "direction_hit": r[8],
                "band_hit": r[9],
                "accuracy_pct": r[10],
                "mae_pct": r[11],
                "status": r[12],
            }
            for r in audit_rows
        ]
        verified = [a for a in audit_history if a["status"] != "PENDING"]
        ver_cnt = len(verified)
        dir_rate = round(sum(1 for a in verified if a["direction_hit"] == 1) / ver_cnt * 100.0, 1) if ver_cnt else 0.0
        band_rate = round(sum(1 for a in verified if a["band_hit"] == 1) / ver_cnt * 100.0, 1) if ver_cnt else 0.0
        avg_acc = round(sum(float(a["accuracy_pct"] or 0) for a in verified) / ver_cnt, 1) if ver_cnt else 0.0
        avg_mae = round(sum(float(a["mae_pct"] or 0) for a in verified) / ver_cnt, 2) if ver_cnt else 0.0

        return {
            "symbol": clean_sym,
            "as_of_date": latest_dt_str,
            "current_price": live_proj["spot"],
            "predicted_direction": live_proj["predicted_direction"],
            "conviction_score": live_proj["conviction"],
            "directional_probabilities": live_proj["probabilities"],
            "expected_5d_price": live_proj["expected_5d_price"],
            "expected_15d_price": live_proj["expected_15d_price"],
            "expected_5d_return_pct": live_proj["expected_5d_return_pct"],
            "expected_15d_return_pct": live_proj["expected_15d_return_pct"],
            "upper_5d": live_proj["upper_5d"],
            "lower_5d": live_proj["lower_5d"],
            "daily_vol_pct": live_proj["daily_vol_pct"],
            "rsi_14": live_proj["rsi_14"],
            "chart_series": chart_series,
            "audit_history": audit_history,
            "symbol_accuracy_summary": {
                "verified_count": ver_cnt,
                "direction_hit_rate_pct": dir_rate,
                "cone_hit_rate_pct": band_rate,
                "avg_accuracy_pct": avg_acc,
                "avg_mae_pct": avg_mae,
            },
        }

    @classmethod
    def evaluate_all_pending_predictions(cls) -> Dict[str, Any]:
        """Evaluate every PENDING prediction across all stocks against newer actual daily candles."""
        cls._ensure_schema()
        from app.services.daily_history_store import DailyHistoryStore

        now_iso = datetime.now(IST).isoformat()
        with cls._lock:
            conn = cls._connect()
            try:
                pending = conn.execute(
                    """
                    SELECT id, symbol, pred_date, base_price, predicted_price_5d,
                           upper_band_5d, lower_band_5d, predicted_direction, conviction_score
                    FROM aladdin_predictions
                    WHERE status = 'PENDING'
                    """
                ).fetchall()
            finally:
                conn.close()

        evaluated_count = 0
        hits = 0
        feedback_batch: List[Dict[str, Any]] = []

        for row_id, sym, p_date, base_p, p_5d, u_5d, l_5d, p_dir, conv in pending:
            fsym = f"NSE:{sym}-EQ"
            start_dt = datetime.strptime(p_date, "%Y-%m-%d").date()
            df = DailyHistoryStore._read_df(fsym, start_dt, date.today())
            if df.empty or len(df) < 6:
                continue
            actual_5d = float(df["Close"].iloc[5])
            ev = cls._evaluate_record_metrics(base_p, p_5d, u_5d, l_5d, p_dir, actual_5d)
            evaluated_count += 1
            if ev["direction_hit"] == 1:
                hits += 1

            with cls._lock:
                conn = cls._connect()
                try:
                    conn.execute(
                        """
                        UPDATE aladdin_predictions
                        SET actual_price_5d = ?, actual_return_5d_pct = ?, predicted_return_5d_pct = ?,
                            direction_hit = ?, band_hit = ?, accuracy_pct = ?, mae_pct = ?,
                            status = ?, evaluated_at = ?
                        WHERE id = ?
                        """,
                        (
                            ev["actual_price_5d"],
                            ev["actual_return_5d_pct"],
                            ev["predicted_return_5d_pct"],
                            ev["direction_hit"],
                            ev["band_hit"],
                            ev["accuracy_pct"],
                            ev["mae_pct"],
                            ev["status"],
                            now_iso,
                            row_id,
                        ),
                    )
                    conn.commit()
                finally:
                    conn.close()

            feedback_batch.append(
                {
                    "symbol": sym,
                    "pred_date": p_date,
                    "conviction_score": conv,
                    "predicted_direction": p_dir,
                    "predicted_return_5d_pct": ev["predicted_return_5d_pct"],
                    "actual_return_5d_pct": ev["actual_return_5d_pct"],
                    "direction_hit": ev["direction_hit"],
                    "band_hit": ev["band_hit"],
                    "evaluated_at": now_iso,
                }
            )

        cls._append_feedback_jsonl(feedback_batch)
        return {
            "evaluated_now": evaluated_count,
            "direction_hits": hits,
            **cls.get_global_prediction_stats(),
        }

    @classmethod
    def get_global_prediction_stats(cls) -> Dict[str, Any]:
        cls._ensure_schema()
        with cls._lock:
            conn = cls._connect()
            try:
                total = conn.execute("SELECT COUNT(*) FROM aladdin_predictions").fetchone()[0]
                ver = conn.execute(
                    "SELECT COUNT(*), SUM(direction_hit), SUM(band_hit), AVG(accuracy_pct), AVG(mae_pct) FROM aladdin_predictions WHERE status != 'PENDING'"
                ).fetchone()
                pending_cnt = conn.execute(
                    "SELECT COUNT(*) FROM aladdin_predictions WHERE status = 'PENDING'"
                ).fetchone()[0]
                recent = conn.execute(
                    """
                    SELECT symbol, pred_date, base_price, predicted_direction, predicted_price_5d,
                           actual_price_5d, accuracy_pct, direction_hit, status
                    FROM aladdin_predictions
                    WHERE status != 'PENDING'
                    ORDER BY pred_date DESC, id DESC
                    LIMIT 15
                    """
                ).fetchall()
            finally:
                conn.close()

        ver_cnt = int(ver[0] or 0) if ver else 0
        dir_hits = int(ver[1] or 0) if ver else 0
        band_hits = int(ver[2] or 0) if ver else 0
        avg_acc = round(float(ver[3] or 0.0), 1) if ver else 0.0
        avg_mae = round(float(ver[4] or 0.0), 2) if ver else 0.0

        feedback_samples = 0
        if FEEDBACK_JSONL_PATH.exists():
            try:
                with open(FEEDBACK_JSONL_PATH, "r", encoding="utf-8") as f:
                    feedback_samples = sum(1 for _ in f)
            except Exception:
                pass

        return {
            "total_predictions": int(total or 0),
            "verified_count": ver_cnt,
            "pending_count": int(pending_cnt or 0),
            "direction_hit_rate_pct": round((dir_hits / ver_cnt) * 100.0, 1) if ver_cnt else 0.0,
            "cone_hit_rate_pct": round((band_hits / ver_cnt) * 100.0, 1) if ver_cnt else 0.0,
            "avg_accuracy_pct": avg_acc,
            "avg_mae_pct": avg_mae,
            "feedback_samples_logged": feedback_samples,
            "recent_verified": [
                {
                    "symbol": r[0],
                    "pred_date": r[1],
                    "base_price": r[2],
                    "predicted_direction": r[3],
                    "predicted_price_5d": r[4],
                    "actual_price_5d": r[5],
                    "accuracy_pct": r[6],
                    "direction_hit": r[7],
                    "status": r[8],
                }
                for r in recent
            ],
        }
