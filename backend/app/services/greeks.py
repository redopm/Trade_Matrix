import math
from typing import Dict, Optional
import py_vollib.black_scholes.implied_volatility as iv
import py_vollib.black_scholes.greeks.analytical as greeks
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Indian risk-free rate is around 7%
RISK_FREE_RATE = 0.07

class GreeksCalculator:
    @staticmethod
    def calculate_greeks(
        option_type: str,  # 'CE' or 'PE'
        underlying_price: float,
        strike_price: float,
        days_to_expiry: float,
        option_price: float
    ) -> Dict[str, Optional[float]]:
        """
        Calculates Implied Volatility and Greeks (Delta, Gamma, Theta, Vega) using the Black-Scholes model.
        Returns a dictionary of greeks.
        """
        flag = 'c' if option_type.upper() == 'CE' else 'p'
        
        # Avoid zero or negative DTE
        t_years = max(days_to_expiry, 0.01) / 365.0
        
        # Default empty result
        result = {
            "iv": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0
        }
        
        if option_price <= 0 or underlying_price <= 0 or strike_price <= 0:
            return result
            
        try:
            import math
            # Calculate intrinsic value
            if flag == 'c':
                intrinsic = underlying_price - strike_price * math.exp(-RISK_FREE_RATE * t_years)
            else:
                intrinsic = strike_price * math.exp(-RISK_FREE_RATE * t_years) - underlying_price
                
            # Fyers LTP might be below intrinsic for illiquid ITM options
            safe_price = max(option_price, intrinsic + 0.05)
            
            # Calculate Implied Volatility
            implied_vol = iv.implied_volatility(
                price=safe_price,
                S=underlying_price,
                K=strike_price,
                t=t_years,
                r=RISK_FREE_RATE,
                flag=flag
            )
            result["iv"] = round(implied_vol * 100, 2)  # Convert to percentage
            
            # Calculate Greeks if IV is valid
            if implied_vol > 0:
                result["delta"] = round(greeks.delta(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, implied_vol), 4)
                result["gamma"] = round(greeks.gamma(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, implied_vol), 4)
                # Theta is traditionally reported per day, py_vollib returns per year, divide by 365
                theta_annual = greeks.theta(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, implied_vol)
                result["theta"] = round(theta_annual / 365.0, 4)
                # Vega is traditionally reported per 1% change in vol, py_vollib returns per 100%, divide by 100
                vega_raw = greeks.vega(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, implied_vol)
                result["vega"] = round(vega_raw / 100.0, 4)
                
                # --- Advanced FII Institutional Greeks ---
                # Vanna (Numerical): Change in Delta for 1% change in Implied Volatility
                vol_up = implied_vol + 0.01
                vol_down = max(implied_vol - 0.01, 0.001)
                delta_up = greeks.delta(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, vol_up)
                delta_down = greeks.delta(flag, underlying_price, strike_price, t_years, RISK_FREE_RATE, vol_down)
                result["vanna"] = round((delta_up - delta_down) / 2.0, 4)
                
                # Charm (Numerical): Change in Delta per 1 day passing (Time Decay)
                t_tomorrow = max(t_years - (1.0 / 365.0), 0.0001)
                delta_tomorrow = greeks.delta(flag, underlying_price, strike_price, t_tomorrow, RISK_FREE_RATE, implied_vol)
                result["charm"] = round(delta_tomorrow - result["delta"], 4)
                
        except Exception as e:
            # Deep ITM/OTM options or pricing anomalies can cause IV calculation to fail
            # We silently catch these and return 0
            logger.error(f"Greeks calculation failed for {option_type} K={strike_price} S={underlying_price} ltp={option_price} t={t_years} | Error: {str(e)}")
            pass
            
        return result
