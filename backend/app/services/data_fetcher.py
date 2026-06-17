"""
DataFetcher Service
Async wrapper for fetching NSE stock data.
  - Primary source: Fyers API (when authenticated)
  - Fallback: yfinance
  - Last resort: jugaad-data

Implements:
  - Rate limiting (semaphore-based)
  - Retry logic (tenacity)
  - Batch processing with controlled concurrency
  - Nifty 500 symbol list management
"""
import asyncio
import json
from datetime import datetime, timedelta, date as dt_date
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


# Lazy singleton for Fyers client — avoids import errors if fyers not installed
_fyers_client = None

def _get_fyers_client():
    global _fyers_client
    if _fyers_client is None:
        try:
            from app.services.fyers_data_client import FyersDataClient
            _fyers_client = FyersDataClient()
        except Exception:
            _fyers_client = None  # fyers-apiv3 not installed or import error
    return _fyers_client


# ── NSE Universe  ─────────────────────────────────────────────────────────────
# Comprehensive NSE universe: Nifty 500 + key mid/small-cap additions
# Organised by SEBI sector classification with .NS suffix for yfinance
# Source: NSE Nifty 500 index constituents (June 2024) + curated additions
# ~520 unique symbols → after dedup this becomes NIFTY500_SYMBOLS
SECTOR_UNIVERSE: dict[str, list[str]] = {

    # ── 1. Financial Services (~110) ─────────────────────────────────────────
    "Financial Services": [
        # Large private banks
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS",
        "IDFCFIRSTB.NS", "FEDERALBNK.NS", "BANDHANBNK.NS", "AUBANK.NS", "RBLBANK.NS",
        "YESBANK.NS", "IDBI.NS",
        # PSU banks
        "SBIN.NS", "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS",
        "IOB.NS", "INDIANB.NS", "CENTRALBK.NS", "BANKINDIA.NS", "MAHABANK.NS",
        "UCOBANK.NS", "KTKBANK.NS", "CSBBANK.NS", "DCBBANK.NS",
        # Small finance banks
        "EQUITASBNK.NS", "SURYODAY.NS", "UJJIVANSFB.NS", "UTKARSHBNK.NS", "ESAFSFB.NS",
        # Insurance
        "LICI.NS", "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "ICICIGI.NS",
        "STARHEALTH.NS", "NIACL.NS", "GODIGIT.NS", "MAXHEALTH.NS", "MFSL.NS",
        # Asset managers / Exchanges
        "HDFCAMC.NS", "CDSL.NS", "BSE.NS", "MCX.NS", "ANGELONE.NS",
        "MOTILALOFS.NS", "KFINTECH.NS", "360ONE.NS", "CAMS.NS", "IIFL.NS",
        "ISEC.NS", "GEOJITFSL.NS",
        # NBFCs
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "MUTHOOTFIN.NS", "CHOLAFIN.NS",
        "SHRIRAMFIN.NS", "M&MFIN.NS", "MANAPPURAM.NS", "SUNDARMFIN.NS",
        "BAJAJHLDNG.NS", "LICHSGFIN.NS", "PNBHOUSING.NS",
        "AAVAS.NS", "HOMEFIRSTFIN.NS", "CANFINHOME.NS",
        "APTUS.NS", "CREDITACC.NS", "SPANDANA.NS", "SATIN.NS", "UJJIVANSF.NS",
        "MAS.NS", "PAISALO.NS", "INDIGRID.NS",
    ],

    # ── 2. Information Technology (~60) ──────────────────────────────────────
    "Information Technology": [
        # IT Services — Large
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        "LTIM.NS", "MPHASIS.NS", "PERSISTENT.NS", "COFORGE.NS", "TATAELXSI.NS",
        # IT Services — Mid
        "OFSS.NS", "KPITTECH.NS", "CYIENT.NS", "BIRLASOFT.NS", "ZENSARTECH.NS",
        "HEXAWARE.NS", "RATEGAIN.NS", "INTELLECT.NS", "MASTEK.NS", "SONATSOFTW.NS",
        "NEWGEN.NS", "NUCLEUS.NS", "ROUTE.NS", "LTTS.NS", "HAPPSTMNDS.NS",
        "DATAMATICS.NS", "XCHANGING.NS", "SUBEX.NS", "KSOLVES.NS",
        # Internet & Digital
        "INFOEDGE.NS", "ZOMATO.NS", "NYKAA.NS", "POLICYBZR.NS",
        "DELHIVERY.NS", "MAPMYINDIA.NS", "INDIAMART.NS", "JUSTDIAL.NS",
        "AFFLE.NS", "LATENTVIEW.NS", "TANLA.NS", "CARTRADE.NS",
        "PAYTM.NS", "EASEMYTRIP.NS",
    ],

    # ── 3. Oil Gas & Consumable Fuels (~16) ──────────────────────────────────
    "Oil Gas & Consumable Fuels": [
        "RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS", "HPCL.NS",
        "HINDPETRO.NS", "GAIL.NS", "PETRONET.NS", "IGL.NS", "MGL.NS",
        "GSPL.NS", "ATGL.NS", "GNFC.NS", "MRPL.NS",
        "AEGASIND.NS", "GUJGASLTD.NS",
    ],

    # ── 4. Fast Moving Consumer Goods (~35) ──────────────────────────────────
    "Fast Moving Consumer Goods": [
        # Large cap
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS",
        "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "EMAMILTD.NS", "TATACONSUM.NS",
        # Mid cap
        "BAJAJCON.NS", "JYOTHYLAB.NS", "VBL.NS", "GODFRYPHLP.NS", "VST.NS",
        "RADICO.NS", "UBL.NS", "MCDOWELL-N.NS", "PGHH.NS", "GILLETTE.NS",
        "ADANIWILMAR.NS", "KRBL.NS", "HATSUN.NS", "BIKAJI.NS", "DOMS.NS",
        # Small cap / niche
        "PATANJALI.NS", "VARUN.NS", "TASTYBIT.NS", "AVONMORE.NS",
        "ZYDUSWELL.NS", "DODLA.NS", "ANANDRATHI.NS",
    ],

    # ── 5. Automobile & Auto Components (~45) ────────────────────────────────
    "Automobile & Auto Components": [
        # OEMs
        "MARUTI.NS", "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
        "EICHERMOT.NS", "TVSMOTORS.NS", "ASHOKLEY.NS", "ESCORTS.NS", "FORCEMOT.NS",
        "OLECTRA.NS",
        # Tyres
        "BALKRISIND.NS", "APOLLOTYRE.NS", "MRF.NS", "CEATLTD.NS",
        # Ancillaries — Large
        "BOSCHLTD.NS", "MOTHERSON.NS", "BHARATFORG.NS", "ENDURANCE.NS",
        "SUNDRMFAST.NS", "GABRIEL.NS", "SUPRAJIT.NS", "TIINDIA.NS",
        "SUBROS.NS", "UCALFUEL.NS", "MINDAIND.NS", "SWARAJENG.NS",
        # Batteries & EV
        "EXIDEIND.NS", "AMARAJABAT.NS", "HBLPOWER.NS",
        # Ancillaries — Mid
        "CRAFTSMAN.NS", "LUMAXIND.NS", "JAMNA.NS", "MINDA.NS",
        "MAHSCOOTER.NS", "STATIC.NS", "SHFL.NS", "JTEKTINDIA.NS",
        "FIEM.NS", "UNOMINDA.NS", "PRICOLLTD.NS", "ASAHI.NS",
    ],

    # ── 6. Healthcare (~60) ──────────────────────────────────────────────────
    "Healthcare": [
        # Pharma — Large
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS",
        "BIOCON.NS", "AUROPHARMA.NS", "TORNTPHARM.NS", "ALKEM.NS",
        # Pharma — Mid
        "GLENMARK.NS", "IPCALAB.NS", "PFIZER.NS", "ABBOTINDIA.NS", "GLAXO.NS",
        "ERIS.NS", "NATCOPHARM.NS", "GRANULES.NS", "STRIDES.NS",
        "GLAND.NS", "LAURUSLABS.NS", "CAPLIPOINT.NS", "AJANTPHARM.NS",
        "JBCHEPHARM.NS", "SUVEN.NS", "NEULANDLAB.NS",
        # Pharma — Small
        "SYNGENE.NS", "WOCKHARDT.NS", "SEQUENT.NS", "WINDLAS.NS",
        "VIMTA.NS", "PANACEA.NS", "OPTIEMUS.NS", "SOLARA.NS",
        "LAURUS.NS", "SMRUTHI.NS", "IOLCP.NS", "ANURAS.NS",
        # Hospitals & Diagnostics
        "APOLLOHOSP.NS", "FORTIS.NS", "NH.NS", "MAXHEALTH.NS",
        "ASTERDM.NS", "RAINBOW.NS", "MEDANTA.NS", "SHALBY.NS",
        # Diagnostics
        "LALPATHLAB.NS", "METROPOLIS.NS", "THYROCARE.NS",
        "KRSNAA.NS", "VIJAYALAB.NS", "SAPPHIREFDS.NS",
    ],

    # ── 7. Capital Goods (~55) ───────────────────────────────────────────────
    "Capital Goods": [
        # Engineering — Large
        "LT.NS", "SIEMENS.NS", "ABB.NS", "CUMMINSIND.NS", "THERMAX.NS",
        "HONAUT.NS", "GRINDWELL.NS", "SKFINDIA.NS", "SCHAEFFLER.NS", "AIAENG.NS",
        # Engineering — Mid
        "ELGIEQUIP.NS", "KAYNES.NS", "AMBER.NS", "DIXON.NS", "BLUESTARCO.NS",
        "KSB.NS", "KIRLOSENG.NS", "BHEL.NS", "BEML.NS",
        "GMMPFAUDLR.NS", "NBLGIL.NS", "ISGEC.NS", "ESABINDIA.NS",
        "TITAGARH.NS", "TEXRAIL.NS",
        # Electrical & Electronics
        "HAVELLS.NS", "POLYCAB.NS", "KEI.NS", "VGUARD.NS", "CROMPTON.NS",
        "ORIENTELEC.NS", "WHIRLPOOL.NS", "VOLTAS.NS", "BAJAJELECTR.NS",
        "FINOLEX.NS", "APCOTEX.NS",
        # Defence
        "HAL.NS", "BEL.NS", "COCHINSHIP.NS", "GRSE.NS",
        "DATAPATTERNSIND.NS", "MAZDOCK.NS", "PARAS.NS", "MTAR.NS",
        # Renewable Equipment
        "SUZLON.NS", "KALPATARPOWER.NS", "INOXWIND.NS",
    ],

    # ── 8. Construction & Real Estate (~40) ──────────────────────────────────
    "Construction & Real Estate": [
        # Infrastructure EPC
        "RVNL.NS", "IRCON.NS", "NBCC.NS", "NCC.NS", "PNCINFRA.NS",
        "KNRCON.NS", "ASHOKA.NS", "GMRINFRA.NS",
        "HGINFRA.NS", "JKIL.NS", "AHLUCONT.NS", "GPPL.NS",
        "IRFC.NS", "PFC.NS", "REC.NS",
        # Real Estate
        "DLF.NS", "GODREJPROP.NS", "PRESTIGE.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS",
        "SOBHA.NS", "BRIGADE.NS", "MAHLIFE.NS", "SUNTECK.NS", "KOLTEPATIL.NS",
        "ANANTRAJ.NS", "KEYSTONE.NS", "SIGNATURE.NS", "INDIABULLS.NS",
        "LODHA.NS", "RUSTOMJEE.NS",
    ],

    # ── 9. Metals & Mining (~30) ─────────────────────────────────────────────
    "Metals & Mining": [
        # Steel
        "JSWSTEEL.NS", "TATASTEEL.NS", "JSPL.NS", "SAIL.NS",
        "APLAPOLLO.NS", "JINDALSAW.NS", "WELCORP.NS", "RATNAMANI.NS",
        "STEELHCL.NS", "NMDC.NS",
        # Aluminium & Non-ferrous
        "HINDALCO.NS", "NATIONALUM.NS", "VEDL.NS", "HINDZINC.NS",
        "HINDCOPPER.NS", "GRAVITA.NS", "PONDY.NS",
        # Mining
        "MOIL.NS", "COALINDIA.NS", "GMDC.NS",
        # Ferro-alloys & misc metals
        "MIDHANI.NS", "HINDMOTORS.NS", "SUNCLAYLTD.NS",
        "SHYAMSTL.NS", "SAREGAMA.NS",
    ],

    # ── 10. Power (~18) ──────────────────────────────────────────────────────
    "Power": [
        "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS", "ADANITRANS.NS", "ADANIPOWER.NS",
        "TATAPOWER.NS", "TORNTPOWER.NS", "CESC.NS", "NHPC.NS", "SJVN.NS",
        "JSWENERGY.NS", "INOXWIND.NS", "SUZLON.NS",
        "RATTANINDIA.NS", "ACME.NS", "GENSOL.NS", "AVAADA.NS",
        "GIPCL.NS",
    ],

    # ── 11. Chemicals (~40) ──────────────────────────────────────────────────
    "Chemicals": [
        # Specialty Chemicals
        "PIDILITIND.NS", "SRF.NS", "DEEPAKNTR.NS", "NAVINFLUOR.NS", "PIIND.NS",
        "AARTIIND.NS", "TATACHEM.NS", "BALAMINES.NS", "FINEORG.NS", "NOCIL.NS",
        "ROSSARI.NS", "VINATIORGA.NS", "CLEAN.NS", "ALKYLAMINE.NS",
        "NEOGEN.NS", "PCBL.NS", "AARTIPHARM.NS", "ATUL.NS",
        "DHARAMDAS.NS", "CAMLIN.NS",
        # Agrochemicals
        "UPL.NS", "RALLIS.NS", "BAYERCROP.NS", "SUMICHEM.NS", "DHANUKA.NS",
        "COROMANDEL.NS", "ASTEC.NS", "HERANBA.NS",
        # Paints
        "ASIANPAINT.NS", "BERGEPAINT.NS", "KANSAINER.NS", "AKZONOBEL.NS",
        "INDIGO.NS",
        # Polymers / Plastics
        "ASTRAL.NS", "SUPREMEIND.NS", "GHCL.NS", "TPCL.NS",
    ],

    # ── 12. Consumer Discretionary (~30) ─────────────────────────────────────
    "Consumer Discretionary": [
        # QSR & Hospitality
        "DEVYANI.NS", "WESTLIFE.NS", "JUBLFOOD.NS", "SAPPHIREFDS.NS",
        "BARBEQUE.NS", "SPECIALITY.NS",
        # Retail
        "TRENT.NS", "SHOPERSTOP.NS", "VMART.NS", "BATA.NS", "RELAXO.NS",
        "EASEMYTRIP.NS", "ZOMATO.NS",
        # Lifestyle & Fashion
        "TITAN.NS", "PAGEIND.NS", "RAYMOND.NS", "VEDANT.NS",
        "ABFRL.NS", "TCNS.NS", "KALYANKJIL.NS",
        # Entertainment
        "PVRINOX.NS", "WONDERLA.NS", "CHALET.NS", "LEMONTREE.NS",
        # Jewellery
        "SENCO.NS", "THANGAMAYIL.NS",
    ],

    # ── 13. Cement & Construction Materials (~15) ─────────────────────────────
    "Cement & Construction Materials": [
        "ULTRACEMCO.NS", "SHREECEM.NS", "AMBUJACEMENT.NS", "RAMCOCEM.NS",
        "DALMIACEM.NS", "JKCEMENT.NS", "JKLAKSHMI.NS", "BIRLACORPN.NS",
        "NCLIND.NS", "HEIDELBERG.NS", "DECCAN.NS", "PRSMJOHNS.NS",
        "SANGHI.NS", "SAGCEM.NS",
    ],

    # ── 14. Telecommunication (~12) ──────────────────────────────────────────
    "Telecommunication": [
        "BHARTIARTL.NS", "IDEA.NS", "TATACOMM.NS", "HFCL.NS", "STLTECH.NS",
        "INDUS.NS", "TEJAS.NS", "RAILTEL.NS",
        "GTLINFRA.NS", "ONMOBILE.NS", "TANLA.NS",
    ],

    # ── 15. Media & Entertainment (~10) ──────────────────────────────────────
    "Media & Entertainment": [
        "ZEEL.NS", "SUNTV.NS", "PVRINOX.NS", "DBCORP.NS",
        "TV18BRDCST.NS", "NETWORK18.NS", "JAGRAN.NS",
        "NDTV.NS", "SAREGAMA.NS",
    ],

    # ── 16. Agriculture, Food & Agri Inputs (~18) ────────────────────────────
    "Agriculture & Food Processing": [
        # Agri inputs
        "COROMANDEL.NS", "BALRAMCHIN.NS", "TRIVENI.NS", "EIDPARRY.NS",
        "DHANUKA.NS",
        # Food processing
        "KRBL.NS", "AVANTIFEED.NS", "WATERBASE.NS",
        "DAAWAT.NS", "SATIA.NS", "GODREJAGRO.NS",
        # Ports & Commodities
        "ADANIPORTS.NS", "CONCOR.NS", "ADANIENT.NS",
        "NATESTEELS.NS",
    ],

    # ── 17. Textiles & Apparel (~20) ─────────────────────────────────────────
    "Textiles & Apparel": [
        "RAYMOND.NS", "ARVIND.NS", "VARDHMAN.NS", "TRIDENT.NS",
        "WELSPUNLIV.NS", "KITEX.NS", "SPANDEXP.NS",
        "RUPA.NS", "MAFATLAL.NS", "GOKEX.NS", "NITIN.NS",
        "KTIL.NS", "WINSOME.NS", "PRECOT.NS",
        "AMBATTUR.NS", "SUTLEJTEX.NS",
    ],

    # ── 18. Transportation & Logistics (~15) ─────────────────────────────────
    "Transportation & Logistics": [
        "IRCTC.NS", "INTERGLOBE.NS", "SPICEJET.NS", "DELHIVERY.NS",
        "VRL.NS", "BLUEDART.NS", "GATEWAY.NS", "CONCOR.NS",
        "GESHIP.NS", "MAHLOG.NS", "TCI.NS",
        "ALLCARGO.NS", "XPRO.NS", "AEGISLOG.NS",
    ],

    # ── 19. Diversified Conglomerates (~8) ────────────────────────────────────
    "Diversified": [
        "GRASIM.NS", "3MINDIA.NS",
        "WELSPUN.NS", "BAJAJHLDNG.NS",
    ],
}

# ── Flat list — deduplicated, preserving sector order ─────────────────────────
_all_symbols: list[str] = []
_seen: set[str] = set()
for _sector_stocks in SECTOR_UNIVERSE.values():
    for _sym in _sector_stocks:
        if _sym not in _seen:
            _seen.add(_sym)
            _all_symbols.append(_sym)

NIFTY500_SYMBOLS: list[str] = _all_symbols

# Sector count summary (for logging/API)
SECTOR_COUNTS: dict[str, int] = {s: len(v) for s, v in SECTOR_UNIVERSE.items()}

logger.info(f"NSE Universe loaded: {len(NIFTY500_SYMBOLS)} unique symbols across {len(SECTOR_UNIVERSE)} sectors")




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
        """Return the full NSE universe (yfinance format), ~500 stocks."""
        return NIFTY500_SYMBOLS.copy()

    @staticmethod
    def get_sector_universe() -> dict[str, list[str]]:
        """Return full sector-wise stock dictionary."""
        return SECTOR_UNIVERSE.copy()

    @staticmethod
    def get_sector_counts() -> dict[str, int]:
        """Return stock count per sector."""
        return SECTOR_COUNTS.copy()

    @staticmethod
    def get_symbols_for_sector(sector: str) -> list[str]:
        """Return symbols for a specific sector."""
        return SECTOR_UNIVERSE.get(sector, []).copy()

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
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
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
            raise e

    async def fetch_price_history(
        self,
        symbol: str,
        period: str = None,
        interval: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV price history.
        Priority: Fyers API (if connected today) > yfinance > jugaad-data.
        """
        period = period or settings.DATA_PERIOD
        interval = interval or settings.DATA_INTERVAL

        # ── Try Fyers first (official NSE data) ─────────────────────────
        if interval in (None, "1d", "1D", "D"):  # Fyers daily data
            fyers = _get_fyers_client()
            if fyers is not None:
                try:
                    # Map period string to date range
                    days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365,
                                "2y": 730, "3y": 1095, "5y": 1825}
                    days = days_map.get(period, 730)
                    range_from = (dt_date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, fyers.get_historical_data, symbol, "D", range_from, None
                    )
                    if df is not None and not df.empty:
                        df = df[["Open", "High", "Low", "Close", "Volume"]]
                        logger.debug(f"Fyers data fetched for {symbol}: {len(df)} rows")
                        return df
                except Exception as e:
                    logger.debug(f"Fyers failed for {symbol}: {e}. Falling back to yfinance.")

        # ── Fallback: yfinance ─────────────────────────────────────────
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
        """Synchronous yfinance history fetch.
        
        Uses yf.download() instead of ticker.history() to correctly handle
        timezone-aware data in yfinance 1.4.x (fixes 'no timezone found' error).
        """
        from datetime import date, timedelta as td
        
        # Convert period string to explicit date range
        period_days = {
            "1mo": 30, "3mo": 90, "6mo": 180,
            "1y": 365, "2y": 730, "3y": 1095, "5y": 1825
        }
        days = period_days.get(period, 730)
        end_dt = date.today()
        start_dt = end_dt - td(days=days)
        
        try:
            # yf.download() handles timezone correctly in yfinance 1.4.x
            df = yf.download(
                tickers=symbol,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                # yf.download returns MultiIndex columns for single ticker, flatten
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [c.title() for c in df.columns]
                df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
                df = df.sort_index()
                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    if col not in df.columns:
                        return None
                return df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            logger.debug(f"yfinance failed for {symbol}: {e}")
        
        return None

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
        # ── Try Fyers first ──────────────────────────────────────────────
        fyers = _get_fyers_client()
        if fyers is not None:
            try:
                if symbol.endswith(".NS"):
                    fyers_sym = f"NSE:{symbol.replace('.NS', '')}-EQ"
                elif symbol.endswith(".BO"):
                    fyers_sym = f"BSE:{symbol.replace('.BO', '')}-EQ"
                else:
                    fyers_sym = symbol
                    
                quotes = await asyncio.get_event_loop().run_in_executor(
                    None, fyers.fetch_quotes, [fyers_sym]
                )
                if quotes and quotes.get("s") == "ok" and quotes.get("d"):
                    data = quotes["d"][0].get("v", {})
                    if "lp" in data:
                        return float(data["lp"])
            except Exception as e:
                logger.debug(f"Fyers failed to fetch current price for {symbol}: {e}. Falling back to yfinance.")

        # ── Fallback: yfinance ─────────────────────────────────────────
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
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
    def _fetch_price_sync(symbol: str) -> Optional[float]:
        try:
            ticker = yf.Ticker(symbol)
            # Primary: fast_info last_price (real-time, low latency)
            try:
                lp = ticker.fast_info.get("last_price")
                if lp and float(lp) > 0:
                    return float(lp)
            except Exception:
                pass
            # Fallback: latest close from 5d history (split-adjusted, always reliable)
            hist = ticker.history(period="5d", interval="1d", auto_adjust=True)
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return None
        except Exception as e:
            raise e


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
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
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
        except Exception as e:
            raise e
