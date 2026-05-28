"""
Patterns Router — Phase 2 API Endpoints
Provides REST API for pattern training, detection, and results.

Endpoints:
  POST /patterns/train              — Start full training pipeline
  GET  /patterns/status             — Model status + accuracy
  GET  /patterns/quota              — Gemini API quota usage
  GET  /patterns/detect/{symbol}    — Detect on single stock
  GET  /patterns/detect-all         — Detect on all Phase 1 signals
  GET  /patterns/chart/{symbol}     — Serve annotated chart image
  GET  /patterns/labels             — View labeled training samples
  GET  /patterns/labels/stats       — Label dataset statistics
  WS   /patterns/ws/train           — Real-time training progress

WebSocket (ws://localhost:8000/api/v1/patterns/ws/train):
  Client receives JSON events:
  {"stage": "labeling", "pct": 45, "message": "Labeling RELIANCE..."}
"""
import asyncio
import json
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import Response, JSONResponse

from app.config import settings
from app.services.pattern_detector import PatternDetector
from app.services.pattern_labeler import PatternLabeler
from app.services.model_trainer import PatternModelTrainer
from app.services.training_orchestrator import TrainingOrchestrator, NIFTY_200_SYMBOLS
from app.services.data_fetcher import DataFetcher
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/patterns", tags=["patterns"])

# Module-level singletons
_detector = PatternDetector()
_labeler = PatternLabeler()
_trainer = PatternModelTrainer()
_fetcher = DataFetcher()
_orchestrator = TrainingOrchestrator()


# ── Model Status ──────────────────────────────────────────────────────────────

@router.get("/status")
async def get_model_status() -> dict:
    """Get current model status, accuracy, and metadata."""
    status = _detector.get_model_status()
    label_stats = _labeler.get_label_stats()
    quota = _labeler.get_quota_status()

    return {
        "model": status,
        "labels": label_stats,
        "gemini_quota": quota,
        "patterns_supported": settings.all_patterns,
        "phase": "2",
    }


@router.get("/quota")
async def get_gemini_quota() -> dict:
    """Check Gemini API daily quota usage."""
    return _labeler.get_quota_status()


# ── Training Pipeline ─────────────────────────────────────────────────────────

@router.post("/train")
async def start_training(
    symbols: Optional[list[str]] = None,
    use_full_nifty200: bool = True,
) -> dict:
    """
    Start the full training pipeline asynchronously.
    Returns immediately; connect to /ws/train for real-time progress.
    """
    if _orchestrator.is_running:
        raise HTTPException(409, "Training already in progress. Connect to /ws/train for status.")

    target_symbols = None if use_full_nifty200 else (symbols or NIFTY_200_SYMBOLS[:50])
    label_count = len(_labeler.load_labels())

    return {
        "status": "starting",
        "message": "Training pipeline started. Connect to WebSocket /api/v1/patterns/ws/train for progress.",
        "existing_labels": label_count,
        "target_symbols": len(target_symbols or NIFTY_200_SYMBOLS),
        "resume_from_existing": label_count > 0,
        "ws_url": "ws://localhost:8000/api/v1/patterns/ws/train",
    }


@router.post("/train/model-only")
async def train_model_only() -> dict:
    """
    Train the XGBoost model from existing labels (skip chart generation + Gemini).
    Use this when you already have enough labels (e.g., from multi-day Gemini runs).
    """
    label_stats = _labeler.get_label_stats()
    total_labels = label_stats.get("total", 0)

    if total_labels < 50:
        raise HTTPException(
            400,
            f"Only {total_labels} labels found. Need 50+. Run /train first to generate labels."
        )

    result = _trainer.train()
    if result.get("success"):
        _detector.reload_model()
        return {
            "status": "success",
            "cv_accuracy": result.get("cv_accuracy"),
            "n_samples": result.get("n_samples"),
            "n_classes": result.get("n_classes"),
            "classes": result.get("classes"),
            "top_features": result.get("top_features", [])[:5],
        }
    else:
        raise HTTPException(500, result.get("error", "Training failed"))


@router.post("/train/cancel")
async def cancel_training() -> dict:
    """Cancel a running training pipeline."""
    if not _orchestrator.is_running:
        return {"status": "not_running"}
    _orchestrator.cancel()
    return {"status": "cancellation_requested"}


# ── Pattern Detection ─────────────────────────────────────────────────────────

@router.get("/detect/{symbol}")
async def detect_pattern(
    symbol: str,
    phase1_passed: bool = False,
    generate_chart: bool = True,
) -> dict:
    """
    Run pattern detection on a single stock.
    
    Args:
        symbol: NSE symbol (e.g., RELIANCE or RELIANCE.NS)
        phase1_passed: Mark Phase 1 as passed for confluence check
        generate_chart: Whether to generate annotated chart image
    """
    sym = symbol.upper()
    if not sym.endswith(".NS"):
        sym = f"{sym}.NS"

    try:
        df = await _fetcher.fetch_price_history(sym, period="2y")
        if df.empty:
            raise HTTPException(404, f"No data found for {symbol}")

        result = await _detector.detect(
            symbol=sym,
            df=df,
            phase1_passed=phase1_passed,
            generate_chart=generate_chart,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pattern detection failed for {symbol}: {e}")
        raise HTTPException(500, str(e))


@router.get("/detect-all")
async def detect_all_signals(limit: int = Query(50, le=200)) -> dict:
    """
    Run pattern detection on the most recent Phase 1 screener signals.
    Useful for batch updating all signals with pattern data.
    """
    from app.database import AsyncSessionLocal
    from app.models.signal import ScreenerSignal
    from sqlalchemy import select, desc

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScreenerSignal)
            .where(ScreenerSignal.passed_all.is_(True))
            .order_by(desc(ScreenerSignal.created_at))
            .limit(limit)
        )
        signals = result.scalars().all()

    if not signals:
        return {"total": 0, "results": [], "message": "No Phase 1 signals found. Run screener first."}

    symbols = list({s.symbol for s in signals})
    detections = {}

    for sym in symbols:
        try:
            df = await _fetcher.fetch_ohlcv(sym, period="1y")
            if not df.empty:
                det = await _detector.detect(sym, df, phase1_passed=True)
                detections[sym] = det
        except Exception as e:
            logger.warning(f"Detection failed for {sym}: {e}")

    confluence_count = sum(1 for d in detections.values() if d.get("is_confluence"))
    pattern_count = sum(
        1 for d in detections.values()
        if d.get("pattern_name") and d.get("pattern_name") != "no_pattern"
    )

    return {
        "total": len(detections),
        "confluence_signals": confluence_count,
        "patterns_detected": pattern_count,
        "results": list(detections.values()),
    }


# ── Chart Images ──────────────────────────────────────────────────────────────

@router.get("/chart/{symbol}")
async def get_chart_image(
    symbol: str,
    date: Optional[str] = None,
) -> Response:
    """
    Serve the annotated chart image for a symbol.
    Returns PNG image bytes.
    """
    from app.services.chart_generator import ChartGenerator
    gen = ChartGenerator()

    sym = symbol.upper()
    if not sym.endswith(".NS"):
        sym = f"{sym}.NS"

    # Find existing chart or generate new one
    from datetime import date as dt_date
    chart_date = date or str(dt_date.today())
    chart_path = gen.get_chart_path(sym, chart_date)

    if chart_path and Path(chart_path).exists():
        img_bytes = Path(chart_path).read_bytes()
        return Response(content=img_bytes, media_type="image/png")

    # Generate fresh chart
    df = await _fetcher.fetch_ohlcv(sym, period="6mo")
    if df.empty:
        raise HTTPException(404, f"No data for {symbol}")

    _, img_bytes = ChartGenerator().generate_chart(symbol=sym, df=df, save=True)
    if not img_bytes:
        raise HTTPException(500, "Chart generation failed")

    return Response(content=img_bytes, media_type="image/png")


# ── Labels & Training Data ────────────────────────────────────────────────────

@router.get("/labels/stats")
async def get_label_stats() -> dict:
    """Get statistics about the labeled training dataset."""
    return _labeler.get_label_stats()


@router.get("/labels")
async def get_labels(
    pattern: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> dict:
    """List labeled training samples with optional filtering."""
    labels = _labeler.load_labels()

    if pattern:
        labels = [l for l in labels if l.get("pattern_name") == pattern]
    if source:
        labels = [l for l in labels if l.get("label_source") == source]

    total = len(labels)
    paginated = labels[offset : offset + limit]

    # Strip heavy fields for list view
    light = []
    for l in paginated:
        light.append({
            "symbol": l.get("symbol"),
            "pattern_name": l.get("pattern_name"),
            "confidence": l.get("confidence"),
            "is_bullish": l.get("is_bullish"),
            "window_start": l.get("window_start"),
            "window_end": l.get("window_end"),
            "label_source": l.get("label_source"),
            "reasoning": l.get("reasoning", "")[:150],
        })

    return {"total": total, "offset": offset, "limit": limit, "items": light}


@router.get("/labels/export")
async def export_labels_for_colab() -> Response:
    """
    Export labels.jsonl for use in Google Colab CNN training.
    Downloads the full labeled dataset as a JSONL file.
    """
    labels_path = Path(settings.LABELS_FILE)
    if not labels_path.exists():
        raise HTTPException(404, "No labels file found. Run training pipeline first.")

    content = labels_path.read_bytes()
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename=tradematrix_labels.jsonl",
            "X-Total-Labels": str(content.count(b"\n")),
        }
    )


@router.post("/model/import")
async def import_colab_model() -> dict:
    """
    Import a model trained in Google Colab.
    Expects model file at models/colab_model.pkl
    (Copy from Colab to this path, then call this endpoint).
    """
    colab_path = Path(settings.MODEL_DIR) / "colab_model.pkl"
    if not colab_path.exists():
        raise HTTPException(
            404,
            f"Colab model not found at {colab_path}. "
            "Upload your colab_model.pkl file there first."
        )

    import shutil
    import joblib

    # Validate it's a valid model bundle
    try:
        bundle = joblib.load(str(colab_path))
        assert "model" in bundle and "label_encoder" in bundle
    except Exception as e:
        raise HTTPException(400, f"Invalid model file: {e}")

    # Replace current model
    shutil.copy2(str(colab_path), settings.MODEL_PATH)
    _detector.reload_model()

    return {
        "status": "success",
        "message": "Colab model imported and activated!",
        "classes": bundle.get("classes", []),
        "n_features": bundle.get("n_features"),
    }


# ── WebSocket: Training Progress ──────────────────────────────────────────────

@router.websocket("/ws/train")
async def training_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time training progress.
    
    Message format:
    {
      "stage": "download" | "labeling" | "training" | "done" | "error",
      "pct": 0-100,
      "message": "Human readable status",
      "timestamp": "ISO datetime"
    }
    """
    await websocket.accept()
    logger.info("Training WebSocket connected")

    from datetime import datetime

    async def send_progress(stage: str, pct: int, message: str):
        try:
            await websocket.send_json({
                "stage": stage,
                "pct": pct,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass

    try:
        await send_progress("init", 0, "Training pipeline initializing...")

        result = await _orchestrator.run_full_pipeline(
            progress_callback=send_progress,
        )

        if result.get("success"):
            await send_progress(
                "done", 100,
                f"✅ Complete! CV accuracy: {result.get('cv_accuracy', 0):.1%} | "
                f"{result.get('labeled_windows', 0)} charts labeled | "
                f"{result.get('n_classes', 0)} pattern classes"
            )
        else:
            await send_progress("error", -1, f"❌ Failed: {result.get('error', 'Unknown error')}")

        await websocket.send_json({"type": "COMPLETE", "result": result})

    except WebSocketDisconnect:
        logger.info("Training WebSocket disconnected")
        _orchestrator.cancel()
    except Exception as e:
        logger.error(f"Training WebSocket error: {e}")
        try:
            await websocket.send_json({"stage": "error", "pct": -1, "message": str(e)})
        except Exception:
            pass
