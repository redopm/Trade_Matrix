from typing import List, Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

class FnoAnalyticsEngine:
    @staticmethod
    def analyze_chain(quotes: List[Dict]) -> Dict[str, Any]:
        """
        Takes raw option chain quotes from Fyers and calculates PCR, Max Pain, and Support/Resistance.
        quotes format: [{"symbol": "NSE:NIFTY2660918800CE", "ltp": 100, "oi": 50000}, ...]
        """
        strikes_data = {}
        total_call_oi = 0
        total_put_oi = 0
        highest_call_oi = 0
        highest_put_oi = 0
        highest_call_strike = 0
        highest_put_strike = 0
        
        for q in quotes:
            # Use pre-parsed strike & type (set by fno.py router) — NOT regex on symbol
            # Symbol like NSE:NIFTY2660918800CE has date+strike combined, so regex gives wrong result
            strike = q.get("strike", 0)
            opt_type = q.get("type", "")
            if not strike or not opt_type:
                continue
                
            oi = q.get("oi", 0)
            vol = q.get("volume", 0)
            
            # Fyers API sometimes omits 'open_interest'. Fallback to 'volume' as a proxy for liquidity/support.
            weight = oi if oi > 0 else vol
            
            if strike not in strikes_data:
                strikes_data[strike] = {"CE": 0, "PE": 0}
            
            strikes_data[strike][opt_type] = weight
            
            if opt_type == "CE":
                total_call_oi += weight
                if weight > highest_call_oi:
                    highest_call_oi = weight
                    highest_call_strike = strike
            else:
                total_put_oi += weight
                if weight > highest_put_oi:
                    highest_put_oi = weight
                    highest_put_strike = strike
                    
        if total_call_oi == 0 and total_put_oi == 0:
            pcr = 0.0
            sentiment = "NEUTRAL"
        else:
            pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0
            
            # ── Stable PCR Sentiment Zones ──────────────────────────────────────
            # These bands prevent signal flip-flopping around PCR = 1.0.
            # A wide SIDEWAYS zone (0.95-1.15) means both buyers & sellers are
            # equally active — no clear directional edge for a buyer.
            # Only outside these bands do we give a directional trade signal.
            #
            #  PCR < 0.80         → STRONG_BEARISH  (Calls dominating heavily)
            #  0.80 <= PCR < 0.95 → BEARISH         (Slight call-writing dominance)
            #  0.95 <= PCR < 1.15 → SIDEWAYS        (No clear direction — safe zone)
            #  1.15 <= PCR < 1.40 → BULLISH         (Slight put-writing dominance)
            #  PCR >= 1.40        → STRONG_BULLISH  (Puts dominating heavily)
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

        min_loss = float('inf')
        max_pain_strike = 0
        
        sorted_strikes = sorted(strikes_data.keys())
        for assumed_expiry in sorted_strikes:
            total_loss = 0
            for k_strike, oi_data in strikes_data.items():
                if assumed_expiry > k_strike:
                    total_loss += (assumed_expiry - k_strike) * oi_data["CE"]
                if assumed_expiry < k_strike:
                    total_loss += (k_strike - assumed_expiry) * oi_data["PE"]
            
            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = assumed_expiry
            
        # ── Average ATM IV (average of all IV values present in chain) ──────────
        # This is used by the ReversalEngine for volatility-adjusted levels.
        # A more accurate approach would be to filter only ATM ±2 strikes,
        # but since Greeks are computed in the router (after this call), we
        # return a placeholder here; fno.py router will override it.
        return {
            "pcr": float(pcr),
            "sentiment": sentiment,
            "max_pain": int(max_pain_strike),
            "highest_call_oi_strike": int(highest_call_strike),  # Resistance
            "highest_put_oi_strike": int(highest_put_strike),    # Support
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
        }
