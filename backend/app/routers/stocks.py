"""
Stocks Router
GET /api/v1/stocks/{symbol}             → Stock fundamental + technical snapshot
GET /api/v1/stocks/{symbol}/chart       → OHLCV chart data
GET /api/v1/stocks/{symbol}/technicals  → Technical indicators only
GET /api/v1/stocks/search               → Search stocks by name/symbol
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.stock import StockUniverse
from app.services.data_fetcher import DataFetcher
from app.services.fundamental import FundamentalAnalyzer
from app.services.technical import TechnicalAnalyzer
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/stocks", tags=["Stocks"])

fetcher = DataFetcher()
fundamental_analyzer = FundamentalAnalyzer()
technical_analyzer = TechnicalAnalyzer()


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="Symbol or company name query"),
    db: AsyncSession = Depends(get_db),
):
    """Search stocks by symbol or company name."""
    result = await db.execute(
        select(StockUniverse).where(
            (StockUniverse.symbol.ilike(f"%{q}%")) |
            (StockUniverse.company_name.ilike(f"%{q}%"))
        ).limit(20)
    )
    stocks = result.scalars().all()
    return [
        {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "current_price": s.current_price,
        }
        for s in stocks
    ]


@router.get("/universe")
async def get_universe():
    """Return the full list of symbols in the screener universe."""
    symbols = fetcher.get_nifty500_symbols()
    return {"count": len(symbols), "symbols": symbols}


@router.get("/data-store/status")
async def get_data_store_status():
    """Get storage size, symbol coverage, and sync progress of the local 2-year Nifty 500 OHLCV store."""
    from app.services.daily_history_store import DailyHistoryStore
    return DailyHistoryStore.get_store_status()


@router.post("/data-store/sync")
async def trigger_data_store_sync(
    background_tasks: BackgroundTasks,
    force_full: bool = Query(False, description="Force full 2-year re-download across Nifty 500 + Indices"),
    sync: bool = Query(False, description="Wait synchronously (for small subsets)"),
    max_symbols: Optional[int] = Query(None, description="Optional limit on number of symbols to sync"),
):
    """Trigger background or synchronous 2-year daily data store download/EOD update."""
    from app.services.daily_history_store import DailyHistoryStore
    status = DailyHistoryStore.get_store_status()
    if status["sync_job"].get("is_running"):
        return {"message": "Sync already running in background", **status}

    if sync:
        return await DailyHistoryStore.sync_full_universe(force_full=force_full, max_symbols=max_symbols)

    async def _bg():
        await DailyHistoryStore.sync_full_universe(force_full=force_full, max_symbols=max_symbols)

    background_tasks.add_task(_bg)
    return {"message": "Nifty 500 2-year daily OHLCV sync started in background", **status}


@router.get("/{symbol}")
async def get_stock_snapshot(symbol: str):
    """
    Get a complete snapshot of a stock:
    fundamentals + technicals + trade parameters.
    """
    symbol = fetcher.normalize_symbol(symbol)

    # Fetch data concurrently
    import asyncio
    info_task = fetcher.fetch_ticker_info(symbol)
    history_task = fetcher.fetch_price_history(symbol)
    info, df = await asyncio.gather(info_task, history_task)

    if info is None:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    fund = fundamental_analyzer.analyze(symbol, info)
    tech = {}
    if df is not None and not df.empty:
        tech = technical_analyzer.analyze(symbol, df)

    return {
        "symbol": symbol,
        "fundamentals": fund,
        "technicals": tech,
        "data_available": df is not None and not df.empty,
    }


@router.get("/{symbol}/chart")
async def get_stock_chart(
    symbol: str,
    days: int = Query(180, ge=30, le=500, description="Number of trading days"),
    period: str = Query("1y", description="Data period (1y, 2y, 6mo)"),
):
    """Get OHLCV chart data for a stock."""
    symbol = fetcher.normalize_symbol(symbol)
    df = await fetcher.fetch_price_history(symbol, period=period)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No chart data for {symbol}")

    chart_data = technical_analyzer.get_chart_data(df, days=days)
    return {
        "symbol": symbol,
        "period": period,
        "candles": len(chart_data),
        "data": chart_data,
    }


@router.get("/{symbol}/technicals")
async def get_stock_technicals(symbol: str):
    """Get current technical indicator values for a stock."""
    symbol = fetcher.normalize_symbol(symbol)
    df = await fetcher.fetch_price_history(symbol)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    tech = technical_analyzer.analyze(symbol, df)
    return tech


@router.get("/{symbol}/fundamentals")
async def get_stock_fundamentals(symbol: str):
    """Get fundamental metrics for a stock."""
    symbol = fetcher.normalize_symbol(symbol)
    info = await fetcher.fetch_ticker_info(symbol)

    if info is None:
        raise HTTPException(status_code=404, detail=f"No fundamental data for {symbol}")

    fund = fundamental_analyzer.analyze(symbol, info)
    return fund
