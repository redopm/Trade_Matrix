def get_quote_by_delta(q_list, target_delta):
    valid = [q for q in q_list if q.get("delta") is not None and q.get("ltp", 0) > 0]
    if not valid: return None
    return min(valid, key=lambda x: abs(float(x["delta"]) - target_delta))

class HedgeFinder:
    @staticmethod
    def get_advanced_hedges(quotes, sentiment, analysis):
        ce_quotes = [q for q in quotes if q["type"] == "CE"]
        pe_quotes = [q for q in quotes if q["type"] == "PE"]
        
        hedges = {
            "auto_pilot": None,
            "safe": None,
            "pro": None,
            "zero_loss": None,
            "sideways": None,
            "breakout": None
        }

        # 1. SAFE HEDGE & 2. PRO HEDGE (Directional)
        if sentiment in ["BULLISH", "OVERSOLD"]:
            buy_leg = get_quote_by_delta(ce_quotes, 0.60)
            sell_leg = get_quote_by_delta(ce_quotes, 0.20)
            
            if buy_leg and sell_leg and buy_leg["strike"] < sell_leg["strike"]:
                # Safe Hedge: Bull Call Spread
                net_premium = buy_leg["ltp"] - sell_leg["ltp"]
                max_profit = (sell_leg["strike"] - buy_leg["strike"]) - net_premium
                rr = max_profit / net_premium if net_premium > 0 else 0
                
                hedges["safe"] = {
                    "name": "Bull Call Spread",
                    "reason": "Limited risk directional play. Buys ITM Call and sells OTM Call to reduce cost.",
                    "legs": [
                        {"action": "BUY", "type": "CE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 1},
                        {"action": "SELL", "type": "CE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1}
                    ],
                    "net_premium": round(net_premium, 2),
                    "max_loss": round(net_premium, 2),
                    "max_profit": round(max_profit, 2),
                    "risk_reward": f"1 : {round(rr, 2)}",
                    "margin_required": "~ 30,000"
                }

                # Pro Hedge: Call Butterfly Spread (Buy 1 ITM, Sell 2 ATM, Buy 1 OTM)
                buy_leg_2 = get_quote_by_delta(ce_quotes, 0.10) # Far OTM wing
                
                if buy_leg_2 and buy_leg_2["strike"] > sell_leg["strike"]:
                    net_premium_pro = (buy_leg["ltp"] + buy_leg_2["ltp"]) - (2 * sell_leg["ltp"])
                    spread_width = sell_leg["strike"] - buy_leg["strike"]
                    max_profit_pro = spread_width - net_premium_pro
                    rr_pro = max_profit_pro / net_premium_pro if net_premium_pro > 0 else 0
                    
                    hedges["pro"] = {
                        "name": "Call Butterfly Spread",
                        "reason": "High profit & STRICTLY LIMITED risk. Excellent Risk:Reward ratio for directional moves.",
                        "legs": [
                            {"action": "BUY", "type": "CE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 1},
                            {"action": "SELL", "type": "CE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 2},
                            {"action": "BUY", "type": "CE", "strike": buy_leg_2["strike"], "entry": float(buy_leg_2["ltp"]), "qty": 1}
                        ],
                        "net_premium": round(net_premium_pro, 2),
                        "max_loss": round(net_premium_pro, 2) if net_premium_pro > 0 else 0,
                        "max_profit": round(max_profit_pro, 2),
                        "risk_reward": f"1 : {round(rr_pro, 2)}",
                        "margin_required": "~ 45,000"
                    }
                
        else: # BEARISH or NEUTRAL directional fallback
            buy_leg = get_quote_by_delta(pe_quotes, -0.60)
            sell_leg = get_quote_by_delta(pe_quotes, -0.20)
            
            if buy_leg and sell_leg and buy_leg["strike"] > sell_leg["strike"]:
                # Safe Hedge: Bear Put Spread
                net_premium = buy_leg["ltp"] - sell_leg["ltp"]
                max_profit = (buy_leg["strike"] - sell_leg["strike"]) - net_premium
                rr = max_profit / net_premium if net_premium > 0 else 0
                
                hedges["safe"] = {
                    "name": "Bear Put Spread",
                    "reason": "Limited risk directional play. Buys ITM Put and sells OTM Put to reduce cost.",
                    "legs": [
                        {"action": "BUY", "type": "PE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 1},
                        {"action": "SELL", "type": "PE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1}
                    ],
                    "net_premium": round(net_premium, 2),
                    "max_loss": round(net_premium, 2),
                    "max_profit": round(max_profit, 2),
                    "risk_reward": f"1 : {round(rr, 2)}",
                    "margin_required": "~ 30,000"
                }

                # Pro Hedge: Put Butterfly Spread (Buy 1 ITM, Sell 2 ATM, Buy 1 OTM)
                buy_leg_2 = get_quote_by_delta(pe_quotes, -0.10) # Far OTM wing
                
                if buy_leg_2 and buy_leg_2["strike"] < sell_leg["strike"]:
                    net_premium_pro = (buy_leg["ltp"] + buy_leg_2["ltp"]) - (2 * sell_leg["ltp"])
                    spread_width = buy_leg["strike"] - sell_leg["strike"]
                    max_profit_pro = spread_width - net_premium_pro
                    rr_pro = max_profit_pro / net_premium_pro if net_premium_pro > 0 else 0
                    
                    hedges["pro"] = {
                        "name": "Put Butterfly Spread",
                        "reason": "High profit & STRICTLY LIMITED risk. Excellent Risk:Reward ratio for directional moves.",
                        "legs": [
                            {"action": "BUY", "type": "PE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 1},
                            {"action": "SELL", "type": "PE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 2},
                            {"action": "BUY", "type": "PE", "strike": buy_leg_2["strike"], "entry": float(buy_leg_2["ltp"]), "qty": 1}
                        ],
                        "net_premium": round(net_premium_pro, 2),
                        "max_loss": round(net_premium_pro, 2) if net_premium_pro > 0 else 0,
                        "max_profit": round(max_profit_pro, 2),
                        "risk_reward": f"1 : {round(rr_pro, 2)}",
                        "margin_required": "~ 45,000"
                    }

        # 3. SIDEWAYS HEDGE (Iron Condor)
        sell_ce = get_quote_by_delta(ce_quotes, 0.20)
        buy_ce = get_quote_by_delta(ce_quotes, 0.10)
        sell_pe = get_quote_by_delta(pe_quotes, -0.20)
        buy_pe = get_quote_by_delta(pe_quotes, -0.10)
        
        if sell_ce and buy_ce and sell_pe and buy_pe:
            net_credit = (sell_ce["ltp"] + sell_pe["ltp"]) - (buy_ce["ltp"] + buy_pe["ltp"])
            call_spread_width = buy_ce["strike"] - sell_ce["strike"]
            put_spread_width = sell_pe["strike"] - buy_pe["strike"]
            max_risk = max(call_spread_width, put_spread_width) - net_credit
            
            if net_credit > 0:
                rr_condor = net_credit / max_risk if max_risk > 0 else 0
                hedges["sideways"] = {
                    "name": "Iron Condor",
                    "reason": "Market expected to remain range-bound. Collects premium from both Call and Put sides.",
                    "legs": [
                        {"action": "SELL", "type": "CE", "strike": sell_ce["strike"], "entry": float(sell_ce["ltp"]), "qty": 1},
                        {"action": "BUY", "type": "CE", "strike": buy_ce["strike"], "entry": float(buy_ce["ltp"]), "qty": 1},
                        {"action": "SELL", "type": "PE", "strike": sell_pe["strike"], "entry": float(sell_pe["ltp"]), "qty": 1},
                        {"action": "BUY", "type": "PE", "strike": buy_pe["strike"], "entry": float(buy_pe["ltp"]), "qty": 1}
                    ],
                    "net_premium": -round(net_credit, 2),
                    "max_loss": round(max_risk, 2),
                    "max_profit": round(net_credit, 2),
                    "risk_reward": f"{round(rr_condor, 2)} : 1",
                    "margin_required": "~ 55,000"
                }

        # 4. ZERO LOSS HEDGE (Credit Ratio Backspread)
        if sentiment in ["BULLISH", "OVERSOLD"]:
            sell_leg = get_quote_by_delta(ce_quotes, 0.40)
            buy_leg = get_quote_by_delta(ce_quotes, 0.15)
            
            if sell_leg and buy_leg and buy_leg["strike"] > sell_leg["strike"]:
                net_premium = sell_leg["ltp"] - (2 * buy_leg["ltp"])
                
                # To be true "zero loss", we must receive a net credit. 
                # If we don't, we search for a further OTM buy leg.
                if net_premium <= 0:
                    buy_leg = get_quote_by_delta(ce_quotes, 0.10)
                    if buy_leg:
                        net_premium = sell_leg["ltp"] - (2 * buy_leg["ltp"])

                max_risk = (buy_leg["strike"] - sell_leg["strike"]) - net_premium
                
                hedges["zero_loss"] = {
                    "name": "Call Ratio Backspread",
                    "reason": "If market falls, ZERO LOSS (you keep the credit). If market skyrockets, UNLIMITED PROFIT. Only small risk if market stalls exactly at the bought strike.",
                    "legs": [
                        {"action": "SELL", "type": "CE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1},
                        {"action": "BUY", "type": "CE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 2}
                    ],
                    "net_premium": -round(net_premium, 2),
                    "max_loss": round(max_risk, 2) if net_premium < (buy_leg["strike"] - sell_leg["strike"]) else 0,
                    "max_profit": "Unlimited",
                    "risk_reward": "Extreme Positive Skew",
                    "margin_required": "~ 1,45,000"
                }
        else:
            sell_leg = get_quote_by_delta(pe_quotes, -0.40)
            buy_leg = get_quote_by_delta(pe_quotes, -0.15)
            
            if sell_leg and buy_leg and buy_leg["strike"] < sell_leg["strike"]:
                net_premium = sell_leg["ltp"] - (2 * buy_leg["ltp"])
                
                if net_premium <= 0:
                    buy_leg = get_quote_by_delta(pe_quotes, -0.10)
                    if buy_leg:
                        net_premium = sell_leg["ltp"] - (2 * buy_leg["ltp"])

                max_risk = (sell_leg["strike"] - buy_leg["strike"]) - net_premium
                
                hedges["zero_loss"] = {
                    "name": "Put Ratio Backspread",
                    "reason": "If market rises, ZERO LOSS (you keep the credit). If market crashes, UNLIMITED PROFIT. Only small risk if market stalls exactly at the bought strike.",
                    "legs": [
                        {"action": "SELL", "type": "PE", "strike": sell_leg["strike"], "entry": float(sell_leg["ltp"]), "qty": 1},
                        {"action": "BUY", "type": "PE", "strike": buy_leg["strike"], "entry": float(buy_leg["ltp"]), "qty": 2}
                    ],
                    "net_premium": -round(net_premium, 2),
                    "max_loss": round(max_risk, 2) if net_premium < (sell_leg["strike"] - buy_leg["strike"]) else 0,
                    "max_profit": "Unlimited",
                    "risk_reward": "Extreme Positive Skew",
                    "margin_required": "~ 1,45,000"
                }
                
        # 5. VOLATILITY BREAKOUT HEDGE (Long Straddle)
        straddle_ce = get_quote_by_delta(ce_quotes, 0.50)
        straddle_pe = get_quote_by_delta(pe_quotes, -0.50)
        if straddle_ce and straddle_pe:
            net_debit = straddle_ce["ltp"] + straddle_pe["ltp"]
            hedges["breakout"] = {
                "name": "Long Straddle",
                "reason": "Extreme volatility expected. Profit from massive moves in ANY direction.",
                "legs": [
                    {"action": "BUY", "type": "CE", "strike": straddle_ce["strike"], "entry": float(straddle_ce["ltp"]), "qty": 1},
                    {"action": "BUY", "type": "PE", "strike": straddle_pe["strike"], "entry": float(straddle_pe["ltp"]), "qty": 1}
                ],
                "net_premium": round(net_debit, 2),
                "max_loss": round(net_debit, 2),
                "max_profit": "Unlimited",
                "risk_reward": "Dynamic",
                "margin_required": "~ 35,000"
            }

        # --- AUTO-PILOT REGIME DETECTION ---
        pcr = analysis.get("pcr", 1.0)
        
        # 1. Strong Breakout / Trending (High PCR or Low PCR)
        if pcr >= 1.2:
            hedges["auto_pilot"] = {
                "recommended_key": "pro",
                "regime_name": "Strong Bullish Trend",
                "reasoning": f"PCR is very high ({pcr}). Market is in a strong uptrend. Deploying Butterfly Spread for maximum directional profit with strictly limited risk."
            }
        elif pcr <= 0.7:
            hedges["auto_pilot"] = {
                "recommended_key": "pro",
                "regime_name": "Strong Bearish Trend",
                "reasoning": f"PCR is critically low ({pcr}). Market is aggressively selling off. Deploying Butterfly Spread to capture downside momentum with safety."
            }
        # 2. Range-Bound / Sideways Market (PCR around 0.85 to 1.1)
        elif 0.85 <= pcr <= 1.1:
            hedges["auto_pilot"] = {
                "recommended_key": "sideways",
                "regime_name": "Range-Bound (Sideways) Market",
                "reasoning": f"PCR is neutral ({pcr}). The market is consolidating. Deploying Iron Condor to collect premium safely from both sides."
            }
        # 3. Transition / Uncertain Market
        else:
            hedges["auto_pilot"] = {
                "recommended_key": "safe",
                "regime_name": "Uncertain / Transitioning",
                "reasoning": f"PCR is {pcr}, indicating mild directional bias but lacking strong conviction. Deploying a safe directional spread to minimize risk."
            }

        return hedges
