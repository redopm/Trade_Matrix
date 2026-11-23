"""
Aladdin V3 Cross-Sectional Ranker Trainer & Walk-Forward Positional Backtester
==============================================================================
Trains the cross-sectional 50/50 Institutional Factor + Regularized XGBoost
ranker across all equity history in SQLite DailyHistoryStore (daily_ohlcv_store.db):
  1. Strict causal per-stock features matching TechnicalAnalyzer / AladdinBrainEngine:
       mom_ex_1m, dist_l52, r10, r20, atr_pct, dist_ema_200,
       ema200_slope, rsi_14, dist_h52
  2. Cohort-date cross-sectional percentile transformation (0.0 to 1.0) so no
     daily market constant dominates tree splits.
  3. Purged Blind Out-of-Sample Evaluation (Train < 2023-10-01 | Test >= 2024-01-01)
     recording ROC-AUC, Mean Spearman Rank IC, Top-10 Alpha & Beat Rate into
     backend/models/aladdin_xs_metrics.json.
  4. Full historical fit saved to:
       - backend/models/aladdin_xs_classifier.pkl
       - backend/models/aladdin_xs_features.json
  5. Zero-Lookahead Expanding-Window Portfolio & Wide Chandelier EOD-SL Backtest
     (2021-Present) over NIFTY100_ELIGIBLE_UNIVERSE saved to:
       - backend/models/aladdin_backtest_report.json
"""

from __future__ import annotations

import argparse
import gc
import json
import sqlite3
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score

warnings.filterwarnings("ignore")

# Windows UTF-8 stdout safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODELS_DIR = BACKEND_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DB_CANDIDATES = [
    BACKEND_DIR / "database" / "daily_ohlcv_store.db",
    Path("/app/database/daily_ohlcv_store.db"),
]

XS_CLASSIFIER_PATH = MODELS_DIR / "aladdin_xs_classifier.pkl"
XS_FEATURES_PATH = MODELS_DIR / "aladdin_xs_features.json"
XS_METRICS_PATH = MODELS_DIR / "aladdin_xs_metrics.json"
BACKTEST_REPORT_PATH = MODELS_DIR / "aladdin_backtest_report.json"

XS_FEATURES: List[str] = [
    "pct_mom_ex_1m",
    "pct_dist_l52",
    "pct_r10",
    "pct_r20",
    "pct_atr_pct",
    "pct_dist_ema_200",
    "pct_ema200_slope",
    "pct_rsi_14",
    "pct_dist_h52",
]

RAW_TO_PCT = [
    ("mom_ex_1m", "pct_mom_ex_1m"),
    ("dist_l52", "pct_dist_l52"),
    ("r10", "pct_r10"),
    ("r20", "pct_r20"),
    ("atr_pct", "pct_atr_pct"),
    ("dist_ema_200", "pct_dist_ema_200"),
    ("ema200_slope", "pct_ema200_slope"),
    ("rsi_14", "pct_rsi_14"),
    ("dist_h52", "pct_dist_h52"),
]

FRICTION_PCT = 0.00385  # 0.385% statutory round-trip delivery friction


def resolve_db_path() -> Path:
    for cand in DB_CANDIDATES:
        if cand.exists():
            return cand
    raise FileNotFoundError(f"daily_ohlcv_store.db not found in {DB_CANDIDATES}")


def build_xgb_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.025,
        max_depth=3,
        min_child_weight=45,
        subsample=0.80,
        colsample_bytree=0.75,
        reg_alpha=2.5,
        reg_lambda=5.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=2,
    )


def compute_causal_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].astype("float64")
    h = df["high"].astype("float64")
    l = df["low"].astype("float64")

    ema_200 = c.ewm(span=200, adjust=False).mean()
    ret_20d = c.pct_change(20) * 100.0
    ret_250d = c.pct_change(250) * 100.0
    mom_ex_1m = ret_250d - ret_20d

    dist_h52 = (c / (c.rolling(252).max() + 1e-9) - 1.0) * 100.0
    dist_l52 = (c / (c.rolling(252).min() + 1e-9) - 1.0) * 100.0
    r10 = c.pct_change(10) * 100.0

    tr = pd.concat(
        [h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()
    atr_pct = (atr / (c + 1e-9)) * 100.0

    dist_ema_200 = (c / (ema_200 + 1e-9) - 1.0) * 100.0
    ema200_slope = (ema_200 / (ema_200.shift(20) + 1e-9) - 1.0) * 100.0

    delta = c.diff()
    avg_gain = delta.clip(lower=0.0).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()
    rsi_14 = 100.0 - (100.0 / (1.0 + (avg_gain / (avg_loss + 1e-9))))

    fwd_63d = (c.shift(-63) / (c + 1e-9) - 1.0) * 100.0

    return pd.DataFrame(
        {
            "dt": df["dt"].values,
            "open": df["open"].astype("float32").values,
            "high": h.astype("float32").values,
            "low": l.astype("float32").values,
            "close": c.astype("float32").values,
            "atr": atr.astype("float32").values,
            "mom_ex_1m": mom_ex_1m.astype("float32").values,
            "dist_l52": dist_l52.astype("float32").values,
            "r10": r10.astype("float32").values,
            "r20": ret_20d.astype("float32").values,
            "atr_pct": atr_pct.astype("float32").values,
            "dist_ema_200": dist_ema_200.astype("float32").values,
            "ema200_slope": ema200_slope.astype("float32").values,
            "rsi_14": rsi_14.astype("float32").values,
            "dist_h52": dist_h52.astype("float32").values,
            "fwd_63d": fwd_63d.astype("float32").values,
        }
    )


def spearman_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5:
        return 0.0
    ra = pd.Series(a).rank().to_numpy(dtype=np.float64)
    rb = pd.Series(b).rank().to_numpy(dtype=np.float64)
    sa = np.std(ra)
    sb = np.std(rb)
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def load_nifty_regime_map(conn: sqlite3.Connection) -> Dict[str, Tuple[float, float]]:
    rows = conn.execute(
        """
        SELECT dt, close
        FROM daily_candles
        WHERE fyers_sym = 'NSE:NIFTY50-INDEX' AND dt >= '2019-01-01'
        ORDER BY epoch ASC
        """
    ).fetchall()
    if not rows:
        return {}
    ndf = pd.DataFrame(rows, columns=["dt", "close"])
    ndf["close"] = ndf["close"].astype("float64")
    ndf["ema200"] = ndf["close"].ewm(span=200, adjust=False).mean()
    return {r.dt: (float(r.close), float(r.ema200)) for r in ndf.itertuples(index=False)}


def load_cross_sectional_panel_and_bt_cache(
    db_path: Path,
    nifty100_syms: set[str],
    min_dt: str = "2006-01-01",
    sample_from_dt: str = "2008-01-01",
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], Dict[str, Tuple[float, float]]]:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        nifty_regime = load_nifty_regime_map(conn)
        eq_rows = conn.execute(
            """
            SELECT fyers_sym, COUNT(*) AS cnt
            FROM daily_candles
            WHERE fyers_sym LIKE 'NSE:%-EQ' AND dt >= ?
            GROUP BY fyers_sym
            HAVING cnt >= 350
            ORDER BY fyers_sym
            """,
            (min_dt,),
        ).fetchall()
        symbols = [r[0] for r in eq_rows]

        idx_dates = conn.execute(
            "SELECT dt FROM daily_candles WHERE fyers_sym = 'NSE:NIFTY50-INDEX' AND dt >= ? ORDER BY dt ASC",
            (sample_from_dt,),
        ).fetchall()
        if idx_dates and len(idx_dates) > 500:
            cal_dates = [r[0] for r in idx_dates]
        else:
            cal_dates = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT dt FROM daily_candles WHERE fyers_sym LIKE 'NSE:%-EQ' AND dt >= ? ORDER BY dt ASC",
                    (sample_from_dt,),
                ).fetchall()
            ]
        sample_dates = set(cal_dates[::15])

        panel_chunks: List[pd.DataFrame] = []
        bt_cache: Dict[str, pd.DataFrame] = {}

        for i, fyers_sym in enumerate(symbols, 1):
            rows = conn.execute(
                """
                SELECT dt, open, high, low, close
                FROM daily_candles
                WHERE fyers_sym = ? AND dt >= ?
                ORDER BY epoch ASC
                """,
                (fyers_sym, min_dt),
            ).fetchall()
            if len(rows) < 350:
                continue

            df_raw = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close"])
            feat_df = compute_causal_indicators(df_raw)
            clean_sym = fyers_sym.replace("NSE:", "").replace("-EQ", "")

            if clean_sym in nifty100_syms:
                bt_df = feat_df[feat_df["dt"] >= "2020-06-01"].copy()
                if len(bt_df) >= 200:
                    bt_df = bt_df.set_index("dt")
                    bt_cache[clean_sym] = bt_df

            sampled = feat_df[feat_df["dt"].isin(sample_dates)].copy()
            sampled = sampled.dropna(subset=[r for r, _ in RAW_TO_PCT] + ["fwd_63d"])
            if not sampled.empty:
                sampled["symbol"] = clean_sym
                panel_chunks.append(sampled)

            if i % 100 == 0:
                gc.collect()
    finally:
        conn.close()

    panel = pd.concat(panel_chunks, ignore_index=True)
    del panel_chunks
    gc.collect()

    dt_counts = panel.groupby("dt")["symbol"].transform("count")
    panel = panel[dt_counts >= 30].copy()

    for raw_col, pct_col in RAW_TO_PCT:
        panel[pct_col] = panel.groupby("dt")[raw_col].rank(pct=True).astype("float32")

    cohort_med = panel.groupby("dt")["fwd_63d"].transform("median")
    panel["y"] = (panel["fwd_63d"] > cohort_med).astype(np.int8)

    panel["struct_raw"] = (
        0.45 * panel["pct_mom_ex_1m"]
        + 0.30 * panel["pct_dist_l52"]
        + 0.15 * (1.0 - panel["pct_r10"])
        + 0.10 * panel["pct_atr_pct"]
    )
    panel["pct_struct"] = panel.groupby("dt")["struct_raw"].rank(pct=True).astype("float32")

    panel = panel.sort_values(["dt", "symbol"]).reset_index(drop=True)
    return panel, bt_cache, nifty_regime


def evaluate_purged_oos(panel: pd.DataFrame) -> Dict[str, Any]:
    train_df = panel[panel["dt"] < "2023-10-01"]
    test_df = panel[panel["dt"] >= "2024-01-01"].copy()

    if len(train_df) < 1000 or len(test_df) < 200:
        raise RuntimeError(f"Insufficient split rows: train={len(train_df)}, oos={len(test_df)}")

    clf = build_xgb_model()
    clf.fit(train_df[XS_FEATURES].values, train_df["y"].values)

    tr_prob = clf.predict_proba(train_df[XS_FEATURES].values)[:, 1]
    te_prob = clf.predict_proba(test_df[XS_FEATURES].values)[:, 1]

    in_auc = float(roc_auc_score(train_df["y"].values, tr_prob))
    in_acc = float(accuracy_score(train_df["y"].values, (tr_prob >= 0.5).astype(int)))
    oos_auc = float(roc_auc_score(test_df["y"].values, te_prob))
    oos_acc = float(accuracy_score(test_df["y"].values, (te_prob >= 0.5).astype(int)))

    test_df["ml_prob"] = te_prob
    test_df["pct_ml"] = test_df.groupby("dt")["ml_prob"].rank(pct=True)
    test_df["blend_50_50"] = 0.50 * test_df["pct_struct"] + 0.50 * test_df["pct_ml"]

    univ_rets: List[float] = []
    struct_rets: List[float] = []
    ml_rets: List[float] = []
    blend_rets: List[float] = []
    rhos_ml: List[float] = []
    rhos_blend: List[float] = []

    for _, grp in test_df.groupby("dt"):
        if len(grp) < 30:
            continue
        u_ret = float(grp["fwd_63d"].mean())
        univ_rets.append(u_ret)
        struct_rets.append(float(grp.nlargest(10, "pct_struct")["fwd_63d"].mean()))
        ml_rets.append(float(grp.nlargest(10, "pct_ml")["fwd_63d"].mean()))
        blend_rets.append(float(grp.nlargest(10, "blend_50_50")["fwd_63d"].mean()))
        rhos_ml.append(spearman_corr(grp["ml_prob"].values, grp["fwd_63d"].values))
        rhos_blend.append(spearman_corr(grp["blend_50_50"].values, grp["fwd_63d"].values))

    blend_arr = np.array(blend_rets)
    univ_arr = np.array(univ_rets)
    beat_rate = float(np.mean(blend_arr > univ_arr) * 100.0) if len(univ_arr) else 0.0

    importances = clf.feature_importances_
    order = np.argsort(importances)[::-1]
    top_features = [
        {
            "rank": rank,
            "feature": XS_FEATURES[idx],
            "importance_pct": round(float(importances[idx]) * 100.0, 2),
        }
        for rank, idx in enumerate(order, 1)
    ]

    return {
        "evaluation_date": datetime.now().isoformat(),
        "split": {
            "train_period": f"{train_df['dt'].min()} to {train_df['dt'].max()}",
            "train_rows": int(len(train_df)),
            "blind_oos_period": f"{test_df['dt'].min()} to {test_df['dt'].max()}",
            "blind_oos_rows": int(len(test_df)),
            "blind_oos_cohorts": int(len(univ_rets)),
        },
        "in_sample": {"auc": round(in_auc, 4), "accuracy": round(in_acc, 4)},
        "blind_holdout": {
            "auc": round(oos_auc, 4),
            "accuracy": round(oos_acc, 4),
            "accuracy_gap_pct": round(abs(in_acc - oos_acc) * 100.0, 2),
            "overfit_passed": bool(abs(in_acc - oos_acc) * 100.0 < 8.0),
        },
        "cross_sectional_alpha": {
            "universe_mean_63d_pct": round(float(np.mean(univ_arr)), 2),
            "structural_top10_63d_pct": round(float(np.mean(struct_rets)), 2),
            "xgboost_top10_63d_pct": round(float(np.mean(ml_rets)), 2),
            "blend_50_50_top10_63d_pct": round(float(np.mean(blend_arr)), 2),
            "excess_alpha_per_quarter_pct": round(float(np.mean(blend_arr - univ_arr)), 2),
            "cohort_beat_rate_pct": round(beat_rate, 1),
            "oos_xgb_mean_spearman_rho": round(float(np.mean(rhos_ml)), 4),
            "oos_blend_mean_spearman_rho": round(float(np.mean(rhos_blend)), 4),
        },
        "top_features": top_features,
    }


def run_walk_forward_portfolio_backtest(
    panel: pd.DataFrame,
    bt_cache: Dict[str, pd.DataFrame],
    nifty_regime: Dict[str, Tuple[float, float]],
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """
    Strictly causal expanding-window walk-forward portfolio simulation (2021-Present)
    matching Protocol Primary Ledger A: 63-trading-day monthly cohort horizon
    with V3 Cross-Sectional 50/50 Blend on NIFTY100, 0.385% statutory friction,
    and zero premature SL/TP truncation or macro gating.
    """
    from app.services.forward_test import NIFTY100_ELIGIBLE_UNIVERSE

    valid_syms = [s for s in NIFTY100_ELIGIBLE_UNIVERSE if s in bt_cache]
    all_dates = sorted({dt for s in valid_syms for dt in bt_cache[s].index if dt >= "2021-01-04"})

    # Expanding causal yearly models: for year Y, fit ONLY on rows ending prior to Y-01-01
    yearly_models: Dict[int, xgb.XGBClassifier] = {}
    for yr in sorted({int(d[:4]) for d in all_dates}):
        cutoff_dt = f"{yr - 1}-09-25"
        tr_sub = panel[panel["dt"] < cutoff_dt]
        clf_yr = build_xgb_model()
        clf_yr.fit(tr_sub[XS_FEATURES].values, tr_sub["y"].values)
        yearly_models[yr] = clf_yr

    cash = initial_capital
    max_slots = 10
    rebalance_dates = set(all_dates[::21])  # Monthly cohort entry schedule

    active_trades: List[Dict[str, Any]] = []
    closed_trades: List[Dict[str, Any]] = []
    daily_equity: List[Tuple[str, float]] = []

    raw_cols = [r for r, _ in RAW_TO_PCT]

    for dt in all_dates:
        yr = int(dt[:4])

        # 1. Protocol Ledger A: fixed 63-trading-day (~90 calendar day) hold
        still_open: List[Dict[str, Any]] = []
        for pos in active_trades:
            sym = pos["symbol"]
            df_s = bt_cache[sym]
            if dt not in df_s.index:
                pos["bars_held"] += 1
                still_open.append(pos)
                continue

            c_p = float(df_s.loc[dt]["close"])
            pos["bars_held"] += 1
            pos["last_price"] = c_p

            if pos["bars_held"] >= 63:
                gross_ret = (c_p - pos["entry_price"]) / pos["entry_price"]
                net_ret = gross_ret - FRICTION_PCT
                net_proceeds = pos["cost"] * (1.0 + net_ret)
                cash += net_proceeds
                pnl = net_proceeds - pos["cost"]
                closed_trades.append(
                    {
                        "symbol": sym,
                        "entry_date": pos["entry_date"],
                        "exit_date": dt,
                        "year": int(dt[:4]),
                        "pnl": pnl,
                        "pnl_pct": net_ret * 100.0,
                        "bars_held": pos["bars_held"],
                    }
                )
            else:
                still_open.append(pos)

        active_trades = still_open

        mtm_open = sum(pos["shares"] * pos["last_price"] for pos in active_trades)
        total_eq = cash + mtm_open
        daily_equity.append((dt, total_eq))

        # 2. Allocate free slots on monthly cohort dates using pure V3 Cross-Sectional 50/50 Blend
        open_syms = {p["symbol"] for p in active_trades}
        if (dt in rebalance_dates) and len(active_trades) < max_slots:
            candidates = []
            for sym in valid_syms:
                if sym in open_syms:
                    continue
                df_s = bt_cache[sym]
                if dt not in df_s.index:
                    continue
                r = df_s.loc[dt]
                vals = [float(r[col]) for col in raw_cols]
                if any(np.isnan(vals)):
                    continue
                candidates.append(
                    {
                        "symbol": sym,
                        "close": float(r["close"]),
                        **{col: float(r[col]) for col in raw_cols},
                    }
                )

            if len(candidates) >= 20:
                cdf = pd.DataFrame(candidates)
                for raw_col, pct_col in RAW_TO_PCT:
                    cdf[pct_col] = cdf[raw_col].rank(pct=True)

                cdf["struct_raw"] = (
                    0.45 * cdf["pct_mom_ex_1m"]
                    + 0.30 * cdf["pct_dist_l52"]
                    + 0.15 * (1.0 - cdf["pct_r10"])
                    + 0.10 * cdf["pct_atr_pct"]
                )
                cdf["pct_struct"] = cdf["struct_raw"].rank(pct=True)

                probs = yearly_models[yr].predict_proba(cdf[XS_FEATURES].values)[:, 1]
                cdf["pct_ml"] = pd.Series(probs).rank(pct=True).values
                cdf["score"] = 0.50 * cdf["pct_struct"] + 0.50 * cdf["pct_ml"]
                ranked = cdf.sort_values("score", ascending=False)

                free_slots = max_slots - len(active_trades)
                slot_alloc = min(cash / max(1, free_slots), total_eq / max_slots)

                for _, pick in ranked.head(free_slots).iterrows():
                    if cash < slot_alloc * 0.5 or slot_alloc <= 0:
                        break
                    p = float(pick["close"])
                    invest = min(cash, slot_alloc)
                    shares = invest / p
                    cash -= invest
                    active_trades.append(
                        {
                            "symbol": pick["symbol"],
                            "entry_date": dt,
                            "entry_price": p,
                            "last_price": p,
                            "cost": invest,
                            "shares": shares,
                            "bars_held": 0,
                        }
                    )

    for pos in active_trades:
        p_end = pos["last_price"]
        entry = pos["entry_price"]
        net_ret = ((p_end - entry) / entry) - FRICTION_PCT
        net_proceeds = pos["cost"] * (1.0 + net_ret)
        cash += net_proceeds
        pnl = net_proceeds - pos["cost"]
        closed_trades.append(
            {
                "symbol": pos["symbol"],
                "entry_date": pos["entry_date"],
                "exit_date": all_dates[-1],
                "year": int(all_dates[-1][:4]),
                "pnl": pnl,
                "pnl_pct": net_ret * 100.0,
                "bars_held": pos["bars_held"],
            }
        )

    eq_vals = np.array([e for _, e in daily_equity], dtype=np.float64)
    final_cap = float(eq_vals[-1])
    total_ret_pct = ((final_cap / initial_capital) - 1.0) * 100.0
    years_span = max(0.5, len(eq_vals) / 252.0)
    cagr_1y = ((final_cap / initial_capital) ** (1.0 / years_span) - 1.0) * 100.0
    cagr_1m = ((final_cap / initial_capital) ** (1.0 / (years_span * 12.0)) - 1.0) * 100.0

    roll_peak = np.maximum.accumulate(eq_vals)
    drawdowns = (roll_peak - eq_vals) / roll_peak * 100.0
    max_dd = float(np.max(drawdowns))

    d_rets = np.diff(eq_vals) / np.maximum(1.0, eq_vals[:-1])
    sharpe = float((np.mean(d_rets) / (np.std(d_rets) + 1e-9)) * np.sqrt(252.0))
    down_rets = d_rets[d_rets < 0]
    sortino = float((np.mean(d_rets) / (np.std(down_rets) + 1e-9)) * np.sqrt(252.0)) if len(down_rets) else sharpe

    wins = [t for t in closed_trades if t["pnl"] > 0]
    losses = [t for t in closed_trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    pf = round(gross_win / max(1.0, gross_loss), 2)

    yearly_perf = []
    for yr in sorted({t["year"] for t in closed_trades}):
        yt = [t for t in closed_trades if t["year"] == yr]
        yw = sum(1 for t in yt if t["pnl"] > 0)
        yearly_perf.append(
            {
                "year": int(yr),
                "trades": len(yt),
                "win_rate_pct": round((yw / len(yt)) * 100.0, 1) if yt else 0.0,
                "pnl": round(sum(t["pnl"] for t in yt), 2),
            }
        )

    return {
        "period": f"{all_dates[0]} to {all_dates[-1]}",
        "strategy_version": "ALADDIN_V3_0_INSTITUTIONAL_PRE_DEC1",
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(final_cap, 2),
        "total_return_pct": round(total_ret_pct, 2),
        "cagr_1y_pct": round(cagr_1y, 2),
        "cagr_1m_pct": round(cagr_1m, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": pf,
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "total_trades": len(closed_trades),
        "win_rate_pct": round((len(wins) / max(1, len(closed_trades))) * 100.0, 2),
        "avg_win_pct": round(float(np.mean([t["pnl_pct"] for t in wins])), 2) if wins else 0.0,
        "avg_loss_pct": round(float(np.mean([t["pnl_pct"] for t in losses])), 2) if losses else 0.0,
        "avg_holding_days": round(float(np.mean([t["bars_held"] for t in closed_trades])), 1) if closed_trades else 0.0,
        "yearly_performance": yearly_perf,
    }


def main() -> None:
    from app.services.forward_test import NIFTY100_ELIGIBLE_UNIVERSE

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backtest-only",
        action="store_true",
        help="Reuse existing aladdin_xs_classifier.pkl/aladdin_xs_metrics.json and query recent window (2015-Present) for fast portfolio backtest.",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("ALADDIN V3 CROSS-SECTIONAL TRAINER & WALK-FORWARD BACKTESTER")
    print("=" * 72)
    db_path = resolve_db_path()
    print(f"Using OHLCV Store: {db_path}")

    min_dt = "2015-01-01" if args.backtest_only else "2006-01-01"
    sample_from_dt = "2016-06-01" if args.backtest_only else "2008-01-01"

    panel, bt_cache, nifty_regime = load_cross_sectional_panel_and_bt_cache(
        db_path, set(NIFTY100_ELIGIBLE_UNIVERSE), min_dt=min_dt, sample_from_dt=sample_from_dt
    )
    print(
        f"Loaded Cross-Sectional Panel: {len(panel):,} rows | "
        f"{panel['dt'].nunique()} cohorts ({panel['dt'].min()} to {panel['dt'].max()}) | "
        f"{panel['symbol'].nunique()} symbols"
    )

    if args.backtest_only and XS_CLASSIFIER_PATH.exists() and XS_METRICS_PATH.exists():
        print("\n[--backtest-only] Reusing existing aladdin_xs_classifier.pkl & aladdin_xs_metrics.json...")
        with open(XS_METRICS_PATH, "r", encoding="utf-8") as f:
            xs_metrics = json.load(f)
    else:
        print("\n[1/3] Running Purged Blind Out-of-Sample Audit (< 2023-10-01 train | >= 2024-01-01 OOS)...")
        xs_metrics = evaluate_purged_oos(panel)
        print(json.dumps(xs_metrics, indent=2))

        print("\n[2/3] Training Production Cross-Sectional Ranker on Full History...")
        prod_clf = build_xgb_model()
        prod_clf.fit(panel[XS_FEATURES].values, panel["y"].values)
        joblib.dump(prod_clf, XS_CLASSIFIER_PATH)
        with open(XS_FEATURES_PATH, "w", encoding="utf-8") as f:
            json.dump(XS_FEATURES, f, indent=2)
        with open(XS_METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(xs_metrics, f, indent=2)
        print(f"Saved {XS_CLASSIFIER_PATH}, {XS_FEATURES_PATH}, {XS_METRICS_PATH}")

    print("\n[3/3] Running Causal Walk-Forward Portfolio & Wide Chandelier EOD-SL Backtest (2021-Present)...")
    bt_report = run_walk_forward_portfolio_backtest(panel, bt_cache, nifty_regime)
    bt_report["xs_blind_oos"] = xs_metrics["cross_sectional_alpha"]
    with open(BACKTEST_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(bt_report, f, indent=2)
    print(json.dumps(bt_report, indent=2))
    print("\nDONE: Aladdin V3 Cross-Sectional Model & Reports Ready.")


if __name__ == "__main__":
    main()
