"""
Backtest Router - TradeMatrix
Provides API endpoints for historical backtesting and strategy performance verification.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.backtester import BacktestEngine
from app.services.data_fetcher import DataFetcher
from app.utils.logger import get_logger
from app.utils.helpers import sanitize_nans

logger = get_logger(__name__)
router = APIRouter(prefix="/backtest", tags=["Backtesting Engine"])

_engine = BacktestEngine()


class BacktestRequest(BaseModel):
    symbol: str = Field(default="RELIANCE.NS", description="Stock symbol to backtest")
    strategy: str = Field(default="ALPHA_PULLBACK", description="Strategy name")
    period: str = Field(default="3y", description="Data period (1y, 2y, 3y, 5y, 10y)")
    initial_capital: float = Field(default=100000.0, description="Initial capital in INR")
    risk_per_trade_pct: float = Field(default=2.0, description="Risk % per trade")
    atr_multiplier: float = Field(default=2.0, description="ATR multiplier for Stop Loss")
    rr_ratio: float = Field(default=2.0, description="Target Risk to Reward ratio")
    slippage_pct: float = Field(default=0.1, description="Slippage + fees % per side")


@router.get("/strategies")
async def get_strategies() -> List[Dict[str, Any]]:
    """List all available strategies with their algorithmic rules."""
    return [
        {
            "id": "ALPHA_PULLBACK",
            "name": "Alpha Pullback (Dip in Macro Uptrend)",
            "description": "Rules from STRATEGIES.md: Buys high-quality pullbacks to 20/50 EMA when the stock is in a macro bull market (Price > 200 EMA).",
            "timeframe": "Daily (Swing)",
            "rules": [
                "Macro: Price > 200 EMA (Long-term Uptrend)",
                "Support: Pullback testing 20 EMA or 50 EMA",
                "Momentum: RSI between 35 and 50 (Oversold Dip)",
                "Exit: Target 1 (1:1 R:R, SL trails to BE), Target 2 (1:2 R:R)"
            ],
            "best_for": "Quality Large & Mid-caps (Reliance, ICICI, LT, Trent)"
        },
        {
            "id": "EMA_CROSSOVER",
            "name": "20/50 EMA Golden Cross Trend Rider",
            "description": "Rides large multi-month bull market trends. Enters on 20 EMA crossing above 50 EMA and trails with ATR Stop Loss.",
            "timeframe": "Daily (Positional)",
            "rules": [
                "Macro: Price & 50 EMA > 200 EMA",
                "Trigger: 20 EMA crosses above 50 EMA",
                "Exit: 2.5x ATR Trailing Stop Loss (Rides large trends)"
            ],
            "best_for": "Strong trending sectors (Defense, Auto, PSU, Capital Goods)"
        },
        {
            "id": "CONNORS_RSI2",
            "name": "Larry Connors RSI(2) Panic Dip",
            "description": "Mean reversion system that buys extreme 2-day panic drops in strong uptrends and exits quickly on 5-day SMA.",
            "timeframe": "Daily (Short-term 2-5 days)",
            "rules": [
                "Macro: Price > 200 EMA",
                "Trigger: 2-day RSI <= 10.0 (Extreme panic selling)",
                "Exit: Price closes above 5-day SMA or 5% Stop Loss"
            ],
            "best_for": "High liquidity stocks during temporary panic days"
        }
    ]


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """
    Run candle-by-candle backtest for a specific stock and strategy.
    """
    try:
        res = _engine.run_stock_backtest(
            symbol=req.symbol,
            strategy_name=req.strategy,
            initial_capital=req.initial_capital,
            risk_per_trade_pct=req.risk_per_trade_pct,
            atr_multiplier=req.atr_multiplier,
            rr_ratio=req.rr_ratio,
            slippage_pct=req.slippage_pct,
            period=req.period,
        )
        if "error" in res:
            raise HTTPException(400, detail=res["error"])
        return sanitize_nans(res)
    except Exception as e:
        logger.error(f"Backtest error for {req.symbol}: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))


@router.get("/quick/{symbol}")
async def quick_backtest(
    symbol: str,
    strategy: str = Query("ALPHA_PULLBACK"),
    period: str = Query("3y"),
):
    """
    Instant quick backtest for single stock.
    """
    try:
        res = _engine.run_stock_backtest(
            symbol=symbol,
            strategy_name=strategy,
            period=period,
        )
        if "error" in res:
            raise HTTPException(400, detail=res["error"])
        return sanitize_nans(res)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


class PortfolioBacktestRequest(BaseModel):
    universe: str = Field(default="NIFTY_MIDCAP_ALPHA", description="Universe key")
    period: str = Field(default="10y", description="Timeframe: 3y, 5y, 10y")
    initial_capital: float = Field(default=100000.0, description="Initial starting capital in INR")
    top_n: int = Field(default=4, description="Number of momentum leaders to hold concurrently")
    rebalance_freq: int = Field(default=21, description="Rebalance frequency in trading days (~21 days = 1 month)")
    slippage_pct: float = Field(default=0.1, description="Brokerage + slippage percentage per side")
    custom_symbols: Optional[List[str]] = Field(default=None, description="Optional custom stock tickers")
    use_macro_regime: bool = Field(default=True, description="Enable Nifty 50 EMA Macro Regime Shield to protect cash in bear markets")
    max_per_sector: int = Field(default=2, description="Maximum stocks permitted concurrently from the same sector")


@router.get("/universes")
async def get_portfolio_universes() -> List[Dict[str, Any]]:
    """List available portfolio universes for 10-year compounding backtest."""
    res = []
    for key, val in _engine.PORTFOLIO_UNIVERSES.items():
        res.append({
            "id": key,
            "name": val["name"],
            "description": val["description"],
            "target_cagr": val.get("target_cagr", "20-30%"),
            "risk_profile": val.get("risk_profile", "Balanced"),
            "symbols_count": len(val["symbols"]),
            "symbols": [s.replace(".NS", "") for s in val["symbols"]]
        })
    return res


@router.post("/portfolio")
async def run_portfolio_backtest(req: PortfolioBacktestRequest):
    """
    Run multi-stock 10-Year Portfolio Momentum Compounding simulation.
    Tests dynamic rebalancing, 200 EMA macro filter, and 50 EMA trailing stop loss.
    """
    try:
        res = _engine.run_portfolio_backtest(
            universe=req.universe,
            period=req.period,
            initial_capital=req.initial_capital,
            top_n=req.top_n,
            rebalance_freq=req.rebalance_freq,
            slippage_pct=req.slippage_pct,
            custom_symbols=req.custom_symbols,
            use_macro_regime=req.use_macro_regime,
            max_per_sector=req.max_per_sector,
        )
        if "error" in res:
            raise HTTPException(400, detail=res["error"])
        return sanitize_nans(res)
    except Exception as e:
        logger.error(f"Portfolio backtest error: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))

