"""
Fyers API Data Client
Handles authentication and high-quality historical data fetching.
Supports TOTP auto-login so no manual Fyers website visit is needed daily.
"""
import time
from datetime import datetime, date, timedelta
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
        self.user_name: Optional[str] = None

    def get_auth_url(self) -> str:
        """Returns the Fyers login URL for the frontend (manual fallback)."""
        session = fyersModel.SessionModel(
            client_id=self.app_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        return session.generate_authcode()

    def set_auth_code(self, auth_code: str) -> bool:
        """Called by the frontend API when user submits the manual auth code."""
        try:
            self.fyers = None
            self.user_name = None
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
            self._save_token(response["access_token"])
            return True
        except Exception as e:
            logger.error(f"Error setting auth code: {e}")
            return False

    def auto_login(self) -> bool:
        """
        Automatically login to Fyers using TOTP + PIN.
        No browser / manual steps required.
        Uses FYERS_CLIENT_ID, FYERS_TOTP_KEY, FYERS_PIN from .env
        """
        totp_key = settings.FYERS_TOTP_KEY
        pin = settings.FYERS_PIN
        client_id = settings.FYERS_CLIENT_ID

        if not all([totp_key, pin, client_id, self.app_id, self.secret_key]):
            logger.error("Missing Fyers credentials for auto-login.")
            return False

        try:
            import pyotp
            import requests as req

            headers = {"Accept": "application/json", "Content-Type": "application/json"}

            # Step 1: Send client_id to get request_key
            # app_id for vagator is the numeric suffix of FYERS_APP_ID
            # e.g. "7UKGQH1LWE-100" -> "100"
            vagator_app_id = self.app_id.split("-")[-1] if "-" in self.app_id else "2"

            r1 = req.post(
                "https://api-t2.fyers.in/vagator/v2/send_login_otp_v2",
                json={"fy_id": client_id, "app_id": vagator_app_id},
                headers=headers, timeout=15
            )
            d1 = r1.json()
            if d1.get("s") != "ok":
                logger.error(f"Fyers Step1 (send_login_otp) failed: {d1}")
                return False
            request_key = d1["request_key"]
            time.sleep(1)

            # Step 2: Verify TOTP code
            totp_code = pyotp.TOTP(totp_key).now()
            r2 = req.post(
                "https://api-t2.fyers.in/vagator/v2/verify_otp",
                json={"request_key": request_key, "otp": totp_code},
                headers=headers, timeout=15
            )
            d2 = r2.json()
            if d2.get("s") != "ok":
                logger.error(f"Fyers Step2 (verify_otp) failed: {d2}")
                return False
            request_key2 = d2["request_key"]

            # Step 3: Verify PIN
            r3 = req.post(
                "https://api-t2.fyers.in/vagator/v2/verify_pin_v2",
                json={"request_key": request_key2, "identity_type": "pin", "identifier": pin},
                headers=headers, timeout=15
            )
            d3 = r3.json()
            if d3.get("s") != "ok":
                logger.error(f"Fyers Step3 (verify_pin) failed: {d3}")
                return False
            access_token_v3 = d3["data"]["access_token"]

            # Step 4: Exchange for OAuth access_token
            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(access_token_v3)
            token_resp = session.generate_token()
            if token_resp.get("s") != "ok":
                logger.error(f"Fyers Step4 (generate_token) failed: {token_resp}")
                return False

            self._save_token(token_resp["access_token"])
            logger.info(f"Fyers auto-login successful for {client_id}")
            return True

        except Exception as e:
            logger.error(f"Fyers auto-login exception: {e}", exc_info=True)
            return False

    def connect(self, force: bool = False) -> bool:
        """
        Connect to Fyers API.
        1. Reuse existing active session if available (0ms fast path).
        2. Reuse today's saved token.
        3. TOTP auto-login to get fresh token.
        4. Error if all fail.
        """
        if not force and self.fyers is not None and self.user_name is not None:
            return True

        access_token = self._load_todays_token()

        if not access_token:
            logger.info("No valid today token. Attempting TOTP auto-login...")
            if self.auto_login():
                access_token = self._load_todays_token()
            if not access_token:
                logger.error("Fyers auto-login failed. Authenticate via Settings > Broker Connection.")
                return False

        self.fyers = fyersModel.FyersModel(
            client_id=self.app_id,
            is_async=False,
            token=access_token,
            log_path=str(Path(BASE_DIR) / "backend" / "logs")
        )

        profile = self.fyers.get_profile()
        if profile.get("s") == "error":
            logger.warning("Saved token invalid. Trying fresh auto-login...")
            if self.auto_login():
                access_token = self._load_todays_token()
                if access_token:
                    self.fyers = fyersModel.FyersModel(
                        client_id=self.app_id, is_async=False,
                        token=access_token,
                        log_path=str(Path(BASE_DIR) / "backend" / "logs")
                    )
                    profile = self.fyers.get_profile()
                    if profile.get("s") == "error":
                        logger.error("Fyers connection failed after fresh auto-login.")
                        return False
            else:
                return False

        name = profile.get("data", {}).get("name", self.client_id)
        self.user_name = name
        logger.info(f"Fyers connected: {name}")
        return True

    def _save_token(self, token: str) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(token)

    def _load_todays_token(self) -> Optional[str]:
        if self.token_file.exists():
            mtime = datetime.fromtimestamp(self.token_file.stat().st_mtime)
            if mtime.date() == date.today():
                token = self.token_file.read_text().strip()
                return token if token else None
        return None

    def get_historical_data(self, symbol: str, resolution: str = "D", range_from: str = "2020-01-01", range_to: str = None) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Fyers. Auto-chunks for API limits.
        symbol: "NSE:RELIANCE-EQ" or "RELIANCE.NS" (auto-converted)
        resolution: "1","5","15","60","D"
        """
        if not self.fyers:
            if not self.connect():
                return pd.DataFrame()

        if not range_to:
            range_to = date.today().strftime("%Y-%m-%d")

        sym_clean = symbol.replace(".NS", "").replace(".BO", "").strip()
        if sym_clean.startswith("NSE:") or sym_clean.startswith("BSE:"):
            fyers_sym = sym_clean
        elif symbol.endswith(".BO"):
            fyers_sym = f"BSE:{sym_clean}-EQ"
        else:
            fyers_sym = f"NSE:{sym_clean}-EQ"

        start_date = datetime.strptime(range_from, "%Y-%m-%d").date()
        end_date = datetime.strptime(range_to, "%Y-%m-%d").date()

        if resolution in ("1D", "D"):
            fyers_limit = date.today() - timedelta(days=729)
            if start_date < fyers_limit:
                start_date = fyers_limit

        all_candles = []
        current_start = start_date

        while current_start <= end_date:
            max_days = 365 if resolution in ("1D", "D") else 90
            current_end = min(current_start + timedelta(days=max_days - 1), end_date)

            data = {
                "symbol": fyers_sym, "resolution": resolution,
                "date_format": "1",
                "range_from": current_start.strftime("%Y-%m-%d"),
                "range_to": current_end.strftime("%Y-%m-%d"),
                "cont_flag": "1"
            }

            res = self.fyers.history(data=data)

            if res.get("s") != "ok":
                if res.get("s") == "no_data":
                    current_start = current_end + timedelta(days=1)
                    continue
                if res.get("code") != 429:
                    logger.debug(f"Fyers history unavailable for {fyers_sym}: {res.get('message', res.get('s'))}")
                break

            candles = res.get("candles", [])
            if candles:
                all_candles.extend(candles)
            current_start = current_end + timedelta(days=1)
            time.sleep(0.05)

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles, columns=["epoch", "Open", "High", "Low", "Close", "Volume"])
        df["datetime"] = pd.to_datetime(df["epoch"], unit="s")
        df["datetime"] = df["datetime"].dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")
        df.set_index("datetime", inplace=True)
        df.drop("epoch", axis=1, inplace=True)
        df = df[~df.index.duplicated(keep="last")]
        return df

    def fetch_quotes(self, symbols: list) -> dict:
        """Fetch live quotes for up to 50 symbols from Fyers."""
        if not self.fyers:
            if not self.connect():
                return {}
        try:
            return self.fyers.quotes(data={"symbols": ",".join(symbols)})
        except Exception as e:
            logger.error(f"Error fetching Fyers quotes: {e}")
            return {}

    async def fetch_depth_concurrent(self, symbols: list, max_workers: int = 10) -> dict:
        """Fetch depth (OI, bid/ask) for multiple symbols concurrently."""
        import asyncio

        if not self.fyers:
            if not self.connect():
                return {}

        def _fetch_single(sym):
            for _ in range(3):
                try:
                    res = self.fyers.depth(data={"symbol": sym, "ohlcv_flag": "1"})
                    if isinstance(res, dict) and res.get("s") == "ok":
                        return res
                except Exception:
                    pass
                time.sleep(0.5)
            return {"s": "error", "message": "Failed", "symbol": sym}

        loop = asyncio.get_event_loop()
        results = {}
        sem = asyncio.Semaphore(3)

        async def _bounded_fetch(sym):
            async with sem:
                await asyncio.sleep(0.35)
                try:
                    return await asyncio.wait_for(loop.run_in_executor(None, _fetch_single, sym), timeout=5.0)
                except asyncio.TimeoutError:
                    return {"s": "error", "message": "Timeout", "symbol": sym}

        responses = await asyncio.gather(*[_bounded_fetch(sym) for sym in symbols])

        for sym, res in zip(symbols, responses):
            if isinstance(res, dict) and res.get("s") == "ok" and "d" in res:
                for k, v in res["d"].items():
                    results[k] = v

        return results
