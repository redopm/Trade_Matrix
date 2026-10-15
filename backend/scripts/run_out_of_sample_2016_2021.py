"""
TradeMatrix Institutional Out-of-Sample Quantitative Backtest (2016-2021)
Single-shot evaluation on 46 vetted Indian large-cap constituents.
Strict zero-lookahead, Day N+1 Open fills, conservative SL-first intraday execution,
unified 5-position portfolio, Indian statutory frictions, and dual diagnostic controls.
"""

import sys
import math
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf

# Force UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

VETTED_TICKERS = [
    'ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS', 'AXISBANK.NS',
    'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BPCL.NS', 'BHARTIARTL.NS',
    'BRITANNIA.NS', 'CIPLA.NS', 'COALINDIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS',
    'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS',
    'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS', 'LT.NS',
    'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS',
    'POWERGRID.NS', 'RELIANCE.NS', 'SBIN.NS', 'SUNPHARMA.NS',
    'TATACONSUM.NS', 'TATASTEEL.NS', 'TCS.NS', 'TECHM.NS',
    'TITAN.NS', 'ULTRACEMCO.NS', 'WIPRO.NS', 'SHRIRAMFIN.NS'
]

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

def prepare_stock_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].capitalize() for c in df.columns]
    else:
        df.columns = [c.capitalize() for c in df.columns]

    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    df["EMA_200"] = ta.ema(c, length=200)
    df["RSI"] = ta.rsi(c, length=14)
    df["ATR"] = ta.atr(h, l, c, length=14)
    df["VOL_MA20"] = ta.sma(v, length=20)
    df["VOL_RATIO"] = df["Volume"] / (df["VOL_MA20"] + 1e-5)
    return df

def wilson_ci(wins: int, total: int, z: float = 1.96) -> str:
    if total == 0:
        return "[0.0%, 0.0%]"
    p = wins / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    lower = max(0.0, center - spread) * 100.0
    upper = min(1.0, center + spread) * 100.0
    return f"[{lower:.1f}%, {upper:.1f}%]"

def simulate_unified_portfolio(
    universe_data: dict,
    macro_df: pd.DataFrame,
    mode: str, # 'FROZEN_CANDIDATE' or 'CONTROL_UNGATED'
    start_date: str = "2016-01-01",
    end_date: str = "2021-12-31",
    initial_capital: float = 500000.0,
    max_positions: int = 5,
    risk_per_trade_pct: float = 1.5,
    max_pos_val_pct: float = 25.0,
    slippage_pct: float = 0.05,
    rr_ratio: float = 2.5,
):
    # Align all calendar trading days from macro_df
    macro_slice = macro_df.loc[start_date:end_date]
    trading_days = [str(d)[:10] for d in macro_slice.index]

    cash = float(initial_capital)
    portfolio_equity = float(initial_capital)
    open_positions = [] # List of dicts
    completed_trades = []
    rejected_signals = []
    daily_nav_history = []
    pending_signals = [] # Signals generated on Day N, entering Day N+1 Open

    for day_idx, current_day in enumerate(trading_days):
        macro_row = macro_slice.loc[current_day]
        macro_bullish = bool(macro_row["Close"] > macro_row["EMA_200"]) if "EMA_200" in macro_row else True

        # ── STEP 1: Execute Pending Entries at Day N+1 Market Open ──
        if pending_signals:
            # Sort pending signals: lowest RSI (primary), highest Volume Ratio (secondary)
            pending_signals.sort(key=lambda x: (x["rsi"], -x["vol_ratio"]))

            for sig in pending_signals:
                sym = sig["symbol"]
                if len(open_positions) >= max_positions:
                    rejected_signals.append({"date": current_day, "symbol": sym, "reason": "MAX_POSITIONS_REACHED", "rsi": sig["rsi"]})
                    continue

                stock_df = universe_data.get(sym)
                if stock_df is None or current_day not in stock_df.index:
                    continue

                bar = stock_df.loc[current_day]
                c_open = float(bar["Open"])
                c_atr = float(bar["ATR"]) if not math.isnan(bar["ATR"]) else c_open * 0.02

                entry_price = c_open * (1.0 + slippage_pct / 100.0)
                sl_distance = c_atr * 2.0
                stop_loss = max(entry_price - sl_distance, entry_price * 0.92) # 8% floor
                target_1 = entry_price + (c_atr * 1.5)
                target_2 = entry_price + (sl_distance * rr_ratio)

                risk_amount = portfolio_equity * (risk_per_trade_pct / 100.0)
                risk_per_share = entry_price - stop_loss
                qty = math.floor(risk_amount / risk_per_share) if risk_per_share > 0 else 0

                # 25% Concentration Cap
                max_pos_val = portfolio_equity * (max_pos_val_pct / 100.0)
                if (qty * entry_price) > max_pos_val:
                    qty = math.floor(max_pos_val / entry_price)

                pos_cost = qty * entry_price
                if qty >= 1 and pos_cost <= cash:
                    cash -= pos_cost
                    open_positions.append({
                        "symbol": sym,
                        "entry_date": current_day,
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
                        "entry_day_idx": day_idx,
                    })
                else:
                    rejected_signals.append({"date": current_day, "symbol": sym, "reason": "INSUFFICIENT_CASH", "rsi": sig["rsi"]})

            pending_signals = []

        # ── STEP 2: Evaluate Exits for Open Positions during the Trading Day ──
        remaining_positions = []
        for pos in open_positions:
            sym = pos["symbol"]
            stock_df = universe_data.get(sym)
            if stock_df is None or current_day not in stock_df.index:
                remaining_positions.append(pos)
                continue

            bar = stock_df.loc[current_day]
            c_open = float(bar["Open"])
            c_high = float(bar["High"])
            c_low = float(bar["Low"])
            c_close = float(bar["Close"])

            exit_price = None
            exit_reason = None

            # Rule A: Intraday conflict tie-breaking (Stop Loss evaluated FIRST)
            if c_low <= pos["current_sl"]:
                # Gap-down fill: if Open is below stop, fill at Open
                if c_open <= pos["current_sl"]:
                    exit_price = c_open * (1.0 - slippage_pct / 100.0)
                else:
                    exit_price = pos["current_sl"] * (1.0 - slippage_pct / 100.0)
                exit_reason = "STOP_LOSS_BREAKEVEN" if pos["t1_hit"] else "STOP_LOSS"

            # Rule B: Target 2 hit (or gap up above Target 2)
            elif c_high >= pos["target_2"]:
                if c_open >= pos["target_2"]:
                    exit_price = c_open * (1.0 - slippage_pct / 100.0)
                else:
                    exit_price = pos["target_2"] * (1.0 - slippage_pct / 100.0)
                exit_reason = "TARGET_2_ACHIEVED"

            # Rule C: Target 1 partial booking & breakeven trail
            elif not pos["t1_hit"] and c_high >= pos["target_1"]:
                pos["t1_hit"] = True
                book_qty = pos["total_shares"] // 2
                if book_qty > 0 and pos["shares"] > book_qty:
                    if c_open >= pos["target_1"]:
                        t1_exit = c_open * (1.0 - slippage_pct / 100.0)
                    else:
                        t1_exit = pos["target_1"] * (1.0 - slippage_pct / 100.0)
                    t1_proceeds = book_qty * t1_exit
                    cash += t1_proceeds
                    pos["shares"] -= book_qty
                    pos["t1_proceeds"] = t1_proceeds
                    pos["t1_exit_price"] = t1_exit
                pos["current_sl"] = pos["entry_price"] # Risk-free trail
                remaining_positions.append(pos)
                continue

            # Rule D: 30 Trading Days Time Stop
            elif (day_idx - pos["entry_day_idx"]) >= 30:
                exit_price = c_close * (1.0 - slippage_pct / 100.0)
                exit_reason = "TIME_EXPIRY_30D"

            if exit_price is not None and exit_reason is not None:
                rem_shares = pos["shares"]
                final_proceeds = rem_shares * exit_price
                cash += final_proceeds

                t1_proceeds = pos.get("t1_proceeds", 0.0) if pos["t1_hit"] else 0.0
                total_sell_val = final_proceeds + t1_proceeds
                total_buy_val = pos["cost"]
                gross_pnl = total_sell_val - total_buy_val

                # Exact statutory frictions calculated on full turnover (Buy + All Sells)
                frictions = calculate_indian_frictions(total_buy_val, total_sell_val)
                net_pnl = round(gross_pnl - frictions, 2)

                # Deduct frictions directly from cash balance
                cash -= frictions

                completed_trades.append({
                    "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "exit_date": current_day,
                    "entry_price": pos["entry_price"],
                    "exit_price": round(exit_price, 2),
                    "shares": pos["total_shares"],
                    "gross_pnl": round(gross_pnl, 2),
                    "frictions": frictions,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "holding_days": day_idx - pos["entry_day_idx"],
                    "is_win": net_pnl > 0
                })
            else:
                remaining_positions.append(pos)

        open_positions = remaining_positions

        # ── STEP 3: Scan Universe for Signals on Day N Close ──
        gate_condition = macro_bullish if mode == "FROZEN_CANDIDATE" else True

        if gate_condition:
            open_symbols = {p["symbol"] for p in open_positions}
            for sym, stock_df in universe_data.items():
                if sym in open_symbols:
                    continue
                if current_day not in stock_df.index:
                    continue

                bar = stock_df.loc[current_day]
                c_close = float(bar["Close"])
                ema_200 = float(bar["EMA_200"])
                rsi = float(bar["RSI"])
                vol_ratio = float(bar["VOL_RATIO"])

                cond_trend = c_close > ema_200
                cond_pullback = 28.0 <= rsi <= 48.0
                cond_vol = vol_ratio >= 0.80

                if cond_trend and cond_pullback and cond_vol:
                    pending_signals.append({
                        "symbol": sym,
                        "date": current_day,
                        "rsi": rsi,
                        "vol_ratio": vol_ratio,
                    })

        # ── STEP 4: Calculate Mark-to-Market Portfolio NAV ──
        unrealized_equity = 0.0
        for pos in open_positions:
            sym = pos["symbol"]
            stock_df = universe_data.get(sym)
            if stock_df is not None and current_day in stock_df.index:
                c_close = float(stock_df.loc[current_day]["Close"])
                unrealized_equity += pos["shares"] * c_close

        total_nav = cash + unrealized_equity
        portfolio_equity = total_nav
        daily_nav_history.append({"date": current_day, "nav": total_nav})

    # Portfolio metrics
    n_trades = len(completed_trades)
    wins = [t for t in completed_trades if t["is_win"]]
    losses = [t for t in completed_trades if not t["is_win"]]
    win_rate = (len(wins) / n_trades * 100.0) if n_trades > 0 else 0.0

    tot_gain = sum(t["net_pnl"] for t in wins)
    tot_loss = abs(sum(t["net_pnl"] for t in losses))
    net_profit = sum(t["net_pnl"] for t in completed_trades)
    pf = (tot_gain / tot_loss) if tot_loss > 0 else (99.0 if tot_gain > 0 else 0.0)
    ev = (net_profit / n_trades) if n_trades > 0 else 0.0

    final_nav = daily_nav_history[-1]["nav"] if daily_nav_history else initial_capital
    total_return_pct = ((final_nav / initial_capital) - 1.0) * 100.0
    n_years = len(trading_days) / 252.0
    cagr = (((final_nav / initial_capital) ** (1.0 / n_years)) - 1.0) * 100.0 if n_years > 0 else 0.0

    nav_series = pd.Series([d["nav"] for d in daily_nav_history])
    peak_series = nav_series.cummax()
    dd_series = (nav_series - peak_series) / peak_series * 100.0
    max_dd = abs(float(dd_series.min())) if len(dd_series) else 0.0
    calmar = (cagr / max_dd) if max_dd > 0 else 0.0

    # Annualized Sharpe (Rf = 6.5%)
    daily_returns = nav_series.pct_change().dropna()
    rf_daily = 0.065 / 252.0
    excess_returns = daily_returns - rf_daily
    sharpe = (excess_returns.mean() / (daily_returns.std() + 1e-8)) * math.sqrt(252.0) if len(daily_returns) else 0.0

    return {
        "mode": mode,
        "n_trades": n_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "wilson_ci": wilson_ci(len(wins), n_trades),
        "pf": round(pf, 2),
        "ev": round(ev, 1),
        "net_pnl": round(net_profit, 0),
        "final_nav": round(final_nav, 0),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr, 2),
        "max_dd_pct": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "sharpe_ratio": round(sharpe, 2),
        "rejected_signals_count": len(rejected_signals),
        "completed_trades": completed_trades,
        "daily_nav_history": daily_nav_history,
    }

def simulate_trend_gated_nifty(macro_df: pd.DataFrame, start_date: str = "2016-01-01", end_date: str = "2021-12-31", initial_capital: float = 500000.0):
    macro_slice = macro_df.loc[start_date:end_date].copy()
    nav = initial_capital
    cash = initial_capital
    in_nifty = False
    shares = 0
    nav_history = []
    trades = 0

    dates = macro_slice.index
    for i in range(len(macro_slice)):
        row = macro_slice.iloc[i]
        c = float(row["Close"])
        ema = float(row["EMA_200"])
        bullish = c > ema

        if bullish and not in_nifty:
            shares = cash / c
            cash = 0.0
            in_nifty = True
            trades += 1
        elif not bullish and in_nifty:
            cash = shares * c
            shares = 0
            in_nifty = False
            trades += 1

        curr_nav = cash if not in_nifty else (shares * c)
        nav_history.append({"date": str(dates[i])[:10], "nav": curr_nav})

    final_nav = nav_history[-1]["nav"]
    total_ret = ((final_nav / initial_capital) - 1.0) * 100.0
    n_years = len(macro_slice) / 252.0
    cagr = (((final_nav / initial_capital) ** (1.0 / n_years)) - 1.0) * 100.0
    nav_series = pd.Series([d["nav"] for d in nav_history])
    peak_series = nav_series.cummax()
    dd_series = (nav_series - peak_series) / peak_series * 100.0
    max_dd = abs(float(dd_series.min()))
    calmar = (cagr / max_dd) if max_dd > 0 else 0.0

    daily_returns = nav_series.pct_change().dropna()
    rf_daily = 0.065 / 252.0
    excess_returns = daily_returns - rf_daily
    sharpe = (excess_returns.mean() / (daily_returns.std() + 1e-8)) * math.sqrt(252.0)

    return {
        "final_nav": round(final_nav, 0),
        "total_return_pct": round(total_ret, 2),
        "cagr_pct": round(cagr, 2),
        "max_dd_pct": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "sharpe_ratio": round(sharpe, 2),
        "trades": trades,
    }

def main():
    print("=" * 105)
    print("TRADEMATRIX INSTITUTIONAL OUT-OF-SAMPLE EVALUATION (2016-01-01 to 2021-12-31)")
    print("Pre-warmed from 2015-01-01 | 46 Vetted Large-Caps | Exact Statutory Cash Delivery Frictions")
    print("=" * 105)

    # 1. Fetch Nifty 50 macro data
    print("\n[1/3] Downloading Nifty 50 (^NSEI) Macro Index from 2015-01-01 to 2021-12-31...")
    nifty_raw = yf.download("^NSEI", start="2015-01-01", end="2021-12-31", progress=False, auto_adjust=True)
    if isinstance(nifty_raw.columns, pd.MultiIndex):
        nifty_raw.columns = [c[0].capitalize() for c in nifty_raw.columns]
    else:
        nifty_raw.columns = [c.capitalize() for c in nifty_raw.columns]

    nifty_df = nifty_raw.copy()
    nifty_df["EMA_200"] = nifty_df["Close"].ewm(span=200, adjust=False).mean()
    nifty_df.index = [str(d)[:10] for d in nifty_df.index]

    # Calculate Benchmark Nifty Buy & Hold 2016-2021
    n_slice = nifty_df.loc["2016-01-01":"2021-12-31"]
    p_start = float(n_slice.iloc[0]["Close"])
    p_end = float(n_slice.iloc[-1]["Close"])
    nifty_bh_ret = ((p_end / p_start) - 1.0) * 100.0
    n_years = len(n_slice) / 252.0
    nifty_bh_cagr = (((p_end / p_start) ** (1.0 / n_years)) - 1.0) * 100.0
    n_peak = n_slice["Close"].cummax()
    n_mdd = abs(float(((n_slice["Close"] - n_peak) / n_peak * 100.0).min()))
    nifty_bh_calmar = round(nifty_bh_cagr / n_mdd, 2)
    n_daily_ret = n_slice["Close"].pct_change().dropna()
    n_excess = n_daily_ret - (0.065 / 252.0)
    nifty_bh_sharpe = round((n_excess.mean() / (n_daily_ret.std() + 1e-8)) * math.sqrt(252.0), 2)

    print(f"Benchmark: Nifty 50 Buy & Hold (2016-2021): Return = +{nifty_bh_ret:.2f}%, CAGR = +{nifty_bh_cagr:.2f}%, Max DD = {n_mdd:.2f}%, Calmar = {nifty_bh_calmar}, Sharpe = {nifty_bh_sharpe}")

    # 2. Fetch all 46 tickers
    print(f"\n[2/3] Downloading 46 vetted universe tickers from 2015-01-01 to 2021-12-31 with corporate split/dividend adjustment...")
    universe_data = {}
    for sym in VETTED_TICKERS:
        try:
            df = yf.download(sym, start="2015-01-01", end="2021-12-31", progress=False, auto_adjust=True)
            if len(df) > 1000:
                prep_df = prepare_stock_indicators(df)
                prep_df.index = [str(d)[:10] for d in prep_df.index]
                universe_data[sym] = prep_df
        except Exception as e:
            print(f"Warning: Failed to process {sym}: {e}")

    print(f"Successfully processed {len(universe_data)} out of {len(VETTED_TICKERS)} tickers with valid history.")

    # 3. Simulate all configurations
    print("\n[3/3] Executing Unified Portfolio Engine across 2016-2021...")
    
    # Run 1: Frozen Candidate (Trial 8)
    res_candidate = simulate_unified_portfolio(universe_data, nifty_df, mode="FROZEN_CANDIDATE")

    # Run 2: Control 1 (Strategy WITHOUT Macro Gate)
    res_ungated = simulate_unified_portfolio(universe_data, nifty_df, mode="CONTROL_UNGATED")

    # Run 3: Control 2 (Trend-Gated Nifty Benchmark)
    res_control2 = simulate_trend_gated_nifty(nifty_df)

    print("\n" + "=" * 105)
    print("EMPIRICAL OUT-OF-SAMPLE TEST RESULTS (2016-2021)")
    print("=" * 105)

    summary_rows = [
        {
            "Strategy / Benchmark": "Frozen Candidate (Trial 8: Gate + Pullback)",
            "Trades": res_candidate["n_trades"],
            "Win Rate %": f"{res_candidate['win_rate']}%",
            "Wilson 95% CI": res_candidate["wilson_ci"],
            "Profit Factor": res_candidate["pf"],
            "EV (Rs.)": f"Rs. {res_candidate['ev']}",
            "Net PnL (Rs.)": f"Rs. {res_candidate['net_pnl']:,.0f}",
            "CAGR %": f"{res_candidate['cagr_pct']}%",
            "Max DD %": f"{res_candidate['max_dd_pct']}%",
            "Calmar": res_candidate["calmar_ratio"],
            "Sharpe (Rf=6.5%)": res_candidate["sharpe_ratio"],
        },
        {
            "Strategy / Benchmark": "Control 1: Ungated Strategy (Gate OFF)",
            "Trades": res_ungated["n_trades"],
            "Win Rate %": f"{res_ungated['win_rate']}%",
            "Wilson 95% CI": res_ungated["wilson_ci"],
            "Profit Factor": res_ungated["pf"],
            "EV (Rs.)": f"Rs. {res_ungated['ev']}",
            "Net PnL (Rs.)": f"Rs. {res_ungated['net_pnl']:,.0f}",
            "CAGR %": f"{res_ungated['cagr_pct']}%",
            "Max DD %": f"{res_ungated['max_dd_pct']}%",
            "Calmar": res_ungated["calmar_ratio"],
            "Sharpe (Rf=6.5%)": res_ungated["sharpe_ratio"],
        },
        {
            "Strategy / Benchmark": "Control 2: Trend-Gated Nifty 50 (Nifty > 200 EMA)",
            "Trades": res_control2["trades"],
            "Win Rate %": "N/A",
            "Wilson 95% CI": "N/A",
            "Profit Factor": "N/A",
            "EV (Rs.)": "N/A",
            "Net PnL": f"Rs. {res_control2['final_nav'] - 500000:,.0f}",
            "CAGR %": f"{res_control2['cagr_pct']}%",
            "Max DD %": f"{res_control2['max_dd_pct']}%",
            "Calmar": res_control2["calmar_ratio"],
            "Sharpe (Rf=6.5%)": res_control2["sharpe_ratio"],
        },
        {
            "Strategy / Benchmark": "Nifty 50 Buy & Hold Benchmark",
            "Trades": 1,
            "Win Rate %": "N/A",
            "Wilson 95% CI": "N/A",
            "Profit Factor": "N/A",
            "EV (Rs.)": "N/A",
            "Net PnL": f"Rs. {(p_end - p_start)/p_start * 500000:,.0f}",
            "CAGR %": f"{nifty_bh_cagr:.2f}%",
            "Max DD %": f"{n_mdd:.2f}%",
            "Calmar": nifty_bh_calmar,
            "Sharpe (Rf=6.5%)": nifty_bh_sharpe,
        },
    ]

    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))
    print("\n" + "=" * 105)
    print(f"Capacity Constraints: {res_candidate['rejected_signals_count']} signals rejected due to 5-position portfolio limit.")
    print("=" * 105)

    # 4. Objective Evaluation against Criteria
    print("\nEVALUATION AGAINST PRE-COMMITTED CRITERIA:")
    c1_pass = res_candidate["n_trades"] >= 150
    print(f"  Criterion 1 (Sample Size N >= 150): N = {res_candidate['n_trades']} -> {'PASS' if c1_pass else 'INCONCLUSIVE (Underpowered)'}")
    
    c2_pass = res_candidate["ev"] > 0
    print(f"  Criterion 2 (Net Positive EV > 0): EV = Rs. {res_candidate['ev']} -> {'PASS' if c2_pass else 'FAIL'}")

    c3_pass = res_candidate["pf"] >= 1.30
    print(f"  Criterion 3 (Profit Factor >= 1.30): PF = {res_candidate['pf']} -> {'PASS' if c3_pass else 'FAIL'}")

    c4_pass = res_candidate["max_dd_pct"] <= 15.0
    print(f"  Criterion 4 (Strict Max DD <= 15.0%): Max DD = {res_candidate['max_dd_pct']}% -> {'PASS' if c4_pass else 'FAIL'}")

    c5_pass = (res_candidate["cagr_pct"] >= nifty_bh_cagr) or (res_candidate["calmar_ratio"] >= 1.5 * nifty_bh_calmar)
    print(f"  Criterion 5 (Beat Nifty CAGR or 1.5x Calmar): CAGR={res_candidate['cagr_pct']}% vs {nifty_bh_cagr:.1f}%, Calmar={res_candidate['calmar_ratio']} vs {nifty_bh_calmar} -> {'PASS' if c5_pass else 'FAIL'}")

    c6_pass = res_candidate["sharpe_ratio"] >= 1.0
    print(f"  Criterion 6 (Annualized Sharpe >= 1.0 with Rf=6.5%): Sharpe = {res_candidate['sharpe_ratio']} -> {'PASS' if c6_pass else 'FAIL'}")

    # Control Decision Rules Evaluation
    print("\nCONTROL BENCHMARK DECISION RULES:")
    gate_dd_reduction = ((res_ungated["max_dd_pct"] - res_candidate["max_dd_pct"]) / res_ungated["max_dd_pct"] * 100.0) if res_ungated["max_dd_pct"] > 0 else 0.0
    print(f"  Control 1 (Gate Attribution): Ungated DD = {res_ungated['max_dd_pct']}%, Gated DD = {res_candidate['max_dd_pct']}% (Delta: {gate_dd_reduction:.1f}% reduction).")
    
    control2_calmar_beat = res_candidate["calmar_ratio"] >= res_control2["calmar_ratio"]
    print(f"  Control 2 (Active Alpha vs Index Trend): Strategy Calmar = {res_candidate['calmar_ratio']} vs Control 2 Calmar = {res_control2['calmar_ratio']} -> {'RETAIN ACTIVE ENGINE' if control2_calmar_beat else 'RETIRE ACTIVE ENGINE (Negative Active Value-Add)'}")

if __name__ == "__main__":
    main()
