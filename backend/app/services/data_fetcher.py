"""
DataFetcher Service
Async wrapper around yfinance for fetching NSE stock data.
Implements:
  - Rate limiting (semaphore-based)
  - Retry logic (tenacity)
  - Batch processing with controlled concurrency
  - Nifty 500 symbol list management
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd
import yfinance as yf
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Nifty 500 Symbols (NSE suffix .NS for yfinance) ─────────────────────────
# Top 200 liquid stocks for Phase 1 (expandable)
NIFTY500_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFOSYS.NS", "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "HCLTECH.NS", "BAJFINANCE.NS", "WIPRO.NS",
    "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ADANIENT.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "ULTRACEMCO.NS", "ASIANPAINT.NS", "BAJAJFINSV.NS",
    "JSWSTEEL.NS", "TATAMOTORS.NS", "M&M.NS", "TATASTEEL.NS", "COALINDIA.NS",
    "DRREDDY.NS", "NESTLEIND.NS", "HDFCLIFE.NS", "CIPLA.NS", "BPCL.NS",
    "SBILIFE.NS", "TATACONSUM.NS", "BRITANNIA.NS", "GRASIM.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "DIVISLAB.NS", "BAJAJ-AUTO.NS", "APOLLOHOSP.NS", "TECHM.NS",
    "INDUSINDBK.NS", "HINDALCO.NS", "VEDL.NS", "SIEMENS.NS", "PIDILITIND.NS",
    "HAVELLS.NS", "MCDOWELL-N.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS",
    "BERGEPAINT.NS", "COLPAL.NS", "TATAPOWER.NS", "ADANIPORTS.NS", "HDFCAMC.NS",
    "MUTHOOTFIN.NS", "CHOLAFIN.NS", "ICICIGI.NS", "VOLTAS.NS", "BIOCON.NS",
    "TORNTPHARM.NS", "ALKEM.NS", "LUPIN.NS", "AUROPHARMA.NS", "GLENMARK.NS",
    "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS",
    "FEDERALBNK.NS", "BANDHANBNK.NS", "AUBANK.NS", "RBLBANK.NS", "YESBANK.NS",
    "LICI.NS", "NMDC.NS", "SAIL.NS", "HINDPETRO.NS", "IOC.NS",
    "CONCOR.NS", "IRCTC.NS", "HAL.NS", "BEL.NS", "BHEL.NS",
    "ABB.NS", "CUMMINSIND.NS", "THERMAX.NS", "SCHAEFFLER.NS", "SKFINDIA.NS",
    "PAGEIND.NS", "MFSL.NS", "SUNDARMFIN.NS", "M&MFIN.NS", "SHRIRAMFIN.NS",
    "BAJAJHLDNG.NS", "SWARAJENG.NS", "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS",
    "CEATLTD.NS", "JKCEMENT.NS", "AMBUJACEMENT.NS", "RAMCOCEM.NS", "SHREECEM.NS",
    "OBEROIRLTY.NS", "DLF.NS", "GODREJPROP.NS", "PRESTIGE.NS", "PHOENIXLTD.NS",
    "ASTRAL.NS", "SUPREMEIND.NS", "FINOLEX.NS", "AARTIIND.NS", "DEEPAKNTR.NS",
    "PIIND.NS", "RALLIS.NS", "BALAMINES.NS", "NAVINFLUOR.NS", "SRF.NS",
    "TATACHEM.NS", "VINDHYATEL.NS", "OFSS.NS", "PERSISTENT.NS", "COFORGE.NS",
    "LTIM.NS", "KPITTECH.NS", "ZENSARTECH.NS", "MPHASIS.NS", "HEXAWARE.NS",
    "TATAELXSI.NS", "INFY.NS", "INFOEDGE.NS", "ZOMATO.NS", "PAYTM.NS",
    "NYKAA.NS", "CARTRADE.NS", "POLICYBZR.NS", "DELHIVERY.NS", "MAPMYINDIA.NS",
    "DIXON.NS", "AMBER.NS", "KAYNES.NS", "SYRMA.NS", "PGEL.NS",
    "BLUESTARCO.NS", "WHIRLPOOL.NS", "CROMPTON.NS", "ORIENTELEC.NS", "BAJAJCON.NS",
    "EMAMILTD.NS", "JYOTHYLAB.NS", "VBL.NS", "GODFRYPHLP.NS", "VST.NS",
    "RADICO.NS", "UBL.NS", "DEVYANI.NS", "WESTLIFE.NS", "JUBLFOOD.NS",
    "EASEMYTRIP.NS", "INDIGO.NS", "SPICEJET.NS", "INTERGLOBE.NS", "MAHINDRA.NS",
    "GMRINFRA.NS", "ADANIGREEN.NS", "ADANITRANS.NS", "ADANIPOWER.NS", "TORNTPOWER.NS",
    "CESC.NS", "JSPL.NS", "HINDZINC.NS", "NATIONALUM.NS", "MOIL.NS",
    "PERSISTENT.NS", "MPHASIS.NS", "WIPRO.NS", "NIITTECH.NS", "KFINTECH.NS",
    "CDSL.NS", "BSE.NS", "MCX.NS", "ANGELONE.NS", "IIFL.NS",
    "MOTILALOFS.NS", "ICICIPRULI.NS", "MAXHEALTH.NS", "NH.NS", "MEDANTA.NS",
    "FORTIS.NS", "THYROCARE.NS", "METROPOLIS.NS", "KRSNAA.NS", "VIJAYA.NS",
    "PGHH.NS", "GILLETTE.NS", "3MINDIA.NS", "HONAUT.NS", "GRINDWELL.NS",
    "RELAXO.NS", "BATA.NS", "VMART.NS", "SHOPERSTOP.NS", "TRENT.NS",
    "APLAPOLLO.NS", "JINDALSAW.NS", "WELCORP.NS", "RATNAMANI.NS", "MAHARASTTRA.NS",
    "IPCALAB.NS", "SANOFI.NS", "PFIZER.NS", "ABBOTINDIA.NS", "GLAXO.NS",
    "ERIS.NS", "NATCOPHARM.NS", "GRANULES.NS", "STRIDES.NS", "SOLARA.NS",
]


class DataFetcher:
    """
    Async data fetcher for NSE stocks using yfinance.
    
    Features:
    - Semaphore-based rate limiting (MAX_CONCURRENT_FETCHES)
    - Exponential backoff retry on failures
    - Batch processing with progress tracking
    - Symbol validation and normalization
    """

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_FETCHES)
        self._loop = None

    @staticmethod
    def get_nifty500_symbols() -> list[str]:
        """Return the list of Nifty 500 symbols (yfinance format)."""
        return NIFTY500_SYMBOLS.copy()

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Ensure symbol has .NS suffix for NSE stocks."""
        symbol = symbol.upper().strip()
        if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
            symbol += ".NS"
        return symbol

    async def fetch_ticker_info(self, symbol: str) -> Optional[dict[str, Any]]:
        """
        Fetch fundamental info for a single ticker.
        Returns None on failure.
        """
        async with self._semaphore:
            await asyncio.sleep(settings.FETCH_DELAY_SECONDS)
            try:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_info_sync, symbol
                )
                return info
            except Exception as e:
                logger.warning(f"Failed to fetch info for {symbol}: {e}")
                return None

    @staticmethod
    def _fetch_info_sync(symbol: str) -> Optional[dict[str, Any]]:
        """Synchronous yfinance info fetch (runs in thread pool)."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or info.get("regularMarketPrice") is None:
                # Try fast_info as fallback
                fast = ticker.fast_info
                if fast:
                    info["regularMarketPrice"] = fast.get("last_price")
            return info
        except Exception as e:
            logger.debug(f"_fetch_info_sync error for {symbol}: {e}")
            return None

    async def fetch_price_history(
        self,
        symbol: str,
        period: str = None,
        interval: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV price history for technical analysis.
        Returns DataFrame with columns: Open, High, Low, Close, Volume
        """
        period = period or settings.DATA_PERIOD
        interval = interval or settings.DATA_INTERVAL

        async with self._semaphore:
            await asyncio.sleep(settings.FETCH_DELAY_SECONDS)
            try:
                df = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_history_sync, symbol, period, interval
                )
                return df
            except Exception as e:
                logger.warning(f"Failed to fetch history for {symbol}: {e}")
                return None

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
    def _fetch_history_sync(
        symbol: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        """Synchronous yfinance history fetch with retry."""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return None
        # Standardize column names
        df.columns = [c.title() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df[["Open", "High", "Low", "Close", "Volume"]]

    async def fetch_batch_info(
        self,
        symbols: list[str],
        progress_callback=None,
    ) -> dict[str, Optional[dict[str, Any]]]:
        """
        Fetch fundamental info for multiple symbols concurrently.
        
        Args:
            symbols: List of ticker symbols
            progress_callback: Optional async callable(symbol, result, index, total)
        
        Returns:
            Dict mapping symbol → info dict (or None on failure)
        """
        results: dict[str, Optional[dict]] = {}
        total = len(symbols)

        async def fetch_one(sym: str, idx: int) -> tuple[str, Optional[dict]]:
            info = await self.fetch_ticker_info(sym)
            if progress_callback:
                await progress_callback(sym, info, idx, total)
            return sym, info

        tasks = [fetch_one(sym, i) for i, sym in enumerate(symbols)]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Batch fetch error: {result}")
                continue
            sym, info = result
            results[sym] = info

        logger.info(
            f"Batch fetch complete: {sum(1 for v in results.values() if v)}/{total} succeeded"
        )
        return results

    async def fetch_batch_history(
        self,
        symbols: list[str],
        period: str = None,
    ) -> dict[str, Optional[pd.DataFrame]]:
        """Fetch price history for multiple symbols concurrently."""
        period = period or settings.DATA_PERIOD
        results: dict[str, Optional[pd.DataFrame]] = {}

        async def fetch_one(sym: str) -> tuple[str, Optional[pd.DataFrame]]:
            df = await self.fetch_price_history(sym, period=period)
            return sym, df

        tasks = [fetch_one(sym) for sym in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Batch history error: {result}")
                continue
            sym, df = result
            results[sym] = df

        logger.info(
            f"History batch complete: {sum(1 for v in results.values() if v is not None)}/{len(symbols)}"
        )
        return results

    async def fetch_current_price(self, symbol: str) -> Optional[float]:
        """Fetch the latest market price for a symbol."""
        async with self._semaphore:
            try:
                price = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_price_sync, symbol
                )
                return price
            except Exception as e:
                logger.warning(f"Failed to fetch price for {symbol}: {e}")
                return None

    @staticmethod
    def _fetch_price_sync(symbol: str) -> Optional[float]:
        try:
            ticker = yf.Ticker(symbol)
            fast = ticker.fast_info
            return float(fast.get("last_price", 0)) or None
        except Exception:
            return None

    async def get_earnings_dates(self, symbol: str) -> list[datetime]:
        """
        Fetch upcoming/recent earnings dates for Event Risk Filter.
        Returns list of datetime objects.
        """
        async with self._semaphore:
            try:
                dates = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_earnings_dates_sync, symbol
                )
                return dates
            except Exception as e:
                logger.debug(f"Could not fetch earnings dates for {symbol}: {e}")
                return []

    @staticmethod
    def _fetch_earnings_dates_sync(symbol: str) -> list[datetime]:
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if cal is None or cal.empty:
                return []
            dates = []
            for col in ["Earnings Date", "Ex-Dividend Date"]:
                if col in cal.columns:
                    for val in cal[col].dropna():
                        if hasattr(val, "to_pydatetime"):
                            dates.append(val.to_pydatetime())
                        elif isinstance(val, datetime):
                            dates.append(val)
            return dates
        except Exception:
            return []
