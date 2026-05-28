"""
Pattern Detector Service — Phase 2 Core Engine
Real-time chart pattern detection using the trained XGBoost model.

Two-stage detection pipeline:
  Stage 1: Geometric pre-filter (instant, rule-based) — eliminates 80%
  Stage 2: XGBoost inference on 23 features — provides pattern + confidence

Integration with Phase 1 screener:
  - After Phase 1 passes, run pattern detector on the shortlisted symbols
  - Confluence signal: Phase1 PASS + Pattern confidence >= 80%
  - Pattern result stored in ScreenerSignal for frontend display
"""
import json
from pathlib import Path
from typing import Optional, Any
from datetime import date

import numpy as np
import pandas as pd

from app.config import settings
from app.services.feature_extractor import FeatureExtractor
from app.services.chart_generator import ChartGenerator
from app.utils.logger import get_logger

logger = get_logger(__name__)

def _clean_numpy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _clean_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_numpy(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        if pd.isna(obj):
            return None
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj


class PatternDetector:
    """
    Real-time pattern detection engine.
    
    Usage:
        detector = PatternDetector()
        result = await detector.detect(symbol, df)
        # result = {
        #   "pattern_name": "double_bottom",
        #   "confidence": 0.87,
        #   "is_bullish": True,
        #   "all_scores": {...},
        #   "is_confluence": True,   (if Phase1 also passed)
        #   "chart_path": "/data/charts/RELIANCE_20241215.png"
        # }
    """

    def __init__(self) -> None:
        self.cfg = settings
        self.extractor = FeatureExtractor()
        self.chart_gen = ChartGenerator()
        self._model_bundle: Optional[dict] = None
        self._model_loaded = False

    def _load_model(self) -> bool:
        """Lazy-load the XGBoost model on first use."""
        if self._model_loaded:
            return self._model_bundle is not None

        model_path = Path(settings.MODEL_PATH)
        if not model_path.exists():
            logger.warning(f"Pattern model not found at {model_path}. Run training first.")
            self._model_loaded = True
            return False

        try:
            import joblib
            self._model_bundle = joblib.load(str(model_path))
            self._model_loaded = True
            logger.info(
                f"Pattern model loaded: {self._model_bundle.get('n_classes')} classes, "
                f"{self._model_bundle.get('n_features')} features"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load pattern model: {e}")
            self._model_loaded = True
            return False

    def reload_model(self) -> bool:
        """Force reload model (after retraining)."""
        self._model_loaded = False
        self._model_bundle = None
        return self._load_model()

    async def detect(
        self,
        symbol: str,
        df: pd.DataFrame,
        phase1_passed: bool = False,
        generate_chart: bool = True,
        window_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Run pattern detection on a stock's price history.

        Args:
            symbol: Stock ticker
            df: Full OHLCV DataFrame
            phase1_passed: Whether Phase 1 screener passed (for confluence)
            generate_chart: Whether to generate an annotated chart image
            window_days: Override window size

        Returns:
            Detection result dict
        """
        window = window_days or self.cfg.CHART_WINDOW_DAYS
        base_result = {
            "symbol": symbol,
            "detection_date": str(date.today()),
            "pattern_name": None,
            "confidence": 0.0,
            "is_bullish": None,
            "all_scores": {},
            "is_confluence": False,
            "chart_path": None,
            "model_used": "none",
            "features": {},
        }

        if df is None or df.empty or len(df) < 30:
            base_result["error"] = "Insufficient price data"
            return _clean_numpy(base_result)

        # Use last N days
        df_window = df.tail(window)

        # ── Stage 1: Feature Extraction ───────────────────────────────────────
        features = self.extractor.extract(df_window)
        if not features:
            base_result["error"] = "Feature extraction failed"
            return _clean_numpy(base_result)

        base_result["features"] = features
        feat_vec = self.extractor.features_to_vector(features)

        # ── Stage 2: ML Model or Rule-Based ───────────────────────────────────
        if self._load_model() and feat_vec is not None:
            result = self._predict_with_model(feat_vec, features)
            result["model_used"] = "xgboost"
        else:
            # Fallback to rule-based detection
            from app.services.pattern_labeler import PatternLabeler
            labeler = PatternLabeler()
            rule_result = labeler._classify_by_rules(features)
            result = {
                "pattern_name": rule_result[0],
                "confidence": rule_result[1],
                "is_bullish": rule_result[2],
                "all_scores": {rule_result[0]: rule_result[1]},
                "model_used": "rule_based",
            }

        base_result.update(result)

        # ── Stage 3: Confluence Check ─────────────────────────────────────────
        pattern = base_result.get("pattern_name")
        confidence = base_result.get("confidence", 0.0)
        is_bullish = base_result.get("is_bullish")

        base_result["is_confluence"] = (
            phase1_passed
            and pattern is not None
            and pattern != "no_pattern"
            and confidence >= self.cfg.CONFLUENCE_CONFIDENCE
            and is_bullish is True   # Only bullish patterns for our long strategy
        )

        # ── Stage 4: Chart Generation ─────────────────────────────────────────
        if generate_chart and pattern and pattern != "no_pattern":
            try:
                annotation = {
                    "pattern_name": pattern,
                    "confidence": confidence,
                    "is_bullish": is_bullish,
                    "neckline": result.get("neckline"),
                }
                _, img_bytes = self.chart_gen.generate_chart(
                    symbol=symbol,
                    df=df,
                    pattern_annotation=annotation,
                    save=True,
                )
                if img_bytes:
                    window_end = str(df.index[-1].date())
                    chart_path = self.chart_gen.get_chart_path(symbol, window_end)
                    base_result["chart_path"] = chart_path
            except Exception as e:
                logger.warning(f"Chart generation failed for {symbol}: {e}")

        if base_result["is_confluence"]:
            logger.info(
                f"🎯 CONFLUENCE: {symbol} | {pattern} ({confidence:.0%}) | "
                f"Phase1+Phase2 both pass!"
            )
        elif pattern and pattern != "no_pattern":
            logger.debug(
                f"Pattern detected: {symbol} | {pattern} ({confidence:.0%}) | "
                f"Phase1: {phase1_passed}"
            )

        return _clean_numpy(base_result)

    def _predict_with_model(
        self, feat_vec: np.ndarray, features: dict
    ) -> dict[str, Any]:
        """Run XGBoost inference and return all class probabilities."""
        bundle = self._model_bundle
        model = bundle["model"]
        le = bundle["label_encoder"]
        classes = bundle["classes"]

        # Predict probabilities
        proba = model.predict_proba(feat_vec.reshape(1, -1))[0]
        all_scores = {cls: round(float(p), 4) for cls, p in zip(classes, proba)}

        # Top prediction
        top_idx = int(np.argmax(proba))
        top_pattern = le.inverse_transform([top_idx])[0]
        top_confidence = float(proba[top_idx])

        # Determine bullish/bearish
        is_bullish = None
        if top_pattern in settings.BULLISH_PATTERNS:
            is_bullish = True
        elif top_pattern in settings.BEARISH_PATTERNS:
            is_bullish = False

        # Ignore low-confidence predictions
        if top_confidence < self.cfg.MIN_PATTERN_CONFIDENCE:
            top_pattern = "no_pattern"
            is_bullish = None

        return {
            "pattern_name": top_pattern,
            "confidence": top_confidence,
            "is_bullish": is_bullish,
            "all_scores": all_scores,
        }

    async def detect_batch(
        self,
        symbols_df_map: dict[str, pd.DataFrame],
        phase1_results: Optional[dict[str, bool]] = None,
    ) -> dict[str, dict]:
        """
        Detect patterns on multiple stocks concurrently.
        Used by the screener to process all Phase 1 shortlist at once.

        Args:
            symbols_df_map: {symbol: df} dict
            phase1_results: {symbol: passed_bool} dict

        Returns:
            {symbol: detection_result} dict
        """
        results = {}
        phase1_results = phase1_results or {}

        for symbol, df in symbols_df_map.items():
            try:
                result = await self.detect(
                    symbol=symbol,
                    df=df,
                    phase1_passed=phase1_results.get(symbol, False),
                    generate_chart=True,
                )
                results[symbol] = result
            except Exception as e:
                logger.error(f"Pattern detection failed for {symbol}: {e}")
                results[symbol] = {
                    "symbol": symbol, "error": str(e),
                    "pattern_name": None, "confidence": 0.0,
                }

        confluence_count = sum(1 for r in results.values() if r.get("is_confluence"))
        logger.info(
            f"Batch detection: {len(results)} stocks | "
            f"{confluence_count} confluence signals"
        )
        return results

    def get_model_status(self) -> dict[str, Any]:
        """Return current model status."""
        model_path = Path(settings.MODEL_PATH)
        meta_path = Path(settings.MODEL_METADATA_PATH)

        if not model_path.exists():
            return {
                "is_ready": False,
                "message": "Model not trained. Go to Training tab to start.",
            }

        status = {
            "is_ready": True,
            "model_path": str(model_path),
            "model_size_kb": round(model_path.stat().st_size / 1024, 1),
        }

        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                status.update({
                    "trained_at": meta.get("trained_at"),
                    "cv_accuracy": meta.get("cv_accuracy"),
                    "n_samples": meta.get("n_samples"),
                    "n_classes": meta.get("n_classes"),
                    "classes": meta.get("classes"),
                    "top_features": meta.get("top_features", [])[:5],
                })
            except Exception:
                pass

        return status
