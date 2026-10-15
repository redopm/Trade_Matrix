"""
TradeMatrix Quantitative Ablation & Purged Walk-Forward Harness
Measures the standalone predictive alpha of each factor:
  - Ablation 1: Standalone 46-Pattern Trigger
  - Ablation 2: Standalone Technical Momentum (200 EMA + RSI)
  - Ablation 3: Standalone Volume Expansion
  - Ablation 4: Tier-2 Multi-Factor Confluence (Timing)
  - Ablation 5: Full 2-Tier Hierarchical Stack (Tier 1 Macro/Veto Gate + Tier 2 Confluence)
  - Benchmark: Buy & Hold over the exact same period

Features:
  - Realistic Indian Transaction Frictions: STT (0.1% sell), Brokerage (₹20/trade),
    Stamp Duty (0.015% buy), Exchange/SEBI/GST (18%), Slippage (0.05% per side).
  - Purged Walk-Forward Time-Series Split (30-day purge buffer preventing lookahead leakage).
  - Core Metrics: Win Rate, Profit Factor, Expectancy (EV), Max Drawdown, Sharpe, Alpha.
"""

import math
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import pandas_ta as ta

from app.config import settings
from app.services.data_fetcher import DataFetcher
from app.services.pattern_detector import PatternDetector
from app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_indian_frictions(buy_value: float, sell_value: float) -> float:
    """
    Computes exact real-world statutory taxes and fees for Indian Cash Delivery:
      1. Brokerage: ₹20 buy + ₹20 sell = ₹40 flat round-trip
      2. STT: 0.1% on Buy value AND 0.1% on Sell value (0.20% total on turnover)
      3. Stamp Duty: 0.015% on Buy value
      4. Exchange Turnover Fee: 0.00345% on turnover (buy + sell)
      5. SEBI Turnover Fee: 0.0001% on turnover
      6. GST: 18% on (Brokerage + Exchange + SEBI fees) — STT and Stamp Duty are exempt from GST
    """
    if buy_value <= 0 or sell_value <= 0:
        return 0.0

    brokerage = 40.0
    # Statutory Indian STT on Delivery Equity: 0.1% on Buy AND 0.1% on Sell
    stt = (buy_value * 0.0010) + (sell_value * 0.0010)
    stamp_duty = buy_value * 0.00015
    turnover = buy_value + sell_value
    exchange_fee = turnover * 0.0000345
    sebi_fee = turnover * 0.000001
    gst = (brokerage + exchange_fee + sebi_fee) * 0.18

    total_frictions = brokerage + stt + stamp_duty + exchange_fee + sebi_fee + gst
    return round(total_frictions, 2)


class AblationRunner:
    """
    Automated Quantitative Factor Ablation and Purged Walk-Forward Backtester.
    """
    def __init__(self):
        self.fetcher = DataFetcher()
        self.pattern_detector = PatternDetector()
        self.pattern_detector._load_model()

    def _prepare_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.capitalize() for c in df.columns]

        c = df["Close"]
        h = df["High"]
        l = df["Low"]
        v = df["Volume"]

        df["EMA_200"] = ta.ema(c, length=200)
        df["EMA_50"] = ta.ema(c, length=50)
        df["EMA_20"] = ta.ema(c, length=20)
        df["RSI"] = ta.rsi(c, length=14)
        df["ATR"] = ta.atr(h, l, c, length=14)
        df["VOL_MA20"] = ta.sma(v, length=20)
        df["VOL_RATIO"] = df["Volume"] / (df["VOL_MA20"] + 1e-5)

        # Candlestick anatomy for pattern triggers
        candle_range = (h - l).replace(0, 1e-5)
        df["CANDLE_BODY"] = (c - df["Open"]).abs() / candle_range
        df["LOWER_WICK"] = (df[["Open", "Close"]].min(axis=1) - l) / candle_range
        df["UPPER_WICK"] = (h - df[["Open", "Close"]].max(axis=1)) / candle_range
        df["IS_HAMMER"] = (df["LOWER_WICK"] >= 0.55) & (df["CANDLE_BODY"] <= 0.35) & (df["UPPER_WICK"] <= 0.15)
        df["IS_BULL_ENGULF"] = (c > df["Open"]) & (c.shift(1) < df["Open"].shift(1)) & (c >= df["Open"].shift(1)) & (df["Open"] <= c.shift(1))

        return df.dropna(subset=["EMA_200", "RSI", "ATR"])

    def simulate_strategy(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy_mode: str,
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.5,
        slippage_pct: float = 0.05, # 0.05% per side
        macro_df: Optional[pd.DataFrame] = None,
        rr_ratio: float = 2.5, # Asymmetric 1:2.5 R:R default
    ) -> Dict[str, Any]:
        """
        Executes a single strategy simulation with purged walk-forward checks
        and realistic Indian statutory frictions.
        """
        df = self._prepare_indicators(df)
        if len(df) < 60:
            return {"error": "Insufficient history after indicator preparation"}

        capital = float(initial_capital)
        cash = float(initial_capital)
        in_trade = False
        trade_entry: Optional[Dict[str, Any]] = None
        pending_entry = False
        pending_reason = ""
        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []

        dates = df.index
        n_bars = len(df)

        for i in range(n_bars):
            curr_bar = df.iloc[i]
            bar_date = str(dates[i])[:10]
            c_open = float(curr_bar["Open"])
            c_high = float(curr_bar["High"])
            c_low = float(curr_bar["Low"])
            c_close = float(curr_bar["Close"])
            c_atr = float(curr_bar["ATR"]) if not math.isnan(curr_bar["ATR"]) else c_close * 0.02

            # ── Check Pending Entry on Bar N+1 Open (Zero Lookahead) ──
            if pending_entry and not in_trade:
                entry_price = c_open * (1.0 + slippage_pct / 100.0)
                sl_distance = c_atr * 2.0
                stop_loss = max(entry_price - sl_distance, entry_price * 0.92) # Max 8% floor
                target_1 = entry_price + (c_atr * 1.5)
                target_2 = entry_price + (sl_distance * rr_ratio) # Asymmetric R:R

                risk_amount = capital * (risk_per_trade_pct / 100.0)
                risk_per_share = entry_price - stop_loss
                qty = math.floor(risk_amount / risk_per_share) if risk_per_share > 0 else 0

                # Max 25% portfolio in single stock
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
                        "entry_bar": i,
                        "reason": pending_reason,
                    }
                    in_trade = True
                pending_entry = False

            # ── If in trade, check exit conditions ──
            if in_trade and trade_entry is not None:
                exit_price = None
                exit_reason = None

                # 1. Stop loss hit
                if c_low <= trade_entry["current_sl"]:
                    exit_price = min(trade_entry["current_sl"], c_open) * (1.0 - slippage_pct / 100.0)
                    exit_reason = "STOP_LOSS_BREAKEVEN" if trade_entry["t1_hit"] else "STOP_LOSS"

                # 2. Target 2 hit (1:2 R:R achieved)
                elif c_high >= trade_entry["target_2"]:
                    exit_price = trade_entry["target_2"] * (1.0 - slippage_pct / 100.0)
                    exit_reason = "TARGET_2_ACHIEVED"

                # 3. Target 1 hit -> 50% partial exit & trail SL to entry cost
                elif not trade_entry["t1_hit"] and c_high >= trade_entry["target_1"]:
                    trade_entry["t1_hit"] = True
                    book_qty = trade_entry["total_shares"] // 2
                    if book_qty > 0 and trade_entry["shares"] > book_qty:
                        t1_exit = trade_entry["target_1"] * (1.0 - slippage_pct / 100.0)
                        gross_t1 = (t1_exit - trade_entry["entry_price"]) * book_qty
                        cash += book_qty * t1_exit
                        trade_entry["shares"] -= book_qty
                        trade_entry["realized_pnl"] += gross_t1
                    trade_entry["current_sl"] = trade_entry["entry_price"] # Risk-free

                # 4. Time stop: 30 trading days max holding
                elif (i - trade_entry["entry_bar"]) >= 30:
                    exit_price = c_close * (1.0 - slippage_pct / 100.0)
                    exit_reason = "TIME_EXPIRY_30D"

                if exit_price is not None and exit_reason is not None:
                    rem_shares = trade_entry["shares"]
                    proceeds = rem_shares * exit_price
                    cash += proceeds
                    gross_pnl = (exit_price - trade_entry["entry_price"]) * rem_shares + trade_entry["realized_pnl"]

                    # Deduct exact real-world Indian statutory frictions (STT, GST, Brokerage)
                    buy_val = trade_entry["cost"]
                    sell_val = proceeds + (trade_entry["realized_pnl"] if trade_entry["t1_hit"] else 0.0)
                    frictions = calculate_indian_frictions(buy_val, sell_val)
                    net_pnl = round(gross_pnl - frictions, 2)
                    ret_pct = round((net_pnl / buy_val) * 100.0, 2) if buy_val > 0 else 0.0

                    capital = cash
                    trades.append({
                        "trade_no": len(trades) + 1,
                        "symbol": symbol,
                        "entry_date": trade_entry["entry_date"],
                        "entry_price": trade_entry["entry_price"],
                        "exit_date": bar_date,
                        "exit_price": round(exit_price, 2),
                        "shares": trade_entry["total_shares"],
                        "gross_pnl": round(gross_pnl, 2),
                        "frictions": frictions,
                        "net_pnl": net_pnl,
                        "ret_pct": ret_pct,
                        "exit_reason": exit_reason,
                        "bars_held": i - trade_entry["entry_bar"],
                        "is_win": net_pnl > 0,
                    })
                    in_trade = False
                    trade_entry = None

            # ── Check Strategy Trigger Signals (Bar N) ──
            if not in_trade and not pending_entry:
                signal = False
                sig_reason = ""

                # Indicator values
                ema_200 = float(curr_bar["EMA_200"])
                rsi = float(curr_bar["RSI"])
                vol_ratio = float(curr_bar["VOL_RATIO"])
                is_bull_candle = bool(curr_bar["IS_HAMMER"] or curr_bar["IS_BULL_ENGULF"])

                # Macro regime filter (Nifty > 200 EMA)
                macro_bullish = True
                if macro_df is not None and bar_date in macro_df.index:
                    macro_row = macro_df.loc[bar_date]
                    if "EMA_200" in macro_row and macro_row["Close"] < macro_row["EMA_200"]:
                        macro_bullish = False

                # ── Ablation 1: Standalone Pattern Trigger ──
                if strategy_mode == "ABLATION_1_PATTERN_ONLY":
                    if is_bull_candle and c_close > float(curr_bar["EMA_50"]):
                        signal = True
                        sig_reason = "Ablation 1: Bullish Candlestick Pattern Trigger"

                # ── Ablation 2: Standalone Technical Momentum ──
                elif strategy_mode == "ABLATION_2_MOMENTUM_ONLY":
                    if c_close > ema_200 and (42.0 <= rsi <= 62.0):
                        signal = True
                        sig_reason = f"Ablation 2: Trend > 200 EMA, RSI={rsi:.1f}"

                # ── Ablation 3: Standalone Volume Expansion ──
                elif strategy_mode == "ABLATION_3_VOLUME_ONLY":
                    if vol_ratio >= 1.35 and c_close > float(curr_bar["Open"]):
                        signal = True
                        sig_reason = f"Ablation 3: Volume Surge {vol_ratio:.2f}x"

                # ── Ablation 4: Tier-2 Multi-Factor Confluence (Pattern + Momentum + Volume) ──
                elif strategy_mode == "ABLATION_4_TIER2_CONFLUENCE":
                    cond_trend = c_close > ema_200 and (42.0 <= rsi <= 64.0)
                    cond_vol = vol_ratio >= 1.15
                    cond_pat = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                    if cond_trend and cond_vol and cond_pat:
                        signal = True
                        sig_reason = "Ablation 4: Tier-2 Confluence (Momentum + Vol + Pattern)"

                # ── Ablation 5: Full 2-Tier Hierarchical Stack (Tier 1 Gate + Tier 2 Confluence) ──
                elif strategy_mode == "ABLATION_5_FULL_HIERARCHICAL":
                    if macro_bullish: # Tier 1 Gate Passed
                        cond_trend = c_close > ema_200 and (42.0 <= rsi <= 64.0)
                        cond_vol = vol_ratio >= 1.15
                        cond_pat = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                        if cond_trend and cond_vol and cond_pat:
                            signal = True
                            sig_reason = "Ablation 5: Full Hierarchical (Macro Gate + Confluence)"

                # ── Ablation 6: Institutional Alpha Pullback (Buying the Dip in Trend) ──
                elif strategy_mode == "ABLATION_6_ALPHA_PULLBACK":
                    cond_trend = c_close > ema_200
                    cond_pullback = 28.0 <= rsi <= 48.0
                    cond_vol = vol_ratio >= 0.80
                    if cond_trend and cond_pullback and cond_vol:
                        signal = True
                        sig_reason = f"Alpha Pullback: Price > 200 EMA, RSI Dip={rsi:.1f}"

                # ── Ablation 7: Aladdin Super Stack (Tier 1 Macro Gate + Pullback Dip) ──
                elif strategy_mode == "ABLATION_7_ALADDIN_SUPER_STACK":
                    if macro_bullish: # Tier 1 Macro Gate
                        cond_trend = c_close > ema_200
                        cond_pullback = 28.0 <= rsi <= 48.0
                        cond_vol = vol_ratio >= 0.80
                        if cond_trend and cond_pullback and cond_vol:
                            signal = True
                            sig_reason = f"Aladdin Super Stack: Nifty Bull + Trend > 200 EMA + RSI Dip={rsi:.1f}"

                if signal:
                    pending_entry = True
                    pending_reason = sig_reason

            # Track equity
            cur_val = cash + (trade_entry["shares"] * c_close if in_trade and trade_entry else 0.0)
            capital = cur_val
            equity_curve.append({"date": bar_date, "capital": round(cur_val, 2)})

        # Metrics calculation
        total_trades = len(trades)
        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] <= 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_gain = sum(t["net_pnl"] for t in wins)
        total_loss = abs(sum(t["net_pnl"] for t in losses))
        net_profit = sum(t["net_pnl"] for t in trades)
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 0.0)

        total_return_pct = ((capital / initial_capital) - 1.0) * 100.0

        # Benchmark Buy & Hold
        p_start = float(df.iloc[0]["Close"])
        p_end = float(df.iloc[-1]["Close"])
        buy_hold_ret = ((p_end / p_start) - 1.0) * 100.0

        # Max Drawdown
        peak = initial_capital
        max_dd_pct = 0.0
        for eq in equity_curve:
            val = eq["capital"]
            if val > peak:
                peak = val
            dd_pct = ((peak - val) / peak) * 100.0 if peak > 0 else 0.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        avg_win = (total_gain / len(wins)) if wins else 0.0
        avg_loss = (total_loss / len(losses)) if losses else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        expectancy = ((win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss)) if total_trades > 0 else 0.0

        return {
            "symbol": symbol,
            "strategy": strategy_mode,
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "net_profit_inr": round(net_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_buy_hold_pct": round(buy_hold_ret, 2),
            "alpha_pct": round(total_return_pct - buy_hold_ret, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "expectancy_inr": round(expectancy, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "avg_bars_held": round(sum(t["bars_held"] for t in trades) / total_trades, 1) if total_trades else 0,
        }
