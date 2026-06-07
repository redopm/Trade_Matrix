import pandas as pd
import requests
import io
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
import pytz

from app.utils.logger import get_logger
from app.services.fyers_data_client import FyersDataClient

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
FYERS_SYM_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

class OptionsDataFetcher:
    def __init__(self):
        self.fyers_client = FyersDataClient()
        self.sym_df: Optional[pd.DataFrame] = None
        self.last_sym_fetch: Optional[datetime] = None

    async def _ensure_symbol_master(self):
        now = datetime.now(IST)
        if self.sym_df is not None and self.last_sym_fetch and (now - self.last_sym_fetch).days == 0:
            return

        logger.info("Downloading Fyers NSE F&O Symbol Master...")
        try:
            loop = asyncio.get_running_loop()
            # Wrap in a lambda to pass the timeout argument
            resp = await loop.run_in_executor(None, lambda: requests.get(FYERS_SYM_URL, timeout=10))
            if resp.status_code == 200:
                self.sym_df = pd.read_csv(io.StringIO(resp.text), header=None, low_memory=False)
                self.last_sym_fetch = now
                logger.info(f"Loaded {len(self.sym_df)} F&O symbols.")
            else:
                logger.error(f"Failed to fetch Fyers symbols: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching symbol master: {e}")

    async def get_nearest_expiry_chain_df(self, underlying: str = "NIFTY") -> Optional[pd.DataFrame]:
        await self._ensure_symbol_master()
        if self.sym_df is None or self.sym_df.empty:
            return None

        # Filter for CE/PE options of the underlying
        opts = self.sym_df[
            (self.sym_df[13] == underlying) & 
            (self.sym_df[16].isin(["CE", "PE"]))
        ]
        
        if opts.empty:
            logger.warning(f"No options found for {underlying}")
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
