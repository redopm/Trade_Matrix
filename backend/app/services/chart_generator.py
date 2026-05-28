"""
Chart Generator Service — Phase 2
Generates professional candlestick chart images from OHLCV data.

Features:
- mplfinance-based candlestick charts (dark theme)
- Overlays: EMA(200), EMA(50), Volume, RSI panel
- Annotates detected patterns (necklines, trendlines, labels)
- Saves PNG images to data/charts/ directory
- Returns annotated images for API serving
"""
import io
import os
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (no GUI needed)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import mplfinance as mpf

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Dark Theme Colors ─────────────────────────────────────────────────────────
DARK_STYLE = {
    "base_mpl_style": "dark_background",
    "marketcolors": mpf.make_marketcolors(
        up="#00f5a0",        # Green for up candles
        down="#ff4466",      # Red for down candles
        edge="inherit",
        wick="inherit",
        volume={"up": "#00f5a040", "down": "#ff446640"},
    ),
    "rc": {
        "axes.labelcolor": "#94a3b8",
        "axes.edgecolor": "#1e293b",
        "xtick.color": "#64748b",
        "ytick.color": "#64748b",
        "grid.color": "#1e293b",
        "figure.facecolor": "#080c14",
        "axes.facecolor": "#0d1420",
        "font.family": "DejaVu Sans",
    },
}


class ChartGenerator:
    """
    Generates candlestick chart images for pattern labeling and display.
    """

    def __init__(self) -> None:
        self.cfg = settings
        self.charts_dir = Path(settings.CHARTS_DIR)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self._style = mpf.make_mpf_style(**DARK_STYLE)

    def generate_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
        pattern_annotation: Optional[dict[str, Any]] = None,
        save: bool = True,
    ) -> tuple[str, bytes]:
        """
        Generate a candlestick chart with technical overlays.

        Args:
            symbol: Stock ticker
            df: Full OHLCV DataFrame
            window_start: Start date for window (YYYY-MM-DD)
            window_end: End date for window (YYYY-MM-DD)
            pattern_annotation: Pattern to draw (from detector)
            save: Save to disk

        Returns:
            (file_path, image_bytes) tuple
        """
        try:
            # Slice to window
            chart_df = self._prepare_dataframe(df, window_start, window_end)
            if chart_df.empty:
                return "", b""

            # Build indicators as overlays
            ema50 = chart_df["Close"].ewm(span=50).mean()
            ema200 = chart_df["Close"].ewm(span=200).mean()

            apds = [
                mpf.make_addplot(
                    ema50, color="#4facfe", width=1.2, alpha=0.9,
                    label="EMA50"
                ),
                mpf.make_addplot(
                    ema200, color="#ffd700", width=1.5, alpha=0.9,
                    label="EMA200"
                ),
            ]

            # RSI panel
            rsi = self._compute_rsi(chart_df["Close"], 14)
            apds.append(
                mpf.make_addplot(
                    rsi, panel=2, color="#a78bfa", width=1.0,
                    ylabel="RSI(14)", ylim=(0, 100)
                )
            )
            # RSI reference lines (30, 70)
            rsi_30 = pd.Series([30.0] * len(chart_df), index=chart_df.index)
            rsi_70 = pd.Series([70.0] * len(chart_df), index=chart_df.index)
            apds.append(mpf.make_addplot(rsi_30, panel=2, color="#ff4466", width=0.8, linestyle="--", alpha=0.6))
            apds.append(mpf.make_addplot(rsi_70, panel=2, color="#00f5a0", width=0.8, linestyle="--", alpha=0.6))

            # Figure size
            figsize = (
                self.cfg.CHART_WIDTH_PX / self.cfg.CHART_DPI,
                self.cfg.CHART_HEIGHT_PX / self.cfg.CHART_DPI,
            )

            title = f"{symbol.replace('.NS', '')} — {window_start or 'start'} to {window_end or 'end'}"
            if pattern_annotation and pattern_annotation.get("pattern_name"):
                pname = pattern_annotation["pattern_name"].replace("_", " ").title()
                conf = pattern_annotation.get("confidence", 0)
                title += f"\n🔍 {pname} ({conf:.0%} confidence)"

            fig, axes = mpf.plot(
                chart_df,
                type="candle",
                style=self._style,
                title=title,
                volume=True,
                addplot=apds,
                figsize=figsize,
                returnfig=True,
                panel_ratios=(4, 1, 2),
                tight_layout=True,
            )

            # Draw pattern annotations if provided
            if pattern_annotation:
                self._draw_pattern_annotation(axes[0], chart_df, pattern_annotation)

            # Save to file
            date_tag = (window_end or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
            sym_clean = symbol.replace(".NS", "").replace(".", "_")
            filename = f"{sym_clean}_{date_tag}.png"
            filepath = self.charts_dir / filename

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=self.cfg.CHART_DPI, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            img_bytes = buf.read()

            if save:
                filepath.write_bytes(img_bytes)
                logger.debug(f"Chart saved: {filepath}")

            return str(filepath), img_bytes

        except Exception as e:
            logger.error(f"Chart generation failed for {symbol}: {e}")
            return "", b""

    def generate_annotated_detection_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        detection_result: dict[str, Any],
    ) -> bytes:
        """
        Generate a chart annotated with real-time detection results.
        Used for the frontend Pattern tab display.
        """
        window_end = str(df.index[-1].date())
        window_start = str(df.index[-self.cfg.CHART_WINDOW_DAYS].date()) \
            if len(df) >= self.cfg.CHART_WINDOW_DAYS else str(df.index[0].date())

        _, img_bytes = self.generate_chart(
            symbol=symbol,
            df=df,
            window_start=window_start,
            window_end=window_end,
            pattern_annotation=detection_result,
            save=False,
        )
        return img_bytes

    def _prepare_dataframe(
        self,
        df: pd.DataFrame,
        window_start: Optional[str],
        window_end: Optional[str],
    ) -> pd.DataFrame:
        """Slice and prepare DataFrame for mplfinance."""
        chart_df = df.copy()

        if window_start:
            chart_df = chart_df[chart_df.index >= window_start]
        if window_end:
            chart_df = chart_df[chart_df.index <= window_end]

        # Ensure correct column names
        col_map = {c.lower(): c for c in chart_df.columns}
        rename = {}
        for std in ["open", "high", "low", "close", "volume"]:
            for c in chart_df.columns:
                if c.lower() == std:
                    rename[c] = std.capitalize()
        chart_df.rename(columns=rename, inplace=True)

        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [r for r in required if r not in chart_df.columns]
        if missing:
            logger.warning(f"Missing columns: {missing}")
            return pd.DataFrame()

        chart_df = chart_df[required].dropna()
        return chart_df

    def _draw_pattern_annotation(
        self,
        ax: plt.Axes,
        df: pd.DataFrame,
        annotation: dict[str, Any],
    ) -> None:
        """Draw pattern-specific annotations on the chart axis."""
        try:
            pattern = annotation.get("pattern_name", "")
            n = len(df)

            # Get neckline coordinates if available
            neckline = annotation.get("neckline")
            if neckline and len(neckline) >= 2:
                ax.axhline(
                    y=neckline[0],
                    color="#ffd700",
                    linewidth=1.5,
                    linestyle="--",
                    alpha=0.8,
                    label="Neckline",
                )

            # Highlight pattern region
            pattern_start_idx = annotation.get("pattern_start_idx", max(0, n - 30))
            pattern_end_idx = annotation.get("pattern_end_idx", n - 1)

            ax.axvspan(
                pattern_start_idx,
                pattern_end_idx,
                alpha=0.08,
                color="#4facfe" if annotation.get("is_bullish") else "#ff4466",
            )

            # Pattern label text
            mid_idx = (pattern_start_idx + pattern_end_idx) // 2
            price_range = df["High"].max() - df["Low"].min()
            label_y = df["High"].max() + price_range * 0.02

            ax.text(
                mid_idx,
                label_y,
                pattern.replace("_", " ").upper(),
                color="#ffd700",
                fontsize=8,
                fontweight="bold",
                ha="center",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="#080c14",
                    edgecolor="#ffd700",
                    alpha=0.8,
                ),
            )
        except Exception as e:
            logger.debug(f"Annotation drawing error (non-critical): {e}")

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Compute RSI without pandas_ta dependency."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    def get_chart_path(self, symbol: str, date: str) -> Optional[str]:
        """Get path to an existing chart image."""
        sym_clean = symbol.replace(".NS", "").replace(".", "_")
        date_tag = date.replace("-", "")
        path = self.charts_dir / f"{sym_clean}_{date_tag}.png"
        return str(path) if path.exists() else None
