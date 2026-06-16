from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.logger import get_logger
from app.services.options_data import OptionsDataFetcher
from app.services.greeks import GreeksCalculator
from app.services.fno_engine import FnoAnalyticsEngine
from app.services.paper_trading import PaperTradingEngine
from app.models.trade import PaperTrade, TradeDirection, TradeStatus
import re
from app.config import settings

logger = get_logger(__name__)

class FnoTrader:
    def __init__(self):
        self.fetcher = OptionsDataFetcher()
        self.paper_engine = PaperTradingEngine()
        
    async def evaluate_and_trade(self, db: AsyncSession, symbol: str, sentiment: str, atm_strike: int) -> Optional[PaperTrade]:
        """
        Evaluate option chain and place an options paper trade based on Delta.
        Buy Call if Bullish, Buy Put if Bearish.
        """
        logger.info(f"Evaluating F&O Trade for {symbol} with sentiment {sentiment} and ATM {atm_strike}")
        
        # 1. Fetch Option Chain
        quotes = await self.fetcher.fetch_option_chain_quotes(symbol, atm_strike)
        if not quotes:
            logger.error("No quotes found for option chain.")
            return None
            
        df = await self.fetcher.get_nearest_expiry_chain_df(symbol)
        if df is None or df.empty:
            return None
            
        spot_price = 0.0
        raw = self.fetcher.fyers_client.fetch_quotes([f"NSE:{symbol}-INDEX" if symbol == "NIFTY" else f"NSE:{symbol}BANK-INDEX" if symbol == "BANKNIFTY" else f"NSE:{symbol}-INDEX"])
        if raw and "d" in raw and len(raw["d"]) > 0:
            spot_price = float(raw["d"][0]["v"].get("lp") or 0)
        spot = spot_price if spot_price > 0 else float(atm_strike)
            
        expiry_epoch = df.iloc[0][8]
        import time
        dte_days = max((expiry_epoch - time.time()) / 86400, 0.01)
        
        # 2. Process Greeks
        processed_quotes = []
        for q in quotes:
            sym = q.get("symbol", "")
            match = re.search(r'(\d+)(CE|PE)$', sym)
            if not match: continue
            
            strike = int(match.group(1))
            opt_type = match.group(2)
            
            greeks = GreeksCalculator.calculate_greeks(
                opt_type, spot, strike, dte_days, q.get("ltp", 0)
            )
            q.update(greeks)
            q["strike"] = strike
            q["type"] = opt_type
            processed_quotes.append(q)
            
        # 3. Strategy Logic (Buy ATM/ITM Option with Delta 0.5 - 0.65)
        # Nifty lot size is 25, BankNifty is 15
        lot_size = 25 if symbol == "NIFTY" else 15
        
        selected_option = None
        
        if sentiment in ["BULLISH", "OVERSOLD"]:
            # Buy CE
            calls = [q for q in processed_quotes if q["type"] == "CE" and q["ltp"] > 0]
            # Find closest delta to 0.55
            if calls:
                selected_option = min(calls, key=lambda x: abs(x.get("delta", 0) - 0.55))
                
        elif sentiment in ["BEARISH", "OVERBOUGHT"]:
            # Buy PE
            puts = [q for q in processed_quotes if q["type"] == "PE" and q["ltp"] > 0]
            # Puts have negative delta, so find closest to -0.55
            if puts:
                selected_option = min(puts, key=lambda x: abs(x.get("delta", 0) - (-0.55)))
                
        if not selected_option:
            logger.info("No suitable option found to trade.")
            return None
            
        # 4. Execute Paper Trade
        entry_price = selected_option["ltp"]
        max_risk = settings.DEFAULT_CAPITAL * 0.02
        
        # Stop loss: 30% of option premium, Target: 60% of option premium
        sl = entry_price * 0.70
        target = entry_price * 1.60
        risk_per_qty = entry_price - sl
        
        # Quantity calculation based on lot size
        ideal_qty = max_risk / risk_per_qty if risk_per_qty > 0 else lot_size
        lots = max(1, int(ideal_qty / lot_size))
        actual_qty = lots * lot_size
        invested = actual_qty * entry_price
        
        trade = PaperTrade(
            symbol=selected_option["symbol"],
            company_name=f"{symbol} Option",
            sector="OPTION",
            direction=TradeDirection.LONG, # We are always BUYING options for now
            entry_date=date.today().strftime("%Y-%m-%d"),
            entry_price=entry_price,
            quantity=actual_qty,
            invested_amount=invested,
            stop_loss=round(sl, 2),
            stop_loss_fixed=round(sl, 2),
            target_price=round(target, 2),
            current_price=entry_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            highest_price=entry_price,
            days_in_trade=0,
            status=TradeStatus.OPEN,
            notes=f"Delta: {selected_option.get('delta')}, IV: {selected_option.get('iv')}"
        )
        
        db.add(trade)
        await db.commit()
        
        logger.info(f"F&O Trade ENTERED: {trade.symbol} | Qty: {actual_qty} @ {entry_price}")
        return trade
