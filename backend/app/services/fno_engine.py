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
            
            sentiment = "NEUTRAL"
            if pcr >= 1.5:
                sentiment = "OVERBOUGHT"
            elif pcr <= 0.6:
                sentiment = "OVERSOLD"
            elif pcr > 1.0:
                sentiment = "BULLISH"
            elif pcr < 1.0:
                sentiment = "BEARISH"

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
            
        return {
            "pcr": float(pcr),
            "max_pain": int(max_pain_strike),
            "highest_call_oi_strike": int(highest_call_strike),  # Resistance
            "highest_put_oi_strike": int(highest_put_strike),    # Support
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "sentiment": sentiment
        }
