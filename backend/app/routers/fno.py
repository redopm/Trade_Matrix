import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter
from app.services.options_data import OptionsDataFetcher
from app.services.greeks import GreeksCalculator
from app.services.fno_engine import FnoAnalyticsEngine
from app.services.hedge_finder import HedgeFinder
from app.services.reversal_engine import ReversalEngine

router = APIRouter(prefix="/fno", tags=["F&O"])

# In-memory OI snapshot — tracks previous OI values to calculate Change OI
# Key: symbol string, Value: oi at last fetch
_oi_snapshot: dict = {}

@router.get("/chain/{symbol}")
async def get_option_chain(symbol: str, atm_strike: Optional[int] = None):
    fetcher = OptionsDataFetcher()

    # ── Auto-detect ATM Strike & Spot Price ──────────────────────────────────
    index_map = {
        "NIFTY": ("NSE:NIFTY50-INDEX", 50),
        "BANKNIFTY": ("NSE:NIFTYBANK-INDEX", 100),
        "FINNIFTY": ("NSE:FINNIFTY-INDEX", 50),
        "MIDCPNIFTY": ("NSE:MIDCPNIFTY-INDEX", 25)
    }
    
    index_sym, step = index_map.get(symbol, ("NSE:NIFTY50-INDEX", 50))
    
    spot_price = 0.0
    raw = fetcher.fyers_client.fetch_quotes([index_sym])
    
    # Handle Fyers API rate limits explicitly
    if raw and raw.get("s") == "error":
        if raw.get("code") == 429:
            return {"error": "Fyers API rate limit reached. Please wait a moment and try again."}
        elif "message" in raw:
            return {"error": f"Fyers API Error: {raw['message']}"}

    if raw and "d" in raw and len(raw["d"]) > 0:
        spot_price = float(raw["d"][0]["v"].get("lp") or 0)
        
    if not atm_strike and spot_price > 0:
        atm_strike = int(round(spot_price / step) * step)
    elif not atm_strike:
        # Fallback to prevent querying all 200+ strikes when spot price is unavailable
        return {"error": f"Failed to fetch live spot price for {symbol} to determine ATM strike. API may be rate limited."}

    df = await fetcher.get_nearest_expiry_chain_df(symbol)
    if df is None or df.empty:
        return {"error": f"No option chain found for {symbol}. Check Fyers connection."}

    # ── Expiry meta ───────────────────────────────────────────────────────────
    expiry_epoch = int(df.iloc[0][8])  # numpy.int64 → native int
    now_epoch = datetime.now().timestamp()
    dte_days = max((expiry_epoch - now_epoch) / (24 * 3600), 0.01)

    # ── Filter exactly 12 strikes above and 12 strikes below ATM ─────────────────────────
    if atm_strike and not df.empty:
        import numpy as np
        unique_strikes = sorted(df[15].unique())
        atm_idx = next((i for i, s in enumerate(unique_strikes) if s >= atm_strike), -1)
        
        if atm_idx != -1:
            start_idx = max(0, atm_idx - 12)
            end_idx = min(len(unique_strikes), atm_idx + 13)
            selected_strikes = unique_strikes[start_idx:end_idx]
            df_filtered = df[df[15].isin(selected_strikes)]
        else:
            df_filtered = df
    else:
        df_filtered = df

    if df_filtered.empty:
        return {"error": "No strikes found around ATM. Check atm_strike value."}

    # sym → strike lookup
    sym_to_strike = {row[9]: float(row[15]) for _, row in df_filtered.iterrows()}
    symbols = df_filtered[9].tolist()

    # ── Fetch live quotes/depth concurrently ─────────────────────────────────────
    import asyncio
    all_quotes = []
    
    # Use concurrent depth fetcher because the standard quotes API omits Open Interest
    depth_results = await fetcher.fyers_client.fetch_depth_concurrent(symbols, max_workers=20)
    
    for sym in symbols:
        depth_data = depth_results.get(sym, {})
        current_oi = int(depth_data.get("oi") or 0)
        prev_oi = _oi_snapshot.get(sym, current_oi)  # First call: chng_oi = 0
        chng_oi = current_oi - prev_oi
        _oi_snapshot[sym] = current_oi  # Update snapshot
        all_quotes.append({
            "symbol": sym,
            "ltp": float(depth_data.get("ltp") or 0),
            "oi": current_oi,
            "chng_oi": chng_oi,
            "volume": int(depth_data.get("v") or 0),
            "prev_close": float(depth_data.get("c") or 0),
        })

    # ── Attach strike + type + Greeks to each quote ───────────────────────────
    underlying_price = float(atm_strike) if atm_strike else 0.0
    processed = []
    for q in all_quotes:
        sym = q.get("symbol", "")
        m = re.search(r'(CE|PE)$', sym)
        if not m:
            continue
        opt_type = m.group(1)
        strike = sym_to_strike.get(sym, 0)
        if strike == 0:
            continue

        spot = underlying_price if underlying_price > 0 else float(strike)
        g = GreeksCalculator.calculate_greeks(
            option_type=opt_type,
            underlying_price=spot,
            strike_price=float(strike),
            days_to_expiry=dte_days,
            option_price=q["ltp"],
        )
        # Convert numpy types to native Python floats to prevent FastAPI JSON serialization errors
        g_native = {
            k: float(v) if v is not None and str(v) != 'nan' else None 
            for k, v in g.items()
        }
        
        processed.append({**q, **g_native, "strike": strike, "type": opt_type})

    analysis = FnoAnalyticsEngine.analyze_chain(processed)
    reversals = ReversalEngine.calculate_fno_reversals(
        quotes=processed, 
        spot_price=spot_price, 
        atm_iv=analysis.get("avg_atm_iv", 15.0), 
        dte=dte_days
    )

    # ── AI Trade Suggestion Logic (Separated Buyer, Seller & Hedger) ────────────
    buyer_strategy = None
    seller_strategy = None
    sentiment = analysis.get("sentiment", "NEUTRAL")

    def get_quote_by_delta(q_list, target_delta):
        valid = [q for q in q_list if q.get("delta") is not None and q.get("ltp", 0) > 0]
        if not valid: return None
        return min(valid, key=lambda x: abs(float(x["delta"]) - target_delta))

    ce_quotes = [q for q in processed if q["type"] == "CE"]
    pe_quotes = [q for q in processed if q["type"] == "PE"]
    
    # ---------------------------------------------------------
    # AI STRATEGY ENGINE
    # ---------------------------------------------------------
    buyer_strategy = None
    seller_strategy = None
    hedging_strategy = None

    if sentiment in ["BULLISH", "OVERSOLD"]:
        # Best risk-reward for Buyers: Slightly ITM (Delta ~ 0.60) -> Lower theta decay, high probability
        buy_ce = get_quote_by_delta(ce_quotes, 0.60)
        # Safe premium collection for Sellers: OTM (Delta ~ 0.20) -> High probability of expiring worthless
        sell_ce = get_quote_by_delta(ce_quotes, 0.20)
        
        if buy_ce:
            buyer_strategy = {
                "name": "Directional Momentum Buy (ITM)",
                "reason": "Market is Bullish. Buying ITM Call (Delta ~0.60) for high probability & lower time decay.",
                "strike": buy_ce["strike"], "type": "CE", "action": "BUY",
                "entry": float(buy_ce["ltp"]),
                "target": round(float(buy_ce["ltp"]) * 1.5, 2),
                "sl": round(float(buy_ce["ltp"]) * 0.75, 2),
                "reversal": reversals["R1"],
                "reversal_data": reversals
            }
            
        sell_pe = get_quote_by_delta(pe_quotes, -0.20)
        if sell_pe:
            seller_strategy = {
                "name": "Support Writing (Premium Collection)",
                "reason": "Market is Bullish. Selling safe OTM Put at support to collect premium.",
                "strike": sell_pe["strike"], "type": "PE", "action": "SELL",
                "entry": float(sell_pe["ltp"]),
                "target": 0.05,
                "sl": round(float(sell_pe["ltp"]) * 2.0, 2),
                "margin_required": "~ ₹95,000"
            }
            
    else: # BEARISH or NEUTRAL
        buy_pe = get_quote_by_delta(pe_quotes, -0.60)
        sell_ce = get_quote_by_delta(ce_quotes, 0.20)
        
        if buy_pe:
            buyer_strategy = {
                "name": "Directional Momentum Buy (ITM)",
                "reason": "Market is Bearish. Buying ITM Put (Delta ~0.60) for high probability & lower time decay.",
                "strike": buy_pe["strike"], "type": "PE", "action": "BUY",
                "entry": float(buy_pe["ltp"]),
                "target": round(float(buy_pe["ltp"]) * 1.5, 2),
                "sl": round(float(buy_pe["ltp"]) * 0.75, 2),
                "reversal": reversals["S1"],
                "reversal_data": reversals
            }
            
        if sell_ce:
            seller_strategy = {
                "name": "Resistance Writing (Premium Collection)",
                "reason": "Market is Bearish. Selling safe OTM Call at resistance to collect premium.",
                "strike": sell_ce["strike"], "type": "CE", "action": "SELL",
                "entry": float(sell_ce["ltp"]),
                "target": 0.05,
                "sl": round(float(sell_ce["ltp"]) * 2.0, 2),
                "margin_required": "~ ₹95,000"
            }
            
    advanced_hedges = HedgeFinder.get_advanced_hedges(processed, sentiment, analysis)
    hedging_strategy = advanced_hedges["safe"]
    
    # Fallback for naked strategies if nothing found
    if not buyer_strategy and atm_strike:
        buyer_strategy = {
            "name": "Volatility Breakout Play",
            "reason": "Market is Neutral. Waiting for breakout.",
            "strike": atm_strike, "type": "CE", "action": "BUY", "entry": 0.0, "target": 0.0, "sl": 0.0, "reversal": 0
        }
        seller_strategy = {
            "name": "Straddle Writing",
            "reason": "Market is range-bound. Sell ATM Straddle to collect max premium.",
            "strike": atm_strike, "type": "CE", "action": "SELL", "entry": 0.0, "target": 0.0, "sl": 0.0, "margin_required": "~ ₹1,50,000"
        }

    # ── Ensure all numeric values in analysis are native Python types ──────────
    safe_analysis = {k: (int(v) if hasattr(v, 'item') else v) for k, v in analysis.items()}

    return {
        "analysis": safe_analysis,
        "quotes": processed,
        "dte": round(dte_days, 2),
        "expiry_epoch": expiry_epoch,
        "atm_strike": atm_strike,
        "spot_price": spot_price,
        "reversals": reversals,
        "buyer_strategy": buyer_strategy,
        "seller_strategy": seller_strategy,
        "hedging_strategy": hedging_strategy,
        "advanced_hedges": advanced_hedges
    }

import sys
import os
import pandas as pd

# Global predictor instance
_predictor = None

async def _get_predictor():
    global _predictor
    if _predictor is None:
        import sys
        import os
        # Add backend/ml/kronos_vertex to path so we can import model.kronos
        ml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/kronos_vertex"))
        if ml_path not in sys.path:
            sys.path.append(ml_path)
            
        from model.kronos import Kronos, KronosTokenizer, KronosPredictor
        
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        _predictor = KronosPredictor(model, tokenizer, max_context=512)
    return _predictor

@router.post("/predict")
async def predict_kronos(payload: dict):
    """
    Local RAM execution of Kronos Model.
    Expects payload: {"symbol": "NSE:NIFTY24APR22500CE", "pred_len": 5, "range_from": "2024-01-01"}
    """
    symbol = payload.get("symbol")
    pred_len = payload.get("pred_len", 5)
    
    if not symbol:
        return {"error": "Symbol is required"}
        
    fetcher = OptionsDataFetcher()
    from datetime import datetime, timedelta
    
    end_date = datetime.now()
    # Check if option symbol
    is_option = len(symbol) > 15 and ("CE" in symbol or "PE" in symbol)
    
    start_date = end_date - timedelta(days=20 if is_option else 100)
    r_from = start_date.strftime("%Y-%m-%d")
    r_to = end_date.strftime("%Y-%m-%d")
    resolution = "15" if is_option else "D"
    
    hist_df = fetcher.fyers_client.get_historical_data(symbol=symbol, resolution=resolution, range_from=r_from, range_to=r_to)
    
    if hist_df.empty:
        return {"error": f"Could not fetch historical data for {symbol} (Resolution: {resolution}, Range: {r_from} to {r_to})"}
        
    # Format data
    hist_records = hist_df.reset_index().rename(columns={"datetime": "timestamps"}).to_dict(orient="records")
    for r in hist_records:
        r['timestamps'] = str(r['timestamps'])
        r['open'] = r['Open']
        r['high'] = r['High']
        r['low'] = r['Low']
        r['close'] = r['Close']
        r['volume'] = r['Volume']
        r['amount'] = r['Volume'] * r['Close']
        
    # Prediction logic (Direct RAM Execution)
    try:
        predictor = await _get_predictor()
        
        # Prepare Dataframe for Kronos
        df_input = pd.DataFrame(hist_records[-400:])
        df_input['timestamps'] = pd.to_datetime(df_input['timestamps'])
        x_df = df_input[['open', 'high', 'low', 'close', 'volume', 'amount']]
        x_timestamp = df_input['timestamps']
        
        # Future timestamps
        last_date = df_input['timestamps'].iloc[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=pred_len, freq='B')
        y_timestamp = pd.to_datetime(future_dates)
        
        # Predict
        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_len,
            T=1.0,
            top_p=0.9,
            sample_count=1,
            verbose=False
        )
        
        pred_records = pred_df.reset_index().rename(columns={"index": "timestamps"}).to_dict(orient="records")
        for r in pred_records:
            if 'timestamps' in r:
                r['timestamps'] = str(r['timestamps'])
                
        return {"prediction": pred_records, "historical": hist_records[-100:]}
        
    except Exception as e:
        return {"error": f"Local Kronos Error: {str(e)}"}
