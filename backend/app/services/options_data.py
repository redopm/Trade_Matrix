import pandas as pd
import requests
import io
import asyncio
import statistics
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import pytz

from app.utils.logger import get_logger
from app.services.fyers_data_client import FyersDataClient

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
FYERS_SYM_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

_cached_sym_df: Optional[pd.DataFrame] = None
_last_sym_fetch: Optional[datetime] = None

INDEX_SYMBOL_MAP: Dict[str, Tuple[str, str, float]] = {
    "NIFTY": ("NIFTY", "NSE:NIFTY50-INDEX", 50.0),
    "NIFTY50": ("NIFTY", "NSE:NIFTY50-INDEX", 50.0),
    "BANKNIFTY": ("BANKNIFTY", "NSE:NIFTYBANK-INDEX", 100.0),
    "NIFTYBANK": ("BANKNIFTY", "NSE:NIFTYBANK-INDEX", 100.0),
    "FINNIFTY": ("FINNIFTY", "NSE:FINNIFTY-INDEX", 50.0),
    "MIDCPNIFTY": ("MIDCPNIFTY", "NSE:MIDCPNIFTY-INDEX", 25.0),
}

DEFAULT_LOT_SIZES: Dict[str, int] = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 65,
    "MIDCPNIFTY": 120,
}


def normalize_underlying(symbol: str) -> Tuple[str, str, float]:
    """
    Normalizes any user-supplied underlying (Index or NSE Equity F&O stock) into:
    (fo_master_underlying, fyers_spot_symbol, default_strike_step).
    """
    clean = (
        symbol.upper()
        .strip()
        .replace(".NS", "")
        .replace(".BO", "")
        .replace("NSE:", "")
        .replace("-EQ", "")
        .replace("-INDEX", "")
    )
    if clean in INDEX_SYMBOL_MAP:
        return INDEX_SYMBOL_MAP[clean]
    return (clean, f"NSE:{clean}-EQ", 10.0)


class OptionsDataFetcher:
    def __init__(self):
        self.fyers_client = FyersDataClient()

    async def _ensure_symbol_master(self):
        global _cached_sym_df, _last_sym_fetch
        now = datetime.now(IST)
        if _cached_sym_df is not None and _last_sym_fetch and (now - _last_sym_fetch).days == 0:
            return

        logger.info("Downloading Fyers NSE F&O Symbol Master...")
        try:
            loop = asyncio.get_running_loop()
            # Wrap in a lambda to pass the timeout argument
            resp = await loop.run_in_executor(None, lambda: requests.get(FYERS_SYM_URL, timeout=15))
            if resp.status_code == 200:
                _cached_sym_df = pd.read_csv(io.StringIO(resp.text), header=None, low_memory=False)
                _last_sym_fetch = now
                logger.info(f"Loaded {len(_cached_sym_df)} F&O symbols.")
            else:
                logger.error(f"Failed to fetch Fyers symbols: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching symbol master: {e}")

    @staticmethod
    def extract_lot_size_and_step(chain_df: pd.DataFrame, underlying: str, fallback_step: float = 50.0) -> Tuple[int, float]:
        """Extract exact live NSE lot size (col 3) and strike step from symbol master rows."""
        lot_size = DEFAULT_LOT_SIZES.get(underlying.upper(), 1)
        strike_step = fallback_step
        if chain_df is None or chain_df.empty:
            return lot_size, strike_step

        try:
            raw_lot = chain_df.iloc[0][3]
            parsed_lot = int(float(raw_lot))
            if parsed_lot > 0:
                lot_size = parsed_lot
        except Exception:
            pass

        try:
            unique_strikes = sorted(float(s) for s in chain_df[15].dropna().unique())
            if len(unique_strikes) >= 3:
                # Focus on middle 50% of strikes where spacing is uniform
                mid_start = max(0, len(unique_strikes) // 4)
                mid_end = min(len(unique_strikes), (3 * len(unique_strikes)) // 4 + 1)
                mid_strikes = unique_strikes[mid_start:mid_end] if mid_end - mid_start >= 3 else unique_strikes
                diffs = [round(mid_strikes[i + 1] - mid_strikes[i], 4) for i in range(len(mid_strikes) - 1) if mid_strikes[i + 1] > mid_strikes[i]]
                if diffs:
                    strike_step = float(statistics.median(diffs))
        except Exception:
            pass

        return lot_size, strike_step

    async def get_nearest_expiry_chain_df(self, underlying: str = "NIFTY") -> Optional[pd.DataFrame]:
        global _cached_sym_df
        await self._ensure_symbol_master()
        if _cached_sym_df is None or _cached_sym_df.empty:
            return None

        fo_underlying, _, _ = normalize_underlying(underlying)

        # Filter for CE/PE options of the underlying
        opts = _cached_sym_df[
            (_cached_sym_df[13] == fo_underlying) &
            (_cached_sym_df[16].isin(["CE", "PE"]))
        ]

        if opts.empty:
            logger.warning(f"No options found for {fo_underlying}")
            return None

        opts_sorted = opts.sort_values(by=8)
        now_epoch = datetime.now(IST).timestamp()
        future_opts = opts_sorted[opts_sorted[8] >= now_epoch]

        if future_opts.empty:
            future_opts = opts_sorted

        nearest_expiry_epoch = future_opts.iloc[0][8]
        current_chain = future_opts[future_opts[8] == nearest_expiry_epoch]
        return current_chain

    async def fetch_option_chain_quotes(self, underlying: str = "NIFTY", atm_strike: Optional[int] = None) -> List[Dict]:
        current_chain = await self.get_nearest_expiry_chain_df(underlying)
        if current_chain is None or current_chain.empty:
            return []
            
        if atm_strike:
            # col 15 is the Strike Price
            min_strike = atm_strike * 0.85
            max_strike = atm_strike * 1.15
            current_chain = current_chain[(current_chain[15] >= min_strike) & (current_chain[15] <= max_strike)]
        
        symbols = current_chain[9].tolist()

        if not symbols:
            return []

        logger.info(f"Fetching quotes for {len(symbols)} option symbols for {underlying}...")
        
        all_quotes = []
        chunk_size = 50
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i + chunk_size]
            quotes = self.fyers_client.fetch_quotes(chunk)
            if quotes and "d" in quotes:
                for q in quotes["d"]:
                    if q.get("s") == "ok":
                        all_quotes.append({
                            "symbol": q.get("n"),
                            "ltp": q["v"].get("lp"),
                            "oi": q["v"].get("open_interest", 0),
                            "volume": q["v"].get("volume", 0),
                            "prev_close": q["v"].get("prev_close_price"),
                        })
            await asyncio.sleep(0.1)
            
        return all_quotes
