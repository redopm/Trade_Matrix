"""
Risk Manager Service — TradeMatrix Phase 1
Calculates ATR-based dynamic Stop Loss, targets, and Risk:Reward for every signal.

Rules:
  - Stop Loss = max(Fixed 5%, 2xATR below entry)
  - Target 1 = entry + 1xrisk (1:1 R:R minimum)
  - Target 2 = entry + 2xrisk (2:1 R:R — our primary target)
  - Target 3 = +12% fixed (per strategy doc)
  - Entry Zone = current_price to current_price + 0.5% (market open buffer)
  - Position Size = 2% capital risk per trade
"""
from typing import Optional, Any
import math

from app.config import settings
from app.utils.logger import get_logger
from app.utils.helpers import sanitize_nans

logger = get_logger(__name__)


class RiskManager:
    """
    Calculates trade parameters for any signal.

    Usage:
        rm = RiskManager(total_capital=100_000)
        trade_params = rm.calculate(
            symbol="RELIANCE.NS",
            current_price=2500.0,
            atr=45.0,
            direction="LONG",
        )
    """

    def __init__(self, total_capital: float = None):
        self.total_capital = total_capital or settings.DEFAULT_CAPITAL
        self.fixed_sl_pct = settings.FIXED_SL_PCT          # 5%
        self.atr_multiplier = settings.ATR_SL_MULTIPLIER   # 2.0
        self.target_pct = settings.TARGET_PROFIT_PCT        # 12%
        self.position_size_pct = settings.DEFAULT_POSITION_SIZE_PCT  # 10%
        self.max_risk_per_trade_pct = 0.02                  # Risk only 2% of capital per trade

    def calculate(
        self,
        symbol: str,
        current_price: float,
        atr: Optional[float] = None,
        direction: str = "LONG",
        rsi: Optional[float] = None,
        bb_lower: Optional[float] = None,
        s1: Optional[float] = None,
        fib_618: Optional[float] = None,
    ) -> dict[str, Any]:
        """Main entry point: compute all trade parameters."""
        if current_price is None or math.isnan(current_price) or current_price <= 0:
            return {"error": "Invalid price"}

        if direction == "LONG":
            res = self._calculate_long(symbol, current_price, atr, rsi, bb_lower, s1, fib_618)
        else:
            res = self._calculate_short(symbol, current_price, atr, rsi)
        return sanitize_nans(res)

    def _calculate_long(
        self,
        symbol: str,
        price: float,
        atr: Optional[float],
        rsi: Optional[float],
        bb_lower: Optional[float],
        s1: Optional[float],
        fib_618: Optional[float],
    ) -> dict[str, Any]:
        """Calculate LONG trade parameters."""

        # 1. Entry Zone
        entry_low = round(price, 2)
        entry_high = round(price * 1.005, 2)
        suggested_entry = price

        # 2. Stop Loss
        fixed_sl = round(price * (1 - self.fixed_sl_pct), 2)
        atr_sl = None
        if atr and atr > 0:
            atr_sl = round(price - (self.atr_multiplier * atr), 2)

        # Effective SL = lower of the two (more room to breathe)
        if atr_sl is not None:
            effective_sl = min(fixed_sl, atr_sl)
        else:
            effective_sl = fixed_sl

        # Check technical support levels
        technical_sl = None
        for level in [s1, fib_618, bb_lower]:
            if level and 0 < level < price:
                sl_from_level = round(level * 0.995, 2)
                if sl_from_level > effective_sl:
                    technical_sl = sl_from_level

        if technical_sl and ((price - technical_sl) / price) >= 0.03:
            final_sl = technical_sl
            sl_type = "TECHNICAL"
        else:
            final_sl = effective_sl
            sl_type = "ATR" if atr_sl is not None else "FIXED"

        # 3. Risk Calculation
        risk_per_share = price - final_sl
        if risk_per_share <= 0:
            final_sl = fixed_sl
            risk_per_share = price - final_sl
            sl_type = "FIXED"

        sl_pct = round((final_sl / price - 1) * 100, 2)

        # 4. Targets
        target_1 = round(price + (risk_per_share * 1.0), 2)
        target_2 = round(price + (risk_per_share * 2.0), 2)
        target_3 = round(price * (1 + self.target_pct), 2)

        rr_t2 = round((target_2 - price) / risk_per_share, 2)
        t1_pct = round((target_1 / price - 1) * 100, 2)
        t2_pct = round((target_2 / price - 1) * 100, 2)
        t3_pct = round((target_3 / price - 1) * 100, 2)

        # 5. Position Sizing (2% capital risk rule)
        max_risk_amount = self.total_capital * self.max_risk_per_trade_pct
        shares_by_risk = math.floor(max_risk_amount / risk_per_share) if risk_per_share > 0 else 0
        max_position_value = self.total_capital * self.position_size_pct
        shares_by_position = math.floor(max_position_value / price) if price > 0 else 0
        suggested_qty = max(min(shares_by_risk, shares_by_position), 1)
        total_investment = round(suggested_qty * price, 2)

        # 6. R:R Quality
        rr_quality = ("EXCELLENT" if rr_t2 >= 2.5 else
                       ("GOOD" if rr_t2 >= 2.0 else
                        ("FAIR" if rr_t2 >= 1.5 else "POOR")))
        meets_minimum_rr = rr_t2 >= 2.0

        return {
            "symbol": symbol,
            "direction": "LONG",
            "entry_price": suggested_entry,
            "entry_zone_low": entry_low,
            "entry_zone_high": entry_high,
            "stop_loss": final_sl,
            "stop_loss_pct": sl_pct,
            "stop_loss_type": sl_type,
            "atr_stop_loss": atr_sl,
            "fixed_stop_loss": fixed_sl,
            "risk_per_share": round(risk_per_share, 2),
            "target_1": target_1,
            "target_2": target_2,
            "target_3": target_3,
            "target_1_pct": t1_pct,
            "target_2_pct": t2_pct,
            "target_3_pct": t3_pct,
            "rr_t1": 1.0,
            "rr_t2": rr_t2,
            "rr_t3": round((target_3 - price) / risk_per_share, 2),
            "rr_quality": rr_quality,
            "meets_minimum_rr": meets_minimum_rr,
            "suggested_qty": suggested_qty,
            "total_investment": total_investment,
            "max_loss_amount": round(suggested_qty * risk_per_share, 2),
            "max_gain_t2": round(suggested_qty * (target_2 - price), 2),
            "capital_used_pct": round((total_investment / self.total_capital) * 100, 1),
            "atr": round(atr, 2) if atr else None,
            "atr_pct": round((atr / price) * 100, 2) if atr else None,
        }

    def _calculate_short(
        self,
        symbol: str,
        price: float,
        atr: Optional[float],
        rsi: Optional[float],
    ) -> dict[str, Any]:
        """Calculate SHORT trade parameters."""
        fixed_sl = round(price * (1 + self.fixed_sl_pct), 2)
        atr_sl = round(price + (self.atr_multiplier * atr), 2) if atr and atr > 0 else None
        effective_sl = max(fixed_sl, atr_sl) if atr_sl is not None else fixed_sl

        risk_per_share = max(effective_sl - price, price * self.fixed_sl_pct)
        sl_pct = round((effective_sl / price - 1) * 100, 2)

        target_1 = round(price - (risk_per_share * 1.0), 2)
        target_2 = round(price - (risk_per_share * 2.0), 2)
        target_3 = round(price * (1 - self.target_pct), 2)

        rr_t2 = round((price - target_2) / risk_per_share, 2)
        meets_minimum_rr = rr_t2 >= 2.0

        max_risk_amount = self.total_capital * self.max_risk_per_trade_pct
        suggested_qty = max(math.floor(max_risk_amount / risk_per_share), 1)

        return {
            "symbol": symbol,
            "direction": "SHORT",
            "entry_price": price,
            "entry_zone_low": round(price * 0.995, 2),
            "entry_zone_high": price,
            "stop_loss": effective_sl,
            "stop_loss_pct": sl_pct,
            "stop_loss_type": "ATR" if atr_sl else "FIXED",
            "atr_stop_loss": atr_sl,
            "fixed_stop_loss": fixed_sl,
            "risk_per_share": round(risk_per_share, 2),
            "target_1": target_1,
            "target_2": target_2,
            "target_3": target_3,
            "target_1_pct": round((target_1 / price - 1) * 100, 2),
            "target_2_pct": round((target_2 / price - 1) * 100, 2),
            "target_3_pct": round((target_3 / price - 1) * 100, 2),
            "rr_t1": 1.0,
            "rr_t2": rr_t2,
            "rr_t3": round((price - target_3) / risk_per_share, 2),
            "rr_quality": "EXCELLENT" if rr_t2 >= 2.5 else ("GOOD" if rr_t2 >= 2.0 else "FAIR"),
            "meets_minimum_rr": meets_minimum_rr,
            "suggested_qty": suggested_qty,
            "total_investment": round(suggested_qty * price, 2),
            "max_loss_amount": round(suggested_qty * risk_per_share, 2),
            "max_gain_t2": round(suggested_qty * (price - target_2), 2),
            "capital_used_pct": round((suggested_qty * price / self.total_capital) * 100, 1),
            "atr": round(atr, 2) if atr else None,
            "atr_pct": round((atr / price) * 100, 2) if atr else None,
        }

    def calculate_batch(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Calculate risk parameters for a list of signals."""
        results = []
        for sig in signals:
            try:
                params = self.calculate(
                    symbol=sig.get("symbol", ""),
                    current_price=sig.get("current_price", 0),
                    atr=sig.get("atr"),
                    direction=sig.get("direction", "LONG"),
                    rsi=sig.get("rsi"),
                    bb_lower=sig.get("bb_lower"),
                    s1=sig.get("s1"),
                    fib_618=sig.get("fib_level_618"),
                )
                results.append({**sig, **params})
            except Exception as e:
                logger.warning(f"Risk calculation failed for {sig.get('symbol', '?')}: {e}")
                results.append(sig)
        return results
