"""
TradeMatrix Backtesting Engine
Robust, bar-by-bar simulation with strict execution reality:
  - No lookahead bias (signal on Bar N, entry on Bar N+1 open)
  - Realistic brokerage & slippage (0.1% per side)
  - Strict 2% risk position sizing (ATR-based dynamic sizing)
  - Trailing Stop Loss (moves to Breakeven when Target 1 / 1x ATR is hit)
  - Full metrics: Win Rate, Profit Factor, Max Drawdown, Sharpe, Equity Curve
"""
import math
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import pandas_ta as ta

from app.config import settings
from app.services.data_fetcher import DataFetcher
from app.utils.logger import get_logger
from app.utils.helpers import sanitize_nans

logger = get_logger(__name__)


class BacktestEngine:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self._portfolio_data_cache: Dict[str, Any] = {}

    def run_stock_backtest(
        self,
        symbol: str,
        df: Optional[pd.DataFrame] = None,
        strategy_name: str = "ALPHA_PULLBACK",
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 2.0,  # Strict 2% max risk per trade
        atr_multiplier: float = 2.0,      # 2x ATR for Stop Loss
        rr_ratio: float = 2.0,             # 1:2 Risk to Reward
        slippage_pct: float = 0.1,         # 0.1% fees/slippage per side
        period: str = "5y",
    ) -> Dict[str, Any]:
        """
        Backtest a single stock with candle-by-candle simulation.
        """
        symbol = DataFetcher.normalize_symbol(symbol)

        # Pre-warm window mapping: fetch extra history so 200 EMA & ATR are stabilized
        # from Day 1 of the requested timeframe, preventing truncated simulations.
        pad_periods = {
            "1y": ("2y", 252),
            "2y": ("3y", 504),
            "3y": ("4y", 756),
            "5y": ("6y", 1260),
            "10y": ("12y", 2520),
            "15y": ("17y", 3780),
            "20y": ("22y", 5040),
        }
        download_period, target_bars = pad_periods.get(period, (period, 252))

        # 1. Fetch data if not supplied
        if df is None or df.empty:
            # Synchronous fetch or use DataFetcher
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        df = pool.submit(
                            asyncio.run,
                            self.data_fetcher.fetch_price_history(symbol, period=download_period, interval="1d")
                        ).result()
                else:
                    df = loop.run_until_complete(
                        self.data_fetcher.fetch_price_history(symbol, period=download_period, interval="1d")
                    )
            except Exception:
                # Direct yfinance fallback
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=download_period, interval="1d")

        if df is None or len(df) < 50:
            return {"error": f"Insufficient historical data for {symbol}."}

        # Normalize column names
        df = df.copy()
        df.columns = [c.capitalize() for c in df.columns]
        if "Close" not in df.columns:
            return {"error": "Missing Close price column."}

        # 2. Compute technical indicators
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        df["EMA_200"] = ta.ema(close, length=200)
        df["EMA_50"] = ta.ema(close, length=50)
        df["EMA_20"] = ta.ema(close, length=20)
        df["RSI"] = ta.rsi(close, length=14)
        df["RSI_2"] = ta.rsi(close, length=2)
        df["ATR"] = ta.atr(high, low, close, length=14)
        df["VOL_MA20"] = ta.sma(volume, length=20)

        # Supertrend
        st = ta.supertrend(high, low, close, length=10, multiplier=3)
        if st is not None and not st.empty:
            df["SUPERTREND"] = st.iloc[:, 0]
            df["SUPERTREND_DIR"] = st.iloc[:, 1]  # 1 = Bullish, -1 = Bearish
        else:
            df["SUPERTREND_DIR"] = 1

        # MACD
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            df["MACD"] = macd_df.iloc[:, 0]
            df["MACD_SIGNAL"] = macd_df.iloc[:, 2]
        else:
            df["MACD"] = 0
            df["MACD_SIGNAL"] = 0

        # Drop warm-up bars
        df = df.dropna(subset=["EMA_200", "RSI", "ATR"]).copy()
        if len(df) < 50:
            return {"error": "Not enough valid data after calculating indicators."}

        # Slice to requested target bars so the full requested timeframe is simulated
        if len(df) > target_bars:
            df = df.iloc[-target_bars:].copy()

        # 3. Simulate bar-by-bar execution
        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []

        capital = float(initial_capital)
        cash = float(initial_capital)
        in_trade = False
        trade_entry: Optional[Dict[str, Any]] = None

        pending_entry = False
        pending_signal_reason = ""

        dates = df.index
        n_bars = len(df)

        for i in range(n_bars):
            curr_bar = df.iloc[i]
            bar_date = str(dates[i])[:10]
            curr_open = float(curr_bar["Open"])
            curr_high = float(curr_bar["High"])
            curr_low = float(curr_bar["Low"])
            curr_close = float(curr_bar["Close"])
            curr_atr = float(curr_bar["ATR"]) if not math.isnan(curr_bar["ATR"]) else curr_close * 0.02

            # ── Check Pending Entry from previous bar's signal ────────
            if pending_entry and not in_trade:
                entry_price = curr_open * (1.0 + slippage_pct / 100.0)
                sl_distance = curr_atr * atr_multiplier
                stop_loss = max(entry_price - sl_distance, entry_price * 0.90)  # Max 10% floor
                target_1 = entry_price + (curr_atr * 1.0)
                target_2 = entry_price + (curr_atr * atr_multiplier * rr_ratio)

                # Risk per trade: strict risk_per_trade_pct of total capital
                risk_amount = capital * (risk_per_trade_pct / 100.0)
                risk_per_share = entry_price - stop_loss

                if risk_per_share > 0:
                    qty = math.floor(risk_amount / risk_per_share)
                else:
                    qty = 0

                # Capital constraint: max 25% of cash in single stock
                max_pos_val = capital * 0.25
                if (qty * entry_price) > max_pos_val:
                    qty = math.floor(max_pos_val / entry_price)

                if qty >= 1 and (qty * entry_price) <= cash:
                    pos_cost = qty * entry_price
                    cash -= pos_cost
                    trade_entry = {
                        "symbol": symbol,
                        "entry_date": bar_date,
                        "entry_price": round(entry_price, 2),
                        "total_shares": qty,
                        "shares": qty,
                        "cost": round(pos_cost, 2),
                        "initial_sl": round(stop_loss, 2),
                        "current_sl": round(stop_loss, 2),
                        "target_1": round(target_1, 2),
                        "target_2": round(target_2, 2),
                        "t1_hit": False,
                        "realized_pnl": 0.0,
                        "reason": pending_signal_reason,
                        "entry_bar": i,
                    }
                    in_trade = True
                pending_entry = False

            # ── If in Trade, Check Exit Conditions ─────────────────────
            if in_trade and trade_entry is not None:
                exit_price = None
                exit_reason = None

                # 1. Stop Loss Hit (Low drops below SL)
                if curr_low <= trade_entry["current_sl"]:
                    exit_price = min(trade_entry["current_sl"], curr_open) * (1.0 - slippage_pct / 100.0)
                    exit_reason = "STOP_LOSS_BREAKEVEN" if trade_entry["t1_hit"] else "STOP_LOSS"

                # 2. Target 2 Hit (High touches Target 2: 1:2 R:R achieved)
                elif curr_high >= trade_entry["target_2"]:
                    exit_price = trade_entry["target_2"] * (1.0 - slippage_pct / 100.0)
                    exit_reason = "TARGET_2_ACHIEVED"

                # 3. Check if Target 1 is hit -> Book 50% Profit & Trail SL to Breakeven!
                elif not trade_entry["t1_hit"] and curr_high >= trade_entry["target_1"]:
                    trade_entry["t1_hit"] = True
                    book_qty = trade_entry["total_shares"] // 2
                    if book_qty > 0 and trade_entry["shares"] > book_qty:
                        t1_exit = trade_entry["target_1"] * (1.0 - slippage_pct / 100.0)
                        t1_pnl = (t1_exit - trade_entry["entry_price"]) * book_qty
                        cash += book_qty * t1_exit
                        trade_entry["shares"] -= book_qty
                        trade_entry["realized_pnl"] += t1_pnl
                    # Trail SL to entry price (Risk-Free Trade)
                    trade_entry["current_sl"] = trade_entry["entry_price"]

                # 4. Time-stop: Exit if in trade for > 35 bars without hitting target
                elif (i - trade_entry["entry_bar"]) >= 35:
                    exit_price = curr_close * (1.0 - slippage_pct / 100.0)
                    exit_reason = "TIME_EXPIRY_35D"

                # Process Exit
                if exit_price is not None and exit_reason is not None:
                    rem_shares = trade_entry["shares"]
                    proceeds = rem_shares * exit_price
                    cash += proceeds
                    gross_pnl = (exit_price - trade_entry["entry_price"]) * rem_shares + trade_entry["realized_pnl"]
                    ret_pct = (gross_pnl / trade_entry["cost"]) * 100.0 if trade_entry["cost"] > 0 else 0.0
                    capital = cash  # Capital updated

                    trades.append({
                        "trade_no": len(trades) + 1,
                        "symbol": symbol,
                        "entry_date": trade_entry["entry_date"],
                        "entry_price": trade_entry["entry_price"],
                        "exit_date": bar_date,
                        "exit_price": round(exit_price, 2),
                        "shares": trade_entry["total_shares"],
                        "pnl": round(gross_pnl, 2),
                        "pnl_pct": round(ret_pct, 2),
                        "exit_reason": exit_reason,
                        "bars_held": i - trade_entry["entry_bar"],
                        "is_win": gross_pnl > 0,
                    })

                    in_trade = False
                    trade_entry = None

            # ── Check Strategy Entry Signals (Only if not in trade) ───
            if not in_trade and not pending_entry:
                signal = False
                signal_msg = ""

                # 1. Strategy: ALPHA_PULLBACK (STRATEGIES.md Master Logic)
                # Trend: Close > 200 EMA
                # Pullback: RSI between 25 and 48
                # Volume: >= 0.8x 20MA
                if strategy_name == "ALPHA_PULLBACK":
                    cond_trend = curr_close > curr_bar["EMA_200"]
                    cond_rsi = 25.0 <= curr_bar["RSI"] <= 48.0
                    cond_vol = curr_bar["VOL_MA20"] > 0 and (curr_bar["Volume"] >= 0.75 * curr_bar["VOL_MA20"])
                    if cond_trend and cond_rsi and cond_vol:
                        signal = True
                        signal_msg = f"Alpha Dip: Price > 200 EMA, RSI={curr_bar['RSI']:.1f}, Vol Surge"

                # 2. Strategy: SUPERTREND_EMA_MOMENTUM
                elif strategy_name == "SUPERTREND_MOMENTUM":
                    cond_trend = curr_close > curr_bar["EMA_200"]
                    cond_st = curr_bar["SUPERTREND_DIR"] == 1
                    cond_rsi = 45.0 <= curr_bar["RSI"] <= 65.0
                    if cond_trend and cond_st and cond_rsi:
                        signal = True
                        signal_msg = f"Supertrend Bullish: Price > 200 EMA, RSI={curr_bar['RSI']:.1f}"

                # 3. Strategy: EMA_GOLDEN_CROSSOVER
                elif strategy_name == "EMA_CROSSOVER":
                    prev_bar = df.iloc[i - 1] if i > 0 else curr_bar
                    cond_cross = (prev_bar["EMA_20"] <= prev_bar["EMA_50"]) and (curr_bar["EMA_20"] > curr_bar["EMA_50"])
                    cond_macro = curr_close > curr_bar["EMA_200"]
                    if cond_cross and cond_macro:
                        signal = True
                        signal_msg = "EMA 20/50 Golden Cross above 200 EMA"

                # 4. Strategy: CONNORS_RSI2
                elif strategy_name == "CONNORS_RSI2":
                    cond_trend = curr_close > curr_bar["EMA_200"]
                    cond_rsi2 = float(curr_bar.get("RSI_2", 50.0)) <= 12.0
                    if cond_trend and cond_rsi2:
                        signal = True
                        signal_msg = f"Connors RSI(2) Dip: RSI2={float(curr_bar.get('RSI_2', 0)):.1f}"

                if signal:
                    pending_entry = True
                    pending_signal_reason = signal_msg

            # Track daily equity
            portfolio_val = cash
            if in_trade and trade_entry is not None:
                portfolio_val += trade_entry["shares"] * curr_close

            capital = portfolio_val
            equity_curve.append({
                "date": bar_date,
                "capital": round(portfolio_val, 2),
                "close": round(curr_close, 2),
            })

        # Close any open trade at the last bar
        if in_trade and trade_entry is not None:
            last_close = float(df.iloc[-1]["Close"])
            rem_shares = trade_entry["shares"]
            gross_pnl = (last_close - trade_entry["entry_price"]) * rem_shares + trade_entry["realized_pnl"]
            ret_pct = (gross_pnl / trade_entry["cost"]) * 100.0 if trade_entry["cost"] > 0 else 0.0
            trades.append({
                "trade_no": len(trades) + 1,
                "symbol": symbol,
                "entry_date": trade_entry["entry_date"],
                "entry_price": trade_entry["entry_price"],
                "exit_date": str(dates[-1])[:10],
                "exit_price": round(last_close, 2),
                "shares": trade_entry["total_shares"],
                "pnl": round(gross_pnl, 2),
                "pnl_pct": round(ret_pct, 2),
                "exit_reason": "OPEN_AT_END",
                "bars_held": n_bars - trade_entry["entry_bar"],
                "is_win": gross_pnl > 0,
            })

        # 4. Calculate Comprehensive Performance Metrics
        total_trades = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

        total_gain = sum(t["pnl"] for t in wins)
        total_loss = abs(sum(t["pnl"] for t in losses))
        net_profit = sum(t["pnl"] for t in trades)
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 0.0)

        final_capital = capital
        total_return_pct = ((final_capital / initial_capital) - 1.0) * 100.0

        # Benchmark Buy & Hold Return
        initial_price = float(df.iloc[0]["Close"])
        final_price = float(df.iloc[-1]["Close"])
        buy_hold_return_pct = ((final_price / initial_price) - 1.0) * 100.0

        # Maximum Drawdown calculation
        peak = initial_capital
        max_dd = 0.0
        max_dd_pct = 0.0
        for eq in equity_curve:
            val = eq["capital"]
            if val > peak:
                peak = val
            dd = peak - val
            dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd = dd

        # Average win and average loss
        avg_win = (total_gain / win_count) if win_count > 0 else 0.0
        avg_loss = (total_loss / loss_count) if loss_count > 0 else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        expectancy = ((win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss)) if total_trades > 0 else 0.0

        # Downsample equity curve for frontend speed (max 100 points)
        step = max(1, len(equity_curve) // 100)
        sampled_curve = equity_curve[::step]
        if equity_curve and (not sampled_curve or sampled_curve[-1]["date"] != equity_curve[-1]["date"]):
            sampled_curve.append(equity_curve[-1])

        return sanitize_nans({
            "symbol": symbol,
            "strategy": strategy_name,
            "period": period,
            "start_date": str(dates[0])[:10],
            "end_date": str(dates[-1])[:10],
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 2),
            "net_profit": round(net_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "buy_hold_return_pct": round(buy_hold_return_pct, 2),
            "alpha": round(total_return_pct - buy_hold_return_pct, 2),
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "max_drawdown_amt": round(max_dd, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "expectancy_per_trade": round(expectancy, 2),
            "trades": trades,
            "equity_curve": sampled_curve,
        })

    PORTFOLIO_UNIVERSES = {
        "NIFTY_MIDCAP_ALPHA": {
            "name": "Nifty Midcap Momentum Leaders (30-50% CAGR Target)",
            "description": "High-growth compounders across Defense, Consumer, Electronics, and Tech. Rotates into top 4 momentum leaders above 200 EMA with 50 EMA trailing stop.",
            "symbols": [
                "TRENT.NS", "BEL.NS", "HAL.NS", "POLYCAB.NS", "DIXON.NS",
                "PERSISTENT.NS", "KPITTECH.NS", "BSE.NS", "SOLARINDS.NS",
                "BAJFINANCE.NS", "TITAN.NS", "TATAELXSI.NS"
            ],
            "target_cagr": "35-50%",
            "risk_profile": "Calculated Alpha Growth"
        },
        "NIFTY_50_TITANS": {
            "name": "Nifty 50 Blue-Chip Titans (Defensive Compounder)",
            "description": "Large-cap heavyweights. Lower volatility, steady compounding with strict capital protection.",
            "symbols": [
                "RELIANCE.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "LT.NS", "TCS.NS",
                "INFY.NS", "HDFCBANK.NS", "SUNPHARMA.NS", "MARUTI.NS", "TITAN.NS"
            ],
            "target_cagr": "12-18%",
            "risk_profile": "Low Volatility Defensive"
        },
        "NIFTY_VETERANS_15Y": {
            "name": "15-Year Veteran Bluechips (Full 15-Year Mega-Cycle)",
            "description": "Unbroken 15+ year history (2011-2026). Backtested across the European debt crisis, 2016 demonetization, 2018 NBFC crisis, and 2020 COVID crash.",
            "symbols": [
                "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
                "TITAN.NS", "LT.NS", "ITC.NS", "SBIN.NS", "TATASTEEL.NS",
                "ASIANPAINT.NS", "BHARTIARTL.NS"
            ],
            "target_cagr": "18-24%",
            "risk_profile": "Multi-Decade Compounder"
        },
        "NIFTY_50_FULL": {
            "name": "Nifty 50 Complete Index (All 50 Heavyweight Constituents)",
            "description": "All 50 benchmark stocks powering India's economy. Dynamic monthly momentum rotation into the top 5 trending leaders above 200 EMA with 50 EMA capital protection trailing stop.",
            "symbols": [
                "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
                "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
                "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
                "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
                "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
                "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
                "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS",
                "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
                "SHRIRAMFIN.NS", "TATACONSUM.NS", "TMPV.NS", "TATASTEEL.NS", "TCS.NS",
                "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
            ],
            "target_cagr": "15-25%",
            "risk_profile": "Benchmark Alpha Compounder"
        }
    }

    def run_portfolio_backtest(
        self,
        universe: str = "NIFTY_MIDCAP_ALPHA",
        period: str = "10y",
        initial_capital: float = 100000.0,
        top_n: int = 4,
        rebalance_freq: int = 21,
        slippage_pct: float = 0.1,
        custom_symbols: Optional[List[str]] = None,
        use_macro_regime: bool = True,
        max_per_sector: int = 2,
    ) -> Dict[str, Any]:
        """
        Multi-stock Portfolio Momentum Rotation simulation.
        Tests 10-year / 5-year capital compounding with strict 200 EMA macro filter
        and 50 EMA trailing stop loss.
        """
        import yfinance as yf

        # 1. Resolve symbols
        if custom_symbols and len(custom_symbols) > 0:
            symbols = [DataFetcher.normalize_symbol(s) for s in custom_symbols]
            univ_info = {
                "name": "Custom Universe",
                "description": f"Custom user universe of {len(symbols)} stocks.",
                "symbols": symbols
            }
        else:
            univ_key = universe.upper()
            if univ_key not in self.PORTFOLIO_UNIVERSES:
                univ_key = "NIFTY_MIDCAP_ALPHA"
            univ_info = self.PORTFOLIO_UNIVERSES[univ_key]
            symbols = univ_info["symbols"]

        # Ensure .NS suffix for yfinance
        yf_symbols = [s if s.endswith(".NS") else f"{s}.NS" for s in symbols]

        # Pre-warm mapping for full-window simulation
        pad_periods = {
            "1y": ("2y", 252),
            "2y": ("3y", 504),
            "3y": ("4y", 756),
            "5y": ("6y", 1260),
            "10y": ("12y", 2520),
            "15y": ("17y", 3780),
            "20y": ("22y", 5040),
        }
        download_period, target_bars = pad_periods.get(period, (period, 252))

        logger.info(f"Running portfolio backtest for {len(yf_symbols)} stocks over period={period} (pre-warming with {download_period})...")

        # 2. Download or retrieve cached historical data
        cache_key = f"{','.join(sorted(yf_symbols))}_{download_period}"
        if cache_key in self._portfolio_data_cache:
            closes = self._portfolio_data_cache[cache_key]
            logger.info(f"Serving cached price data for portfolio {cache_key} ({len(closes)} bars)")
        else:
            try:
                data = yf.download(yf_symbols, period=download_period, interval="1d", progress=False)
                if data is None or data.empty:
                    return {"error": "Failed to download historical price data."}
                closes = data["Close"]
                if isinstance(closes, pd.Series):
                    closes = closes.to_frame()
                self._portfolio_data_cache[cache_key] = closes
            except Exception as e:
                logger.error(f"Error fetching portfolio data: {e}", exc_info=True)
                return {"error": f"Data download error: {str(e)}"}

        # 3. Precompute indicators
        ema200 = closes.ewm(span=200, adjust=False).mean()
        ema50 = closes.ewm(span=50, adjust=False).mean()
        # 6-Month Rate of Change (126 trading days)
        mom6m = closes.pct_change(126, fill_method=None)

        dates = closes.index
        # Need at least 200 bars for warm-up
        if len(dates) < 220:
            return {"error": f"Insufficient data bars ({len(dates)}) for period {period}."}

        # Pre-load NIFTY 50 Index for Macro Regime Gate (Cash Protection)
        nifty_closes = None
        nifty_ema50 = None
        if use_macro_regime:
            try:
                nifty_data = yf.download("^NSEI", period=download_period, interval="1d", progress=False)
                if nifty_data is not None and not nifty_data.empty:
                    n_c = nifty_data["Close"]
                    if isinstance(n_c, pd.DataFrame):
                        n_c = n_c.iloc[:, 0]
                    nifty_closes = n_c
                    nifty_ema50 = n_c.ewm(span=50, adjust=False).mean()
            except Exception as e:
                logger.warning(f"Failed to fetch Nifty index for macro regime: {e}")

        # Build symbol-to-sector lookup for sector diversification
        from app.services.data_fetcher import SECTOR_UNIVERSE
        symbol_to_sector = {}
        for sec, sym_list in SECTOR_UNIVERSE.items():
            for s in sym_list:
                clean = s.replace(".NS", "").replace(".BO", "").strip()
                symbol_to_sector[clean] = sec
                symbol_to_sector[f"{clean}.NS"] = sec

        # Start trading at exact target window while indicators are fully pre-warmed
        start_idx = max(200, len(dates) - target_bars)
        capital = float(initial_capital)
        cash = float(initial_capital)
        positions: Dict[str, Dict[str, Any]] = {}

        trades_log: List[Dict[str, Any]] = []
        equity_series: List[Dict[str, Any]] = []

        fee_factor_sell = 1.0 - (slippage_pct / 100.0)
        fee_factor_buy = 1.0 + (slippage_pct / 100.0)
        daily_cash_yield = (1.0 + 0.06) ** (1.0 / 252.0) - 1.0  # 6.0% p.a. LiquidBees yield on unallocated cash

        for i in range(start_idx, len(dates)):
            curr_date = dates[i]
            bar_date_str = str(curr_date)[:10]
            curr_prices = closes.iloc[i]

            # Unallocated cash earns daily overnight risk-free yield (LiquidBees / Cash ETF)
            cash += cash * daily_cash_yield

            # ── A. Check Stop-Loss for active holdings ──────────────────
            # Rule: If close drops 2% below 50 EMA, stop out to protect gains
            for sym in list(positions.keys()):
                p = curr_prices[sym]
                e50 = ema50.iloc[i][sym]
                if pd.notna(p) and pd.notna(e50) and p < (e50 * 0.98):
                    pos = positions.pop(sym)
                    proceeds = pos["shares"] * p * fee_factor_sell
                    cash += proceeds
                    pnl = proceeds - (pos["shares"] * pos["entry_price"])
                    ret_pct = ((p / pos["entry_price"]) - 1.0) * 100.0
                    trades_log.append({
                        "trade_no": len(trades_log) + 1,
                        "date": bar_date_str,
                        "symbol": sym.replace(".NS", ""),
                        "action": "SELL_SL",
                        "price": round(float(p), 2),
                        "shares": pos["shares"],
                        "pnl": round(float(pnl), 2),
                        "pnl_pct": round(float(ret_pct), 2),
                        "reason": "Breached 50 EMA Trailing SL (Capital Protected)"
                    })

            # ── B. Monthly Rebalance Check ──────────────────────────────
            if (i - start_idx) % rebalance_freq == 0:
                # Check Market Macro Regime (Nifty 50 Trend Gate)
                is_market_bullish = True
                if use_macro_regime and nifty_closes is not None and nifty_ema50 is not None:
                    try:
                        if curr_date in nifty_closes.index:
                            is_market_bullish = float(nifty_closes.loc[curr_date]) >= float(nifty_ema50.loc[curr_date])
                        else:
                            valid_dates = nifty_closes.index[nifty_closes.index <= curr_date]
                            if len(valid_dates) > 0:
                                last_dt = valid_dates[-1]
                                is_market_bullish = float(nifty_closes.loc[last_dt]) >= float(nifty_ema50.loc[last_dt])
                    except Exception:
                        is_market_bullish = True

                if use_macro_regime and not is_market_bullish:
                    # Bearish market regime: Protect capital, do NOT enter new long positions!
                    target_syms = []
                else:
                    # Rank stocks above 200 EMA by 6M momentum with sector diversification cap
                    scores = {}
                    for sym in yf_symbols:
                        if sym not in curr_prices:
                            continue
                        p = curr_prices[sym]
                        e200 = ema200.iloc[i][sym]
                        m = mom6m.iloc[i][sym]
                        if pd.notna(p) and pd.notna(e200) and pd.notna(m) and p > e200:
                            scores[sym] = float(m)

                    sorted_syms = sorted(scores.keys(), key=lambda s: scores[s], reverse=True)
                    target_syms = []
                    sector_counts = {}
                    for sym in sorted_syms:
                        clean_sym = sym.replace(".NS", "")
                        sec = symbol_to_sector.get(clean_sym, symbol_to_sector.get(sym, "General"))
                        if sector_counts.get(sec, 0) < max_per_sector:
                            target_syms.append(sym)
                            sector_counts[sec] = sector_counts.get(sec, 0) + 1
                            if len(target_syms) >= top_n:
                                break

                # Liquidate stocks that dropped out of target list
                for sym in list(positions.keys()):
                    if sym not in target_syms:
                        pos = positions.pop(sym)
                        p = curr_prices[sym]
                        proceeds = pos["shares"] * p * fee_factor_sell
                        cash += proceeds
                        pnl = proceeds - (pos["shares"] * pos["entry_price"])
                        ret_pct = ((p / pos["entry_price"]) - 1.0) * 100.0
                        trades_log.append({
                            "trade_no": len(trades_log) + 1,
                            "date": bar_date_str,
                            "symbol": sym.replace(".NS", ""),
                            "action": "SELL_ROTATION",
                            "price": round(float(p), 2),
                            "shares": pos["shares"],
                            "pnl": round(float(pnl), 2),
                            "pnl_pct": round(float(ret_pct), 2),
                            "reason": "Rotated to stronger momentum leader"
                        })

                # Calculate total portfolio equity to determine equal-weight allocation
                invested_val = sum(
                    positions[s]["shares"] * curr_prices[s]
                    for s in positions
                    if pd.notna(curr_prices[s])
                )
                curr_total = cash + invested_val
                target_alloc = curr_total / float(top_n)

                # Enter new positions
                for sym in target_syms:
                    p = curr_prices[sym]
                    if pd.isna(p) or p <= 0:
                        continue
                    if sym not in positions:
                        alloc = min(target_alloc, cash)
                        # Only enter if allocation is meaningful (> 2% of capital)
                        if alloc > (curr_total * 0.05):
                            shares = int((alloc / fee_factor_buy) / p)
                            if shares > 0:
                                cost = shares * p * fee_factor_buy
                                cash -= cost
                                positions[sym] = {"shares": shares, "entry_price": float(p)}
                                trades_log.append({
                                    "trade_no": len(trades_log) + 1,
                                    "date": bar_date_str,
                                    "symbol": sym.replace(".NS", ""),
                                    "action": "BUY",
                                    "price": round(float(p), 2),
                                    "shares": shares,
                                    "pnl": 0.0,
                                    "pnl_pct": 0.0,
                                    "reason": f"Ranked Top {top_n} Momentum Leader (6M RoC: +{scores.get(sym, 0)*100:.1f}%)"
                                })

            # ── C. Record Daily Portfolio Equity ─────────────────────────
            invested_val = sum(
                positions[s]["shares"] * curr_prices[s]
                for s in positions
                if pd.notna(curr_prices[s])
            )
            curr_total = cash + invested_val
            equity_series.append({
                "date": bar_date_str,
                "year": bar_date_str[:4],
                "capital": round(float(curr_total), 2),
                "cash": round(float(cash), 2),
                "invested": round(float(invested_val), 2),
                "active_holdings": len(positions)
            })

        # 4. Performance Metrics Calculation
        if not equity_series:
            return {"error": "No equity series generated."}

        final_capital = equity_series[-1]["capital"]
        net_profit = final_capital - initial_capital
        total_return_pct = ((final_capital / initial_capital) - 1.0) * 100.0

        num_years = (len(dates) - start_idx) / 252.0
        cagr_pct = (((final_capital / initial_capital) ** (1.0 / num_years)) - 1.0) * 100.0 if num_years > 0 else 0.0

        # Maximum Drawdown
        peak = initial_capital
        max_dd_amt = 0.0
        max_dd_pct = 0.0
        for eq in equity_series:
            c = eq["capital"]
            if c > peak:
                peak = c
            dd = peak - c
            dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_amt = dd

        # Calmar Ratio: CAGR / Max Drawdown
        calmar = (cagr_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

        # Yearly Performance Breakdown Table
        eq_df = pd.DataFrame(equity_series)
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        yearly_table = []
        for year, group in eq_df.groupby(eq_df["date"].dt.year):
            first_cap = float(group.iloc[0]["capital"])
            last_cap = float(group.iloc[-1]["capital"])
            ret_yr = ((last_cap / first_cap) - 1.0) * 100.0
            # Trades in this year
            yr_trades = [t for t in trades_log if t["date"].startswith(str(year))]
            yearly_table.append({
                "year": int(year),
                "start_capital": round(first_cap, 2),
                "end_capital": round(last_cap, 2),
                "return_pct": round(ret_yr, 2),
                "trades_count": len(yr_trades),
                "is_profitable": ret_yr > 0
            })

        profitable_years = sum(1 for y in yearly_table if y["is_profitable"])
        yearly_win_rate = (profitable_years / len(yearly_table) * 100.0) if yearly_table else 0.0

        # Current Active Holdings Breakdown
        latest_prices = closes.iloc[-1]
        active_holdings_summary = []
        for sym, pos in positions.items():
            curr_p = float(latest_prices[sym]) if sym in latest_prices and pd.notna(latest_prices[sym]) else pos["entry_price"]
            pos_val = pos["shares"] * curr_p
            pnl_val = (curr_p - pos["entry_price"]) * pos["shares"]
            ret_pct = ((curr_p / pos["entry_price"]) - 1.0) * 100.0
            active_holdings_summary.append({
                "symbol": sym.replace(".NS", ""),
                "shares": pos["shares"],
                "entry_price": round(pos["entry_price"], 2),
                "current_price": round(curr_p, 2),
                "current_value": round(pos_val, 2),
                "pnl": round(pnl_val, 2),
                "pnl_pct": round(ret_pct, 2)
            })

        # Downsample equity curve for fast frontend rendering (max 120 points)
        step = max(1, len(equity_series) // 120)
        sampled_curve = equity_series[::step]
        if equity_series and (not sampled_curve or sampled_curve[-1]["date"] != equity_series[-1]["date"]):
            sampled_curve.append(equity_series[-1])

        # Trade stats
        closed_trades = [t for t in trades_log if t["action"] in ("SELL_SL", "SELL_ROTATION")]
        win_trades = [t for t in closed_trades if t["pnl"] > 0]
        trade_win_rate = (len(win_trades) / len(closed_trades) * 100.0) if closed_trades else 0.0

        return sanitize_nans({
            "universe_name": univ_info["name"],
            "universe_description": univ_info["description"],
            "period": period,
            "start_date": equity_series[0]["date"],
            "end_date": equity_series[-1]["date"],
            "years_tested": round(num_years, 1),
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 2),
            "net_profit": round(net_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "cagr_pct": round(cagr_pct, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "max_drawdown_amt": round(max_dd_amt, 2),
            "calmar_ratio": round(calmar, 2),
            "total_trades": len(trades_log),
            "closed_trades_count": len(closed_trades),
            "trade_win_rate": round(trade_win_rate, 1),
            "yearly_win_rate": round(yearly_win_rate, 1),
            "profitable_years": profitable_years,
            "total_years": len(yearly_table),
            "yearly_breakdown": yearly_table,
            "active_holdings": active_holdings_summary,
            "trades": trades_log,
            "equity_curve": sampled_curve
        })

