"""
Market Regime Detection Service
Detects if the broader market is BULLISH, BEARISH, or SIDEWAYS.
Uses:
- Nifty 50  (^NSEI / NSE:NIFTY50-INDEX)  → Price vs 200 EMA, RSI, ADX
- India VIX (NSE:INDIAVIX-INDEX)          → Fear gauge  [Fyers primary, yfinance fallback]
- Nifty Bank (NSE:NIFTYBANK-INDEX)        → Bank sector breadth
- Sensex     (BSE:SENSEX-INDEX)           → Cross-index confirmation
- Advance/Decline Ratio                   → Market breadth proxy
"""
import asyncio
from datetime import datetime, timedelta, date
import pandas as pd
import yfinance as yf
from app.utils.logger import get_logger
from app.services.data_fetcher import NIFTY500_SYMBOLS

logger = get_logger(__name__)


# ── Fyers index symbol map ────────────────────────────────────────────────────
FYERS_INDEX_SYMBOLS = {
    "vix":        "NSE:INDIAVIX-INDEX",
    "nifty":      "NSE:NIFTY50-INDEX",
    "nifty_bank": "NSE:NIFTYBANK-INDEX",
    "sensex":     "BSE:SENSEX-INDEX",
}

def _fyers_quote(fyers_symbol: str) -> float | None:
    """Fetch last-traded price for a Fyers index symbol."""
    try:
        from app.services.fyers_data_client import FyersDataClient
        client = FyersDataClient()
        if not client.connect():
            return None
        res = client.fyers.quotes(data={"symbols": fyers_symbol})
        if res.get("s") != "ok":
            return None
        d = res.get("d", [])
        if d:
            v = d[0].get("v", {})
            return float(v.get("lp") or v.get("prev_close_price") or 0) or None
    except Exception as e:
        logger.warning(f"Fyers quote failed for {fyers_symbol}: {e}")
    return None


def _fyers_ohlcv(fyers_symbol: str, days: int = 365) -> pd.DataFrame:
    """Fetch historical OHLCV from Fyers for an index symbol."""
    try:
        from app.services.fyers_data_client import FyersDataClient
        client = FyersDataClient()
        if not client.connect():
            return pd.DataFrame()
        range_from = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        range_to   = date.today().strftime("%Y-%m-%d")
        data = {
            "symbol":      fyers_symbol,
            "resolution":  "D",
            "date_format": "1",
            "range_from":  range_from,
            "range_to":    range_to,
            "cont_flag":   "1",
        }
        res = client.fyers.history(data=data)
        if res.get("s") != "ok":
            return pd.DataFrame()
        candles = res.get("candles", [])
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["epoch", "Open", "High", "Low", "Close", "Volume"])
        df["datetime"] = pd.to_datetime(df["epoch"], unit="s")
        df.set_index("datetime", inplace=True)
        df.drop("epoch", axis=1, inplace=True)
        return df
    except Exception as e:
        logger.warning(f"Fyers history failed for {fyers_symbol}: {e}")
    return pd.DataFrame()


class MarketRegimeDetector:
    _cache: dict | None = None
    _cache_time: datetime | None = None
    _lock = asyncio.Lock()              # prevents parallel detection storm
    CACHE_TTL_MINUTES = 60

    @classmethod
    async def get_current_regime(cls) -> dict:
        """Get the current market regime, using cache if fresh."""
        # Fast path: return cache without acquiring lock
        if cls._cache and cls._cache_time:
            if datetime.now() - cls._cache_time < timedelta(minutes=cls.CACHE_TTL_MINUTES):
                return cls._cache

        # Slow path: only one coroutine detects at a time; others wait and reuse result
        async with cls._lock:
            # Re-check after acquiring lock (another task may have already refreshed)
            if cls._cache and cls._cache_time:
                if datetime.now() - cls._cache_time < timedelta(minutes=cls.CACHE_TTL_MINUTES):
                    return cls._cache

            regime_data = await cls._detect_regime()
            cls._cache = regime_data
            cls._cache_time = datetime.now()
            return regime_data

    @classmethod
    async def _detect_regime(cls) -> dict:
        """Run the actual detection logic."""
        logger.info("Detecting Market Regime...")
        try:
            # Run all fetches concurrently
            nifty_task      = asyncio.to_thread(cls._fetch_nifty_data)
            vix_task        = asyncio.to_thread(cls._fetch_vix)
            ad_task         = asyncio.to_thread(cls._fetch_ad_ratio)
            nifty_bank_task = asyncio.to_thread(cls._fetch_nifty_bank)
            sensex_task     = asyncio.to_thread(cls._fetch_sensex)

            nifty_df, vix, ad_ratio, nifty_bank, sensex = await asyncio.gather(
                nifty_task, vix_task, ad_task, nifty_bank_task, sensex_task,
                return_exceptions=True,
            )

            # Handle gather exceptions gracefully
            if isinstance(nifty_df, Exception):   nifty_df    = None
            if isinstance(vix, Exception):        vix         = None
            if isinstance(ad_ratio, Exception):   ad_ratio    = 1.0
            if isinstance(nifty_bank, Exception): nifty_bank  = None
            if isinstance(sensex, Exception):     sensex      = None

            if nifty_df is None or nifty_df.empty:
                logger.warning("Could not fetch Nifty data. Defaulting to SIDEWAYS.")
                return cls._default_regime("Data fetch failed")

            latest  = nifty_df.iloc[-1]
            price   = latest["Close"]
            ema200  = latest["EMA_200"]   if "EMA_200"  in nifty_df.columns else price
            rsi     = latest["RSI_14"]    if "RSI_14"   in nifty_df.columns else 50
            adx     = latest["ADX_14"]    if "ADX_14"   in nifty_df.columns else 0

            # --- Regime Logic ---
            regime     = "SIDEWAYS"
            confidence = 0.5
            reasons    = []

            is_uptrend   = price > ema200
            is_downtrend = price < ema200
            trend_strength = adx > 20

            if is_uptrend and trend_strength and rsi > 40:
                regime     = "BULLISH"
                confidence = 0.6
                reasons.append("Price > 200 EMA")
                reasons.append("ADX > 20 (Strong Trend)")

                if ad_ratio > 1.2:
                    confidence += 0.2
                    reasons.append("A/D Ratio Bullish")
                elif ad_ratio < 0.8:
                    confidence -= 0.1
                    reasons.append("A/D Ratio Weak (Warning)")

                if vix and vix < 18:
                    confidence += 0.2
                    reasons.append(f"VIX Low ({vix:.1f}) — Bullish")
                elif vix and vix > 22:
                    confidence -= 0.2
                    reasons.append(f"VIX High ({vix:.1f}) — Fear")

            elif is_downtrend and trend_strength and rsi < 60:
                regime     = "BEARISH"
                confidence = 0.6
                reasons.append("Price < 200 EMA")
                reasons.append("ADX > 20 (Strong Trend)")

                if ad_ratio < 0.8:
                    confidence += 0.2
                    reasons.append("A/D Ratio Bearish")
                elif ad_ratio > 1.2:
                    confidence -= 0.1

                if vix and vix > 20:
                    confidence += 0.2
                    reasons.append(f"VIX High ({vix:.1f}) — Panic/Bearish")

            else:
                regime = "SIDEWAYS"
                reasons.append("Weak Trend (ADX < 20) or Conflicting Indicators")
                confidence = 0.8

            # Normalize confidence
            confidence = max(0.0, min(1.0, confidence))

            if regime != "SIDEWAYS" and confidence < 0.4:
                regime = "SIDEWAYS"
                reasons.append("Downgraded to SIDEWAYS due to low confidence")
                confidence = 0.5

            result = {
                "regime":       regime,
                "confidence":   round(confidence, 2),
                "nifty_price":  round(price, 2),
                "nifty_rsi":    round(rsi, 2),
                "nifty_ema200": round(ema200, 2),
                "adx":          round(adx, 2),
                "vix":          round(vix, 2) if vix else None,
                "nifty_bank":   round(nifty_bank, 2) if nifty_bank else None,
                "sensex":       round(sensex, 2) if sensex else None,
                "ad_ratio":     round(ad_ratio, 2),
                "reasons":      reasons,
                "timestamp":    datetime.now().isoformat(),
            }
            logger.info(
                f"Market Regime: {regime} ({confidence:.0%}) | "
                f"Nifty={price:.0f} VIX={vix} Bank={nifty_bank} Sensex={sensex}"
            )
            return result

        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return cls._default_regime(str(e))

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _default_regime(reason: str) -> dict:
        return {
            "regime":       "SIDEWAYS",
            "confidence":   0.5,
            "nifty_price":  0.0,
            "nifty_rsi":    50.0,
            "nifty_ema200": 0.0,
            "adx":          0.0,
            "vix":          None,
            "nifty_bank":   None,
            "sensex":       None,
            "ad_ratio":     1.0,
            "reasons":      [f"Fallback to sideways due to error: {reason}"],
            "timestamp":    datetime.now().isoformat(),
        }

    @staticmethod
    def _fetch_nifty_data() -> pd.DataFrame:
        """Nifty 50 OHLCV: try Fyers first, fallback to yfinance."""
        try:
            df = _fyers_ohlcv(FYERS_INDEX_SYMBOLS["nifty"], days=365)
            if df.empty:
                raise ValueError("Fyers returned empty")
        except Exception:
            try:
                df = yf.Ticker("^NSEI").history(period="1y", interval="1d")
            except Exception as e:
                logger.error(f"Error fetching Nifty data: {e}")
                return None

        if df is None or df.empty:
            return None

        # Technical indicators
        df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()

        delta  = df["Close"].diff()
        gain   = delta.where(delta > 0, 0).rolling(14).mean()
        loss   = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs     = gain / loss
        df["RSI_14"] = 100 - (100 / (1 + rs))

        high_diff = df["High"].diff()
        low_diff  = df["Low"].diff()
        df["+DM"] = pd.Series(
            [h if h > 0 and h > -l else 0 for h, l in zip(high_diff, low_diff)],
            index=df.index
        )
        df["-DM"] = pd.Series(
            [-l if l < 0 and -l > h else 0 for h, l in zip(high_diff, low_diff)],
            index=df.index
        )
        tr = pd.concat([
            df["High"] - df["Low"],
            abs(df["High"] - df["Close"].shift()),
            abs(df["Low"]  - df["Close"].shift()),
        ], axis=1).max(axis=1)
        atr       = tr.rolling(14).mean()
        plus_di   = 100 * (df["+DM"].rolling(14).mean() / atr)
        minus_di  = 100 * (df["-DM"].rolling(14).mean() / atr)
        dx        = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df["ADX_14"] = dx.rolling(14).mean()

        return df

    @staticmethod
    def _fetch_vix() -> float | None:
        """India VIX: Fyers primary, yfinance fallback."""
        # Try Fyers first (real-time)
        val = _fyers_quote(FYERS_INDEX_SYMBOLS["vix"])
        if val and val > 0:
            logger.info(f"VIX from Fyers: {val}")
            return val
        # Fallback: yfinance
        try:
            ticker = yf.Ticker("^INDIAVIX")
            fast   = ticker.fast_info
            v = float(fast.get("last_price", 0) or 0)
            if v > 0:
                logger.info(f"VIX from yfinance: {v}")
                return v
            # Second fallback: last close from history
            hist = ticker.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Error fetching VIX from yfinance: {e}")
        return None

    @staticmethod
    def _fetch_nifty_bank() -> float | None:
        """Nifty Bank last price: Fyers primary, yfinance fallback."""
        val = _fyers_quote(FYERS_INDEX_SYMBOLS["nifty_bank"])
        if val and val > 0:
            return val
        try:
            ticker = yf.Ticker("^NSEBANK")
            hist   = ticker.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Error fetching Nifty Bank: {e}")
        return None

    @staticmethod
    def _fetch_sensex() -> float | None:
        """Sensex last price: Fyers primary, yfinance fallback."""
        val = _fyers_quote(FYERS_INDEX_SYMBOLS["sensex"])
        if val and val > 0:
            return val
        try:
            ticker = yf.Ticker("^BSESN")
            hist   = ticker.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Error fetching Sensex: {e}")
        return None

    @staticmethod
    def _fetch_ad_ratio() -> float:
        try:
            top_50 = NIFTY500_SYMBOLS[:50]
            data   = yf.download(top_50, period="5d", group_by="ticker", progress=False)

            advances = 0
            declines = 0

            for sym in top_50:
                try:
                    if sym in data.columns.levels[0]:
                        close = data[sym]["Close"].dropna()
                        if len(close) >= 2:
                            change = close.iloc[-1] - close.iloc[-2]
                            if change > 0:
                                advances += 1
                            elif change < 0:
                                declines += 1
                except Exception:
                    pass

            if declines == 0:
                return advances if advances > 0 else 1.0
            return advances / declines
        except Exception as e:
            logger.error(f"Error fetching AD ratio: {e}")
            return 1.0
