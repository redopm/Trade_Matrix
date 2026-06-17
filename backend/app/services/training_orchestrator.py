"""
Training Orchestrator — Phase 2
Full end-to-end pipeline: Download → Label (rule-based) → Train → Save

Stages:
  1. Fetch valid NSE symbols from Fyers Symbol Master (always up-to-date)
  2. Download OHLCV data via Fyers API / yfinance
  3. Generate sliding 60-day windows and extract geometric features
  4. Label each window using rule-based pattern classifier
  5. Train XGBoost on labeled features
  6. Save model + metadata
  7. Reload detector with new model

Progress tracking:
  - WebSocket broadcast at each stage
  - Supports cancellation
  - Resumes from existing labels (skip already-labeled windows)
"""
import asyncio
import io
import requests
from typing import Any, Callable, Optional
from datetime import datetime, timedelta

import pandas as pd

from app.config import settings
from app.services.data_fetcher import DataFetcher
from app.services.chart_generator import ChartGenerator
from app.services.pattern_labeler import PatternLabeler
from app.services.feature_extractor import FeatureExtractor
from app.services.model_trainer import PatternModelTrainer
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Fyers Symbol Master → NSE Equity Symbols ──────────────────────────────────
# Fyers provides a public CSV with ALL valid NSE symbols.
# We filter for -EQ series (cash market equities) and convert to yfinance format.
FYERS_SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_CM.csv"

# Minimal fallback list (if Fyers CSV download fails)
_FALLBACK_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "BAJFINANCE.NS", "TITAN.NS", "WIPRO.NS", "ONGC.NS", "NTPC.NS",
    "POWERGRID.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "TECHM.NS", "HCLTECH.NS",
    "BAJAJFINSV.NS", "COALINDIA.NS", "GRASIM.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "DIVISLAB.NS", "CIPLA.NS", "APOLLOHOSP.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "BRITANNIA.NS",
]


def get_training_symbols(max_symbols: int = 500) -> list[str]:
    """
    Fetch all valid NSE equity symbols from Fyers Symbol Master CSV.

    This is ALWAYS up-to-date and never has "Invalid symbol" errors.
    Returns yfinance-compatible symbols (RELIANCE.NS format).

    The Fyers NSE_CM.csv contains ALL listed NSE stocks.
    We filter for -EQ (equity cash market) series only.

    Args:
        max_symbols: Maximum number of symbols to use for training.
                     Default 500 covers Nifty 500 universe well.
    Returns:
        List of .NS symbols (e.g. ['RELIANCE.NS', 'TCS.NS', ...])
    """
    try:
        logger.info(f"Fetching NSE symbol list from Fyers Symbol Master...")
        resp = requests.get(FYERS_SYMBOL_MASTER_URL, timeout=30)
        resp.raise_for_status()

        # Parse CSV — Fyers NSE_CM.csv has NO header row.
        # Verified column structure (from live CSV inspection):
        #   Col 0:  fytoken (e.g., 101000000016921)
        #   Col 1:  company name (e.g., "20 MICRONS LTD")
        #   Col 9:  symbol ticker WITH exchange (e.g., "NSE:20MICRONS-EQ")
        #   Col 12: exchange_token (numeric — lower = more established/liquid stock)
        #   Col 13: symbol ticker ONLY (e.g., "20MICRONS")
        df = pd.read_csv(io.StringIO(resp.text), header=None, low_memory=False)

        # 1. Fetch live NSE equity tickers from Fyers
        df = pd.read_csv(io.StringIO(resp.text), header=None, low_memory=False)
        eq_mask = df[9].astype(str).str.endswith("-EQ")
        live_fyers_tickers = set([
            str(t).strip() for t in df[eq_mask][13] 
            if str(t).strip() and str(t).strip() != "nan"
        ])

        # 2. Extract our curated Large-cap & Mid-cap universe
        # This prevents training on manipulated micro-caps/penny stocks
        from app.services.data_fetcher import SECTOR_UNIVERSE
        curated_symbols = []
        for sector, symbols in SECTOR_UNIVERSE.items():
            for sym in symbols:
                # Remove .NS and .BO suffix for comparison
                ticker = sym.split(".")[0]
                # Only include if it is a live, valid NSE equity symbol
                if ticker in live_fyers_tickers:
                    curated_symbols.append(f"{ticker}.NS")

        # Deduplicate and limit count
        ns_symbols = list(dict.fromkeys(curated_symbols))[:max_symbols]

        logger.info(
            f"Fyers Symbol Master: Validated {len(ns_symbols)} curated Large/Mid-cap "
            f"NSE EQ symbols for training (filtered out micro-caps)."
        )
        return ns_symbols

    except Exception as e:
        logger.warning(
            f"Could not fetch Fyers Symbol Master ({e}). "
            f"Using fallback list of {len(_FALLBACK_SYMBOLS)} stocks."
        )
        return _FALLBACK_SYMBOLS.copy()


# Keep NIFTY_200_SYMBOLS for backward compatibility with other router references
NIFTY_200_SYMBOLS = _FALLBACK_SYMBOLS

NIFTY_200_SYMBOLS = [
    # Nifty 50 (core large caps)
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "BAJFINANCE.NS", "TITAN.NS", "WIPRO.NS", "ONGC.NS", "NTPC.NS",
    "POWERGRID.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "TECHM.NS", "HCLTECH.NS",
    "BAJAJFINSV.NS", "COALINDIA.NS", "GRASIM.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "JSWSTEEL.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "M&M.NS", "HINDALCO.NS",
    "DIVISLAB.NS", "CIPLA.NS", "APOLLOHOSP.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "BRITANNIA.NS", "TATACONSUM.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "BPCL.NS", "IOC.NS", "INDUSINDBK.NS", "PIDILITIND.NS",
    # Nifty Next 50
    "SIEMENS.NS", "DLF.NS", "GODREJCP.NS", "DABUR.NS", "COLPAL.NS",
    "MARICO.NS", "BERGEPAINT.NS", "HAVELLS.NS", "VOLTAS.NS", "WHIRLPOOL.NS",
    "CONCOR.NS", "BANKINDIA.NS", "CANBK.NS", "PNBHOUSING.NS", "MUTHOOTFIN.NS",
    "BAJAJHLDNG.NS", "3MINDIA.NS", "AMBUJACEM.NS", "ACC.NS", "RAMCOCEM.NS",
    "SAIL.NS", "NMDC.NS", "VEDL.NS", "HINDZINC.NS", "NATIONALUM.NS",
    "ZOMATO.NS", "NYKAA.NS", "PAYTM.NS", "POLICYBZR.NS", "DELHIVERY.NS",
    "IRCTC.NS", "INDIAMART.NS", "NAUKRI.NS", "JUSTDIAL.NS",
    "MPHASIS.NS", "LTIM.NS", "PERSISTENT.NS", "COFORGE.NS",
    "OFSS.NS", "KPITTECH.NS", "TATAELXSI.NS", "ZENSARTECH.NS",
    # Mid Cap quality
    "CROMPTON.NS", "POLYCAB.NS", "APLAPOLLO.NS", "KALYANKJIL.NS", "ABCAPITAL.NS",
    "CHOLAFIN.NS", "BAJAJCON.NS", "PIRAMALPHARM.NS", "TORNTPHARM.NS", "ALKEM.NS",
    "LUPIN.NS", "BIOCON.NS", "AUROPHARMA.NS", "GLENMARK.NS", "IPCALAB.NS",
    "PFIZER.NS", "ABBOTINDIA.NS", "METROPOLIS.NS", "LALPATHLAB.NS", "THYROCARE.NS",
    "ASTRAL.NS", "GSFC.NS", "CHAMBLFERT.NS", "COROMANDEL.NS",
    "UPL.NS", "PIIND.NS", "RALLIS.NS", "BAYERCROP.NS", "SHREECEM.NS",
    "INDIGO.NS", "GMRINFRA.NS",
    "ASHOKLEY.NS", "ESCORTS.NS", "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS",
    "CEATLTD.NS", "JKTYRE.NS", "GODFRYPHLP.NS", "UNITDSPR.NS", "RADICO.NS",
    "VBL.NS", "TITAN.NS", "SENCO.NS",
    # Banking & NBFC
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS", "RBLBANK.NS", "KTKBANK.NS",
    "KARURVYSYA.NS", "DCBBANK.NS", "UJJIVANSFB.NS", "EQUITASBNK.NS", "SURYODAY.NS",
    "MANAPPURAM.NS", "AAVAS.NS", "HOMEFIRST.NS", "REPCOHOME.NS", "APTUS.NS",
    # IT / Tech
    "CYIENT.NS", "BSOFT.NS", "MASTEK.NS",
    "HAPPSTMNDS.NS", "TANLA.NS", "INTELLECT.NS", "NEWGEN.NS",
    # Consumer
    "PAGEIND.NS", "VMART.NS", "DMART.NS", "TRENT.NS", "SHOPERSTOP.NS",
    "BATAINDIA.NS", "RELAXO.NS",
    # Infrastructure
    "KEC.NS", "KPIL.NS", "ENGINERSIN.NS", "NBCC.NS",
    "PNCINFRA.NS", "BRIGADE.NS", "PRESTIGE.NS", "SOBHA.NS",
    # Energy
    "TATAPOWER.NS", "CESC.NS", "TORNTPOWER.NS", "JINDALSTEL.NS", "MOIL.NS",
    "RECLTD.NS", "PFC.NS", "IRFC.NS", "HUDCO.NS", "NHPC.NS",
    # Healthcare
    "FORTIS.NS", "NH.NS", "ASTERDM.NS", "RAINBOW.NS", "MAXHEALTH.NS",
    "SOLARINDS.NS", "GRANULES.NS", "LAURUSLABS.NS", "DIVISLAB.NS",
    # Auto ancillaries
    "MOTHERSON.NS", "BOSCHLTD.NS", "EXIDEIND.NS", "SUNDRMFAST.NS",
    "SUPRAJIT.NS", "GABRIEL.NS", "SANDHAR.NS", "LUMAXIND.NS", "ENDURANCE.NS",
]


class TrainingOrchestrator:
    """
    End-to-end training pipeline orchestrator.
    
    Manages the full Phase 2 data pipeline:
    Download → Chart → Label → Features → Train → Save
    """

    def __init__(self) -> None:
        self.cfg = settings
        self.data_fetcher = DataFetcher()
        self.chart_gen = ChartGenerator()
        self.labeler = PatternLabeler()
        self.extractor = FeatureExtractor()
        self.trainer = PatternModelTrainer()
        self._is_running = False
        self._cancel = False

    async def run_full_pipeline(
        self,
        symbols: Optional[list[str]] = None,
        progress_callback: Optional[Callable] = None,
        use_rules_only: bool = True,
    ) -> dict[str, Any]:
        """
        Run the complete training pipeline.

        Args:
            symbols: Override stock list (default: Nifty 200)
            progress_callback: async fn(stage, pct, message) for progress
            use_rules_only: If True (default), use fast geometric rule-based labeling.
                            No Gemini API calls, no rate limits, completes in minutes.
                            If False, use Gemini Vision API for higher-accuracy labels
                            (slow: 15 req/min free tier, ~93 min for 1400 charts).

        Returns:
            Pipeline report
        """
        if self._is_running:
            return {"success": False, "error": "Training already in progress"}

        self._is_running = True
        self._cancel = False
        start_time = datetime.now()
        report = {}

        try:
            # If no symbols provided, fetch live from Fyers Symbol Master
            if symbols is None:
                await self._emit(progress_callback, "download", 0,
                                 "Fetching valid NSE symbols from Fyers Symbol Master...")
                target_symbols = await asyncio.get_event_loop().run_in_executor(
                    None, get_training_symbols, 500
                )
            else:
                target_symbols = symbols

            total = len(target_symbols)

            await self._emit(progress_callback, "download", 2,
                             f"Starting pipeline for {total} NSE equity stocks...")

            # ── Stage 1: Download OHLCV ───────────────────────────────────────
            logger.info(f"Stage 1: Downloading data for {total} stocks...")
            symbol_data: dict[str, pd.DataFrame] = {}

            sem = asyncio.Semaphore(self.cfg.MAX_CONCURRENT_FETCHES)
            tasks = [
                self._fetch_one(sym, sem)
                for sym in target_symbols
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, result in zip(target_symbols, results):
                if isinstance(result, pd.DataFrame) and not result.empty:
                    symbol_data[sym] = result

            downloaded = len(symbol_data)
            await self._emit(progress_callback, "download", 15,
                             f"Downloaded {downloaded}/{total} stocks")

            # ── Stage 2 + 3: Generate charts + Label with Gemini ─────────────
            existing_labels = {
                f"{l['symbol']}_{l.get('window_end', '')}": True
                for l in self.labeler.load_labels()
            }

            total_windows = 0
            labeled_count = 0

            for i, (sym, df) in enumerate(symbol_data.items()):
                if self._cancel:
                    break

                pct = 15 + int((i / downloaded) * 65)
                await self._emit(progress_callback, "labeling", pct,
                                 f"Labeling {sym} ({i+1}/{downloaded})...")

                windows = self._generate_windows(df)
                total_windows += len(windows)

                for w_start, w_end, df_window in windows:
                    cache_key = f"{sym}_{w_end}"
                    if cache_key in existing_labels:
                        labeled_count += 1
                        continue

                    if use_rules_only:
                        # ── Fast path: geometric rule-based labeling (no API) ──────
                        # Uses the same 23 geometric features to classify patterns.
                        # Completes in milliseconds per chart, no rate limits.
                        label = self.labeler._label_with_rules(sym, df_window, w_start, w_end)
                        if label:
                            label["symbol"] = sym
                            label["chart_path"] = ""
                            label["window_start"] = w_start
                            label["window_end"] = w_end
                            label["label_source"] = "rule_based"
                            label["created_at"] = datetime.now().isoformat()
                            features = self.extractor.extract(df_window)
                            if features:
                                label["features"] = features
                            self.labeler._save_label(label)
                            labeled_count += 1
                    else:
                        # ── Slow path: Gemini Vision API (optional, high accuracy) ──
                        # 15 req/min on free tier. ~93 min for 1400 charts.
                        _, img_bytes = self.chart_gen.generate_chart(
                            symbol=sym, df=df,
                            window_start=w_start, window_end=w_end, save=True,
                        )
                        label = await self.labeler.label_chart(
                            symbol=sym, image_bytes=img_bytes, chart_path="",
                            window_start=w_start, window_end=w_end, df_window=df_window,
                        )
                        if label:
                            labeled_count += 1

                    existing_labels[cache_key] = True

            await self._emit(progress_callback, "labeling", 80,
                             f"Labeled {labeled_count} chart windows")

            # ── Stage 4: Train model ──────────────────────────────────────────
            if labeled_count < 50:
                await self._emit(progress_callback, "training", 82,
                                 f"⚠️ Only {labeled_count} labels. Need 50+. Try more stocks.")
                return {
                    "success": False,
                    "error": f"Insufficient training data: {labeled_count} labels",
                    "labeled_count": labeled_count,
                }

            await self._emit(progress_callback, "training", 83,
                             f"Training XGBoost on {labeled_count} samples...")

            train_result = self.trainer.train(
                progress_callback=progress_callback
            )

            if not train_result.get("success"):
                await self._emit(progress_callback, "error", 85,
                                 f"Training failed: {train_result.get('error')}")
                return train_result

            await self._emit(progress_callback, "training", 95,
                             f"Model trained! Accuracy: {train_result.get('cv_accuracy', 0):.1%}")

            # ── Stage 5: Reload detector ──────────────────────────────────────
            from app.services.pattern_detector import PatternDetector
            detector = PatternDetector()
            detector.reload_model()

            elapsed = (datetime.now() - start_time).total_seconds()
            report = {
                "success": True,
                "downloaded_stocks": downloaded,
                "total_windows": total_windows,
                "labeled_windows": labeled_count,
                "cv_accuracy": train_result.get("cv_accuracy"),
                "n_classes": train_result.get("n_classes"),
                "classes": train_result.get("classes"),
                "elapsed_seconds": round(elapsed, 1),
            }

            await self._emit(progress_callback, "done", 100,
                             f"✅ Training complete! CV accuracy: {train_result.get('cv_accuracy', 0):.1%}")

            logger.info(f"Training pipeline complete: {report}")
            return report

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            await self._emit(progress_callback, "error", -1, f"Error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self._is_running = False

    def _generate_windows(
        self, df: pd.DataFrame
    ) -> list[tuple[str, str, pd.DataFrame]]:
        """Generate sliding 60-day windows from full history."""
        windows = []
        window = self.cfg.CHART_WINDOW_DAYS
        step = self.cfg.CHART_SLIDE_STEP

        if len(df) < window:
            return windows

        dates = df.index
        i = window
        while i <= len(dates):
            w_df = df.iloc[i - window:i]
            w_start = str(dates[i - window].date())
            w_end = str(dates[i - 1].date())
            windows.append((w_start, w_end, w_df))
            i += step

        return windows

    async def _fetch_one(
        self, symbol: str, sem: asyncio.Semaphore
    ) -> pd.DataFrame:
        """Fetch one stock with semaphore rate limiting."""
        async with sem:
            await asyncio.sleep(self.cfg.FETCH_DELAY_SECONDS)
            try:
                return await self.data_fetcher.fetch_price_history(
                    symbol, period=self.cfg.TRAINING_PERIOD
                )
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                return pd.DataFrame()

    @staticmethod
    async def _emit(
        callback: Optional[Callable],
        stage: str,
        pct: int,
        message: str,
    ) -> None:
        """Emit progress to callback if provided."""
        if callback:
            try:
                await callback(stage=stage, pct=pct, message=message)
            except Exception:
                pass

    def cancel(self) -> None:
        """Cancel the running pipeline."""
        self._cancel = True
        logger.info("Training pipeline cancellation requested.")

    @property
    def is_running(self) -> bool:
        return self._is_running
