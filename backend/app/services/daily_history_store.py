"""
Local Nifty 500 + NSE Indices 2-Year Daily OHLCV Data Store (SQLite WAL).

Architecture:
- Persists 2 years (~729 calendar days / ~500 trading sessions) of daily candles
  at BASE_DIR / "database" / "daily_ohlcv_store.db".
- Fast Path: Returns a timezone-aware (Asia/Kolkata) DataFrame in ~1 ms directly
  from disk when already synced up to the latest NSE session.
- Delta Path: Fetches ONLY missing recent candles starting from the last stored
  date (overlapping 1 day to automatically detect stock splits/bonuses).
- Auto EOD Sync: Runs daily at 15:38 IST (Mon-Fri) to append that day's candle.
"""
import asyncio
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz

from app.config import _BACKEND_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")
DB_DIR = Path(_BACKEND_DIR) / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
STORE_DB_PATH = DB_DIR / "daily_ohlcv_store.db"

FULL_SEED_DAYS = 729  # Fyers daily limit is ~729 calendar days (2 years)

CORE_INDEX_SYMBOLS: List[str] = [
    "NSE:NIFTY50-INDEX",
    "NSE:NIFTYBANK-INDEX",
    "NSE:FINNIFTY-INDEX",
    "NSE:MIDCPNIFTY-INDEX",
]


class DailyHistoryStore:
    _db_lock = threading.RLock()
    _initialized = False
    _sync_status: Dict[str, Any] = {
        "is_running": False,
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

    @staticmethod
    def _latest_closed_trading_date(now_ist: Optional[datetime] = None) -> date:
        """Return latest expected EOD daily candle date according to IST market hours."""
        now_ist = now_ist or datetime.now(IST)
        wd = now_ist.weekday()
        mins = now_ist.hour * 60 + now_ist.minute
        if wd == 5:  # Saturday -> Friday
            return now_ist.date() - timedelta(days=1)
        if wd == 6:  # Sunday -> Friday
            return now_ist.date() - timedelta(days=2)
        # Weekday
        if mins >= (15 * 60 + 35):
            return now_ist.date()
        # Before 15:35 IST on a weekday: expect previous weekday
        if wd == 0:  # Monday -> Friday
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

        # Ensure stored history actually covers start_date (with 20-day holiday/listing grace)
        grace_start = (start_date + timedelta(days=20)).strftime("%Y-%m-%d")
        if min_dt_s > grace_start and (rows_cnt or 0) < 420:
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
            # During live session, refresh at most once every 60 minutes per symbol
            if last_synced_dt and (now_ist - last_synced_dt).total_seconds() < 3600:
                return True
            return False

        # After hours / weekends: if max_dt reaches target_eod OR we already synced after target_eod 15:35 IST (covers NSE holidays)
        if max_dt_s >= target_eod_str:
            return True
        if last_synced_dt:
            cutoff_eod = IST.localize(datetime(target_eod.year, target_eod.month, target_eod.day, 15, 35))
            if last_synced_dt >= cutoff_eod:
                return True
        return False

    @classmethod
    def _read_df(cls, fyers_sym: str, start_date: date, end_date: date) -> pd.DataFrame:
        cls._ensure_schema()
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
    def _upsert_df(cls, fyers_sym: str, df: pd.DataFrame, replace_all: bool = False) -> int:
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

        with cls._db_lock:
            conn = cls._connect()
            try:
                if replace_all:
                    conn.execute("DELETE FROM daily_candles WHERE fyers_sym = ?", (fyers_sym,))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO daily_candles
                    (fyers_sym, dt, epoch, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    records,
                )
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
    def _get_meta_and_overlap_close(cls, fyers_sym: str) -> tuple[Optional[tuple], Optional[float]]:
        cls._ensure_schema()
        with cls._db_lock:
            conn = cls._connect()
            try:
                meta = conn.execute(
                    "SELECT min_dt, max_dt, rows_count, last_synced_at FROM symbol_sync_meta WHERE fyers_sym = ?",
                    (fyers_sym,),
                ).fetchone()
                overlap_close = None
                if meta and meta[1]:
                    row = conn.execute(
                        "SELECT close FROM daily_candles WHERE fyers_sym = ? AND dt = ?",
                        (fyers_sym, meta[1]),
                    ).fetchone()
                    if row:
                        overlap_close = float(row[0])
                return meta, overlap_close
            finally:
                conn.close()

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
        Reads from local SQLite when fresh; otherwise fetches only missing delta candles
        (or seeds full 2-year history for cold symbols) with corporate-action split guard.
        """
        cls._ensure_schema()
        now_ist = datetime.now(IST)
        target_eod = cls._latest_closed_trading_date(now_ist)
        meta, stored_max_close = cls._get_meta_and_overlap_close(fyers_sym)

        if not force_refresh and cls._is_fresh(meta, start_date, target_eod, now_ist):
            df_local = cls._read_df(fyers_sym, start_date, end_date)
            if not df_local.empty:
                return df_local

        today_dt = now_ist.date()
        two_yr_start = today_dt - timedelta(days=FULL_SEED_DAYS)

        # Decide whether to do incremental delta fetch or full 2-year seed
        can_incremental = (
            not force_refresh
            and meta is not None
            and (meta[2] or 0) >= 100
            and meta[0] is not None
            and meta[1] is not None
            and meta[0] <= (max(start_date, two_yr_start) + timedelta(days=20)).strftime("%Y-%m-%d")
        )

        if can_incremental:
            overlap_start = datetime.strptime(meta[1], "%Y-%m-%d").date()
            delta_df = fyers_client._fetch_raw_historical_df(fyers_sym, "D", overlap_start, today_dt)
            if delta_df is not None and not delta_df.empty:
                # Corporate Action (Split / Bonus) Detection on overlapping max_dt
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
                                    f"({meta[1]}: {stored_max_close} -> {new_close}). Re-seeding full 2Y."
                                )
                    except Exception:
                        pass

                if split_detected:
                    full_df = fyers_client._fetch_raw_historical_df(fyers_sym, "D", two_yr_start, today_dt)
                    if full_df is not None and not full_df.empty:
                        cls._upsert_df(fyers_sym, full_df, replace_all=True)
                else:
                    cls._upsert_df(fyers_sym, delta_df, replace_all=False)
            else:
                cls._touch_meta_synced_at(fyers_sym)
        else:
            seed_start = min(start_date, two_yr_start)
            full_df = fyers_client._fetch_raw_historical_df(fyers_sym, "D", seed_start, max(end_date, today_dt))
            if full_df is not None and not full_df.empty:
                cls._upsert_df(fyers_sym, full_df, replace_all=force_refresh)

        return cls._read_df(fyers_sym, start_date, end_date)

    @classmethod
    def get_all_tracked_fyers_symbols(cls) -> List[str]:
        """Return 4 core NSE Index symbols + full Nifty 500 equity symbols in Fyers format."""
        from app.services.data_fetcher import NIFTY500_SYMBOLS

        out: List[str] = list(CORE_INDEX_SYMBOLS)
        seen = set(out)
        for s in NIFTY500_SYMBOLS:
            clean = s.replace(".NS", "").replace(".BO", "").replace("NSE:", "").replace("-EQ", "").strip().upper()
            fsym = f"NSE:{clean}-EQ"
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
                bounds = conn.execute("SELECT MIN(min_dt), MAX(max_dt) FROM symbol_sync_meta").fetchone()
            finally:
                conn.close()

        db_size_mb = round(STORE_DB_PATH.stat().st_size / (1024 * 1024), 2) if STORE_DB_PATH.exists() else 0.0
        return {
            "db_path": str(STORE_DB_PATH),
            "db_size_mb": db_size_mb,
            "stored_symbols": int(sym_count or 0),
            "target_universe_size": len(cls.get_all_tracked_fyers_symbols()),
            "total_daily_candles": int(row_count or 0),
            "min_date": bounds[0] if bounds else None,
            "max_date": bounds[1] if bounds else None,
            "sync_job": dict(cls._sync_status),
        }

    @classmethod
    async def sync_full_universe(
        cls,
        force_full: bool = False,
        max_symbols: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Synchronizes 2-year daily OHLCV candles across Nifty 500 + core NSE Indices
        with safe Fyers pacing so Option Trading / live endpoints are never starved.
        """
        if cls._sync_status["is_running"]:
            return {"status": "ALREADY_RUNNING", **cls.get_store_status()}

        from app.services.fyers_data_client import FyersDataClient

        symbols = cls.get_all_tracked_fyers_symbols()
        if max_symbols and max_symbols > 0:
            symbols = symbols[:max_symbols]

        cls._sync_status = {
            "is_running": True,
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
            if not fyers.connect():
                cls._sync_status["last_error"] = "Fyers connection failed"
                cls._sync_status["is_running"] = False
                cls._sync_status["finished_at"] = datetime.now(IST).isoformat()
                return

            now_ist = datetime.now(IST)
            target_eod = cls._latest_closed_trading_date(now_ist)
            today_dt = now_ist.date()
            start_dt = today_dt - timedelta(days=FULL_SEED_DAYS)

            for fsym in symbols:
                cls._sync_status["current_symbol"] = fsym
                try:
                    meta, _ = cls._get_meta_and_overlap_close(fsym)
                    if not force_full and cls._is_fresh(meta, start_dt, target_eod, now_ist):
                        cls._sync_status["cached_skipped"] += 1
                    else:
                        df = cls.get_or_sync_daily_df(
                            fyers, fsym, start_dt, today_dt, force_refresh=force_full
                        )
                        if df is not None and not df.empty:
                            cls._sync_status["updated_symbols"] += 1
                        else:
                            cls._sync_status["failed_symbols"] += 1
                        # Safe pace (~2.5 symbols/sec max) to stay well below Fyers 5 req/sec burst limit
                        time.sleep(0.42)
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
