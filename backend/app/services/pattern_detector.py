"""
Pattern Detector Service — Phase 2 Core Engine
Real-time chart pattern detection using the trained PyTorch Expert Vision Model.

Two-stage detection pipeline:
  Stage 1: Automatic Image + Num Feature Extraction
  Stage 2: PyTorch inference on Dual-Head model (EfficientNetV2 + LSTM)

Integration with Phase 1 screener:
  - After Phase 1 passes, run pattern detector on the shortlisted symbols
  - Confluence signal: Phase1 PASS + Pattern confidence >= Threshold
  - Pattern result stored in ScreenerSignal for frontend display
"""
import json
import io
import asyncio
from pathlib import Path
from typing import Optional, Any
from datetime import date

import numpy as np
import pandas as pd
import torch
from torchvision import transforms
from PIL import Image

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
    Real-time AI pattern detection engine using PyTorch.
    """
    def __init__(self) -> None:
        self.cfg = settings
        self.extractor = FeatureExtractor()
        self.chart_gen = ChartGenerator()
        self._model = None
        self._classes = []
        self._device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._model_loaded = False
        
        # Standard ImageNet transform for EfficientNet
        self._img_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    def _load_model(self) -> bool:
        """Lazy-load the PyTorch model on first use."""
        if self._model_loaded:
            return self._model is not None

        model_path = Path(settings.MODEL_PATH)
        meta_path = Path(settings.MODEL_METADATA_PATH)
        
        if not model_path.exists() or not meta_path.exists():
            logger.warning(f"Pattern model or metadata not found at {model_path}.")
            self._model_loaded = True
            return False

        try:
            from app.models.expert_model import ExpertTradeMatrixModel
            
            # Read metadata
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            self._classes = meta.get("classes", [])
            n_classes = meta.get("n_classes", len(self._classes))
            
            # Load PyTorch model
            self._model = ExpertTradeMatrixModel(n_classes=n_classes)
            # Load state dict — weights_only=False needed for compatibility
            self._model.load_state_dict(
                torch.load(str(model_path), map_location=self._device, weights_only=False),
                strict=True
            )
            self._model.to(self._device)
            self._model.eval()
            
            self._model_loaded = True
            logger.info(
                f"Expert Pattern model loaded: type=efficientnetv2_lstm, "
                f"n_classes={n_classes}, device={self._device}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load expert model: {e}")
            self._model_loaded = True
            return False

    def reload_model(self) -> bool:
        """Force reload model (after retraining)."""
        self._model_loaded = False
        self._model = None
        return self._load_model()
        
    def _prepare_tensors(self, df: pd.DataFrame, window_size: int = 60):
        """Prepare Dual-Input tensors (Image + Numerical)"""
        # 1. Numerical Tensor — CRITICAL: only use exactly 5 OHLCV columns
        #    yfinance df may contain extra columns (Dividends, Stock Splits etc.)
        #    which would break LSTM input_size=5 and cause NaN outputs.
        ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        window = df[ohlcv_cols].tail(window_size).copy()
        if len(window) < window_size:
            pad = pd.DataFrame(
                np.zeros((window_size - len(window), 5)),
                columns=ohlcv_cols
            )
            window = pd.concat([pad, window], ignore_index=True)
            
        max_p = window['High'].max() + 1e-5
        min_p = window['Low'].min() - 1e-5
        
        for col in ['Open', 'High', 'Low', 'Close']:
            window[col] = (window[col] - min_p) / (max_p - min_p)
            
        window['Volume'] = window['Volume'] / (window['Volume'].max() + 1e-5)
        # Fill any remaining NaN (e.g. from zero-volume days) with 0
        window = window.fillna(0.0)
        num_tensor = torch.tensor(window.values, dtype=torch.float32).unsqueeze(0).to(self._device)

        # 2. Image Tensor
        import matplotlib.pyplot as plt
        import mplfinance as mpf
        
        buf = io.BytesIO()
        dark_style = mpf.make_mpf_style(base_mpl_style='dark_background')
        fig, _ = mpf.plot(df.tail(window_size), type='candle', style=dark_style, volume=False, figsize=(4,4), returnfig=True, tight_layout=True)
        fig.savefig(buf, format='png', dpi=80)
        plt.close(fig)
        buf.seek(0)
        img = Image.open(buf).convert('RGB').resize((224, 224))
        
        img_tensor = self._img_transform(img).unsqueeze(0).to(self._device)
        return img_tensor, num_tensor

    async def detect(
        self,
        symbol: str,
        df: pd.DataFrame,
        phase1_passed: bool = False,
        generate_chart: bool = True,
        window_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """Run pattern detection on a stock's price history."""
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
            "features": {}, # Empty since we don't rely on rule-based anymore
        }

        if df is None or df.empty or len(df) < window:
            base_result["error"] = f"Insufficient price data (need at least {window} days)"
            return _clean_numpy(base_result)

        model_loaded = self._load_model()
        
        if not model_loaded or not self._model:
            base_result["error"] = "AI Model not loaded"
            return _clean_numpy(base_result)

        # ── Run AI Inference (Offloaded to thread) ──
        try:
            def _run_inference():
                img_tensor, num_tensor = self._prepare_tensors(df, window_size=window)
                with torch.no_grad():
                    out = self._model(img_tensor, num_tensor)
                    proba = torch.nn.functional.softmax(out, dim=1)[0].cpu().numpy()
                return proba

            proba = await asyncio.to_thread(_run_inference)
            
            all_scores = {cls: round(float(p), 4) for cls, p in zip(self._classes, proba)}
            top_idx = int(np.argmax(proba))
            top_pattern = self._classes[top_idx]
            top_confidence = float(proba[top_idx])

            is_bullish = None
            if top_pattern in self.cfg.BULLISH_PATTERNS:
                is_bullish = True
            elif top_pattern in self.cfg.BEARISH_PATTERNS:
                is_bullish = False

            if top_confidence < self.cfg.MIN_PATTERN_CONFIDENCE:
                top_pattern = "no_pattern"
                is_bullish = None

            base_result.update({
                "pattern_name": top_pattern,
                "confidence": top_confidence,
                "is_bullish": is_bullish,
                "all_scores": all_scores,
                "model_used": "expert_vision"
            })
            
        except Exception as e:
            logger.error(f"Inference failed for {symbol}: {e}")
            base_result["error"] = "Inference Exception"
            return _clean_numpy(base_result)

        # ── Confluence Check ──
        pattern = base_result.get("pattern_name")
        confidence = base_result.get("confidence", 0.0)

        base_result["is_confluence"] = (
            phase1_passed
            and pattern is not None
            and pattern != "no_pattern"
            and confidence >= self.cfg.CONFLUENCE_CONFIDENCE
            and base_result.get("is_bullish") is True
        )

        # ── Chart Generation ──
        if generate_chart and pattern and pattern != "no_pattern":
            try:
                annotation = {
                    "pattern_name": pattern,
                    "confidence": confidence,
                    "is_bullish": base_result.get("is_bullish"),
                }
                _, img_bytes = await asyncio.to_thread(
                    self.chart_gen.generate_chart,
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
            logger.info(f"🎯 CONFLUENCE: {symbol} | {pattern} ({confidence:.0%}) | Phase1+Phase2 pass!")
        elif pattern and pattern != "no_pattern":
            logger.debug(f"Pattern detected: {symbol} | {pattern} ({confidence:.0%})")

        return _clean_numpy(base_result)

    async def detect_batch(
        self,
        symbols_df_map: dict[str, pd.DataFrame],
        phase1_results: Optional[dict[str, bool]] = None,
    ) -> dict[str, dict]:
        """Detect patterns on multiple stocks concurrently."""
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
        logger.info(f"Batch detection: {len(results)} stocks | {confluence_count} confluence signals")
        return results

    def get_model_status(self) -> dict[str, Any]:
        """Return current model status."""
        model_path = Path(settings.MODEL_PATH)
        meta_path = Path(settings.MODEL_METADATA_PATH)

        if not model_path.exists():
            return {
                "is_ready": False,
                "message": "AI Model not installed in backend/models.",
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
                    "architecture": meta.get("architecture"),
                    "n_classes": meta.get("n_classes"),
                    "classes": meta.get("classes"),
                    "val_accuracy": meta.get("val_accuracy"),
                })
            except Exception:
                pass

        return status
