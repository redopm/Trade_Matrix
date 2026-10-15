import asyncio
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import math

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

backend_path = Path("c:/project/Trade_matrix/backend")
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.data_fetcher import DataFetcher
import pandas_ta as ta
import yfinance as yf

def calculate_indian_frictions(buy_value: float, sell_value: float) -> float:
    if buy_value <= 0 or sell_value <= 0:
        return 0.0
    brokerage = 40.0
    stt = (buy_value * 0.0010) + (sell_value * 0.0010)
    stamp_duty = buy_value * 0.00015
    turnover = buy_value + sell_value
    exchange_fee = turnover * 0.0000345
    sebi_fee = turnover * 0.000001
    gst = (brokerage + exchange_fee + sebi_fee) * 0.18
    return round(brokerage + stt + stamp_duty + exchange_fee + sebi_fee + gst, 2)

def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
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

    candle_range = (h - l).replace(0, 1e-5)
    df["CANDLE_BODY"] = (c - df["Open"]).abs() / candle_range
    df["LOWER_WICK"] = (df[["Open", "Close"]].min(axis=1) - l) / candle_range
    df["UPPER_WICK"] = (h - df[["Open", "Close"]].max(axis=1)) / candle_range
    df["IS_HAMMER"] = (df["LOWER_WICK"] >= 0.55) & (df["CANDLE_BODY"] <= 0.35) & (df["UPPER_WICK"] <= 0.15)
    df["IS_BULL_ENGULF"] = (c > df["Open"]) & (c.shift(1) < df["Open"].shift(1)) & (c >= df["Open"].shift(1)) & (df["Open"] <= c.shift(1))
    return df.dropna(subset=["EMA_200", "RSI", "ATR"])

def run_simulation(symbol, df, strat_mode, macro_df=None, rr_ratio=2.5, initial_capital=100000.0):
    df = prepare_indicators(df)
    capital = initial_capital
    cash = initial_capital
    in_trade = False
    trade_entry = None
    pending_entry = False
    trades = []
    slippage_pct = 0.05
    risk_per_trade_pct = 1.5

    dates = df.index
    for i in range(len(df)):
        curr_bar = df.iloc[i]
        bar_date = str(dates[i])[:10]
        c_open = float(curr_bar["Open"])
        c_high = float(curr_bar["High"])
        c_low = float(curr_bar["Low"])
        c_close = float(curr_bar["Close"])
        c_atr = float(curr_bar["ATR"]) if not math.isnan(curr_bar["ATR"]) else c_close * 0.02

        if pending_entry and not in_trade:
            entry_price = c_open * (1.0 + slippage_pct / 100.0)
            sl_distance = c_atr * 2.0
            stop_loss = max(entry_price - sl_distance, entry_price * 0.92)
            target_1 = entry_price + (c_atr * 1.5)
            target_2 = entry_price + (sl_distance * rr_ratio)

            risk_amount = capital * (risk_per_trade_pct / 100.0)
            risk_per_share = entry_price - stop_loss
            qty = math.floor(risk_amount / risk_per_share) if risk_per_share > 0 else 0
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
                    "t1_proceeds": 0.0,
                    "entry_bar": i,
                }
                in_trade = True
            pending_entry = False

        if in_trade and trade_entry is not None:
            exit_price = None
            exit_reason = None

            if c_low <= trade_entry["current_sl"]:
                if c_open <= trade_entry["current_sl"]:
                    exit_price = c_open * (1.0 - slippage_pct / 100.0)
                else:
                    exit_price = trade_entry["current_sl"] * (1.0 - slippage_pct / 100.0)
                exit_reason = "STOP_LOSS_BREAKEVEN" if trade_entry["t1_hit"] else "STOP_LOSS"

            elif c_high >= trade_entry["target_2"]:
                if c_open >= trade_entry["target_2"]:
                    exit_price = c_open * (1.0 - slippage_pct / 100.0)
                else:
                    exit_price = trade_entry["target_2"] * (1.0 - slippage_pct / 100.0)
                exit_reason = "TARGET_2"

            elif not trade_entry["t1_hit"] and c_high >= trade_entry["target_1"]:
                trade_entry["t1_hit"] = True
                book_qty = trade_entry["total_shares"] // 2
                if book_qty > 0 and trade_entry["shares"] > book_qty:
                    if c_open >= trade_entry["target_1"]:
                        t1_exit = c_open * (1.0 - slippage_pct / 100.0)
                    else:
                        t1_exit = trade_entry["target_1"] * (1.0 - slippage_pct / 100.0)
                    t1_proceeds = book_qty * t1_exit
                    cash += t1_proceeds
                    trade_entry["shares"] -= book_qty
                    trade_entry["t1_proceeds"] = t1_proceeds
                trade_entry["current_sl"] = trade_entry["entry_price"]

            elif (i - trade_entry["entry_bar"]) >= 30:
                exit_price = c_close * (1.0 - slippage_pct / 100.0)
                exit_reason = "TIME_30D"

            if exit_price is not None and exit_reason is not None:
                rem_shares = trade_entry["shares"]
                final_proceeds = rem_shares * exit_price
                cash += final_proceeds

                t1_proceeds = trade_entry.get("t1_proceeds", 0.0) if trade_entry["t1_hit"] else 0.0
                total_sell_val = final_proceeds + t1_proceeds
                total_buy_val = trade_entry["cost"]
                gross_pnl = total_sell_val - total_buy_val

                frictions = calculate_indian_frictions(total_buy_val, total_sell_val)
                net_pnl = round(gross_pnl - frictions, 2)
                cash -= frictions

                trades.append({
                    "symbol": symbol,
                    "entry_date": trade_entry["entry_date"],
                    "exit_date": bar_date,
                    "gross_pnl": gross_pnl,
                    "frictions": frictions,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "is_win": net_pnl > 0
                })
                in_trade = False
                trade_entry = None

        if not in_trade and not pending_entry:
            c_close = float(curr_bar["Close"])
            ema_200 = float(curr_bar["EMA_200"])
            rsi = float(curr_bar["RSI"])
            vol_ratio = float(curr_bar["VOL_RATIO"])
            is_bull_candle = bool(curr_bar["IS_HAMMER"] or curr_bar["IS_BULL_ENGULF"])

            macro_bullish = True
            if macro_df is not None and bar_date in macro_df.index:
                macro_row = macro_df.loc[bar_date]
                if "EMA_200" in macro_row and macro_row["Close"] < macro_row["EMA_200"]:
                    macro_bullish = False

            signal = False
            if strat_mode == "ABLATION_1_PATTERN_ONLY":
                signal = is_bull_candle and c_close > float(curr_bar["EMA_50"])
            elif strat_mode == "ABLATION_2_MOMENTUM_ONLY":
                signal = c_close > ema_200 and (42.0 <= rsi <= 62.0)
            elif strat_mode == "ABLATION_3_VOLUME_ONLY":
                signal = vol_ratio >= 1.35 and c_close > float(curr_bar["Open"])
            elif strat_mode == "ABLATION_4_TIER2_CONFLUENCE":
                cond_trend = c_close > ema_200 and (42.0 <= rsi <= 64.0)
                cond_vol = vol_ratio >= 1.15
                cond_pat = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                signal = cond_trend and cond_vol and cond_pat
            elif strat_mode == "ABLATION_5_FULL_HIERARCHICAL":
                if macro_bullish:
                    cond_trend = c_close > ema_200 and (42.0 <= rsi <= 64.0)
                    cond_vol = vol_ratio >= 1.15
                    cond_pat = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                    signal = cond_trend and cond_vol and cond_pat
            elif strat_mode == "ABLATION_6a_ALPHA_PULLBACK_V1":
                signal = c_close > ema_200 and (25.0 <= rsi <= 48.0) and vol_ratio >= 0.80
            elif strat_mode == "ABLATION_6b_ALPHA_PULLBACK_V2":
                signal = c_close > ema_200 and (28.0 <= rsi <= 48.0) and vol_ratio >= 0.80
            elif strat_mode == "ABLATION_6c_PLUS_NIFTY_GATE":
                signal = macro_bullish and (c_close > ema_200) and (28.0 <= rsi <= 48.0) and (vol_ratio >= 0.80)
            elif strat_mode == "ABLATION_6d_PLUS_CONFIRMATION":
                cond_conf = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                signal = (c_close > ema_200) and (28.0 <= rsi <= 48.0) and (vol_ratio >= 0.80) and cond_conf
            elif strat_mode == "ABLATION_7a_SUPER_STACK_V1":
                cond_conf = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                signal = macro_bullish and (c_close > ema_200) and (28.0 <= rsi <= 48.0) and (vol_ratio >= 0.80) and cond_conf
            elif strat_mode == "ABLATION_7b_SUPER_STACK_V2":
                cond_conf = is_bull_candle or (c_close > float(curr_bar["EMA_20"]))
                signal = macro_bullish and (c_close > ema_200) and (28.0 <= rsi <= 48.0) and (vol_ratio >= 0.80) and cond_conf
            elif strat_mode == "TRIAL_8_FROZEN_CANDIDATE":
                signal = macro_bullish and (c_close > ema_200) and (28.0 <= rsi <= 48.0) and (vol_ratio >= 0.80)

            if signal:
                pending_entry = True

    return trades

def wilson_ci(wins: int, total: int, z: float = 1.96):
    if total == 0:
        return "[0.0%, 0.0%]"
    p = wins / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    lower = max(0.0, center - spread) * 100.0
    upper = min(1.0, center + spread) * 100.0
    return f"[{lower:.1f}%, {upper:.1f}%]"

async def main():
    fetcher = DataFetcher()
    symbols = ["BHARTIARTL", "BEL", "LT", "ICICIBANK"]

    nifty_raw = yf.Ticker("^NSEI").history(period="5y")
    nifty_df = nifty_raw.copy()
    nifty_df["EMA_200"] = nifty_df["Close"].ewm(span=200, adjust=False).mean()
    nifty_df.index = [str(d)[:10] for d in nifty_df.index]

    dfs = {}
    for s in symbols:
        dfs[s] = await fetcher.fetch_price_history(s, period="3y")

    strats = [
        ("Ablation 1 (Pattern Only)", "ABLATION_1_PATTERN_ONLY", 2.0),
        ("Ablation 2 (Momentum Only)", "ABLATION_2_MOMENTUM_ONLY", 2.0),
        ("Ablation 3 (Volume Only)", "ABLATION_3_VOLUME_ONLY", 2.0),
        ("Ablation 4 (Tier-2 Confluence)", "ABLATION_4_TIER2_CONFLUENCE", 2.0),
        ("Ablation 5 (Hierarchical Stack)", "ABLATION_5_FULL_HIERARCHICAL", 2.0),
        ("Ablation 6a (Alpha Pullback Dip V1)", "ABLATION_6a_ALPHA_PULLBACK_V1", 2.0),
        ("Ablation 6b (Alpha Pullback Dip V2)", "ABLATION_6b_ALPHA_PULLBACK_V2", 2.5),
        ("Ablation 6c (Alpha Pullback + Gate)", "ABLATION_6c_PLUS_NIFTY_GATE", 2.5),
        ("Ablation 6d (Alpha Pullback + Conf)", "ABLATION_6d_PLUS_CONFIRMATION", 2.5),
        ("Ablation 7a (Super Stack V1)", "ABLATION_7a_SUPER_STACK_V1", 2.0),
        ("Ablation 7b (Super Stack V2)", "ABLATION_7b_SUPER_STACK_V2", 2.5),
        ("Trial 8 (Frozen Candidate: Gate + Pullback)", "TRIAL_8_FROZEN_CANDIDATE", 2.5),
    ]

    print("\nAUTO-GENERATED CONSOLIDATED RESULTS TABLE (TRUE POOLED METRICS WITH FIXED FRICTIONS):\n")
    print("| Strategy Configuration | Trades | Win Rate % | 95% Confidence Interval (Wilson) | Profit Factor | Portfolio EV | Net PnL |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    for label, mode, rr in strats:
        all_trades = []
        for s in symbols:
            t = run_simulation(s, dfs[s], mode, macro_df=nifty_df, rr_ratio=rr)
            all_trades.extend(t)

        n = len(all_trades)
        wins = [x for x in all_trades if x["is_win"]]
        losses = [x for x in all_trades if not x["is_win"]]
        n_wins = len(wins)
        wr = (n_wins / n * 100.0) if n > 0 else 0.0
        ci = wilson_ci(n_wins, n)

        tot_gain = sum(x["net_pnl"] for x in wins)
        tot_loss = abs(sum(x["net_pnl"] for x in losses))
        net_pnl = sum(x["net_pnl"] for x in all_trades)

        pf = (tot_gain / tot_loss) if tot_loss > 0 else (99.0 if tot_gain > 0 else 0.0)
        ev = (net_pnl / n) if n > 0 else 0.0

        pnl_str = f"+₹{net_pnl:,.0f}" if net_pnl > 0 else f"-₹{abs(net_pnl):,.0f}"
        ev_str = f"+₹{ev:.1f}" if ev > 0 else f"-₹{abs(ev):.1f}"

        print(f"| **{label}** | {n} | {wr:.1f}% | {ci} | {pf:.2f} | {ev_str} | {pnl_str} |")

if __name__ == "__main__":
    asyncio.run(main())
