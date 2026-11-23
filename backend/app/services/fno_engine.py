import math
from typing import List, Dict, Any, Optional
from app.utils.logger import get_logger
from app.services.hedge_finder import HedgeFinder

logger = get_logger(__name__)


def classify_strike_buildup(ltp: float, prev_close: float, chng_oi: int, oi: int, volume: int) -> str:
    """
    Classifies 4-quadrant derivative buildup per option strike:
      - OI up + Price up   -> Long Buildup (Buyers aggressive)
      - OI up + Price down -> Short Buildup (Writers aggressive)
      - OI dn + Price up   -> Short Covering (Writers trapped & covering)
      - OI dn + Price down -> Long Unwinding (Longs taking profit / stopping out)
    Falls back to intraday price + volume intensity when chng_oi is 0 (cold cache).
    """
    price_diff = (ltp - prev_close) if (ltp > 0 and prev_close > 0) else 0.0
    if chng_oi > 0:
        return "Long Buildup" if price_diff >= 0 else "Short Buildup"
    elif chng_oi < 0:
        return "Short Covering" if price_diff >= 0 else "Long Unwinding"

    # Cold-start proxy when prior OI snapshot equals current OI
    if ltp > 0 and prev_close > 0 and volume > 0:
        pct = (price_diff / prev_close) * 100.0
        high_turn = oi == 0 or (volume / max(oi, 1)) >= 0.25
        if high_turn and pct >= 2.0:
            return "Active Buying"
        if high_turn and pct <= -2.0:
            return "Active Selling"
    return "Neutral"


class FnoAnalyticsEngine:
    @staticmethod
    def enrich_quotes_buildup(quotes: List[Dict]) -> List[Dict]:
        """Adds strike-level 4-quadrant buildup tag & price_chg_pct in-place."""
        for q in quotes:
            ltp = float(q.get("ltp") or 0)
            prev_c = float(q.get("prev_close") or 0)
            chng_oi = int(q.get("chng_oi") or 0)
            oi = int(q.get("oi") or 0)
            vol = int(q.get("volume") or 0)
            q["price_chg_pct"] = round(((ltp - prev_c) / prev_c) * 100.0, 2) if (ltp > 0 and prev_c > 0) else 0.0
            q["buildup"] = classify_strike_buildup(ltp, prev_c, chng_oi, oi, vol)
        return quotes

    @staticmethod
    def analyze_chain(quotes: List[Dict]) -> Dict[str, Any]:
        """
        Takes raw option chain quotes from Fyers and calculates PCR, Volume PCR,
        OI flow, Max Pain, and Support/Resistance while keeping full backward compatibility.
        """
        strikes_data: Dict[float, Dict[str, float]] = {}
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0
        total_call_chng_oi = 0
        total_put_chng_oi = 0
        highest_call_oi = 0
        highest_put_oi = 0
        highest_call_strike = 0.0
        highest_put_strike = 0.0

        for q in quotes:
            strike = q.get("strike", 0)
            opt_type = q.get("type", "")
            if not strike or not opt_type:
                continue

            oi = int(q.get("oi") or 0)
            vol = int(q.get("volume") or 0)
            chng_oi = int(q.get("chng_oi") or 0)

            weight = oi if oi > 0 else vol

            if strike not in strikes_data:
                strikes_data[strike] = {"CE": 0, "PE": 0}

            strikes_data[strike][opt_type] = weight

            if opt_type == "CE":
                total_call_oi += weight
                total_call_vol += vol
                total_call_chng_oi += chng_oi
                if weight > highest_call_oi:
                    highest_call_oi = weight
                    highest_call_strike = float(strike)
            else:
                total_put_oi += weight
                total_put_vol += vol
                total_put_chng_oi += chng_oi
                if weight > highest_put_oi:
                    highest_put_oi = weight
                    highest_put_strike = float(strike)

        if total_call_oi == 0 and total_put_oi == 0:
            pcr = 0.0
            sentiment = "NEUTRAL"
        else:
            pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0.0
            if pcr >= 1.40:
                sentiment = "STRONG_BULLISH"
            elif pcr >= 1.15:
                sentiment = "BULLISH"
            elif pcr >= 0.95:
                sentiment = "SIDEWAYS"
            elif pcr >= 0.80:
                sentiment = "BEARISH"
            else:
                sentiment = "STRONG_BEARISH"

        vol_pcr = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else float(pcr)

        min_loss = float("inf")
        max_pain_strike = 0.0

        sorted_strikes = sorted(strikes_data.keys())
        for assumed_expiry in sorted_strikes:
            total_loss = 0.0
            for k_strike, oi_data in strikes_data.items():
                if assumed_expiry > k_strike:
                    total_loss += (assumed_expiry - k_strike) * oi_data["CE"]
                if assumed_expiry < k_strike:
                    total_loss += (k_strike - assumed_expiry) * oi_data["PE"]

            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = float(assumed_expiry)

        def _fmt_strike(s: float) -> Any:
            return int(s) if float(s).is_integer() else round(s, 2)

        return {
            "pcr": float(pcr),
            "vol_pcr": float(vol_pcr),
            "sentiment": sentiment,
            "max_pain": _fmt_strike(max_pain_strike),
            "highest_call_oi_strike": _fmt_strike(highest_call_strike),
            "highest_put_oi_strike": _fmt_strike(highest_put_strike),
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "total_call_vol": int(total_call_vol),
            "total_put_vol": int(total_put_vol),
            "total_call_chng_oi": int(total_call_chng_oi),
            "total_put_chng_oi": int(total_put_chng_oi),
            "net_oi_flow": int(total_put_chng_oi - total_call_chng_oi),
        }


class AladdinOptionBrain:
    """
    5-Pillar Multi-Factor Institutional Option Conviction & Strategy Engine.
    Combines Underlying Technicals + OI Smart Money + Greeks/Theta Efficiency
    + Volatility/IV Skew + Reversal Walls to select high-accuracy option trades
    and risk-defined hedges.
    """

    @staticmethod
    def _pick_by_delta(q_list: List[Dict], target_delta: float) -> Optional[Dict]:
        valid = [q for q in q_list if q.get("delta") is not None and float(q.get("ltp") or 0) > 0]
        if not valid:
            return None
        # Prefer liquid strikes with non-zero OI or volume when close in delta
        return min(
            valid,
            key=lambda x: (
                abs(float(x["delta"]) - target_delta),
                -(int(x.get("oi") or 0) + int(x.get("volume") or 0)),
            ),
        )

    @classmethod
    def evaluate_chain(
        cls,
        symbol: str,
        spot_price: float,
        quotes: List[Dict],
        analysis: Dict[str, Any],
        reversals: Dict[str, Any],
        dte_days: float,
        lot_size: int = 65,
        underlying_tech: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tech = underlying_tech or {}
        rsi = float(tech.get("rsi_14") or 50.0)
        ema_20 = float(tech.get("ema_20") or spot_price)
        ema_50 = float(tech.get("ema_50") or spot_price)
        hv_20 = float(tech.get("hv_20") or 14.0)
        hv_percentile = float(tech.get("hv_percentile") or 50.0)
        day_chg_pct = float(tech.get("day_change_pct") or 0.0)
        tech_trend = str(tech.get("trend") or "NEUTRAL")

        pcr = float(analysis.get("pcr") or 1.0)
        vol_pcr = float(analysis.get("vol_pcr") or pcr)
        avg_atm_iv = float(analysis.get("avg_atm_iv") or 15.0)
        iv_skew = float(analysis.get("iv_skew") or 0.0)  # ATM PE IV - ATM CE IV
        call_wall = float(reversals.get("R1") or analysis.get("highest_call_oi_strike") or spot_price * 1.02)
        put_wall = float(reversals.get("S1") or analysis.get("highest_put_oi_strike") or spot_price * 0.98)
        zero_gamma = float(reversals.get("zero_gamma") or spot_price)
        max_pain = float(reversals.get("max_pain") or analysis.get("max_pain") or spot_price)

        # ── 1. PILLAR 1: UNDERLYING TREND & INTRADAY MOMENTUM (Max 25) ────────
        trend_bias = 0.0  # -1.0 Strong Bearish to +1.0 Strong Bullish
        if spot_price > 0 and ema_20 > 0:
            trend_bias += 0.30 if spot_price > ema_20 else -0.30
        if ema_20 > 0 and ema_50 > 0:
            trend_bias += 0.25 if ema_20 > ema_50 else -0.25
        if rsi >= 55:
            trend_bias += 0.25 if rsi <= 72 else 0.10
        elif rsi <= 45:
            trend_bias -= 0.25 if rsi >= 28 else 0.10
        if day_chg_pct >= 0.25:
            trend_bias += 0.20
        elif day_chg_pct <= -0.25:
            trend_bias -= 0.20
        trend_bias = max(-1.0, min(1.0, trend_bias))

        trend_clarity = abs(trend_bias)
        if trend_clarity >= 0.65:
            p1_score = round(18.0 + min(trend_clarity, 1.0) * 7.0, 1)
            p1_status = f"Strong {tech_trend} Trend (RSI {rsi:.1f}, {day_chg_pct:+.2f}%)"
        elif trend_clarity >= 0.30:
            p1_score = round(12.0 + trend_clarity * 8.0, 1)
            p1_status = f"Moderate {tech_trend} Bias (RSI {rsi:.1f})"
        else:
            p1_score = 13.5  # Sideways / range clarity helps non-directional strategies
            p1_status = f"Sideways / Mixed MAs (RSI {rsi:.1f})"
        p1_score = min(25.0, p1_score)

        # ── 2. PILLAR 2: OI SMART MONEY & PCR FLOW (Max 25) ───────────────────
        oi_bias = 0.0
        if pcr >= 1.30:
            oi_bias += 0.45
        elif pcr >= 1.12:
            oi_bias += 0.28
        elif pcr <= 0.72:
            oi_bias -= 0.45
        elif pcr <= 0.88:
            oi_bias -= 0.28

        if vol_pcr >= 1.15:
            oi_bias += 0.25
        elif vol_pcr <= 0.85:
            oi_bias -= 0.25

        net_oi_flow = int(analysis.get("net_oi_flow") or 0)
        if net_oi_flow > 0:
            oi_bias += 0.15
        elif net_oi_flow < 0:
            oi_bias -= 0.15

        # Wall asymmetry (closer to Put Wall floor supports bounce; jammed at Call Wall caps upside)
        dist_to_call_pct = ((call_wall - spot_price) / spot_price * 100.0) if spot_price > 0 else 1.0
        dist_to_put_pct = ((spot_price - put_wall) / spot_price * 100.0) if spot_price > 0 else 1.0
        if dist_to_call_pct > dist_to_put_pct * 1.25:
            oi_bias += 0.15
        elif dist_to_put_pct > dist_to_call_pct * 1.25:
            oi_bias -= 0.15
        oi_bias = max(-1.0, min(1.0, oi_bias))

        confluence_agree = (trend_bias * oi_bias) >= 0 or (abs(trend_bias) < 0.2 and abs(oi_bias) < 0.2)
        if confluence_agree:
            p2_score = round(min(25.0, 14.0 + (abs(oi_bias) * 11.0)), 1)
            p2_status = f"OI & Volume Flow Aligned (PCR {pcr:.2f} | Vol-PCR {vol_pcr:.2f})"
        else:
            p2_score = round(max(8.0, 14.0 - abs(trend_bias - oi_bias) * 3.0), 1)
            p2_status = f"Trend vs OI Divergence Warning (Price {tech_trend} vs PCR {pcr:.2f})"

        # ── 3. PILLAR 3: GREEKS, DELTA & THETA EFFICIENCY (Max 20) ────────────
        ce_quotes = sorted([q for q in quotes if q.get("type") == "CE" and float(q.get("ltp") or 0) > 0], key=lambda x: x["strike"])
        pe_quotes = sorted([q for q in quotes if q.get("type") == "PE" and float(q.get("ltp") or 0) > 0], key=lambda x: x["strike"], reverse=True)

        composite_bias = (0.45 * trend_bias) + (0.40 * oi_bias) + (0.15 * (1.0 if spot_price >= zero_gamma else -1.0))
        if composite_bias >= 0.18:
            directional_bias = "BULLISH"
        elif composite_bias <= -0.18:
            directional_bias = "BEARISH"
        else:
            directional_bias = "RANGE_BOUND"

        theta_shield_active = dte_days <= 2.0
        target_buy_quote = (
            cls._pick_by_delta(ce_quotes, 0.58) if directional_bias == "BULLISH"
            else cls._pick_by_delta(pe_quotes, -0.58) if directional_bias == "BEARISH"
            else cls._pick_by_delta(ce_quotes, 0.20)
        )

        gamma_theta_ratio = 1.0
        if target_buy_quote and spot_price > 0:
            g_val = abs(float(target_buy_quote.get("gamma") or 0.0005))
            t_val = max(abs(float(target_buy_quote.get("theta") or 1.0)), 0.1)
            gamma_theta_ratio = round((g_val * spot_price * 0.005) / t_val, 2)

        if theta_shield_active:
            p3_score = 13.5  # Spreads & sellers thrive; naked buyers protected by shield
            p3_status = f"Theta Shield Active ({dte_days:.1f}d to Expiry — Prefer Spreads/Selling)"
        elif gamma_theta_ratio >= 0.35:
            p3_score = round(min(20.0, 15.0 + min(gamma_theta_ratio, 1.0) * 5.0), 1)
            p3_status = f"Optimal Delta/Gamma Efficiency (Ratio {gamma_theta_ratio:.2f}, DTE {dte_days:.1f}d)"
        else:
            p3_score = 14.0
            p3_status = f"Balanced Greeks Window (DTE {dte_days:.1f}d)"

        # ── 4. PILLAR 4: VOLATILITY, IV SKEW & 5Y HV EDGE REGIME (Max 15) ──────
        iv_hv_spread = round(avg_atm_iv - hv_20, 2)
        blended_vol = 0.6 * avg_atm_iv + 0.4 * hv_20
        expected_dte_move_pts = round(spot_price * (blended_vol / 100.0) * math.sqrt(max(dte_days, 0.5) / 365.0), 1) if spot_price > 0 else 0.0
        expected_1sd_range = [round(spot_price - expected_dte_move_pts, 1), round(spot_price + expected_dte_move_pts, 1)] if spot_price > 0 else [0.0, 0.0]

        iv_regime = "NORMAL"
        if avg_atm_iv > 19.0 or iv_hv_spread >= 3.0:
            iv_regime = "HIGH_IV_OVERPRICED" if iv_hv_spread >= 3.0 else "HIGH_IV"
            p4_score = 13.0 if directional_bias == "RANGE_BOUND" else 12.0
            p4_status = f"Rich IV {avg_atm_iv:.1f}% vs HV {hv_20:.1f}% (+{iv_hv_spread:.1f}%) — Sellers/Spreads Edge"
        elif avg_atm_iv < 11.5 or iv_hv_spread <= -1.0:
            iv_regime = "CHEAP_IV_BUYER_EDGE"
            p4_score = 14.5 if directional_bias != "RANGE_BOUND" else 10.5
            p4_status = f"Cheap IV {avg_atm_iv:.1f}% vs HV {hv_20:.1f}% (Pctl {hv_percentile:.0f}%) — Buyers Edge"
        else:
            iv_regime = "OPTIMAL_IV"
            p4_score = 14.0
            p4_status = f"Balanced IV {avg_atm_iv:.1f}% | HV20 {hv_20:.1f}% (Pctl {hv_percentile:.0f}%)"

        # ── 5. PILLAR 5: REVERSAL WALLS & ZERO GAMMA CLEARANCE (Max 15) ─────────
        zero_gamma_regime = "POSITIVE_GAMMA" if spot_price >= zero_gamma else "NEGATIVE_GAMMA"
        clearance_pct = (
            dist_to_call_pct if directional_bias == "BULLISH"
            else dist_to_put_pct if directional_bias == "BEARISH"
            else min(abs(dist_to_call_pct), abs(dist_to_put_pct))
        )
        if directional_bias == "RANGE_BOUND":
            p5_score = 13.5 if min(dist_to_call_pct, dist_to_put_pct) > 0.3 else 9.5
            p5_status = f"Max Pain Anchor {max_pain} | S1 {put_wall:.0f} – R1 {call_wall:.0f}"
        elif clearance_pct >= 0.75:
            p5_score = 14.0 if (directional_bias == "BULLISH" and reversals.get("concrete_wall_support")) or (directional_bias == "BEARISH" and reversals.get("concrete_wall_resistance")) else 13.0
            p5_status = f"Clean {clearance_pct:.2f}% Runway to {'R1' if directional_bias == 'BULLISH' else 'S1'} ({zero_gamma_regime.replace('_', ' ')})"
        elif clearance_pct >= 0.30:
            p5_score = 11.0
            p5_status = f"Moderate {clearance_pct:.2f}% Room Before Wall ({'R1' if directional_bias == 'BULLISH' else 'S1'})"
        else:
            p5_score = 7.5
            p5_status = f"Jam Against {'Call Resistance R1' if directional_bias == 'BULLISH' else 'Put Support S1'} — Use Spread"

        conviction_score = round(min(98.0, max(25.0, p1_score + p2_score + p3_score + p4_score + p5_score)), 1)
        if conviction_score >= 80:
            grade = "A+"
        elif conviction_score >= 70:
            grade = "A"
        elif conviction_score >= 58:
            grade = "B"
        else:
            grade = "C"

        # ── RECOMMENDED EXECUTION MODE ────────────────────────────────────────
        if directional_bias == "RANGE_BOUND":
            recommended_mode = "IRON_CONDOR" if dte_days > 2.5 else "CREDIT_SPREAD_SELLING"
        elif theta_shield_active or iv_regime == "HIGH_IV":
            recommended_mode = "DEBIT_SPREAD" if directional_bias != "RANGE_BOUND" else "IRON_CONDOR"
        elif conviction_score >= 66 and clearance_pct >= 0.45:
            recommended_mode = "OPTION_BUYING"
        else:
            recommended_mode = "DEBIT_SPREAD"

        # ── INDIA VIX REGIME FILTER & POSITION CAP ────────────────────────────
        india_vix = float(analysis.get("india_vix") or 0.0)
        vix_val = india_vix if india_vix > 0 else avg_atm_iv
        if vix_val < 12.5:
            vix_regime = "LOW_VIX_COMPRESSION"
            max_lots_allowed = 2
            vix_advisory = (
                f"Low VIX ({vix_val:.1f}) compression — Breakout follow-through is slower; "
                "favor Credit Spreads or high-Delta ITM."
            )
            if recommended_mode == "OPTION_BUYING" and conviction_score < 70.0:
                recommended_mode = "DEBIT_SPREAD"
        elif vix_val <= 18.0:
            vix_regime = "NORMAL_VIX_TRENDING"
            max_lots_allowed = 3
            vix_advisory = (
                f"Optimal VIX ({vix_val:.1f}) regime — Balanced option premiums & directional follow-through."
            )
        elif vix_val <= 22.0:
            vix_regime = "ELEVATED_VIX_CAUTION"
            max_lots_allowed = 1
            vix_advisory = (
                f"Elevated VIX ({vix_val:.1f}) — Option premiums carry IV-crush risk; "
                "capped at 1 lot & spreads preferred."
            )
            if recommended_mode == "OPTION_BUYING" and conviction_score < 74.0:
                recommended_mode = "DEBIT_SPREAD"
        else:
            vix_regime = "HIGH_VIX_PANIC_GUARD"
            max_lots_allowed = 1
            vix_advisory = (
                f"High VIX Panic Regime ({vix_val:.1f}) — Strict 1-lot risk cap & "
                "defined-risk hedged spreads enforced."
            )
            recommended_mode = "DEBIT_SPREAD" if directional_bias != "RANGE_BOUND" else "IRON_CONDOR"

        # ── BUILD TOP 3 RANKED PICKS ──────────────────────────────────────────
        top_picks: List[Dict[str, Any]] = []
        hedge_sentiment = "BULLISH" if directional_bias == "BULLISH" else ("BEARISH" if directional_bias == "BEARISH" else "SIDEWAYS")
        hedges = HedgeFinder.get_advanced_hedges(quotes, hedge_sentiment, analysis, dte_days=dte_days)

        def _make_pick_from_quote(q: Dict, action: str, title: str, tag: str, rationale: str, is_seller: bool = False) -> Dict[str, Any]:
            ltp = max(float(q.get("ltp") or 0), 0.5)
            delta_val = float(q.get("delta") or (0.20 if is_seller else 0.58))
            theta_val = float(q.get("theta") or 0.0)
            iv_val = float(q.get("iv") or avg_atm_iv)

            if is_seller:
                sl_px = round(ltp * 1.75, 2)
                t1_px = round(max(0.5, ltp * 0.35), 2)
                t2_px = 0.05
                pop = round(min(88.0, max(62.0, (1.0 - abs(delta_val)) * 100.0 + (conviction_score - 60.0) * 0.15)), 1)
                rec_lots = 1
                cap_req = round(spot_price * lot_size * 0.14, 2) if spot_price > 0 else 95000.0
                rr_str = "1 : 1.3"
            else:
                # Risk-parity paper sizing: risk max ~₹5,000 per trade
                sl_px = round(max(0.5, ltp * 0.72), 2)
                risk_pts = max(ltp - sl_px, 1.0)
                t1_px = round(ltp + (risk_pts * 1.6), 2)
                t2_px = round(ltp + (risk_pts * 2.5), 2)
                pop = round(min(78.0, max(44.0, (abs(delta_val) * 85.0) + (conviction_score - 55.0) * 0.35)), 1)
                risk_per_lot = risk_pts * max(lot_size, 1)
                rec_lots = max(1, min(max_lots_allowed, int(5000.0 / max(risk_per_lot, 500.0))))
                cap_req = round(ltp * max(lot_size, 1) * rec_lots, 2)
                rr_str = "1 : 1.8"

            return {
                "rank": len(top_picks) + 1,
                "tag": tag,
                "name": title,
                "symbol": q.get("symbol"),
                "strike": q.get("strike"),
                "type": q.get("type"),
                "action": action,
                "entry": round(ltp, 2),
                "sl": sl_px,
                "target": t1_px,
                "target_1": t1_px,
                "target_2": t2_px,
                "lot_size": lot_size,
                "recommended_lots": rec_lots,
                "capital_required": cap_req,
                "conviction_score": conviction_score,
                "pop_pct": pop,
                "delta": round(delta_val, 3),
                "theta": round(theta_val, 2),
                "iv": round(iv_val, 2),
                "buildup": q.get("buildup", "Neutral"),
                "rr_ratio": rr_str,
                "rationale": rationale,
                "legs": [
                    {
                        "symbol": q.get("symbol"),
                        "action": action,
                        "type": q.get("type"),
                        "strike": q.get("strike"),
                        "entry": round(ltp, 2),
                        "sl": sl_px,
                        "target": t1_px,
                        "qty": rec_lots,
                    }
                ],
            }

        # Pick 1: Primary Directional Buyer or Range Seller
        if directional_bias == "BULLISH":
            c_buy = cls._pick_by_delta(ce_quotes, 0.58)
            if c_buy:
                top_picks.append(
                    _make_pick_from_quote(
                        c_buy,
                        "BUY",
                        f"Bullish Momentum Call ({c_buy['strike']} CE)",
                        "HIGHEST WIN PROBABILITY BUY" if not theta_shield_active else "INTRADAY MOMENTUM SCALP",
                        f"Spot {tech_trend} (RSI {rsi:.1f}) aligns with PCR {pcr:.2f} & Put Wall {put_wall:.0f}. Delta {c_buy.get('delta')} shields against Theta decay.",
                        is_seller=False,
                    )
                )
        elif directional_bias == "BEARISH":
            p_buy = cls._pick_by_delta(pe_quotes, -0.58)
            if p_buy:
                top_picks.append(
                    _make_pick_from_quote(
                        p_buy,
                        "BUY",
                        f"Bearish Breakdown Put ({p_buy['strike']} PE)",
                        "HIGHEST WIN PROBABILITY BUY" if not theta_shield_active else "INTRADAY MOMENTUM SCALP",
                        f"Bearish Technicals (RSI {rsi:.1f}) confirm Call writing ceiling {call_wall:.0f} (PCR {pcr:.2f}). ITM/ATM Delta {p_buy.get('delta')} maximizes directional capture.",
                        is_seller=False,
                    )
                )

        # Pick 2: Defined-Risk Spread (Theta-Proof Hedge)
        spread_key = "sideways" if directional_bias == "RANGE_BOUND" and hedges.get("sideways") else "safe"
        spread = hedges.get(spread_key)
        if spread and spread.get("legs"):
            # Attach exact option symbols from quotes onto spread legs
            enriched_legs = []
            for leg in spread["legs"]:
                match_q = next((q for q in quotes if q["strike"] == leg["strike"] and q["type"] == leg["type"]), None)
                e_px = float(leg["entry"])
                is_b = leg["action"] == "BUY"
                enriched_legs.append({
                    **leg,
                    "symbol": match_q.get("symbol") if match_q else "",
                    "sl": round(e_px * 0.65, 2) if is_b else round(e_px * 1.8, 2),
                    "target": round(e_px * 1.45, 2) if is_b else round(max(0.5, e_px * 0.35), 2),
                })
            net_prem = float(spread.get("net_premium") or 0.0)
            is_credit = net_prem < 0
            abs_prem = abs(net_prem)
            max_loss_val = float(spread.get("max_loss") or abs_prem or 1.0)
            max_prof_val = float(spread.get("max_profit") or abs_prem or 1.0)
            spread_pick = {
                "rank": len(top_picks) + 1,
                "tag": "THETA-SHIELD SPREAD" if theta_shield_active or spread_key == "sideways" else "DEFINED-RISK HEDGE",
                "name": spread["name"],
                "symbol": enriched_legs[0]["symbol"],
                "strike": enriched_legs[0]["strike"],
                "type": f"{spread['name']}",
                "action": "CREDIT SPREAD" if is_credit else "DEBIT SPREAD",
                "entry": round(abs_prem, 2),
                "sl": round(abs_prem * 1.6 if is_credit else max(0.5, abs_prem * 0.55), 2),
                "target": round(max(0.5, abs_prem * 0.30) if is_credit else abs_prem + (max_prof_val * 0.75), 2),
                "target_1": round(max(0.5, abs_prem * 0.30) if is_credit else abs_prem + (max_prof_val * 0.75), 2),
                "target_2": round(0.05 if is_credit else abs_prem + max_prof_val, 2),
                "lot_size": lot_size,
                "recommended_lots": 1,
                "capital_required": round(max(max_loss_val * lot_size, abs_prem * lot_size), 2),
                "conviction_score": min(96.0, round(conviction_score + (3.5 if theta_shield_active else 0.0), 1)),
                "pop_pct": round(min(84.0, 62.0 + (conviction_score - 55.0) * 0.25), 1),
                "delta": 0.40 if not is_credit else 0.22,
                "theta": 0.0,
                "iv": round(avg_atm_iv, 2),
                "buildup": "Hedged Spread",
                "rr_ratio": spread.get("risk_reward", "1 : 1.5"),
                "rationale": spread["reason"],
                "legs": enriched_legs,
            }
            top_picks.append(spread_pick)

        # Pick 3: High-Probability OTM Theta Seller (beyond Put/Call Wall)
        if directional_bias == "BULLISH":
            sell_otm = cls._pick_by_delta(pe_quotes, -0.20)
            if sell_otm:
                top_picks.append(
                    _make_pick_from_quote(
                        sell_otm,
                        "SELL",
                        f"Theta Support Put Sell ({sell_otm['strike']} PE)",
                        "HIGH-POP THETA INCOME",
                        f"High Probability (~80%) OTM Put writing below Put Wall {put_wall:.0f} to harvest daily Theta decay.",
                        is_seller=True,
                    )
                )
        else:
            sell_otm = cls._pick_by_delta(ce_quotes, 0.20)
            if sell_otm:
                top_picks.append(
                    _make_pick_from_quote(
                        sell_otm,
                        "SELL",
                        f"Theta Resistance Call Sell ({sell_otm['strike']} CE)",
                        "HIGH-POP THETA INCOME",
                        f"High Probability (~80%) OTM Call writing above Call Wall {call_wall:.0f} to harvest daily Theta decay.",
                        is_seller=True,
                    )
                )

        # Ensure primary buyer/seller compatible dictionaries are always clean
        win_prob = top_picks[0]["pop_pct"] if top_picks else 55.0
        if (theta_shield_active or vix_regime == "HIGH_VIX_PANIC_GUARD") and top_picks and len(top_picks) > 1 and top_picks[0].get("action") == "BUY":
            # Promote Spread above naked buying during final expiry decay window or high-VIX panic
            top_picks[0], top_picks[1] = top_picks[1], top_picks[0]
            top_picks[0]["rank"] = 1
            top_picks[1]["rank"] = 2

        return {
            "symbol": symbol,
            "conviction_score": conviction_score,
            "grade": grade,
            "directional_bias": directional_bias,
            "recommended_mode": recommended_mode,
            "theta_shield_active": theta_shield_active,
            "india_vix": round(vix_val, 2),
            "vix_regime": vix_regime,
            "vix_advisory": vix_advisory,
            "max_lots_allowed": max_lots_allowed,
            "iv_regime": iv_regime,
            "iv_hv_spread": iv_hv_spread,
            "expected_dte_move_pts": expected_dte_move_pts,
            "expected_1sd_range": expected_1sd_range,
            "win_probability_pct": win_prob,
            "confluence_agree": confluence_agree,
            "lot_size": lot_size,
            "underlying_technicals": {
                "rsi_14": round(rsi, 2),
                "ema_20": round(ema_20, 2),
                "ema_50": round(ema_50, 2),
                "hv_20": round(hv_20, 2),
                "hv_percentile": round(hv_percentile, 1),
                "day_change_pct": round(day_chg_pct, 2),
                "trend": tech_trend,
                "zero_gamma_regime": zero_gamma_regime,
            },
            "pillars": [
                {"key": "trend_momentum", "label": "Underlying Trend & RSI", "score": p1_score, "max": 25, "status": p1_status},
                {"key": "oi_smart_money", "label": "OI & Volume Smart Money", "score": p2_score, "max": 25, "status": p2_status},
                {"key": "greeks_theta", "label": "Greeks & Theta Shield", "score": p3_score, "max": 20, "status": p3_status},
                {"key": "iv_skew", "label": "IV & Skew Regime", "score": p4_score, "max": 15, "status": p4_status},
                {"key": "reversal_walls", "label": "Gamma Walls & Max Pain", "score": p5_score, "max": 15, "status": p5_status},
            ],
            "top_picks": top_picks[:3],
            "hedges": hedges,
        }

