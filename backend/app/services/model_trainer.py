"""
Model Trainer Service — Phase 2
Trains an XGBoost pattern classifier on Gemini-labeled chart data.

Pipeline:
  1. Load labeled data from labels.jsonl
  2. Extract/verify geometric features for each label
  3. Encode pattern labels (8 classes + no_pattern)
  4. Train XGBoost with cross-validation
  5. Save model + metadata (accuracy, feature importance, classes)
  6. Report classification metrics

Design:
  - XGBoost: Fast (CPU), interpretable, robust on small datasets (300-2000 samples)
  - Cross-validation: 5-fold stratified (handles class imbalance)
  - Class weights: Upsampling rare patterns for balanced training
  - Feature importance: Logged for debugging
"""
import json
import os
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

import numpy as np
import joblib
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

from app.config import settings
from app.services.feature_extractor import FeatureExtractor
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PatternModelTrainer:
    """
    Trains and saves an XGBoost pattern classifier.
    
    Model details:
    - Algorithm: XGBoost (gradient boosting, CPU-optimized)
    - Input: 23 geometric features
    - Output: 9 classes (8 patterns + no_pattern)
    - Training: 5-fold cross-validation with stratification
    """

    # XGBoost hyperparameters (tuned for small-medium datasets)
    XGBOOST_PARAMS = {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "multi:softprob",
        "eval_metric": "mlogloss",
        "use_label_encoder": False,
        "random_state": 42,
        "n_jobs": -1,         # Use all CPU cores
        "tree_method": "hist",  # Fast histogram method
    }

    def __init__(self) -> None:
        self.cfg = settings
        self.extractor = FeatureExtractor()
        self.model_dir = Path(settings.MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train(
        self,
        labels_override: Optional[list[dict]] = None,
        min_samples_per_class: int = 5,
        progress_callback=None,
    ) -> dict[str, Any]:
        """
        Full training pipeline: load data → train → evaluate → save.

        Args:
            labels_override: Use these labels instead of loading from file
            min_samples_per_class: Minimum labels needed per pattern class
            progress_callback: async callable for progress reporting

        Returns:
            Training report with accuracy, feature importance, etc.
        """
        logger.info("Starting pattern model training...")

        # ── Step 1: Load and validate labels ─────────────────────────────────
        if labels_override:
            all_labels = labels_override
        else:
            from app.services.pattern_labeler import PatternLabeler
            labeler = PatternLabeler()
            all_labels = labeler.load_labels()

        logger.info(f"Total labels loaded: {len(all_labels)}")

        if len(all_labels) < 50:
            return {
                "success": False,
                "error": f"Insufficient training data: {len(all_labels)} labels (need 50+)",
            }

        # ── Step 2: Extract features ──────────────────────────────────────────
        X, y, valid_labels = self._prepare_dataset(all_labels, min_samples_per_class)
        logger.info(f"Dataset: {X.shape[0]} samples × {X.shape[1]} features, {len(set(y))} classes")

        if X.shape[0] < 30:
            return {
                "success": False,
                "error": f"Too few valid samples: {X.shape[0]}",
            }

        # ── Step 3: Encode labels ─────────────────────────────────────────────
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        classes = list(le.classes_)
        n_classes = len(classes)

        logger.info(f"Classes: {classes}")

        # ── Step 4: Cross-validation ──────────────────────────────────────────
        params = {**self.XGBOOST_PARAMS, "num_class": n_classes}
        model = xgb.XGBClassifier(**params)

        cv = StratifiedKFold(n_splits=min(5, min(
            np.bincount(y_encoded).min(), 5
        )), shuffle=True, random_state=42)

        cv_scores = cross_val_score(
            model, X, y_encoded, cv=cv, scoring="accuracy", n_jobs=-1
        )
        cv_accuracy = float(np.mean(cv_scores))
        cv_std = float(np.std(cv_scores))

        logger.info(f"Cross-validation accuracy: {cv_accuracy:.2%} ± {cv_std:.2%}")

        # ── Step 5: Final training on full dataset ────────────────────────────
        model.fit(
            X, y_encoded,
            eval_set=[(X, y_encoded)],
            verbose=False,
        )

        # ── Step 6: Evaluation ────────────────────────────────────────────────
        y_pred = model.predict(X)
        train_accuracy = float(accuracy_score(y_encoded, y_pred))

        report_dict = classification_report(
            y_encoded, y_pred,
            target_names=classes,
            output_dict=True,
            zero_division=0,
        )

        # Feature importance
        feature_importance = dict(zip(
            FeatureExtractor.FEATURE_NAMES,
            model.feature_importances_.tolist(),
        ))
        top_features = sorted(feature_importance.items(), key=lambda x: -x[1])[:10]

        logger.info(f"Top features: {[f[0] for f in top_features[:5]]}")

        # ── Step 7: Save model and metadata ──────────────────────────────────
        model_path = Path(settings.MODEL_PATH)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        # Save: {xgb model + label encoder + feature names} as dict
        model_bundle = {
            "model": model,
            "label_encoder": le,
            "feature_names": FeatureExtractor.FEATURE_NAMES,
            "classes": classes,
            "n_features": X.shape[1],
        }
        joblib.dump(model_bundle, str(model_path))

        metadata = {
            "trained_at": datetime.now().isoformat(),
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_classes": n_classes,
            "classes": classes,
            "cv_accuracy": round(cv_accuracy, 4),
            "cv_std": round(cv_std, 4),
            "train_accuracy": round(train_accuracy, 4),
            "classification_report": report_dict,
            "feature_importance": feature_importance,
            "top_features": top_features,
            "model_path": str(model_path),
        }

        meta_path = Path(settings.MODEL_METADATA_PATH)
        meta_path.write_text(json.dumps(metadata, indent=2))

        logger.info(
            f"✅ Model trained! CV accuracy: {cv_accuracy:.2%} | "
            f"Classes: {classes} | Saved: {model_path}"
        )

        return {"success": True, **metadata}

    def _prepare_dataset(
        self,
        labels: list[dict],
        min_samples: int,
    ) -> tuple[np.ndarray, list[str], list[dict]]:
        """
        Convert labels to feature matrix X and label vector y.
        Filters out invalid labels and rare classes.
        """
        X_list = []
        y_list = []
        valid = []

        for label in labels:
            pattern = label.get("pattern_name")
            confidence = float(label.get("confidence", 0))
            features_dict = label.get("features")

            # Filter: skip low-confidence patterns (but keep no_pattern)
            if not pattern:
                continue
            if pattern != "no_pattern" and confidence < 0.5:
                continue

            # Get features
            if features_dict and isinstance(features_dict, dict):
                feat_vec = self.extractor.features_to_vector(features_dict)
            else:
                # Try to re-extract if we have raw data (not available, skip)
                continue

            if feat_vec is None or np.any(np.isnan(feat_vec)):
                continue

            X_list.append(feat_vec)
            y_list.append(pattern)
            valid.append(label)

        if not X_list:
            return np.array([]), [], []

        X = np.array(X_list, dtype=np.float32)
        y = y_list

        # Remove classes with too few samples
        from collections import Counter
        class_counts = Counter(y)
        valid_classes = {cls for cls, cnt in class_counts.items() if cnt >= min_samples}

        if valid_classes != set(y):
            removed = set(y) - valid_classes
            logger.warning(f"Removing rare classes (< {min_samples} samples): {removed}")
            mask = [label in valid_classes for label in y]
            X = X[mask]
            y = [label for label, m in zip(y, mask) if m]
            valid = [v for v, m in zip(valid, mask) if m]

        logger.info(f"Final dataset: {X.shape[0]} samples, classes: {dict(Counter(y))}")
        return X, y, valid

    def load_model(self) -> Optional[dict[str, Any]]:
        """Load the saved model bundle."""
        model_path = Path(settings.MODEL_PATH)
        if not model_path.exists():
            return None
        try:
            return joblib.load(str(model_path))
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None

    def get_model_metadata(self) -> Optional[dict[str, Any]]:
        """Load model metadata."""
        meta_path = Path(settings.MODEL_METADATA_PATH)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text())
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return None
