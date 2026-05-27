"""
Stocks Router
GET /api/v1/stocks/{symbol}             → Stock fundamental + technical snapshot
GET /api/v1/stocks/{symbol}/chart       → OHLCV chart data
GET /api/v1/stocks/{symbol}/technicals  → Technical indicators only
GET /api/v1/stocks/search               → Search stocks by name/symbol
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
