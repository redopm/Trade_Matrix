"""
Local Nifty 500 + NSE Indices 2-to-20 Year Daily OHLCV Data Store (SQLite WAL).

Architecture:
- Persists 2-year Fyers official NSE candles + up to 20-year corporate-action-adjusted
  NSE historical candles (~5,000 sessions per stock) at _BACKEND_DIR/database/daily_ohlcv_store.db.
- Fast Path: Returns a timezone-aware (Asia/Kolkata) DataFrame in ~1-3 ms directly
  from disk when already synced up to the latest NSE session.
- Delta Path: Fetches ONLY missing recent candles starting from max_dt
  (overlapping 1 day to automatically detect stock splits/bonuses).
- Auto EOD Sync: Runs daily Mon-Fri at 15:38 IST and auto-resumes incomplete syncs on startup.
"""
import asyncio
import json
import shutil
import sqlite3
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz
import yfinance as yf

from app.config import _BACKEND_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
DB_DIR = Path(_BACKEND_DIR) / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
STORE_DB_PATH = DB_DIR / "daily_ohlcv_store.db"

FULL_SEED_DAYS = 729  # Fyers daily history window (~2 years)

CORE_INDEX_SYMBOLS: List[str] = [
    "NSE:NIFTY50-INDEX",
    "NSE:NIFTYBANK-INDEX",
    "NSE:FINNIFTY-INDEX",
    "NSE:MIDCPNIFTY-INDEX",
]

# Handle common NSE ticker renames / Fyers vs Yahoo Finance symbol differences
_SYMBOL_ALIASES: Dict[str, Any] = {
    "NSE:ZOMATO-EQ": ("ETERNAL", "ZOMATO"),
    "NSE:TATAMOTORS-EQ": ("TMPV", "TATAMOTORS"),
    "NSE:TMPV-EQ": ("TMPV",),
    "NSE:MCDOWELL-N-EQ": ("UNITDSPR",),
    "NSE:AMBUJACEMENT-EQ": ("AMBUJACEM",),
    "NSE:AMBUJACEM-EQ": ("AMBUJACEM", "AMBUJACEMENT"),
    "NSE:TVSMOTORS-EQ": ("TVSMOTOR",),
    "NSE:TVSMOTOR-EQ": ("TVSMOTOR", "TVSMOTORS"),
    "NSE:HAVELLES-EQ": ("HAVELLS",),
    "NSE:ADANITRANS-EQ": ("ADANIENSOL",),
    "NSE:AMARAJABAT-EQ": ("ARE&M",),
    "NSE:GMRINFRA-EQ": ("GMRAIRPORT",),
    "NSE:KALPATARPOWER-EQ": ("KPIL",),
    "NSE:ADANIWILMAR-EQ": ("AWL",),
    "NSE:SUNCLAYLTD-EQ": ("SUNDRMFAST",),
    "NSE:WELSPUN-EQ": ("WELSPUNLIV",),
    "NSE:BAJAJ-AUTO-EQ": ("BAJAJ-AUTO",),
    "NSE:M&M-EQ": ("M&M",),
    "NSE:M&MFIN-EQ": ("M&MFIN",),
    # ── 76 Legacy / Informal / Renamed / Merged Tickers in SECTOR_UNIVERSE ──
    "NSE:ACME-EQ": ("ACMESOLAR",),
    "NSE:AEGASIND-EQ": ("AEGISLOG",),
    "NSE:AKZONOBEL-EQ": ("AKZOINDIA", "KANSAINER", "BERGEPAINT"),
    "NSE:AMBATTUR-EQ": ("PAGEIND",),
    "NSE:APCOTEX-EQ": ("APCOTEXIND",),
    "NSE:ASAHI-EQ": ("ASAHIINDIA",),
    "NSE:AVAADA-EQ": ("TATAPOWER",),
    "NSE:BAJAJELECTR-EQ": ("BAJAJELEC",),
    "NSE:BARBEQUE-EQ": ("UFBL", "DEVYANI"),
    "NSE:BATA-EQ": ("BATAINDIA",),
    "NSE:BIRLASOFT-EQ": ("BSOFT",),
    "NSE:CAMLIN-EQ": ("CAMLINFINE", "KOKUYOCMLN"),
    "NSE:DAAWAT-EQ": ("LTFOODS",),
    "NSE:DALMIACEM-EQ": ("DALBHARAT",),
    "NSE:DATAPATTERNSIND-EQ": ("DATAPATTNS",),
    "NSE:DECCAN-EQ": ("DECCANCE",),
    "NSE:DHARAMDAS-EQ": ("DCMSHRIRAM",),
    "NSE:FIEM-EQ": ("FIEMIND",),
    "NSE:FINOLEX-EQ": ("FINCABLES", "FINPIPE"),
    "NSE:GMDC-EQ": ("GMDCLTD",),
    "NSE:GSPL-EQ": ("GSPLEQ", "GSPLTRANS", "IGL"),
    "NSE:GUJGASLTD-EQ": ("GSPLEQ", "GSPLTRANS", "IGL"),
    "NSE:HBLPOWER-EQ": ("HBLENGINE",),
    "NSE:HEXAWARE-EQ": ("HEXT", "COFORGE"),
    "NSE:HINDMOTORS-EQ": ("HINDMOTORS", "FORCEMOT"),
    "NSE:HOMEFIRSTFIN-EQ": ("HOMEFIRST",),
    "NSE:HPCL-EQ": ("HINDPETRO",),
    "NSE:INDIABULLS-EQ": ("SAMMAANCAP", "EMBDL"),
    "NSE:INFOEDGE-EQ": ("NAUKRI",),
    "NSE:INTERGLOBE-EQ": ("INDIGO",),
    "NSE:ISEC-EQ": ("ICICIBANK",),
    "NSE:JAMNA-EQ": ("JAMNAAUTO",),
    "NSE:JBCHEPHARM-EQ": ("TORNTPHARM",),
    "NSE:JSPL-EQ": ("JINDALSTEL",),
    "NSE:KEYSTONE-EQ": ("RUSTOMJEE",),
    "NSE:KTIL-EQ": ("KPRMILL",),
    "NSE:LAURUS-EQ": ("LAURUSLABS",),
    "NSE:LTIM-EQ": ("LTM", "LTIM", "LTTS"),
    "NSE:MAFATLAL-EQ": ("ARVIND",),
    "NSE:MAS-EQ": ("MASFIN",),
    "NSE:MINDA-EQ": ("UNOMINDA",),
    "NSE:MINDAIND-EQ": ("MINDACORP", "UNOMINDA"),
    "NSE:MTAR-EQ": ("MTARTECH",),
    "NSE:NATESTEELS-EQ": ("TATASTEEL",),
    "NSE:NBLGIL-EQ": ("NBCC",),
    "NSE:NITIN-EQ": ("NITINSPIN",),
    "NSE:PANACEA-EQ": ("PANACEABIO",),
    "NSE:PONDY-EQ": ("POCL",),
    "NSE:PRSMJOHNS-EQ": ("PRSMJOHNSN",),
    "NSE:RATTANINDIA-EQ": ("RTNINDIA", "RTNPOWER"),
    "NSE:REC-EQ": ("RECLTD",),
    "NSE:SANGHI-EQ": ("SANGHIIND", "AMBUJACEM"),
    "NSE:SAPPHIREFDS-EQ": ("SAPPHIRE",),
    "NSE:SEQUENT-EQ": ("ONESOURCE", "LAURUSLABS"),
    "NSE:SHFL-EQ": ("SHRIRAMFIN",),
    "NSE:SHYAMSTL-EQ": ("SHYAMMETL",),
    "NSE:SMRUTHI-EQ": ("IOLCP",),
    "NSE:SPANDEXP-EQ": ("SPORTKING", "SPANDANA"),
    "NSE:SPICEJET-EQ": ("INDIGO",),
    "NSE:STATIC-EQ": ("BOSCHLTD",),
    "NSE:STEELHCL-EQ": ("JSWSTEEL",),
    "NSE:STRIDES-EQ": ("STAR",),
    "NSE:SUBEX-EQ": ("SUBEXLTD",),
    "NSE:TASTYBIT-EQ": ("TASTYBITE",),
    "NSE:TCNS-EQ": ("ABFRL",),
    "NSE:THANGAMAYIL-EQ": ("THANGAMAYL",),
    "NSE:TPCL-EQ": ("TPLPLASTEH",),
    "NSE:TV18BRDCST-EQ": ("NETWORK18",),
    "NSE:UCALFUEL-EQ": ("UCAL",),
    "NSE:UJJIVANSF-EQ": ("UJJIVANSFB",),
    "NSE:VARDHMAN-EQ": ("VTL",),
    "NSE:VARUN-EQ": ("VBL",),
    "NSE:VEDANT-EQ": ("MANYAVAR",),
    "NSE:VIJAYALAB-EQ": ("VIJAYA",),
    "NSE:VIMTA-EQ": ("VIMTALABS",),
    "NSE:VRL-EQ": ("VRLLOG",),
    "NSE:VST-EQ": ("VSTIND",),
    "NSE:WOCKHARDT-EQ": ("WOCKPHARMA",),
}

_YF_INDEX_MAP: Dict[str, str] = {
    "NSE:NIFTY50-INDEX": "^NSEI",
    "NSE:NIFTYBANK-INDEX": "^NSEBANK",
    "NSE:FINNIFTY-INDEX": "NIFTY_FIN_SERVICE.NS",
    "NSE:MIDCPNIFTY-INDEX": "NIFTY_MIDCAP_100.NS",
}


class DailyHistoryStore:
    _db_lock = threading.RLock()
    _initialized = False
    _sync_status: Dict[str, Any] = {
        "is_running": False,
        "mode": "2Y_EOD",
        "total_symbols": 0,
        "completed_symbols": 0,
        "updated_symbols": 0,
        "cached_skipped": 0,
        "failed_symbols": 0,
        "current_symbol": "",
        "started_at": None,
        "finished_at": None,
        "last_error": None,
    }

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(STORE_DB_PATH), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

    @classmethod
    def _ensure_schema(cls) -> None:
        if cls._initialized and STORE_DB_PATH.exists():
            return
        with cls._db_lock:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            conn = cls._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS daily_candles (
                        fyers_sym TEXT NOT NULL,
                        dt TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL,
                        PRIMARY KEY (fyers_sym, dt)
                    );
                    CREATE INDEX IF NOT EXISTS ix_daily_candles_sym_epoch
                        ON daily_candles (fyers_sym, epoch);
                    CREATE TABLE IF NOT EXISTS symbol_sync_meta (
                        fyers_sym TEXT PRIMARY KEY,
                        min_dt TEXT,
                        max_dt TEXT,
                        rows_count INTEGER DEFAULT 0,
                        last_synced_at TEXT
                    );
                    """
                )
                conn.commit()
                cls._initialized = True
            finally:
                conn.close()

    @classmethod
    def _candidate_alias_bases(cls, fyers_sym: str) -> List[str]:
        raw_clean = (
            fyers_sym.replace("NSE:", "")
            .replace("BSE:", "")
            .replace("-EQ", "")
            .replace("-BE", "")
            .strip()
        )
        raw_val = _SYMBOL_ALIASES.get(fyers_sym)
        ordered: List[str] = []
        if isinstance(raw_val, (tuple, list)):
            ordered.extend(str(v).strip() for v in raw_val if v)
        elif isinstance(raw_val, str) and raw_val.strip():
            ordered.append(raw_val.strip())
        if raw_clean and raw_clean not in ordered:
            ordered.append(raw_clean)
        deduped: List[str] = []
        for item in ordered:
            if item not in deduped:
                deduped.append(item)
        return deduped

    @staticmethod
    def _to_yf_symbol(fyers_sym: str) -> str:
        if fyers_sym in _YF_INDEX_MAP:
            return _YF_INDEX_MAP[fyers_sym]
        if fyers_sym in _SYMBOL_ALIASES:
            val = _SYMBOL_ALIASES[fyers_sym]
            first = val[0] if isinstance(val, (tuple, list)) else val
            return f"{first}.NS"
        clean = (
            fyers_sym.replace("NSE:", "")
            .replace("BSE:", "")
            .replace("-EQ", "")
            .replace("-BE", "")
            .strip()
        )
        return f"{clean}.NS"

    @classmethod
    def _fetch_yf_nse_daily_df(cls, fyers_sym: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Fetch corporate-action-adjusted NSE daily history via Yahoo Finance (.NS / ^NSEI).
        Used automatically for 3Y–20Y deep historical backfills and zero-fail Fyers fallback.
        """
        if fyers_sym in _YF_INDEX_MAP:
            candidates = [_YF_INDEX_MAP[fyers_sym]]
        else:
            candidates = [f"{cand}.NS" for cand in cls._candidate_alias_bases(fyers_sym)]

        end_plus = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
        start_s = start_date.strftime("%Y-%m-%d")
        min_accept = 10 if (end_date - start_date).days >= 60 else 1
        best_df = pd.DataFrame()

        for yf_sym in candidates:
            try:
                df = yf.download(
                    tickers=yf_sym,
                    start=start_s,
                    end=end_plus,
                    interval="1d",
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df.columns = [str(c).title() for c in df.columns]
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        if col not in df.columns:
                            df = pd.DataFrame()
                            break
                    if df.empty:
                        continue
                    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"])
                    idx = pd.to_datetime(df.index)
                    if idx.tz is None:
                        idx = idx.tz_localize(IST)
                    else:
                        idx = idx.tz_convert(IST)
                    df.index = idx
                    df.index.name = "datetime"
                    df = df.sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if len(df) >= min_accept:
                        return df
                    if len(df) > len(best_df):
                        best_df = df
            except Exception as e:
                logger.debug(f"YF fallback failed for {yf_sym}: {e}")
        return best_df

    @staticmethod
    def _latest_closed_trading_date(now_ist: Optional[datetime] = None) -> date:
        now_ist = now_ist or datetime.now(IST)
        wd = now_ist.weekday()
        mins = now_ist.hour * 60 + now_ist.minute
        if wd == 5:
            return now_ist.date() - timedelta(days=1)
        if wd == 6:
            return now_ist.date() - timedelta(days=2)
        if mins >= (15 * 60 + 35):
            return now_ist.date()
        if wd == 0:
            return now_ist.date() - timedelta(days=3)
        return now_ist.date() - timedelta(days=1)

    @staticmethod
    def _is_market_open_ist(now_ist: Optional[datetime] = None) -> bool:
        now_ist = now_ist or datetime.now(IST)
        if now_ist.weekday() >= 5:
            return False
        mins = now_ist.hour * 60 + now_ist.minute
        return (9 * 60 + 15) <= mins <= (15 * 60 + 34)

    @classmethod
    def _is_fresh(cls, meta: Optional[tuple], start_date: date, target_eod: date, now_ist: datetime) -> bool:
        if not meta:
            return False
        min_dt_s, max_dt_s, rows_cnt, last_synced_s = meta
        if not min_dt_s or not max_dt_s or (rows_cnt or 0) < 30:
            return False

        # Only trigger deep fetch if caller asks for older history and symbol isn't already deep-synced
        grace_start = (start_date + timedelta(days=30)).strftime("%Y-%m-%d")
        if min_dt_s > grace_start and start_date >= (now_ist.date() - timedelta(days=760)) and (rows_cnt or 0) < 420:
            return False
        if min_dt_s > grace_start and start_date < (now_ist.date() - timedelta(days=800)) and (rows_cnt or 0) < 1500:
            return False

        last_synced_dt = None
        if last_synced_s:
            try:
                last_synced_dt = datetime.fromisoformat(last_synced_s)
                if last_synced_dt.tzinfo is None:
                    last_synced_dt = IST.localize(last_synced_dt)
            except Exception:
                last_synced_dt = None

        target_eod_str = target_eod.strftime("%Y-%m-%d")
        if cls._is_market_open_ist(now_ist):
            if last_synced_dt and (now_ist - last_synced_dt).total_seconds() < 3600:
                return True
            return False

        if max_dt_s >= target_eod_str:
            return True
        if last_synced_dt:
            cutoff_eod = IST.localize(datetime(target_eod.year, target_eod.month, target_eod.day, 15, 35))
            if last_synced_dt >= cutoff_eod:
                return True
        return False

    # Canonical DB key redirects for legacy/synonym symbols already stored in SQLite
    _CANONICAL_DB_REDIRECTS: Dict[str, str] = {
        "NSE:TATAMOTORS-EQ": "NSE:TMPV-EQ",
        "NSE:HAVELLES-EQ": "NSE:HAVELLS-EQ",
        "NSE:TVSMOTOR-EQ": "NSE:TVSMOTORS-EQ",
        "NSE:AMBUJACEM-EQ": "NSE:AMBUJACEMENT-EQ",
    }

    @classmethod
    def _resolve_stored_fyers_sym(cls, fyers_sym: str) -> str:
        """Redirect synonym/demerged NSE keys to their canonical SQLite key if present."""
        if fyers_sym in ("NSE:TATAMOTORS-EQ", "NSE:HAVELLES-EQ"):
            return cls._CANONICAL_DB_REDIRECTS[fyers_sym]
        alt = cls._CANONICAL_DB_REDIRECTS.get(fyers_sym)
        if not alt:
            return fyers_sym
        cls._ensure_schema()
        with cls._db_lock:
            conn = cls._connect()
            try:
                direct = conn.execute(
                    "SELECT rows_count FROM symbol_sync_meta WHERE fyers_sym = ?", (fyers_sym,)
                ).fetchone()
                if direct and (direct[0] or 0) >= 200:
                    return fyers_sym
                mapped = conn.execute(
                    "SELECT rows_count FROM symbol_sync_meta WHERE fyers_sym = ?", (alt,)
                ).fetchone()
                if mapped and (mapped[0] or 0) >= 30:
                    return alt
            finally:
                conn.close()
        return fyers_sym

    @classmethod
    def _read_df(cls, fyers_sym: str, start_date: date, end_date: date) -> pd.DataFrame:
        cls._ensure_schema()
        fyers_sym = cls._resolve_stored_fyers_sym(fyers_sym)
        start_s = start_date.strftime("%Y-%m-%d")
        end_s = end_date.strftime("%Y-%m-%d")
        with cls._db_lock:
            conn = cls._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT epoch, open, high, low, close, volume
                    FROM daily_candles
                    WHERE fyers_sym = ? AND dt >= ? AND dt <= ?
                    ORDER BY epoch ASC
                    """,
                    (fyers_sym, start_s, end_s),
                ).fetchall()
            finally:
                conn.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["epoch", "Open", "High", "Low", "Close", "Volume"])
        df["datetime"] = pd.to_datetime(df["epoch"], unit="s").dt.tz_localize("UTC").dt.tz_convert(IST)
        df.set_index("datetime", inplace=True)
        df.drop("epoch", axis=1, inplace=True)
        df = df[~df.index.duplicated(keep="last")]
        return df

    @classmethod
    def _upsert_df(
        cls,
        fyers_sym: str,
        df: pd.DataFrame,
        replace_all: bool = False,
        ignore_existing: bool = False,
    ) -> int:
        if df is None or df.empty:
            return 0
        cls._ensure_schema()
        now_iso = datetime.now(IST).isoformat()
        records = []
        for idx, row in df.iterrows():
            ts = pd.Timestamp(idx)
            if ts.tzinfo is None:
                ts = ts.tz_localize(IST)
            else:
                ts = ts.tz_convert(IST)
            epoch = int(ts.timestamp())
            dt_str = ts.strftime("%Y-%m-%d")
            records.append(
                (
                    fyers_sym,
                    dt_str,
                    epoch,
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                )
            )

        sql_stmt = (
            "INSERT OR IGNORE INTO daily_candles (fyers_sym, dt, epoch, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            if ignore_existing
            else "INSERT OR REPLACE INTO daily_candles (fyers_sym, dt, epoch, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )

        with cls._db_lock:
            conn = cls._connect()
            try:
                if replace_all:
                    conn.execute("DELETE FROM daily_candles WHERE fyers_sym = ?", (fyers_sym,))
                conn.executemany(sql_stmt, records)
                stats = conn.execute(
                    "SELECT MIN(dt), MAX(dt), COUNT(*) FROM daily_candles WHERE fyers_sym = ?",
                    (fyers_sym,),
                ).fetchone()
                min_dt, max_dt, cnt = stats if stats else (None, None, 0)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO symbol_sync_meta
                    (fyers_sym, min_dt, max_dt, rows_count, last_synced_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (fyers_sym, min_dt, max_dt, int(cnt or 0), now_iso),
                )
                conn.commit()
            finally:
                conn.close()
        return len(records)

    @classmethod
    def _touch_meta_synced_at(cls, fyers_sym: str) -> None:
        cls._ensure_schema()
        now_iso = datetime.now(IST).isoformat()
        with cls._db_lock:
            conn = cls._connect()
            try:
                conn.execute(
                    "UPDATE symbol_sync_meta SET last_synced_at = ? WHERE fyers_sym = ?",
                    (now_iso, fyers_sym),
                )
                conn.commit()
            finally:
                conn.close()

    @classmethod
    def _get_meta_and_overlap_close(cls, fyers_sym: str) -> tuple[Optional[tuple], Optional[float], Optional[float]]:
        cls._ensure_schema()
        with cls._db_lock:
            conn = cls._connect()
            try:
                meta = conn.execute(
                    "SELECT min_dt, max_dt, rows_count, last_synced_at FROM symbol_sync_meta WHERE fyers_sym = ?",
                    (fyers_sym,),
                ).fetchone()
                max_close = None
                min_close = None
                if meta and meta[1]:
                    r1 = conn.execute(
                        "SELECT close FROM daily_candles WHERE fyers_sym = ? AND dt = ?",
                        (fyers_sym, meta[1]),
                    ).fetchone()
                    if r1:
                        max_close = float(r1[0])
                if meta and meta[0]:
                    r2 = conn.execute(
                        "SELECT close FROM daily_candles WHERE fyers_sym = ? AND dt = ?",
                        (fyers_sym, meta[0]),
                    ).fetchone()
                    if r2:
                        min_close = float(r2[0])
                return meta, max_close, min_close
            finally:
                conn.close()

    @classmethod
    def _fetch_fyers_with_alias(cls, fyers_client: Any, fyers_sym: str, start_dt: date, end_dt: date) -> pd.DataFrame:
        min_accept = 10 if (end_dt - start_dt).days >= 60 else 1
        best_df = pd.DataFrame()
        df = fyers_client._fetch_raw_historical_df(fyers_sym, "D", start_dt, end_dt)
        if df is not None and not df.empty:
            if len(df) >= min_accept:
                return df
            best_df = df
        if fyers_sym in _YF_INDEX_MAP:
            return best_df
        bases = cls._candidate_alias_bases(fyers_sym)
        for cand in bases:
            alt_fyers = f"NSE:{cand}-EQ"
            if alt_fyers == fyers_sym:
                continue
            df_alt = fyers_client._fetch_raw_historical_df(alt_fyers, "D", start_dt, end_dt)
            if df_alt is not None and not df_alt.empty:
                if len(df_alt) >= min_accept:
                    return df_alt
                if len(df_alt) > len(best_df):
                    best_df = df_alt
        for cand in bases[:2]:
            alt_be = f"NSE:{cand}-BE"
            df_be = fyers_client._fetch_raw_historical_df(alt_be, "D", start_dt, end_dt)
            if df_be is not None and not df_be.empty:
                if len(df_be) >= min_accept:
                    return df_be
                if len(df_be) > len(best_df):
                    best_df = df_be
        return best_df

    @classmethod
    def get_or_sync_daily_df(
        cls,
        fyers_client: Any,
        fyers_sym: str,
        start_date: date,
        end_date: date,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Return daily OHLCV DataFrame for fyers_sym across [start_date, end_date].
        Uses local SQLite first; fetches missing recent candles from Fyers (with .NS fallback),
        or fetches deep >2Y history smoothly via adjusted .NS NSE history.
        """
        cls._ensure_schema()
        fyers_sym = cls._resolve_stored_fyers_sym(fyers_sym)
        now_ist = datetime.now(IST)
        target_eod = cls._latest_closed_trading_date(now_ist)
        meta, stored_max_close, stored_min_close = cls._get_meta_and_overlap_close(fyers_sym)

        if not force_refresh and cls._is_fresh(meta, start_date, target_eod, now_ist):
            df_local = cls._read_df(fyers_sym, start_date, end_date)
            if not df_local.empty:
                return df_local

        today_dt = now_ist.date()
        two_yr_start = today_dt - timedelta(days=FULL_SEED_DAYS)

        # If caller needs older history (>2Y) than Fyers provides and symbol isn't deep-synced yet
        if start_date < (two_yr_start - timedelta(days=30)) and (not meta or (meta[2] or 0) < 1500):
            if not meta or not meta[0] or meta[0] > (start_date + timedelta(days=45)).strftime("%Y-%m-%d"):
                yf_deep = cls._fetch_yf_nse_daily_df(fyers_sym, start_date, today_dt)
                if yf_deep is not None and not yf_deep.empty:
                    if meta and meta[0] and stored_min_close:
                        try:
                            seam = yf_deep[yf_deep.index.strftime("%Y-%m-%d") == meta[0]]
                            if not seam.empty and float(seam["Close"].iloc[-1]) > 0:
                                ratio = stored_min_close / float(seam["Close"].iloc[-1])
                                if 0.90 <= ratio <= 1.25:
                                    for c in ["Open", "High", "Low", "Close"]:
                                        yf_deep[c] = yf_deep[c] * ratio
                        except Exception:
                            pass
                    cls._upsert_df(fyers_sym, yf_deep, replace_all=False, ignore_existing=True)
                    meta, stored_max_close, stored_min_close = cls._get_meta_and_overlap_close(fyers_sym)

        can_incremental = (
            not force_refresh
            and meta is not None
            and (meta[2] or 0) >= 100
            and meta[1] is not None
        )

        if can_incremental:
            overlap_start = datetime.strptime(meta[1], "%Y-%m-%d").date()
            delta_df = cls._fetch_fyers_with_alias(fyers_client, fyers_sym, overlap_start, today_dt)
            if delta_df.empty:
                delta_df = cls._fetch_yf_nse_daily_df(fyers_sym, overlap_start, today_dt)

            if delta_df is not None and not delta_df.empty:
                split_detected = False
                if stored_max_close and stored_max_close > 0:
                    try:
                        overlap_rows = delta_df[delta_df.index.strftime("%Y-%m-%d") == meta[1]]
                        if not overlap_rows.empty:
                            new_close = float(overlap_rows["Close"].iloc[-1])
                            if abs(new_close - stored_max_close) / stored_max_close > 0.015:
                                split_detected = True
                                logger.info(
                                    f"[DailyStore] Corporate action detected on {fyers_sym} "
                                    f"({meta[1]}: {stored_max_close} -> {new_close}). Refreshing recent 2Y."
                                )
                    except Exception:
                        pass

                if split_detected:
                    full_df = cls._fetch_fyers_with_alias(fyers_client, fyers_sym, two_yr_start, today_dt)
                    if not full_df.empty:
                        cls._upsert_df(fyers_sym, full_df, replace_all=False, ignore_existing=False)
                else:
                    cls._upsert_df(fyers_sym, delta_df, replace_all=False, ignore_existing=False)
            else:
                cls._touch_meta_synced_at(fyers_sym)
        else:
            seed_start = min(start_date, two_yr_start)
            seed_end = max(end_date, today_dt)
            full_df = cls._fetch_fyers_with_alias(fyers_client, fyers_sym, seed_start, seed_end)
            if len(full_df) < 10 and (seed_end - seed_start).days >= 60:
                # Zero-fail fallback: fetch official .NS daily history directly
                yf_df = cls._fetch_yf_nse_daily_df(fyers_sym, seed_start, seed_end)
                if len(yf_df) > len(full_df):
                    full_df = yf_df
            if full_df is not None and not full_df.empty:
                stale_stub = meta is not None and (meta[2] or 0) < 10
                cls._upsert_df(fyers_sym, full_df, replace_all=(force_refresh or stale_stub), ignore_existing=False)

        return cls._read_df(fyers_sym, start_date, end_date)

    @classmethod
    def get_all_tracked_fyers_symbols(cls) -> List[str]:
        """Return 4 core NSE Index symbols + full Nifty 500 + Nifty 100 eligible symbols in Fyers format."""
        from app.services.data_fetcher import NIFTY500_SYMBOLS
        try:
            from app.services.forward_test import NIFTY100_ELIGIBLE_UNIVERSE
        except Exception:
            NIFTY100_ELIGIBLE_UNIVERSE = []

        out: List[str] = list(CORE_INDEX_SYMBOLS)
        seen = set(out)
        for s in list(NIFTY500_SYMBOLS) + list(NIFTY100_ELIGIBLE_UNIVERSE):
            clean = s.replace(".NS", "").replace(".BO", "").replace("NSE:", "").replace("-EQ", "").strip().upper()
            fsym = cls._resolve_stored_fyers_sym(f"NSE:{clean}-EQ")
            if fsym not in seen:
                seen.add(fsym)
                out.append(fsym)
        return out

    @classmethod
    def get_store_status(cls) -> Dict[str, Any]:
        cls._ensure_schema()
        with cls._db_lock:
            conn = cls._connect()
            try:
                sym_count = conn.execute("SELECT COUNT(*) FROM symbol_sync_meta").fetchone()[0]
                row_count = conn.execute("SELECT COUNT(*) FROM daily_candles").fetchone()[0]
                deep_count = conn.execute("SELECT COUNT(*) FROM symbol_sync_meta WHERE rows_count >= 1500").fetchone()[0]
                bounds = conn.execute("SELECT MIN(min_dt), MAX(max_dt) FROM symbol_sync_meta").fetchone()
            finally:
                conn.close()

        db_size_mb = round(STORE_DB_PATH.stat().st_size / (1024 * 1024), 2) if STORE_DB_PATH.exists() else 0.0
        return {
            "db_path": str(STORE_DB_PATH),
            "db_size_mb": db_size_mb,
            "stored_symbols": int(sym_count or 0),
            "deep_10_20y_symbols": int(deep_count or 0),
            "target_universe_size": len(cls.get_all_tracked_fyers_symbols()),
            "total_daily_candles": int(row_count or 0),
            "min_date": bounds[0] if bounds else None,
            "max_date": bounds[1] if bounds else None,
            "sync_job": dict(cls._sync_status),
        }

    @classmethod
    def get_health_report(cls) -> Dict[str, Any]:
        """Diagnostic health report for local Nifty 500 + Index OHLCV coverage and freshness."""
        cls._ensure_schema()
        tracked = cls.get_all_tracked_fyers_symbols()
        with cls._db_lock:
            conn = cls._connect()
            try:
                rows = conn.execute(
                    "SELECT fyers_sym, min_dt, max_dt, rows_count, last_synced_at FROM symbol_sync_meta"
                ).fetchall()
            finally:
                conn.close()

        meta_map = {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}
        missing_symbols = [s for s in tracked if s not in meta_map or (meta_map[s][2] or 0) < 30]
        now_ist = datetime.now(IST)
        target_eod_str = cls._latest_closed_trading_date(now_ist).strftime("%Y-%m-%d")

        fresh_eod_symbols = sum(
            1
            for s in tracked
            if s in meta_map
            and meta_map[s][1]
            and meta_map[s][1] >= target_eod_str
            and (meta_map[s][2] or 0) >= 30
        )
        present_count = len(tracked) - len(missing_symbols)
        stale_eod_symbols = max(0, present_count - fresh_eod_symbols)
        store_status = cls.get_store_status()
        target_size = max(1, len(tracked))
        coverage_pct = round(present_count / target_size * 100.0, 2)
        deep_coverage_pct = round(store_status["deep_10_20y_symbols"] / target_size * 100.0, 2)

        if coverage_pct >= 99.0 and fresh_eod_symbols >= int(len(tracked) * 0.95):
            status = "HEALTHY"
        elif coverage_pct >= 99.0:
            status = "PARTIAL_STALE"
        else:
            status = "SYNC_NEEDED"

        return {
            "status": status,
            "coverage_pct": coverage_pct,
            "stored_symbols": present_count,
            "target_universe_size": len(tracked),
            "missing_count": len(missing_symbols),
            "missing_symbols": missing_symbols,
            "deep_10_20y_symbols": store_status["deep_10_20y_symbols"],
            "deep_coverage_pct": deep_coverage_pct,
            "fresh_eod_symbols": fresh_eod_symbols,
            "stale_eod_symbols": stale_eod_symbols,
            "target_eod_date": target_eod_str,
            "alias_mappings_configured": len(_SYMBOL_ALIASES),
            "store_status": store_status,
        }

    @classmethod
    async def sync_full_universe(
        cls,
        force_full: bool = False,
        max_symbols: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Synchronizes 2-year Fyers daily candles (with .NS fallback) across Nifty 500 + Indices."""
        if cls._sync_status["is_running"]:
            return {"status": "ALREADY_RUNNING", **cls.get_store_status()}

        from app.services.fyers_data_client import FyersDataClient

        symbols = cls.get_all_tracked_fyers_symbols()
        if max_symbols and max_symbols > 0:
            symbols = symbols[:max_symbols]

        cls._sync_status = {
            "is_running": True,
            "mode": "2Y_EOD",
            "total_symbols": len(symbols),
            "completed_symbols": 0,
            "updated_symbols": 0,
            "cached_skipped": 0,
            "failed_symbols": 0,
            "current_symbol": "",
            "started_at": datetime.now(IST).isoformat(),
            "finished_at": None,
            "last_error": None,
        }

        def _sync_worker() -> None:
            fyers = FyersDataClient()
            fyers.connect()

            now_ist = datetime.now(IST)
            target_eod = cls._latest_closed_trading_date(now_ist)
            today_dt = now_ist.date()
            start_dt = today_dt - timedelta(days=FULL_SEED_DAYS)

            for fsym in symbols:
                cls._sync_status["current_symbol"] = fsym
                try:
                    meta, _, _ = cls._get_meta_and_overlap_close(fsym)
                    if not force_full and cls._is_fresh(meta, start_dt, target_eod, now_ist):
                        cls._sync_status["cached_skipped"] += 1
                    else:
                        is_cold = (meta is None) or force_full or ((meta[2] or 0) < 100)
                        df = cls.get_or_sync_daily_df(
                            fyers, fsym, start_dt, today_dt, force_refresh=force_full
                        )
                        if df is not None and not df.empty:
                            cls._sync_status["updated_symbols"] += 1
                        else:
                            cls._sync_status["failed_symbols"] += 1
                        time.sleep(2.6 if is_cold else 1.35)
                except Exception as exc:
                    cls._sync_status["failed_symbols"] += 1
                    cls._sync_status["last_error"] = f"{fsym}: {exc}"
                finally:
                    cls._sync_status["completed_symbols"] += 1

            cls._sync_status["current_symbol"] = ""
            cls._sync_status["is_running"] = False
            cls._sync_status["finished_at"] = datetime.now(IST).isoformat()

        await asyncio.to_thread(_sync_worker)
        return {"status": "COMPLETED", **cls.get_store_status()}

    @classmethod
    async def backfill_deep_history(
        cls,
        years: int = 20,
        max_symbols: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Backfills up to 20 years (~5,000 daily NSE sessions per stock) into daily_ohlcv_store.db
        using adjusted NSE .NS history stitched cleanly onto Fyers live recent candles.
        """
        if cls._sync_status["is_running"]:
            return {"status": "ALREADY_RUNNING", **cls.get_store_status()}

        symbols = cls.get_all_tracked_fyers_symbols()
        if max_symbols and max_symbols > 0:
            symbols = symbols[:max_symbols]

        cls._sync_status = {
            "is_running": True,
            "mode": f"DEEP_{years}Y_BACKFILL",
            "total_symbols": len(symbols),
            "completed_symbols": 0,
            "updated_symbols": 0,
            "cached_skipped": 0,
            "failed_symbols": 0,
            "current_symbol": "",
            "started_at": datetime.now(IST).isoformat(),
            "finished_at": None,
            "last_error": None,
        }

        def _backfill_worker() -> None:
            now_ist = datetime.now(IST)
            today_dt = now_ist.date()
            deep_start = today_dt - timedelta(days=int(years * 365))
            cutoff_str = (deep_start + timedelta(days=90)).strftime("%Y-%m-%d")

            for fsym in symbols:
                cls._sync_status["current_symbol"] = fsym
                try:
                    meta, _, stored_min_close = cls._get_meta_and_overlap_close(fsym)
                    if meta and meta[0] and meta[0] <= cutoff_str and (meta[2] or 0) >= 1500:
                        cls._sync_status["cached_skipped"] += 1
                    else:
                        yf_df = cls._fetch_yf_nse_daily_df(fsym, deep_start, today_dt)
                        if yf_df is not None and not yf_df.empty:
                            # Align .NS dividend-adjusted history smoothly to Fyers boundary if stored
                            if meta and meta[0] and stored_min_close and stored_min_close > 0:
                                try:
                                    seam = yf_df[yf_df.index.strftime("%Y-%m-%d") == meta[0]]
                                    if not seam.empty and float(seam["Close"].iloc[-1]) > 0:
                                        ratio = stored_min_close / float(seam["Close"].iloc[-1])
                                        if 0.90 <= ratio <= 1.25:
                                            for c in ["Open", "High", "Low", "Close"]:
                                                yf_df[c] = yf_df[c] * ratio
                                except Exception:
                                    pass
                            cls._upsert_df(fyers_sym=fsym, df=yf_df, replace_all=False, ignore_existing=True)
                            cls._sync_status["updated_symbols"] += 1
                        else:
                            cls._sync_status["failed_symbols"] += 1
                        time.sleep(0.25)
                except Exception as exc:
                    cls._sync_status["failed_symbols"] += 1
                    cls._sync_status["last_error"] = f"{fsym}: {exc}"
                finally:
                    cls._sync_status["completed_symbols"] += 1

            cls._sync_status["current_symbol"] = ""
            cls._sync_status["is_running"] = False
            cls._sync_status["finished_at"] = datetime.now(IST).isoformat()

        await asyncio.to_thread(_backfill_worker)
        return {"status": "COMPLETED", **cls.get_store_status()}

    @classmethod
    def validate_against_fyers_master(cls) -> Dict[str, Any]:
        """Validate all 504 tracked symbols against Fyers official NSE_CM.csv symbol master."""
        url = "https://public.fyers.in/sym_details/NSE_CM.csv"
        text = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", errors="ignore")
        fyers_bases = set()
        for line in text.splitlines():
            parts = line.split(",")
            if len(parts) > 9:
                sym = parts[9].strip()
                if sym.startswith("NSE:") and (sym.endswith("-EQ") or sym.endswith("-BE")):
                    base = sym.replace("NSE:", "").split("-")[0].strip()
                    if base:
                        fyers_bases.add(base)

        tracked = cls.get_all_tracked_fyers_symbols()
        direct_count = 0
        alias_count = 0
        unmatched: List[str] = []

        for fsym in tracked:
            if fsym in CORE_INDEX_SYMBOLS:
                direct_count += 1
                continue
            raw_base = (
                fsym.replace("NSE:", "")
                .replace("BSE:", "")
                .replace("-EQ", "")
                .replace("-BE", "")
                .strip()
            )
            if raw_base in fyers_bases:
                direct_count += 1
            elif any(cand in fyers_bases for cand in cls._candidate_alias_bases(fsym)):
                alias_count += 1
            else:
                unmatched.append(fsym)

        return {
            "status": "VALIDATED" if len(unmatched) == 0 else "PARTIAL",
            "total_tracked_symbols": len(tracked),
            "fyers_master_tickers_loaded": len(fyers_bases),
            "direct_matches": direct_count,
            "alias_resolved_matches": alias_count,
            "unmatched_count": len(unmatched),
            "unmatched_symbols": unmatched,
            "validated_at": datetime.now(IST).isoformat(),
        }

    @classmethod
    def run_enterprise_watchdog(cls, auto_heal: bool = True) -> Dict[str, Any]:
        """Run enterprise diagnostics: Broker TOTP, Data Store self-healing, Disk/RAM, and AI stats."""
        from app.services.fyers_data_client import FyersDataClient

        fyers = FyersDataClient()
        try:
            broker_connected = bool(fyers.connect())
        except Exception as e:
            logger.warning(f"[Watchdog] Fyers connect check failed: {e}")
            broker_connected = False
        broker_user = fyers.user_name if broker_connected and fyers.user_name else "DISCONNECTED"

        health = cls.get_health_report()
        healed_symbols: List[str] = []
        if (
            auto_heal
            and health.get("missing_count", 0) > 0
            and not cls._sync_status.get("is_running")
            and broker_connected
        ):
            today_dt = datetime.now(IST).date()
            start_dt = today_dt - timedelta(days=FULL_SEED_DAYS)
            for sym in (health.get("missing_symbols") or [])[:15]:
                try:
                    df = cls.get_or_sync_daily_df(fyers, sym, start_dt, today_dt)
                    if df is not None and not df.empty:
                        healed_symbols.append(sym)
                except Exception as exc:
                    logger.warning(f"[Watchdog] Self-heal failed for {sym}: {exc}")
            health = cls.get_health_report()

        usage = shutil.disk_usage(str(DB_DIR))
        disk_total_gb = round(usage.total / (1024 ** 3), 2)
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_used_pct = round((usage.used / max(usage.total, 1)) * 100.0, 1)

        ram_total_mb = 0.0
        ram_available_mb = 0.0
        swap_total_mb = 0.0
        swap_free_mb = 0.0
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            try:
                mem_kv: Dict[str, int] = {}
                for line in meminfo_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if ":" in line:
                        k, rest = line.split(":", 1)
                        val_kb = rest.strip().split()[0]
                        if val_kb.isdigit():
                            mem_kv[k.strip()] = int(val_kb)
                ram_total_mb = round(mem_kv.get("MemTotal", 0) / 1024.0, 1)
                ram_available_mb = round(mem_kv.get("MemAvailable", 0) / 1024.0, 1)
                swap_total_mb = round(mem_kv.get("SwapTotal", 0) / 1024.0, 1)
                swap_free_mb = round(mem_kv.get("SwapFree", 0) / 1024.0, 1)
            except Exception:
                pass

        pred_stats: Dict[str, Any] = {}
        try:
            from app.services.prediction_ledger import PredictionLedger
            pred_stats = PredictionLedger.get_global_prediction_stats()
        except Exception as e:
            logger.debug(f"[Watchdog] Prediction stats unavailable: {e}")

        empirical_stats_path = Path(_BACKEND_DIR) / "data" / "pattern_empirical_stats.json"
        overall_ok = (
            broker_connected
            and float(health.get("coverage_pct", 0.0)) >= 99.0
            and disk_free_gb >= 1.5
        )
        overall_status = "ENTERPRISE_HEALTHY" if overall_ok else "ATTENTION_REQUIRED"

        report = {
            "overall_status": overall_status,
            "checked_at": datetime.now(IST).isoformat(),
            "broker": {
                "connected": broker_connected,
                "user": broker_user,
            },
            "data_store": {
                "status": health.get("status"),
                "coverage_pct": health.get("coverage_pct"),
                "stored_symbols": health.get("stored_symbols"),
                "target_universe_size": health.get("target_universe_size"),
                "missing_count": health.get("missing_count"),
                "deep_10_20y_symbols": health.get("deep_10_20y_symbols"),
                "deep_coverage_pct": health.get("deep_coverage_pct"),
                "fresh_eod_symbols": health.get("fresh_eod_symbols"),
                "db_size_mb": (health.get("store_status") or {}).get("db_size_mb", 0.0),
                "total_daily_candles": (health.get("store_status") or {}).get("total_daily_candles", 0),
                "healed_symbols": healed_symbols,
            },
            "infrastructure": {
                "disk_total_gb": disk_total_gb,
                "disk_free_gb": disk_free_gb,
                "disk_used_pct": disk_used_pct,
                "ram_total_mb": ram_total_mb,
                "ram_available_mb": ram_available_mb,
                "swap_total_mb": swap_total_mb,
                "swap_free_mb": swap_free_mb,
            },
            "ai_calibration": {
                "prediction_stats": pred_stats,
                "empirical_stats_ready": empirical_stats_path.exists(),
            },
        }

        try:
            snap_path = Path(_BACKEND_DIR) / "data" / "system_watchdog_latest.json"
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Watchdog] Could not persist watchdog snapshot: {e}")

        return report
