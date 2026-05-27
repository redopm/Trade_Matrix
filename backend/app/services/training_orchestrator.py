"""
Training Orchestrator — Phase 2
Full end-to-end pipeline: Download → Chart Gen → Gemini Label → Train → Save

Stages:
  1. Download OHLCV for all Nifty 200 stocks (3 years)
  2. Generate 60-day sliding window chart images (mplfinance)
  3. Send to Gemini Vision for auto-labeling
  4. Extract geometric features from each window
  5. Train XGBoost on labeled features
  6. Save model + metadata
  7. Reload detector with new model

Progress tracking:
  - WebSocket broadcast at each stage
  - Supports cancellation
  - Resumes from existing labels (skip already-labeled windows)
"""
import asyncio
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

# Nifty 200 stock symbols for training universe
NIFTY_200_SYMBOLS = [
    # Nifty 50 (core large caps)
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFOSYS.NS", "ICICIBANK.NS",
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
    "IRCTC.NS", "INDIAMART.NS", "NAUKRI.NS", "JUSTDIAL.NS", "MCLEODRUSEL.NS",
    "MPHASIS.NS", "HEXAWARE.NS", "LTIM.NS", "PERSISTENT.NS", "COFORGE.NS",
    "OFSS.NS", "KPIT.NS", "TATAELXSI.NS", "ZENSARTECH.NS", "NIITTECH.NS",
    # Mid Cap quality
    "CROMPTON.NS", "POLYCAB.NS", "APLAPOLLO.NS", "KALYANKJIL.NS", "ABCAPITAL.NS",
    "CHOLAFIN.NS", "BAJAJCON.NS", "PIRAMALENT.NS", "TORNTPHARM.NS", "ALKEM.NS",
    "LUPIN.NS", "BIOCON.NS", "AUROPHARMA.NS", "GLENMARK.NS", "IPCA.NS",
    "PFIZER.NS", "ABBOTINDIA.NS", "METROPOLIS.NS", "LALPATHLAB.NS", "THYROCARE.NS",
    "ASTRAL.NS", "FINOLEX.NS", "GSFC.NS", "CHAMBLFERT.NS", "COROMANDEL.NS",
    "UPL.NS", "PI.NS", "RALLIS.NS", "BAYER.NS", "SHREECEM.NS",
    "INDIGO.NS", "INTERGLOBE.NS", "SPICEJET.NS", "GMRINFRA.NS", "IRB.NS",
    "ASHOKLEY.NS", "ESCORTS.NS", "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS",
    "CEAT.NS", "JKTYRE.NS", "GODFRYPHLP.NS", "MCDOWELL-N.NS", "RADICO.NS",
    "VBL.NS", "VAIBHAVGBL.NS", "TITAN.NS", "PCJEWELLER.NS", "SENCO.NS",
    # Banking & NBFC
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS", "RBLBANK.NS", "KTKBANK.NS",
    "KARURVYSYA.NS", "DCBBANK.NS", "UJJIVANSFB.NS", "EQUITAS.NS", "SURYODAY.NS",
    "MANAPPURAM.NS", "AAVAS.NS", "HOMEFIRST.NS", "REPCO.NS", "APTUS.NS",
    # IT / Tech
    "MINDTREE.NS", "CYIENT.NS", "MPHASIS.NS", "BIRLASOFT.NS", "MASTEK.NS",
    "HAPPSTMNDS.NS", "TANLA.NS", "INTELLECT.NS", "NEWGEN.NS", "ZENSAR.NS",
    # Consumer
    "PAGEIND.NS", "VMART.NS", "DMART.NS", "TRENT.NS", "SHOPERSTOP.NS",
    "BATAINDIA.NS", "RELAXO.NS", "CAMPUS.NS", "LIBERTY.NS", "KHADIM.NS",
    # Infrastructure
    "KEC.NS", "KALPATPOWR.NS", "ENGINERSIN.NS", "NBCC.NS", "HCC.NS",
    "PNCINFRA.NS", "SADBHAV.NS", "BRIGADE.NS", "PRESTIGE.NS", "SOBHA.NS",
    # Energy
    "TATAPOWER.NS", "CESC.NS", "TORNTPOWER.NS", "JSPL.NS", "MOIL.NS",
    "RECLTD.NS", "PFC.NS", "IRFC.NS", "HUDCO.NS", "NHPC.NS",
    # Healthcare
    "FORTIS.NS", "NARAYANA.NS", "ASTER.NS", "RAINBOW.NS", "MAXHEALTH.NS",
    "HCG.NS", "SOLARINDS.NS", "GRANULES.NS", "LAURUS.NS", "DIVI.NS",
    # Auto ancillaries
    "MOTHERSON.NS", "BOSCHLTD.NS", "EXIDEIND.NS", "AMARAJABAT.NS", "SUNDRMFAST.NS",
    "SUPRAJIT.NS", "GABRIEL.NS", "SANDHAR.NS", "LUMAX.NS", "ENDURANCE.NS",
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
    ) -> dict[str, Any]:
        """
        Run the complete training pipeline.

        Args:
            symbols: Override stock list (default: Nifty 200)
            progress_callback: async fn(stage, pct, message) for progress

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
            target_symbols = symbols or NIFTY_200_SYMBOLS
            total = len(target_symbols)

            await self._emit(progress_callback, "download", 0,
                             f"Starting pipeline for {total} stocks...")

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

                    # Generate chart
                    _, img_bytes = self.chart_gen.generate_chart(
                        symbol=sym,
                        df=df,
                        window_start=w_start,
                        window_end=w_end,
                        save=True,
                    )

                    # Label with Gemini
                    label = await self.labeler.label_chart(
                        symbol=sym,
                        image_bytes=img_bytes,
                        chart_path="",
                        window_start=w_start,
                        window_end=w_end,
                        df_window=df_window,
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
                return await self.data_fetcher.fetch_ohlcv(
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
