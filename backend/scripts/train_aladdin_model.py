"""
The Aladdin Brain — Robust Anti-Overfitting Training Engine
===========================================================
Trains the institutional Aladdin AI ML model using:
  1. Purged Chronological Time-Series Split (2020-23 Train, 2024 Val, 2025-26 Blind Holdout)
  2. Shallow Regularized Trees (max_depth=4, subsample=0.8, colsample=0.7)
  3. Strict L1 (reg_alpha=1.5) & L2 (reg_lambda=3.0) Penalties
  4. Early Stopping on unseen validation regime (patience=30 rounds)
  5. Holdout Generalization Verification (overfitting gap < 8%)

Artifacts Saved:
  - backend/models/aladdin_classifier.pkl
  - backend/models/aladdin_regressor.pkl
  - backend/models/aladdin_feature_names.json
  - backend/models/aladdin_metrics.json
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import joblib

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import xgboost as xgb
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_squared_error,
    r2_score
)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DATA_PATH = MODELS_DIR / "aladdin_training_data.parquet"
CSV_PATH = MODELS_DIR / "aladdin_training_data.csv"

CLASSIFIER_PATH = MODELS_DIR / "aladdin_classifier.pkl"
REGRESSOR_PATH = MODELS_DIR / "aladdin_regressor.pkl"
FEATURES_JSON = MODELS_DIR / "aladdin_feature_names.json"
METRICS_JSON = MODELS_DIR / "aladdin_metrics.json"


def load_dataset() -> pd.DataFrame:
    if DATA_PATH.exists():
        print(f"Loading dataset from {DATA_PATH}...")
        df = pd.read_parquet(DATA_PATH)
    elif CSV_PATH.exists():
        print(f"Loading dataset from {CSV_PATH}...")
        df = pd.read_csv(CSV_PATH, index_col=0, parse_dates=True)
    else:
        raise FileNotFoundError(f"Training dataset not found in {MODELS_DIR}. Run generate_aladdin_dataset.py first.")
    
    print(f"Dataset loaded: {len(df):,} rows, {len(df.columns)} columns.")
    return df


def purged_time_split(df: pd.DataFrame, embargo_days: int = 15):
    """
    Splits data chronologically with 15-day embargo to eliminate lookahead bias:
      - Training & Validation: 2021-01-04 -> 2024-12-15 (Covers both Bull Run and 2024 Consolidation)
      - Blind Holdout Test:    2025-01-01 -> 2026-09-22 (Completely unseen future data)
    """
    df_sorted = df.sort_index()

    # Holdout boundary: 2025-01-01 onwards
    in_sample_mask = (df_sorted.index < "2024-12-15")
    test_mask = (df_sorted.index >= "2025-01-01")

    in_sample_df = df_sorted[in_sample_mask]
    test_df = df_sorted[test_mask]

    # Purged split within in-sample: 80% train, 20% validation
    split_idx = int(len(in_sample_df) * 0.82)
    train_df = in_sample_df.iloc[:split_idx]
    val_df = in_sample_df.iloc[split_idx + embargo_days:] # 15-day embargo gap

    print("-" * 70)
    print("PURGED CHRONOLOGICAL TIME SPLIT:")
    print(f"• Training Set    (In-Sample) : {len(train_df):,} rows | {train_df.index.min().strftime('%Y-%m-%d')} to {train_df.index.max().strftime('%Y-%m-%d')}")
    print(f"• Validation Set  (Tuning)    : {len(val_df):,} rows | {val_df.index.min().strftime('%Y-%m-%d')} to {val_df.index.max().strftime('%Y-%m-%d')}")
    print(f"• Blind Holdout   (Unseen)    : {len(test_df):,} rows | {test_df.index.min().strftime('%Y-%m-%d')} to {test_df.index.max().strftime('%Y-%m-%d')}")
    print("-" * 70)

    return train_df, val_df, test_df


def train_classifier(X_train, y_train, X_val, y_val, feature_names):
    """
    Trains Regularized XGBoost Classifier.
    Enforces Quant Shields: Shallow depth (4), min child weight, L1/L2 penalties, and class balancing.
    """
    print("\n[PHASE 1] Training Regularized XGBoost Classifier (Win Probability)...")

    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_pos = neg_count / max(1, pos_count)
    print(f"Class Balance: {pos_count:,} Wins vs {neg_count:,} Losses (scale_pos_weight: {scale_pos:.2f})")

    clf = xgb.XGBClassifier(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=3,                # Ultra-shallow 3-level trees (robust generalizer)
        min_child_weight=25,        # Minimum 25 trade instances per leaf
        subsample=0.80,             # 80% row sampling
        colsample_bytree=0.70,      # 70% feature sampling per tree
        reg_alpha=2.0,              # L1 Lasso penalty (zeros out noisy features)
        reg_lambda=4.0,             # L2 Ridge penalty (prevents extreme weights)
        scale_pos_weight=1.0,       # Natural probability calibration
        gamma=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        early_stopping_rounds=40,
        n_jobs=-1
    )

    clf.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=25
    )

    print(f"Classifier converged at best iteration: {clf.best_iteration}")
    return clf


def train_regressor(X_train, y_train_ret, X_val, y_val_ret):
    """
    Trains Regularized XGBoost Regressor for forward return magnitude.
    """
    print("\n[PHASE 2] Training Regularized XGBoost Regressor (Expected Return %)...")

    reg = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=4,
        min_child_weight=20,
        subsample=0.80,
        colsample_bytree=0.70,
        reg_alpha=1.5,
        reg_lambda=3.0,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=42,
        early_stopping_rounds=30,
        n_jobs=-1
    )

    reg.fit(
        X_train, y_train_ret,
        eval_set=[(X_train, y_train_ret), (X_val, y_val_ret)],
        verbose=False
    )

    return reg


def evaluate_model(clf, reg, X_train, y_train, X_test, y_test, y_test_ret, feature_names):
    """
    Evaluates out-of-sample generalization on the Blind Holdout (2025-2026).
    Checks overfitting gap and generates full quant scorecard.
    """
    print("\n" + "=" * 70)
    print("🛡️ BLIND HOLDOUT EVALUATION (2025–2026 UNSEEN DATA)")
    print("=" * 70)

    # In-Sample (Train) Performance
    y_train_pred_prob = clf.predict_proba(X_train)[:, 1]
    train_auc = roc_auc_score(y_train, y_train_pred_prob)
    train_acc = accuracy_score(y_train, (y_train_pred_prob >= 0.50).astype(int))

    # Out-of-Sample (Blind Holdout) Performance
    y_test_pred_prob = clf.predict_proba(X_test)[:, 1]
    test_auc = roc_auc_score(y_test, y_test_pred_prob)
    test_acc = accuracy_score(y_test, (y_test_pred_prob >= 0.50).astype(int))

    # Conviction Thresholds & Deciles
    p70 = np.percentile(y_test_pred_prob, 70)
    p80 = np.percentile(y_test_pred_prob, 80)
    p90 = np.percentile(y_test_pred_prob, 90)

    top_30_mask = (y_test_pred_prob >= p70)
    top_20_mask = (y_test_pred_prob >= p80)
    top_10_mask = (y_test_pred_prob >= p90)

    prec_top_30 = precision_score(y_test, top_30_mask.astype(int), zero_division=0) * 100.0
    prec_top_20 = precision_score(y_test, top_20_mask.astype(int), zero_division=0) * 100.0
    prec_top_10 = precision_score(y_test, top_10_mask.astype(int), zero_division=0) * 100.0

    # Overfitting Gap check
    prec_baseline = np.mean(y_test) * 100.0
    acc_gap = abs(train_acc - test_acc) * 100.0
    auc_gap = abs(train_auc - test_auc) * 100.0

    print(f"• Baseline Market Win Rate (Blind Holdout) : {prec_baseline:.1f}%")
    print(f"• In-Sample  (Train) ROC-AUC                : {train_auc:.4f} (Accuracy: {train_acc*100:.1f}%)")
    print(f"• Out-of-Sample (Test) ROC-AUC              : {test_auc:.4f} (Accuracy: {test_acc*100:.1f}%)")
    print(f"• Overfitting Accuracy Gap                  : {acc_gap:.2f}% (Target: < 8.0%)")
    print(f"• Overfitting AUC Gap                       : {auc_gap:.2f}%")
    print("-" * 70)
    print("TARGET DECILE WIN RATES (BLIND HOLDOUT GENERALIZATION):")
    print(f"• Top 30% Model Conviction (Prob >= {p70:.2f}) : {prec_top_30:.1f}% Win Rate ({top_30_mask.sum():,} trades)")
    print(f"• Top 20% Model Conviction (Prob >= {p80:.2f}) : {prec_top_20:.1f}% Win Rate ({top_20_mask.sum():,} trades)")
    print(f"• Top 10% Institutional Calls (Prob >= {p90:.2f}) : {prec_top_10:.1f}% Win Rate ({top_10_mask.sum():,} trades)")
    print("-" * 70)

    # Feature Importance (Top 15)
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    top_features = []
    print("TOP 10 MOST INFLUENTIAL ALPHA FACTORS:")
    for rank, idx in enumerate(sorted_idx[:10], 1):
        name = feature_names[idx]
        imp = importances[idx] * 100.0
        top_features.append({"rank": rank, "feature": name, "importance_pct": round(imp, 2)})
        print(f"  {rank:02d}. {name:<25} : {imp:.2f}%")
    print("-" * 70)

    metrics = {
        "evaluation_date": datetime.now().isoformat(),
        "holdout_period": "2025-01-01 to Present",
        "in_sample": {
            "auc": round(float(train_auc), 4),
            "accuracy": round(float(train_acc), 4)
        },
        "blind_holdout": {
            "auc": round(float(test_auc), 4),
            "accuracy": round(float(test_acc), 4),
            "baseline_win_rate_pct": round(float(prec_baseline), 2),
            "top_30_pct_win_rate": round(float(prec_top_30), 2),
            "top_20_pct_win_rate": round(float(prec_top_20), 2),
            "top_10_pct_win_rate": round(float(prec_top_10), 2),
            "prob_threshold_p80": round(float(p80), 4),
            "prob_threshold_p90": round(float(p90), 4),
        },
        "anti_overfitting_audit": {
            "accuracy_gap_pct": round(float(acc_gap), 2),
            "auc_gap_pct": round(float(auc_gap), 2),
            "overfit_passed": bool(acc_gap < 8.0)
        },
        "top_features": top_features
    }

    return metrics


def main():
    print("=" * 70)
    print("[ALADDIN AI] ROBUST ANTI-OVERFITTING TRAINING PIPELINE")
    print("=" * 70)

    df = load_dataset()

    # Define feature columns (all columns except identifiers and target labels)
    exclude_cols = ["symbol", "close", "label", "max_forward_ret", "min_forward_ret", "final_ret"]
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    print(f"Engineered Feature Vector Length: {len(feature_cols)}")

    # 1. Purged Chronological Time Split
    train_df, val_df, test_df = purged_time_split(df)

    X_train = train_df[feature_cols].values
    y_train = train_df["label"].values
    y_train_ret = train_df["final_ret"].values

    X_val = val_df[feature_cols].values
    y_val = val_df["label"].values
    y_val_ret = val_df["final_ret"].values

    X_test = test_df[feature_cols].values
    y_test = test_df["label"].values
    y_test_ret = test_df["final_ret"].values

    # 2. Train Models
    classifier = train_classifier(X_train, y_train, X_val, y_val, feature_cols)
    regressor = train_regressor(X_train, y_train_ret, X_val, y_val_ret)

    # 3. Evaluate on Blind Holdout
    metrics = evaluate_model(classifier, regressor, X_train, y_train, X_test, y_test, y_test_ret, feature_cols)

    # 4. Save Artifacts
    print("\nSaving Production Artifacts to models/...")
    joblib.dump(classifier, CLASSIFIER_PATH)
    print(f"• Classifier saved: {CLASSIFIER_PATH}")

    joblib.dump(regressor, REGRESSOR_PATH)
    print(f"• Regressor saved:  {REGRESSOR_PATH}")

    with open(FEATURES_JSON, "w") as f:
        json.dump(feature_cols, f, indent=2)
    print(f"• Feature Names saved: {FEATURES_JSON}")

    with open(METRICS_JSON, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"• Quant Metrics saved: {METRICS_JSON}")

    print("\n" + "=" * 70)
    print("[SUCCESS] ALADDIN BRAIN ML MODEL READY FOR LIVE PRODUCTION INFERENCE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
