import math
from typing import List, Dict, Any, Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ReversalEngine:
    
    @staticmethod
    def calculate_fno_reversals(quotes: List[Dict], spot_price: float, atm_iv: float, dte: float) -> Dict[str, Any]:
        """
        Calculates exact Institutional Reversal points using the FII Master Engine Model:
        1. Base: Net GEX Flip Point (Zero Gamma Pivot)
        2. Adjusters: Vanna & Charm shifted S1/R1 Gamma Walls
        3. Validation: Volume Profile POC
        Returns S1, S2, R1, R2, max_pain, zero_gamma, volume_poc.
        """
        if not spot_price or spot_price <= 0:
            return {"R1": 0, "R2": 0, "S1": 0, "S2": 0, "max_pain": 0, "zero_gamma": 0, "volume_poc": 0, "concrete_wall_support": False, "concrete_wall_resistance": False}

        # ---------------------------------------------------------
        # MODEL A: IV STANDARD DEVIATION RANGE
        # ---------------------------------------------------------
        daily_sd = spot_price * (atm_iv / 100.0) * math.sqrt(1 / 365.0)
        iv_resistance = round(spot_price + daily_sd, 2)
        iv_support = round(spot_price - daily_sd, 2)

        # ---------------------------------------------------------
        # MODEL A: MAX PAIN & VOLUME POC CALCULATION
        # ---------------------------------------------------------
        strikes = sorted(list(set([q.get("strike", 0) for q in quotes if q.get("strike")])))
        min_pain_value = float('inf')
        max_pain_strike = spot_price
        
        max_volume = 0
        volume_poc = spot_price
        
        strike_net_gex = {} # To calculate Zero Gamma
        
        for test_strike in strikes:
            total_pain = 0
            strike_vol = 0
            call_gex = 0
            put_gex = 0
            
            for q in quotes:
                strike = q.get("strike", 0)
                opt_type = q.get("type", "")
                oi = q.get("oi", 0)
                vol = q.get("volume", 0)
                gamma = q.get("gamma", 0)
                
                # Volume POC Tracking
                if strike == test_strike:
                    strike_vol += vol
                    
                    if gamma and oi:
                        gex = float(gamma) * float(oi)
                        if opt_type == "CE":
                            call_gex += gex
                        elif opt_type == "PE":
                            put_gex += gex
                
                # Max Pain Tracking
                if opt_type == "CE" and strike < test_strike:
                    total_pain += (test_strike - strike) * oi
                elif opt_type == "PE" and strike > test_strike:
                    total_pain += (strike - test_strike) * oi
            
            if total_pain < min_pain_value:
                min_pain_value = total_pain
                max_pain_strike = test_strike
                
            if strike_vol > max_volume:
                max_volume = strike_vol
                volume_poc = test_strike
                
            # Net GEX = Call GEX - Put GEX
            # Actually, standard definition: Net GEX = Call GEX - Put GEX. We find where it crosses 0.
            strike_net_gex[test_strike] = call_gex - put_gex

        # ---------------------------------------------------------
        # ZERO GAMMA LEVEL (GEX Flip Point)
        # ---------------------------------------------------------
        zero_gamma = spot_price
        min_abs_gex = float('inf')
        for st, net_g in strike_net_gex.items():
            if abs(net_g) < min_abs_gex:
                min_abs_gex = abs(net_g)
                zero_gamma = st

        # ---------------------------------------------------------
        # MODEL B: ADJUSTED GAMMA WALLS (Weighted Center of Gravity + Vanna/Charm)
        # ---------------------------------------------------------
        sum_ce_gex = 0
        sum_ce_strike_gex = 0
        
        sum_pe_gex = 0
        sum_pe_strike_gex = 0
        
        for q in quotes:
            strike = q.get("strike", 0)
            opt_type = q.get("type", "")
            gamma = q.get("gamma", 0)
            vanna = q.get("vanna", 0)
            charm = q.get("charm", 0)
            oi = q.get("oi", 0)
            
            if gamma and oi and strike:
                # Base GEX
                base_gex = float(gamma) * float(oi)
                
                # Dynamic Shift Approximation: Add Vanna & Charm influence to weight.
                # If Vanna is positive, it amplifies GEX in rising IV. We just assume a baseline shift to make the wall more "accurate".
                # For simplicity, we just add the absolute value of vanna+charm to slightly pull the gravity center towards high dynamic areas.
                dynamic_weight = base_gex * (1 + abs(float(vanna)) + abs(float(charm)))
                
                # We look above spot for Resistance, below spot for Support
                if opt_type == "CE" and strike >= spot_price:
                    sum_ce_gex += dynamic_weight
                    sum_ce_strike_gex += (strike * dynamic_weight)
                        
                elif opt_type == "PE" and strike <= spot_price:
                    sum_pe_gex += dynamic_weight
                    sum_pe_strike_gex += (strike * dynamic_weight)

        adjusted_gamma_resistance = round(sum_ce_strike_gex / sum_ce_gex, 2) if sum_ce_gex > 0 else spot_price
        adjusted_gamma_support = round(sum_pe_strike_gex / sum_pe_gex, 2) if sum_pe_gex > 0 else spot_price

        # ---------------------------------------------------------
        # COMPARE AND ASSIGN S1/S2 and R1/R2
        # ---------------------------------------------------------
        supports = sorted(list(set([iv_support, float(adjusted_gamma_support)])))
        if len(supports) == 1:
            supports.append(supports[0] - 50) 
            
        resistances = sorted(list(set([iv_resistance, float(adjusted_gamma_resistance)])))
        if len(resistances) == 1:
            resistances.append(resistances[0] + 50) 

        # ---------------------------------------------------------
        # CONCRETE WALL VALIDATION
        # ---------------------------------------------------------
        # If Volume POC is within 0.5% of Adjusted Gamma Support, it's a concrete wall.
        s1 = supports[-1]
        r1 = resistances[0]
        concrete_support = abs(volume_poc - s1) < (spot_price * 0.005)
        concrete_resistance = abs(volume_poc - r1) < (spot_price * 0.005)
        
        return {
            "S1": s1,
            "S2": supports[0],
            "R1": r1,
            "R2": resistances[-1],
            "max_pain": max_pain_strike,
            "iv_sd": round(daily_sd, 2),
            "zero_gamma": zero_gamma,
            "volume_poc": volume_poc,
            "concrete_wall_support": concrete_support,
            "concrete_wall_resistance": concrete_resistance
        }
