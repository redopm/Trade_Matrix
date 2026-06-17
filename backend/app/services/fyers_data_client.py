"""
Fyers API Data Client
Handles authentication and high-quality historical data fetching.
"""
import os
import time
import urllib.parse
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
from fyers_apiv3 import fyersModel

from app.config import settings, BASE_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

class FyersDataClient:
    def __init__(self):
        self.client_id = settings.FYERS_CLIENT_ID
        self.app_id = settings.FYERS_APP_ID
        self.secret_key = settings.FYERS_SECRET_ID
        self.redirect_uri = settings.FYERS_REDIRECT_URI
        
        self.token_file = Path(BASE_DIR) / "backend" / "models" / "fyers_token.txt"
        self.fyers: Optional[fyersModel.FyersModel] = None
        
    def get_auth_url(self) -> str:
        """Returns the Fyers login URL for the frontend."""
        session = fyersModel.SessionModel(
            client_id=self.app_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        return session.generate_authcode()
        
    def set_auth_code(self, auth_code: str) -> bool:
        """Called by the frontend API when user submits the auth code."""
        try:
            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(auth_code)
            response = session.generate_token()
            
            if response.get("s") != "ok":
                logger.error(f"Failed to generate final token: {response}")
                return False
                
            final_token = response["access_token"]
            
            # Save to file
            with open(self.token_file, "w") as f:
                f.write(final_token)
                
            return True
        except Exception as e:
            logger.error(f"Error setting auth code: {e}")
            return False

    def connect(self) -> bool:
        """Connect to Fyers API. Re-use token if valid for the day."""
        access_token = None
        
        if self.token_file.exists():
            modified_time = datetime.fromtimestamp(self.token_file.stat().st_mtime)
            if modified_time.date() == date.today():
                with open(self.token_file, "r") as f:
                    access_token = f.read().strip()
                    
        if not access_token:
            logger.error("No valid Fyers token found. Please authenticate via the UI Settings page.")
            return False
                
        self.fyers = fyersModel.FyersModel(
            client_id=self.app_id,
            is_async=False,
            token=access_token,
            log_path=str(Path(BASE_DIR) / "backend" / "logs")
        )
        
        # Verify connection by getting profile
        profile = self.fyers.get_profile()
        if profile.get('s') == 'error':
            logger.warning("Token expired or invalid, please re-authenticate via UI.")
            return False
                
        logger.info(f"Fyers connected successfully for {self.client_id}")
        return True

    def get_historical_data(self, symbol: str, resolution: str = "D", range_from: str = "2020-01-01", range_to: str = None) -> pd.DataFrame:
        """
        Fetch historical data from Fyers (chunks automatically if >365 days).
        Format symbol: "NSE:RELIANCE-EQ"
        resolution: "1", "5", "15", "60", "D"
        range_from/to format: "yyyy-mm-dd"
        """
        if not self.fyers:
            if not self.connect():
                return pd.DataFrame()
                
        if not range_to:
            range_to = date.today().strftime("%Y-%m-%d")
            
        if symbol.endswith(".NS"):
            fyers_sym = f"NSE:{symbol.replace('.NS', '')}-EQ"
        elif symbol.endswith(".BO"):
            fyers_sym = f"BSE:{symbol.replace('.BO', '')}-EQ"
        else:
            fyers_sym = symbol

        from datetime import datetime, timedelta
        start_date = datetime.strptime(range_from, "%Y-%m-%d").date()
        end_date = datetime.strptime(range_to, "%Y-%m-%d").date()

        # Fyers daily data limit: max 2 years (730 days) back.
        # Requesting older data returns -300 'Invalid symbol' error.
        if resolution in ("1D", "D"):
            fyers_limit = date.today() - timedelta(days=729)
            if start_date < fyers_limit:
                logger.debug(
                    f"Clamping {fyers_sym} start {start_date} → {fyers_limit} "
                    f"(Fyers 2-year daily limit)"
                )
                start_date = fyers_limit
        
        all_candles = []
        current_start = start_date
        
        while current_start <= end_date:
            max_days = 365 if resolution in ("1D", "D") else 90
            current_end = min(current_start + timedelta(days=max_days - 1), end_date)
            
            data = {
                "symbol": fyers_sym,
                "resolution": resolution,
                "date_format": "1",
                "range_from": current_start.strftime("%Y-%m-%d"),
                "range_to": current_end.strftime("%Y-%m-%d"),
                "cont_flag": "1"
            }
            
            res = self.fyers.history(data=data)
            
            if res.get("s") != "ok":
                # 'no_data' means this date range has no candles.
                # Can happen for: today's date, illiquid micro-caps, recently listed stocks.
                # Silently skip this chunk — don't log as error, just move on.
                if res.get("s") == "no_data":
                    current_start = current_end + timedelta(days=1)
                    continue
                # Actual error (invalid symbol, auth failure, etc.) — log and stop
                if res.get("code") != 429:
                    logger.debug(f"Fyers history unavailable for {fyers_sym} ({current_start} to {current_end}): {res.get('message', res.get('s'))}")
                break
                
            candles = res.get("candles", [])
            if candles:
                all_candles.extend(candles)
                
            current_start = current_end + timedelta(days=1)
            time.sleep(0.05) # Rate limit protection
            
        if not all_candles:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_candles, columns=['epoch', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['datetime'] = pd.to_datetime(df['epoch'], unit='s')
        df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        df.set_index('datetime', inplace=True)
        df.drop('epoch', axis=1, inplace=True)
        
        # Ensure no duplicates from chunk boundaries
        df = df[~df.index.duplicated(keep='last')]
        return df

    def fetch_quotes(self, symbols: list[str]) -> dict:
        """
        Fetch live quotes for a list of symbols from Fyers.
        Max 50 symbols per request.
        """
        if not self.fyers:
            if not self.connect():
                return {}
                
        data = {
            "symbols": ",".join(symbols)
        }
        try:
            res = self.fyers.quotes(data=data)
            return res
        except Exception as e:
            logger.error(f"Error fetching Fyers quotes: {e}")
            return {}

    async def fetch_depth_concurrent(self, symbols: list[str], max_workers: int = 10) -> dict:
        """
        Fetch depth data (which contains Open Interest) for multiple symbols concurrently.
        Since Fyers V3 depth API only takes a single symbol, we use a ThreadPoolExecutor.
        """
        import asyncio
        
        if not self.fyers:
            if not self.connect():
                return {}

        def _fetch_single(sym):
            import time
            for attempt in range(3):
                try:
                    res = self.fyers.depth(data={"symbol": sym, "ohlcv_flag": "1"})
                    if isinstance(res, dict) and res.get("s") == "ok":
                        return res
                except Exception:
                    pass
                time.sleep(0.5) # Wait before retry
            return {"s": "error", "message": "Failed", "symbol": sym}

        loop = asyncio.get_event_loop()
        results = {}
        
        # Throttle to 3 concurrent requests to avoid Fyers WAF rate-limiting
        sem = asyncio.Semaphore(3)
        
        async def _bounded_fetch(sym):
            async with sem:
                # Add a tiny artificial delay to spread out requests (3 req / 0.35s ~ 8 req/s)
                await asyncio.sleep(0.35)
                try:
                    return await asyncio.wait_for(loop.run_in_executor(None, _fetch_single, sym), timeout=5.0)
                except asyncio.TimeoutError:
                    return {"s": "error", "message": "Timeout", "symbol": sym}

        tasks = [_bounded_fetch(sym) for sym in symbols]
        responses = await asyncio.gather(*tasks)

        for sym, res in zip(symbols, responses):
            if isinstance(res, dict) and res.get("s") == "ok" and "d" in res:
                for k, v in res["d"].items():
                    results[k] = v

        return results
