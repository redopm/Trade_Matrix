"""
Gemini Vision Pattern Labeler — Phase 2
Uses Google Gemini 1.5 Flash to auto-label historical chart images.

Free Tier Handling (IMPORTANT):
- Free tier limit: ~15 RPM (requests per minute), ~1500 RPD (per day)
- 429 errors handled with exponential backoff (up to 5 retries)
- Daily quota counter tracked in data/gemini_quota.json
- Automatically switches to rule-based labeler when quota exhausted
- Supports multi-day labeling (run daily, resumes from existing labels)

Colab Upgrade Path:
- Labels generated here (JSONL) can be exported to Google Colab
- Colab trains a PyTorch CNN for higher accuracy
- Trained Colab model can be imported back as model.pkl

Prompt Design:
  Structured JSON output from Gemini → direct parse, no regex needed
"""
import asyncio
import json
import time
import random
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, date

from app.config import settings
from app.utils.logger import get_logger
from app.services.feature_extractor import FeatureExtractor

logger = get_logger(__name__)

# ── Pattern Definitions for Gemini Prompt ─────────────────────────────────────
PATTERN_DESCRIPTIONS = {
    "double_bottom": "Two troughs at roughly equal price levels (W shape), separated by a peak. Bullish reversal.",
    "hs_bottom": "Inverse Head & Shoulders: three troughs where the middle one is lowest. Bullish reversal.",
    "bull_flag": "Sharp upward move (flagpole) followed by a brief consolidation in a downward-sloping channel. Bullish continuation.",
    "cup_handle": "Rounded bowl-shaped bottom followed by a small dip (handle). Bullish continuation/reversal.",
    "ascending_triangle": "Flat resistance line with rising support (higher lows). Bullish continuation.",
    "double_top": "Two peaks at roughly equal levels (M shape). Bearish reversal.",
    "bear_flag": "Sharp downward move followed by brief upward consolidation channel. Bearish continuation.",
    "descending_triangle": "Flat support line with declining resistance (lower highs). Bearish continuation.",
    "no_pattern": "No clear classical pattern detected. Choppy or trending without a recognizable setup.",
}

GEMINI_SYSTEM_PROMPT = """You are an expert technical analyst specializing in chart pattern recognition for Indian NSE stocks.

Analyze the provided candlestick chart and identify if ANY of these 8 classical patterns is visible:

BULLISH PATTERNS:
1. double_bottom: {double_bottom}
2. hs_bottom: {hs_bottom}
3. bull_flag: {bull_flag}
4. cup_handle: {cup_handle}
5. ascending_triangle: {ascending_triangle}

BEARISH PATTERNS:
6. double_top: {double_top}
7. bear_flag: {bear_flag}
8. descending_triangle: {descending_triangle}

9. no_pattern: {no_pattern}

IMPORTANT RULES:
- Only label a pattern if you are at least 60% confident
- Be strict - poor setups should be labeled "no_pattern"
- Consider volume confirmation (higher volume on breakouts = higher confidence)
- EMAs (yellow=200, blue=50) help identify trend context

Respond ONLY in this exact JSON format:
{{
  "pattern_name": "<one of the 9 options above>",
  "confidence": <integer 0-100>,
  "is_bullish": <true/false/null for no_pattern>,
  "reasoning": "<2-3 sentence explanation of why this pattern>",
  "pattern_start_bar": <approximate bar number from left where pattern starts, 0-indexed>,
  "pattern_end_bar": <approximate bar number where pattern ends>,
  "neckline_price": <approximate price of the neckline/breakout level or null>
}}
""".format(**PATTERN_DESCRIPTIONS)


class PatternLabeler:
    """
    Labels historical chart images using Gemini Vision API.
    Falls back to geometric rule-based labeling when:
      - No API key set
      - 429 quota exceeded (auto-detected)
      - Daily limit reached (1500 req/day free tier)
    """

    # Gemini free tier limits
    DAILY_QUOTA_LIMIT = 1400        # Be conservative (actual = 1500)
    MAX_RETRIES = 5
    BASE_BACKOFF_SECONDS = 65.0     # After 429: wait 65s minimum

    def __init__(self) -> None:
        self.cfg = settings
        self.feature_extractor = FeatureExtractor()
        self._gemini_client = None
        self._last_request_time = 0.0
        self._request_interval = 60.0 / max(self.cfg.GEMINI_RATE_LIMIT, 1)
        self._quota_exhausted = False  # Flag: switch to rule-based

        self.labels_file = Path(settings.LABELS_FILE)
        self.labels_file.parent.mkdir(parents=True, exist_ok=True)
        self._quota_file = Path(settings.LABELS_FILE).parent / "gemini_quota.json"

        # Initialize Gemini if API key is available
        if self.cfg.GEMINI_API_KEY:
            self._init_gemini()
        else:
            logger.warning("No GEMINI_API_KEY set. Using rule-based labeler fallback.")

    def _init_gemini(self) -> None:
        """Initialize Gemini client using new google.genai SDK."""
        try:
            from google import genai
            self._gemini_client = genai.Client(api_key=self.cfg.GEMINI_API_KEY)
            logger.info(f"Gemini Vision initialized (google.genai): {self.cfg.GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self._gemini_client = None

    def _get_quota_used_today(self) -> int:
        """Read today's API usage from quota tracker file."""
        today = str(date.today())
        try:
            if self._quota_file.exists():
                data = json.loads(self._quota_file.read_text())
                if data.get("date") == today:
                    return data.get("count", 0)
        except Exception:
            pass
        return 0

    def _increment_quota(self) -> int:
        """Increment today's quota counter. Returns new count."""
        today = str(date.today())
        count = self._get_quota_used_today() + 1
        try:
            self._quota_file.write_text(
                json.dumps({"date": today, "count": count})
            )
        except Exception:
            pass
        return count

    def is_quota_available(self) -> bool:
        """Check if we have remaining Gemini quota for today."""
        if self._quota_exhausted:
            return False
        used = self._get_quota_used_today()
        available = used < self.DAILY_QUOTA_LIMIT
        if not available:
            logger.warning(
                f"Gemini daily quota reached ({used}/{self.DAILY_QUOTA_LIMIT}). "
                "Switching to rule-based labeler for today."
            )
            self._quota_exhausted = True
        return available

    async def label_chart(
        self,
        symbol: str,
        image_bytes: bytes,
        chart_path: str,
        window_start: str,
        window_end: str,
        df_window=None,
    ) -> Optional[dict[str, Any]]:
        """
        Label a single chart using Gemini Vision (or fallback).

        Returns:
            Label dict with pattern_name, confidence, is_bullish, reasoning
        """
        if self._gemini_client and image_bytes and self.is_quota_available():
            label = await self._label_with_gemini(
                symbol, image_bytes, window_start, window_end
            )
            # If Gemini failed (returned None), fall back to rules
            if label is None:
                label = self._label_with_rules(symbol, df_window, window_start, window_end)
        else:
            label = self._label_with_rules(symbol, df_window, window_start, window_end)

        if label:
            label["symbol"] = symbol
            label["chart_path"] = chart_path
            label["window_start"] = window_start
            label["window_end"] = window_end
            label["label_source"] = "gemini" if self._gemini_client else "rule_based"
            label["created_at"] = datetime.now().isoformat()

            # Extract geometric features
            if df_window is not None:
                features = self.feature_extractor.extract(df_window)
                if features:
                    label["features"] = features

            self._save_label(label)

        return label

    async def _label_with_gemini(
        self,
        symbol: str,
        image_bytes: bytes,
        window_start: str,
        window_end: str,
    ) -> Optional[dict[str, Any]]:
        """Call Gemini Vision API with exponential backoff on 429."""
        await self._respect_rate_limit()

        for attempt in range(self.MAX_RETRIES):
            try:
                from google import genai
                from google.genai import types
                from PIL import Image
                import io

                img = Image.open(io.BytesIO(image_bytes))

                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._gemini_client.models.generate_content(
                        model=self.cfg.GEMINI_MODEL,
                        contents=[
                            GEMINI_SYSTEM_PROMPT,
                            img,
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                            max_output_tokens=512,
                        ),
                    )
                )

                raw_text = response.text.strip()
                # Remove markdown code fences if present
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()

                data = json.loads(raw_text)

                # Track quota
                count = self._increment_quota()

                result = {
                    "pattern_name": data.get("pattern_name", "no_pattern"),
                    "confidence": float(data.get("confidence", 0)) / 100.0,
                    "is_bullish": data.get("is_bullish"),
                    "reasoning": data.get("reasoning", ""),
                    "pattern_start_idx": data.get("pattern_start_bar"),
                    "pattern_end_idx": data.get("pattern_end_bar"),
                    "neckline": [data["neckline_price"]] if data.get("neckline_price") else None,
                    "gemini_raw": raw_text,
                }

                logger.info(
                    f"Gemini [{count}/{self.DAILY_QUOTA_LIMIT}] {symbol} "
                    f"[{window_start}→{window_end}]: "
                    f"{result['pattern_name']} ({result['confidence']:.0%})"
                )
                return result

            except Exception as e:
                err_str = str(e)

                # ── 429 Rate limit: exponential backoff ───────────────────
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    if "day" in err_str.lower() or "daily" in err_str.lower():
                        # Daily quota hit — don't retry, switch to rules
                        logger.warning(
                            "Gemini DAILY quota exhausted. "
                            "Switching to rule-based labeler. Resume tomorrow."
                        )
                        self._quota_exhausted = True
                        return None

                    # Per-minute quota: exponential backoff
                    backoff = self.BASE_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 10)
                    logger.warning(
                        f"Gemini 429 (attempt {attempt+1}/{self.MAX_RETRIES}). "
                        f"Waiting {backoff:.0f}s before retry..."
                    )
                    await asyncio.sleep(backoff)
                    continue

                # ── Other errors: log and return None ─────────────────────
                logger.error(f"Gemini API error for {symbol} (attempt {attempt+1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(5)
                    continue
                return None

        logger.error(f"Gemini failed after {self.MAX_RETRIES} retries for {symbol}")
        return None

    def _label_with_rules(
        self,
        symbol: str,
        df,
        window_start: str,
        window_end: str,
    ) -> dict[str, Any]:
        """
        Rule-based geometric labeler as Gemini fallback.
        Uses the 23 features to heuristically determine patterns.
        """
        if df is None or df.empty:
            return {"pattern_name": "no_pattern", "confidence": 0.5, "is_bullish": None}

        features = self.feature_extractor.extract(df)
        if not features:
            return {"pattern_name": "no_pattern", "confidence": 0.5, "is_bullish": None}

        pattern, confidence, is_bullish = self._classify_by_rules(features)

        return {
            "pattern_name": pattern,
            "confidence": confidence,
            "is_bullish": is_bullish,
            "reasoning": f"Rule-based geometric classification: {pattern}",
            "features": features,
        }

    def _classify_by_rules(
        self, features: dict[str, float]
    ) -> tuple[str, float, Optional[bool]]:
        """
        Classify pattern using geometric rules.
        Returns (pattern_name, confidence, is_bullish).
        """
        n_peaks = features.get("n_peaks", 0)
        n_troughs = features.get("n_troughs", 0)
        peak_sym = features.get("peak_symmetry_score", 0)
        trough_sym = features.get("trough_symmetry_score", 0)
        upper_slope = features.get("upper_trendline_slope", 0)
        lower_slope = features.get("lower_trendline_slope", 0)
        convergence = features.get("trendline_convergence", 0)
        recovery = features.get("recovery_from_low_pct", 0)
        vol_breakout = features.get("volume_at_breakout_ratio", 1.0)
        vol_trend = features.get("volume_trend_slope", 0)
        rsi_end = features.get("rsi_at_window_end", 0.5)
        obv_slope = features.get("obv_slope", 0)

        # ── Double Bottom: 2 troughs, symmetric, bullish ─────────────────────
        if (n_troughs >= 2 and n_peaks >= 1 and trough_sym > 0.85
                and recovery > 0.5 and obv_slope > 0):
            conf = min(0.5 + trough_sym * 0.3 + recovery * 0.2, 0.92)
            return "double_bottom", conf, True

        # ── Double Top: 2 peaks, symmetric, bearish ──────────────────────────
        if (n_peaks >= 2 and n_troughs >= 1 and peak_sym > 0.85
                and recovery < 0.3 and obv_slope < 0):
            conf = min(0.5 + peak_sym * 0.3 + (1 - recovery) * 0.2, 0.90)
            return "double_top", conf, False

        # ── Head & Shoulders Bottom (3 troughs, middle is deepest) ───────────
        if (n_troughs >= 3 and features.get("trough_depth_std", 0) > 0.05
                and trough_sym > 0.75 and obv_slope > 0):
            conf = min(0.5 + trough_sym * 0.25 + obv_slope * 0.1, 0.88)
            return "hs_bottom", conf, True

        # ── Ascending Triangle: flat upper, rising lower ──────────────────────
        if (abs(upper_slope) < 0.005 and lower_slope > 0.003
                and vol_breakout > 1.2):
            conf = min(0.55 + min(lower_slope * 50, 0.3), 0.85)
            return "ascending_triangle", conf, True

        # ── Descending Triangle: flat lower, declining upper ──────────────────
        if (abs(lower_slope) < 0.005 and upper_slope < -0.003
                and vol_breakout > 1.2):
            conf = min(0.55 + min(abs(upper_slope) * 50, 0.3), 0.85)
            return "descending_triangle", conf, False

        # ── Bull Flag: strong uptrend + brief consolidation ───────────────────
        if (lower_slope > 0.01 and upper_slope < 0 and upper_slope > -0.01
                and vol_trend < 0 and vol_breakout > 1.5):
            conf = 0.70
            return "bull_flag", conf, True

        # ── Bear Flag: strong downtrend + brief upward consolidation ──────────
        if (upper_slope < -0.01 and lower_slope > 0 and lower_slope < 0.01
                and vol_trend < 0 and vol_breakout > 1.5):
            conf = 0.68
            return "bear_flag", conf, False

        # ── Cup & Handle: rounded bottom + slight pullback ────────────────────
        if (recovery > 0.7 and n_troughs >= 1
                and features.get("pattern_compactness", 0) > 0.5
                and obv_slope > 0):
            conf = min(0.55 + recovery * 0.2, 0.80)
            return "cup_handle", conf, True

        return "no_pattern", 0.9, None

    async def _respect_rate_limit(self) -> None:
        """Enforce per-minute rate limiting (14 req/min for free tier)."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            wait = self._request_interval - elapsed
            await asyncio.sleep(wait)
        self._last_request_time = time.monotonic()

    def get_quota_status(self) -> dict[str, Any]:
        """Return current Gemini quota usage."""
        used = self._get_quota_used_today()
        return {
            "used_today": used,
            "daily_limit": self.DAILY_QUOTA_LIMIT,
            "remaining": max(0, self.DAILY_QUOTA_LIMIT - used),
            "is_exhausted": self._quota_exhausted or used >= self.DAILY_QUOTA_LIMIT,
            "reset_at": "midnight IST",
            "strategy": "Multi-day labeling: resumes from existing labels each day",
        }

    def _save_label(self, label: dict[str, Any]) -> None:
        """Append label to JSONL file."""
        try:
            with open(self.labels_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(label, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to save label: {e}")

    def load_labels(self) -> list[dict[str, Any]]:
        """Load all labels from JSONL file."""
        labels = []
        if not self.labels_file.exists():
            return labels
        try:
            with open(self.labels_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            labels.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return labels
        except Exception as e:
            logger.error(f"Failed to load labels: {e}")
            return []

    def get_label_stats(self) -> dict[str, Any]:
        """Get statistics about the labeled dataset."""
        labels = self.load_labels()
        if not labels:
            return {"total": 0, "by_pattern": {}, "by_source": {}}

        by_pattern: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for l in labels:
            pn = l.get("pattern_name", "unknown")
            src = l.get("label_source", "unknown")
            by_pattern[pn] = by_pattern.get(pn, 0) + 1
            by_source[src] = by_source.get(src, 0) + 1

        return {
            "total": len(labels),
            "by_pattern": by_pattern,
            "by_source": by_source,
            "labels_file": str(self.labels_file),
        }
