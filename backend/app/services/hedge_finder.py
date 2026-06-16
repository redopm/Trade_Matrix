"""
HedgeFinder — Advanced Multi-Leg Options Strategy Engine
Produces correctly structured, risk-verified hedge suggestions.
"""
from datetime import datetime

def get_quote_by_delta(q_list, target_delta):
    valid = [q for q in q_list if q.get("delta") is not None and q.get("ltp", 0) > 0]
    if not valid:
        return None
    return min(valid, key=lambda x: abs(float(x["delta"]) - target_delta))

def get_quote_by_strike(q_list, strike):
    """Get a specific quote by exact strike price."""
    matches = [q for q in q_list if q.get("strike") == strike and q.get("ltp", 0) > 0]
    return matches[0] if matches else None

def format_expiry_label(dte_days: float) -> str:
    """Returns human-readable expiry label."""
    if dte_days is None:
        return "Current Expiry"
    dte = int(dte_days)
    if dte <= 7:
        return f"Weekly Expiry ({dte}d left)"
    elif dte <= 31:
        return f"Monthly Expiry ({dte}d left)"
    else:
        return f"Quarterly Expiry ({dte}d left)"

def calc_iron_condor_max_risk(call_width, put_width, net_credit):
    """Max risk in Iron Condor = max(spread width) - net credit received."""
    return max(call_width, put_width) - net_credit

class HedgeFinder:
    @staticmethod
    def get_advanced_hedges(quotes, sentiment, analysis, dte_days=None):
        ce_quotes = sorted([q for q in quotes if q["type"] == "CE"], key=lambda x: x["strike"])
        pe_quotes = sorted([q for q in quotes if q["type"] == "PE"], key=lambda x: x["strike"], reverse=True)

        expiry_label = format_expiry_label(dte_days)

        hedges = {
            "auto_pilot": None,
            "safe": None,
            "pro": None,
            "zero_loss": None,
            "sideways": None,
            "breakout": None,
        }

        # ─────────────────────────────────────────────────────────────────────────
        # 1. SAFE HEDGE + 2. PRO HEDGE (Directional)
        # ─────────────────────────────────────────────────────────────────────────
        if sentiment in ["BULLISH", "OVERSOLD"]:
            buy_leg  = get_quote_by_delta(ce_quotes, 0.60)  # ITM CE (lower strike)
            sell_leg = get_quote_by_delta(ce_quotes, 0.25)  # OTM CE (higher strike)

            if buy_leg and sell_leg and buy_leg["strike"] < sell_leg["strike"]:
                net_premium = round(buy_leg["ltp"] - sell_leg["ltp"], 2)
                spread_width = sell_leg["strike"] - buy_leg["strike"]
                max_profit = round(spread_width - net_premium, 2)
                max_loss   = round(net_premium, 2)
                rr = round(max_profit / max_loss, 2) if max_loss > 0 else 0

                hedges["safe"] = {
                    "name": "Bull Call Spread",
                    "reason": "Limited risk directional play. Buy ITM Call, sell OTM Call to reduce premium cost.",
                    "expiry": expiry_label,
                    "legs": [
                        {"action": "BUY",  "type": "CE", "strike": buy_leg["strike"],  "entry": float(buy_leg["ltp"]),  "qty": 1},
                        {"action": "SELL", "type": "CE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1},
                    ],
                    "net_premium":     net_premium,
                    "max_loss":        max_loss,
                    "max_profit":      max_profit,
                    "risk_reward":     f"1 : {rr}",
                    "margin_required": "~ 30,000",
                }

                # Pro: Call Butterfly (ITM BUY + 2x ATM SELL + OTM BUY)
                buy_leg_2 = get_quote_by_delta(ce_quotes, 0.10)  # Far OTM wing
                if buy_leg_2 and buy_leg_2["strike"] > sell_leg["strike"]:
                    net_debit_pro  = round((buy_leg["ltp"] + buy_leg_2["ltp"]) - (2 * sell_leg["ltp"]), 2)
                    span_width     = sell_leg["strike"] - buy_leg["strike"]
                    max_profit_pro = round(span_width - net_debit_pro, 2)
                    max_loss_pro   = round(max(net_debit_pro, 0), 2)
                    rr_pro         = round(max_profit_pro / max_loss_pro, 2) if max_loss_pro > 0 else 0

                    hedges["pro"] = {
                        "name": "Call Butterfly Spread",
                        "reason": "High profit with strictly limited risk. Best when you expect a moderate up-move.",
                        "expiry": expiry_label,
                        "legs": [
                            {"action": "BUY",  "type": "CE", "strike": buy_leg["strike"],   "entry": float(buy_leg["ltp"]),   "qty": 1},
                            {"action": "SELL", "type": "CE", "strike": sell_leg["strike"],  "entry": float(sell_leg["ltp"]),  "qty": 2},
                            {"action": "BUY",  "type": "CE", "strike": buy_leg_2["strike"], "entry": float(buy_leg_2["ltp"]), "qty": 1},
                        ],
                        "net_premium":     net_debit_pro,
                        "max_loss":        max_loss_pro,
                        "max_profit":      max_profit_pro,
                        "risk_reward":     f"1 : {rr_pro}",
                        "margin_required": "~ 45,000",
                    }

        else:  # BEARISH / NEUTRAL
            buy_leg  = get_quote_by_delta(pe_quotes, -0.60)  # ITM PE (higher strike)
            sell_leg = get_quote_by_delta(pe_quotes, -0.25)  # OTM PE (lower strike)

            if buy_leg and sell_leg and buy_leg["strike"] > sell_leg["strike"]:
                net_premium = round(buy_leg["ltp"] - sell_leg["ltp"], 2)
                spread_width = buy_leg["strike"] - sell_leg["strike"]
                max_profit = round(spread_width - net_premium, 2)
                max_loss   = round(net_premium, 2)
                rr = round(max_profit / max_loss, 2) if max_loss > 0 else 0

                hedges["safe"] = {
                    "name": "Bear Put Spread",
                    "reason": "Limited risk directional play. Buy ITM Put, sell OTM Put to reduce premium cost.",
                    "expiry": expiry_label,
                    "legs": [
                        {"action": "BUY",  "type": "PE", "strike": buy_leg["strike"],  "entry": float(buy_leg["ltp"]),  "qty": 1},
                        {"action": "SELL", "type": "PE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1},
                    ],
                    "net_premium":     net_premium,
                    "max_loss":        max_loss,
                    "max_profit":      max_profit,
                    "risk_reward":     f"1 : {rr}",
                    "margin_required": "~ 30,000",
                }

                # Pro: Put Butterfly
                buy_leg_2 = get_quote_by_delta(pe_quotes, -0.10)
                if buy_leg_2 and buy_leg_2["strike"] < sell_leg["strike"]:
                    net_debit_pro  = round((buy_leg["ltp"] + buy_leg_2["ltp"]) - (2 * sell_leg["ltp"]), 2)
                    span_width     = buy_leg["strike"] - sell_leg["strike"]
                    max_profit_pro = round(span_width - net_debit_pro, 2)
                    max_loss_pro   = round(max(net_debit_pro, 0), 2)
                    rr_pro         = round(max_profit_pro / max_loss_pro, 2) if max_loss_pro > 0 else 0

                    hedges["pro"] = {
                        "name": "Put Butterfly Spread",
                        "reason": "High profit with strictly limited risk. Best when you expect a moderate down-move.",
                        "expiry": expiry_label,
                        "legs": [
                            {"action": "BUY",  "type": "PE", "strike": buy_leg["strike"],   "entry": float(buy_leg["ltp"]),   "qty": 1},
                            {"action": "SELL", "type": "PE", "strike": sell_leg["strike"],  "entry": float(sell_leg["ltp"]),  "qty": 2},
                            {"action": "BUY",  "type": "PE", "strike": buy_leg_2["strike"], "entry": float(buy_leg_2["ltp"]), "qty": 1},
                        ],
                        "net_premium":     net_debit_pro,
                        "max_loss":        max_loss_pro,
                        "max_profit":      max_profit_pro,
                        "risk_reward":     f"1 : {rr_pro}",
                        "margin_required": "~ 45,000",
                    }

        # ─────────────────────────────────────────────────────────────────────────
        # 3. SIDEWAYS HEDGE — Iron Condor (FIXED STRIKE LOGIC)
        # Rule: sell_ce < buy_ce (call spread goes UP from sell to buy)
        #       buy_pe  < sell_pe (put spread goes DOWN from sell to buy)
        # Net credit = (sell_ce + sell_pe) - (buy_ce + buy_pe)
        # ─────────────────────────────────────────────────────────────────────────
        # Sort CE ascending, PE descending so delta ordering is natural
        sell_ce = get_quote_by_delta(ce_quotes, 0.20)  # OTM CE to SELL
        buy_ce  = get_quote_by_delta(ce_quotes, 0.10)  # Further OTM CE to BUY (hedge)
        sell_pe = get_quote_by_delta(pe_quotes, -0.20) # OTM PE to SELL
        buy_pe  = get_quote_by_delta(pe_quotes, -0.10) # Further OTM PE to BUY (hedge)

        # Enforce proper spread direction
        ic_valid = (
            sell_ce and buy_ce and sell_pe and buy_pe and
            sell_ce["strike"] < buy_ce["strike"] and   # CE: sell lower, buy higher
            sell_pe["strike"] > buy_pe["strike"]        # PE: sell higher, buy lower
        )

        if ic_valid:
            net_credit     = round((sell_ce["ltp"] + sell_pe["ltp"]) - (buy_ce["ltp"] + buy_pe["ltp"]), 2)
            call_width     = buy_ce["strike"]  - sell_ce["strike"]
            put_width      = sell_pe["strike"] - buy_pe["strike"]
            max_risk       = round(max(call_width, put_width) - net_credit, 2)

            # Only suggest if we actually collect a credit AND risk:reward is tradeable (>= 1:3)
            if net_credit > 0 and max_risk > 0:
                rr_condor = round(net_credit / max_risk, 2)
                rr_display = f"1 : {round(max_risk / net_credit, 1)}"  # e.g. 1 : 4.7 (risk per unit reward)

                hedges["sideways"] = {
                    "name": "Iron Condor",
                    "reason": f"Market expected to remain between {sell_pe['strike']} - {sell_ce['strike']}. Collects premium from both sides.",
                    "expiry": expiry_label,
                    "legs": [
                        {"action": "SELL", "type": "CE", "strike": sell_ce["strike"], "entry": float(sell_ce["ltp"]), "qty": 1},
                        {"action": "BUY",  "type": "CE", "strike": buy_ce["strike"],  "entry": float(buy_ce["ltp"]),  "qty": 1},
                        {"action": "SELL", "type": "PE", "strike": sell_pe["strike"], "entry": float(sell_pe["ltp"]), "qty": 1},
                        {"action": "BUY",  "type": "PE", "strike": buy_pe["strike"],  "entry": float(buy_pe["ltp"]),  "qty": 1},
                    ],
                    "net_premium":     -net_credit,   # Negative = receive premium
                    "max_loss":        max_risk,
                    "max_profit":      net_credit,
                    "risk_reward":     rr_display,
                    "breakeven_range": f"{sell_pe['strike'] - net_credit} — {sell_ce['strike'] + net_credit}",
                    "margin_required": "~ 55,000",
                }

        # ─────────────────────────────────────────────────────────────────────────
        # 4. ZERO LOSS HEDGE — Ratio Backspread (Credit Structure)
        # ─────────────────────────────────────────────────────────────────────────
        if sentiment in ["BULLISH", "OVERSOLD"]:
            sell_rb = get_quote_by_delta(ce_quotes, 0.40)  # Slightly OTM CE SELL
            buy_rb  = get_quote_by_delta(ce_quotes, 0.15)  # Further OTM CE BUY x2

            if sell_rb and buy_rb and buy_rb["strike"] > sell_rb["strike"]:
                net_cr = round(sell_rb["ltp"] - (2 * buy_rb["ltp"]), 2)
                if net_cr <= 0:
                    buy_rb = get_quote_by_delta(ce_quotes, 0.10)
                    if buy_rb:
                        net_cr = round(sell_rb["ltp"] - (2 * buy_rb["ltp"]), 2)

                if buy_rb and net_cr > 0:
                    max_risk_rb = round((buy_rb["strike"] - sell_rb["strike"]) - net_cr, 2)
                    hedges["zero_loss"] = {
                        "name": "Call Ratio Backspread",
                        "reason": "If market falls → ZERO LOSS (keep the credit). If market surges → UNLIMITED profit. Small risk only if market pins at buy strike.",
                        "expiry": expiry_label,
                        "legs": [
                            {"action": "SELL", "type": "CE", "strike": sell_rb["strike"], "entry": float(sell_rb["ltp"]), "qty": 1},
                            {"action": "BUY",  "type": "CE", "strike": buy_rb["strike"],  "entry": float(buy_rb["ltp"]),  "qty": 2},
                        ],
                        "net_premium":     -net_cr,
                        "max_loss":        max(max_risk_rb, 0),
                        "max_profit":      "Unlimited",
                        "risk_reward":     "Extreme Positive Skew",
                        "margin_required": "~ 1,45,000",
                    }
        else:
            sell_rb = get_quote_by_delta(pe_quotes, -0.40)
            buy_rb  = get_quote_by_delta(pe_quotes, -0.15)

            if sell_rb and buy_rb and buy_rb["strike"] < sell_rb["strike"]:
                net_cr = round(sell_rb["ltp"] - (2 * buy_rb["ltp"]), 2)
                if net_cr <= 0:
                    buy_rb = get_quote_by_delta(pe_quotes, -0.10)
                    if buy_rb:
                        net_cr = round(sell_rb["ltp"] - (2 * buy_rb["ltp"]), 2)

                if buy_rb and net_cr > 0:
                    max_risk_rb = round((sell_rb["strike"] - buy_rb["strike"]) - net_cr, 2)
                    hedges["zero_loss"] = {
                        "name": "Put Ratio Backspread",
                        "reason": "If market rises → ZERO LOSS (keep the credit). If market crashes → UNLIMITED profit. Small risk only if market pins at buy strike.",
                        "expiry": expiry_label,
                        "legs": [
                            {"action": "SELL", "type": "PE", "strike": sell_rb["strike"], "entry": float(sell_rb["ltp"]), "qty": 1},
                            {"action": "BUY",  "type": "PE", "strike": buy_rb["strike"],  "entry": float(buy_rb["ltp"]),  "qty": 2},
                        ],
                        "net_premium":     -net_cr,
                        "max_loss":        max(max_risk_rb, 0),
                        "max_profit":      "Unlimited",
                        "risk_reward":     "Extreme Positive Skew",
                        "margin_required": "~ 1,45,000",
                    }

        # ─────────────────────────────────────────────────────────────────────────
        # 5. VOLATILITY BREAKOUT — Long Straddle (ATM BUY CE + BUY PE)
        # ─────────────────────────────────────────────────────────────────────────
        straddle_ce = get_quote_by_delta(ce_quotes, 0.50)
        straddle_pe = get_quote_by_delta(pe_quotes, -0.50)

        if straddle_ce and straddle_pe:
            net_debit = round(straddle_ce["ltp"] + straddle_pe["ltp"], 2)
            breakeven_up   = round(straddle_ce["strike"] + net_debit, 2)
            breakeven_down = round(straddle_pe["strike"] - net_debit, 2)

            hedges["breakout"] = {
                "name": "Long Straddle",
                "reason": f"Profit from any large move. Breakevens: >{breakeven_up} or <{breakeven_down}. Ideal before news/events.",
                "expiry": expiry_label,
                "legs": [
                    {"action": "BUY", "type": "CE", "strike": straddle_ce["strike"], "entry": float(straddle_ce["ltp"]), "qty": 1},
                    {"action": "BUY", "type": "PE", "strike": straddle_pe["strike"], "entry": float(straddle_pe["ltp"]), "qty": 1},
                ],
                "net_premium":     net_debit,
                "max_loss":        net_debit,
                "max_profit":      "Unlimited",
                "risk_reward":     "Dynamic",
                "margin_required": "~ 35,000",
            }

        # ─────────────────────────────────────────────────────────────────────────
        # AUTO-PILOT: Smart Regime Detection using PCR + DTE
        # ─────────────────────────────────────────────────────────────────────────
        pcr = analysis.get("pcr", 1.0)
        dte = int(dte_days) if dte_days else 7

        if pcr >= 1.2:
            hedges["auto_pilot"] = {
                "recommended_key": "pro",
                "regime_name": "Strong Bullish Trend",
                "reasoning": f"PCR is very high ({pcr:.2f}). Strong Put writing = bulls in control. Butterfly Spread captures directional move with limited risk.",
            }
        elif pcr <= 0.7:
            hedges["auto_pilot"] = {
                "recommended_key": "pro",
                "regime_name": "Strong Bearish Trend",
                "reasoning": f"PCR critically low ({pcr:.2f}). Aggressive call writing = bears dominant. Put Butterfly captures downside with defined risk.",
            }
        elif 0.85 <= pcr <= 1.1:
            if dte <= 3:
                # Very close to expiry — Iron Condor has too much pin risk, prefer safe directional
                hedges["auto_pilot"] = {
                    "recommended_key": "safe",
                    "regime_name": "Expiry Day — Sideways",
                    "reasoning": f"PCR neutral ({pcr:.2f}) but only {dte}d to expiry. Iron Condor pin risk is high. Use safe directional spread instead.",
                }
            else:
                hedges["auto_pilot"] = {
                    "recommended_key": "sideways",
                    "regime_name": "Range-Bound Market",
                    "reasoning": f"PCR neutral ({pcr:.2f}) with {dte}d to expiry. Market is consolidating — Iron Condor collects premium safely.",
                }
        else:
            hedges["auto_pilot"] = {
                "recommended_key": "safe",
                "regime_name": "Uncertain / Transitioning",
                "reasoning": f"PCR is {pcr:.2f} — mild directional bias. Use a safe spread to minimize risk while capturing some move.",
            }

        return hedges
