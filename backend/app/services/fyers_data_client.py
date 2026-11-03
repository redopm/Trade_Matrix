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

        # Robust path resolution for local dev and Docker container
        if Path("/app/models").is_dir():
            models_dir = Path("/app/models")
        elif (Path(BASE_DIR) / "backend" / "models").is_dir():
            models_dir = Path(BASE_DIR) / "backend" / "models"
        elif (Path(BASE_DIR) / "models").is_dir():
            models_dir = Path(BASE_DIR) / "models"
        else:
            models_dir = Path(BASE_DIR) / "backend" / "models"

        self.token_file = models_dir / "fyers_token.txt"
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

    def set_auth_code(self, auth_code: str):
        """Called by the frontend API when user submits the manual auth code."""
        try:
            self.fyers = None
            self.user_name = None
            
            clean_code = auth_code.strip()
            if "auth_code=" in clean_code:
                import re
                m = re.search(r"[?&]auth_code=([^&]+)", clean_code) or re.search(r"auth_code=([^&]+)", clean_code)
                if m:
                    clean_code = m.group(1).strip()
            import urllib.parse
            clean_code = urllib.parse.unquote(clean_code)

            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(clean_code)
            response = session.generate_token()
            if response.get("s") != "ok":
                msg = response.get("message") or response.get("errMsg") or str(response)
                logger.error(f"Failed to generate final token: {response}")
                return False, msg
            self._save_token(response["access_token"])
            return True, None
        except Exception as e:
            logger.error(f"Error setting auth code: {e}")
            return False, str(e)

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
            import base64
            from urllib.parse import parse_qs, urlparse
            import pyotp
            import requests as req

            def encode_input(s):
                return base64.b64encode(str(s).encode("ascii")).decode("ascii")

            session = req.Session()
            session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

            # Step 1: Send client_id (Base64) to get request_key
            r1 = session.post(
                "https://api-t2.fyers.in/vagator/v2/send_login_otp_v2",
                json={"fy_id": encode_input(client_id), "app_id": "2"},
                timeout=15
            ).json()
            if r1.get("s") != "ok":
                logger.error(f"Fyers Step1 (send_login_otp) failed: {r1}")
                return False
            request_key_1 = r1["request_key"]
            time.sleep(1)

            # Step 2: Verify TOTP code
            totp_code = pyotp.TOTP(totp_key).now()
            r2 = session.post(
                "https://api-t2.fyers.in/vagator/v2/verify_otp",
                json={"request_key": request_key_1, "otp": totp_code},
                timeout=15
            ).json()
            if r2.get("s") != "ok":
                logger.error(f"Fyers Step2 (verify_otp) failed: {r2}")
                return False
            request_key_2 = r2["request_key"]

            # Step 3: Verify PIN (Base64)
            r3 = session.post(
                "https://api-t2.fyers.in/vagator/v2/verify_pin_v2",
                json={"request_key": request_key_2, "identity_type": "pin", "identifier": encode_input(pin)},
                timeout=15
            ).json()
            if r3.get("s") != "ok":
                logger.error(f"Fyers Step3 (verify_pin) failed: {r3}")
                return False
            access_token_v2 = r3["data"]["access_token"]
            session.headers.update({"authorization": f"Bearer {access_token_v2}"})

            # Step 4: Request OAuth Authorization Code
            base_app_id = self.app_id.split("-")[0] if "-" in self.app_id else self.app_id
            payload_token = {
                "fyers_id": client_id,
                "app_id": base_app_id,
                "redirect_uri": self.redirect_uri,
                "appType": "100",
                "code_challenge": "",
                "state": "None",
                "scope": "",
                "nonce": "",
                "response_type": "code",
                "create_cookie": True
            }
            r4 = session.post("https://api-t1.fyers.in/api/v3/token", json=payload_token, timeout=15).json()
            if r4.get("s") != "ok":
                logger.error(f"Fyers Step4 (get authorization code) failed: {r4}")
                return False

            auth_url = r4.get("Url")
            parsed_url = urlparse(auth_url)
            query_params = parse_qs(parsed_url.query)
            if "auth_code" not in query_params:
                logger.error(f"Fyers Step4 auth_code missing in URL: {auth_url}")
                return False
            auth_code = query_params["auth_code"][0]

            # Step 5: Exchange Auth Code for Final API Access Token
            grant_session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            grant_session.set_token(auth_code)
            response_final = grant_session.generate_token()
            if response_final.get("s") != "ok":
                logger.error(f"Fyers Step5 (generate final token) failed: {response_final}")
                return False

            self._save_token(response_final["access_token"])
            logger.info(f"Fyers 24x7 auto-login successful for {client_id}")
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
