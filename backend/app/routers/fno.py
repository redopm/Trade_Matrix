import re
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.trade import PaperTrade, TradeStatus
from app.services.options_data import OptionsDataFetcher, normalize_underlying
from app.services.greeks import GreeksCalculator
from app.services.fno_engine import FnoAnalyticsEngine, AladdinOptionBrain
from app.services.reversal_engine import ReversalEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/fno", tags=["F&O"])

# 45s cache per (fo_underlying, atm_strike) to keep tab switching instant & avoid rate limits
_chain_cache: Dict[str, Dict[str, Any]] = {}
_CHAIN_CACHE_TTL = 45.0
# 120s cache for underlying technicals (RSI, 20/50 EMA)
_tech_cache: Dict[str, Dict[str, Any]] = {}
# 90s cache for aggregated institutional flow endpoint
_inst_flow_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


class DeployFnoLeg(BaseModel):
    symbol: Optional[str] = ""
    action: str  # "BUY" or "SELL"
    type: str    # "CE" or "PE"
    strike: float
    entry: float
    sl: Optional[float] = 0.0
    target: Optional[float] = 0.0
    qty: int = 1


class DeployFnoTradeRequest(BaseModel):
    underlying: str
    strategy_name: str
    lot_size: int = 65
    lots: int = 1
    conviction_score: Optional[float] = None
    notes: Optional[str] = None
    legs: List[DeployFnoLeg]


class AutoTradeRequest(BaseModel):
    min_conviction: float = 62.0
    lots: Optional[int] = None


def _compute_rsi_ema_sync(fetcher: OptionsDataFetcher, spot_fyers_sym: str, spot_price: float, day_chg_pct: float) -> Dict[str, Any]:
    """Compute EMA-20, EMA-50, and Wilder RSI-14 on the F&O underlying."""
    now = datetime.now()
    cached = _tech_cache.get(spot_fyers_sym)
    if cached and (time.time() - cached["ts"]) < 120:
        tech = dict(cached["data"])
        tech["day_change_pct"] = round(day_chg_pct, 2)
        return tech

    result = {
        "ema_20": round(spot_price, 2),
        "ema_50": round(spot_price, 2),
        "rsi_14": 50.0,
        "day_change_pct": round(day_chg_pct, 2),
        "trend": "NEUTRAL",
    }
    try:
        r_from = (now - timedelta(days=120)).strftime("%Y-%m-%d")
        r_to = now.strftime("%Y-%m-%d")
        df = fetcher.fyers_client.get_historical_data(symbol=spot_fyers_sym, resolution="D", range_from=r_from, range_to=r_to)
        if df is not None and not df.empty and "Close" in df.columns:
            closes = pd.Series(df["Close"].astype(float).values)
            if spot_price > 0 and len(closes) > 0:
                closes.iloc[-1] = float(spot_price)
            if len(closes) >= 20:
                ema_20 = float(closes.ewm(span=20, adjust=False).mean().iloc[-1])
                ema_50 = float(closes.ewm(span=min(50, len(closes)), adjust=False).mean().iloc[-1])
                delta = closes.diff()
                gain = delta.clip(lower=0.0).ewm(com=13, adjust=False).mean()
                loss = (-delta.clip(upper=0.0)).ewm(com=13, adjust=False).mean()
                rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 1e-9 else 10.0
                rsi_14 = float(100.0 - (100.0 / (1.0 + rs)))

                if spot_price > ema_20 and ema_20 > ema_50 and rsi_14 >= 54:
                    trend = "STRONG_BULLISH"
                elif spot_price > ema_20:
                    trend = "BULLISH"
                elif spot_price < ema_20 and ema_20 < ema_50 and rsi_14 <= 46:
                    trend = "STRONG_BEARISH"
                elif spot_price < ema_20:
                    trend = "BEARISH"
                else:
                    trend = "SIDEWAYS"

                result = {
                    "ema_20": round(ema_20, 2),
                    "ema_50": round(ema_50, 2),
                    "rsi_14": round(rsi_14, 2),
                    "day_change_pct": round(day_chg_pct, 2),
                    "trend": trend,
                }
                _tech_cache[spot_fyers_sym] = {"ts": time.time(), "data": result}
    except Exception as e:
        logger.warning(f"Underlying technicals fallback for {spot_fyers_sym}: {e}")
    return result


@router.get("/chain/{symbol}")
async def get_option_chain(symbol: str, atm_strike: Optional[int] = None, force_refresh: bool = False):
    fetcher = OptionsDataFetcher()

    fo_underlying, spot_fyers_sym, fallback_step = normalize_underlying(symbol)
    cache_key = f"{fo_underlying}:{atm_strike or 'AUTO'}"
    cached_entry = _chain_cache.get(cache_key)
    if not force_refresh and cached_entry and (time.time() - cached_entry["ts"]) < _CHAIN_CACHE_TTL:
        return cached_entry["data"]

    # Fetch native Fyers v3 Option Chain (Spot + Strikes + LTP + OI + OI Change + Volume + VIX in 1 call!)
    # Run symbol master CSV load (for exact NSE lot size) in parallel.
    oc_task = asyncio.to_thread(fetcher.fyers_client.fetch_option_chain, spot_fyers_sym, 18, "")
    df_task = fetcher.get_nearest_expiry_chain_df(fo_underlying)
    oc_raw, df = await asyncio.gather(oc_task, df_task)

    if oc_raw and oc_raw.get("s") == "error":
        if oc_raw.get("code") == 429:
            if cached_entry:
                return cached_entry["data"]
            return {"error": "Fyers API rate limit reached. Please wait a few seconds and try again."}
        return {"error": f"Fyers API Error: {oc_raw.get('message', oc_raw)}"}

    oc_data = (oc_raw or {}).get("data") or {}
    raw_chain = oc_data.get("optionsChain") or []
    expiry_list = oc_data.get("expiryData") or []
    india_vix_obj = oc_data.get("indiavixData") or {}
    india_vix = float(india_vix_obj.get("ltp") or 0) if isinstance(india_vix_obj, dict) else 0.0

    if not raw_chain:
        return {"error": f"No option chain returned for {fo_underlying}. Verify symbol is F&O enabled."}

    # Extract spot price & spot change from the underlying entry (strike_price == -1)
    spot_price = 0.0
    spot_chg_pct = 0.0
    option_rows = []
    for item in raw_chain:
        opt_type = item.get("option_type") or ""
        s_price = item.get("strike_price", -1)
        if opt_type == "" and s_price == -1:
            spot_price = float(item.get("ltp") or 0)
            spot_chg_pct = float(item.get("ltpchp") or 0)
        elif opt_type in ("CE", "PE") and s_price and float(s_price) > 0:
            option_rows.append(item)

    if not option_rows:
        return {"error": f"No CE/PE strikes returned in Fyers option chain for {fo_underlying}."}

    lot_size, csv_step = OptionsDataFetcher.extract_lot_size_and_step(df, fo_underlying, fallback_step)
    unique_strikes = sorted(set(float(item["strike_price"]) for item in option_rows))

    # Infer exact step from chain strikes when available
    step = csv_step
    if len(unique_strikes) >= 3:
        diffs = [round(unique_strikes[i + 1] - unique_strikes[i], 4) for i in range(len(unique_strikes) - 1) if unique_strikes[i + 1] > unique_strikes[i]]
        if diffs:
            step = float(min(diffs))

    if atm_strike and unique_strikes:
        atm_strike_val = min(unique_strikes, key=lambda s: abs(s - float(atm_strike)))
    elif spot_price > 0 and unique_strikes:
        atm_strike_val = min(unique_strikes, key=lambda s: abs(s - spot_price))
    else:
        atm_strike_val = unique_strikes[len(unique_strikes) // 2]

    atm_out = int(atm_strike_val) if float(atm_strike_val).is_integer() else round(atm_strike_val, 2)

    # ── Expiry meta ───────────────────────────────────────────────────────────
    expiry_epoch = 0
    if expiry_list and isinstance(expiry_list[0], dict) and expiry_list[0].get("expiry"):
        expiry_epoch = int(float(expiry_list[0]["expiry"]))
    elif df is not None and not df.empty:
        expiry_epoch = int(df.iloc[0][8])
    else:
        expiry_epoch = int(datetime.now().timestamp() + 3 * 86400)

    now_epoch = datetime.now().timestamp()
    dte_days = max((expiry_epoch - now_epoch) / (24 * 3600), 0.01)

    # ── Filter to ATM ±12 strikes if wider range was returned ─────────────────
    if unique_strikes:
        atm_idx = unique_strikes.index(atm_strike_val)
        start_idx = max(0, atm_idx - 12)
        end_idx = min(len(unique_strikes), atm_idx + 13)
        allowed_strikes = set(unique_strikes[start_idx:end_idx])
    else:
        allowed_strikes = set()

    # Fetch underlying RSI/EMA-20/EMA-50 (1 cached history call every 120s)
    underlying_tech = await asyncio.to_thread(_compute_rsi_ema_sync, fetcher, spot_fyers_sym, spot_price, spot_chg_pct)

    # ── Attach strike + type + Greeks + liquidity to each option quote ────────
    processed = []
    spot = spot_price if spot_price > 0 else float(atm_strike_val)
    for item in option_rows:
        strike = float(item["strike_price"])
        if allowed_strikes and strike not in allowed_strikes:
            continue
        sym = item.get("symbol", "")
        opt_type = item.get("option_type", "")
        ltp = float(item.get("ltp") or 0)
        ltp_chg = float(item.get("ltpch") or 0)
        prev_close = round(max(0.0, ltp - ltp_chg), 2) if ltp > 0 else 0.0
        current_oi = int(item.get("oi") or 0)
        chng_oi = int(item.get("oich") or 0)

        g = GreeksCalculator.calculate_greeks(
            option_type=opt_type,
            underlying_price=spot,
            strike_price=strike,
            days_to_expiry=dte_days,
            option_price=ltp,
            symbol_key=sym,
        )
        g_native = {
            k: float(v) if v is not None and str(v) != 'nan' else None
            for k, v in g.items()
        }
        strike_fmt = int(strike) if float(strike).is_integer() else round(strike, 2)
        processed.append({
            "symbol": sym,
            "ltp": ltp,
            "oi": current_oi,
            "chng_oi": chng_oi,
            "volume": int(item.get("volume") or 0),
            "prev_close": prev_close,
            "bid": float(item.get("bid") or 0),
            "ask": float(item.get("ask") or 0),
            **g_native,
            "strike": strike_fmt,
            "type": opt_type,
            "lot_size": lot_size,
        })

    # 4-Quadrant Buildup + Analytics
    FnoAnalyticsEngine.enrich_quotes_buildup(processed)
    analysis = FnoAnalyticsEngine.analyze_chain(processed)

    # ── Fix avg_atm_iv & IV Skew BEFORE calling ReversalEngine ────────────────
    atm_window = max(step * 2.1, spot_price * 0.015) if spot_price > 0 else (step * 2.1)
    atm_ce_ivs = [float(q["iv"]) for q in processed if q["type"] == "CE" and abs(float(q["strike"]) - atm_strike_val) <= atm_window and q.get("iv") and 0.5 < float(q["iv"]) < 250.0]
    atm_pe_ivs = [float(q["iv"]) for q in processed if q["type"] == "PE" and abs(float(q["strike"]) - atm_strike_val) <= atm_window and q.get("iv") and 0.5 < float(q["iv"]) < 250.0]
    all_atm_ivs = atm_ce_ivs + atm_pe_ivs
    avg_atm_iv = round(sum(all_atm_ivs) / len(all_atm_ivs), 2) if all_atm_ivs else 15.0
    atm_ce_iv = round(sum(atm_ce_ivs) / len(atm_ce_ivs), 2) if atm_ce_ivs else avg_atm_iv
    atm_pe_iv = round(sum(atm_pe_ivs) / len(atm_pe_ivs), 2) if atm_pe_ivs else avg_atm_iv
    iv_skew = round(atm_pe_iv - atm_ce_iv, 2)

    analysis["avg_atm_iv"] = avg_atm_iv
    analysis["atm_ce_iv"] = atm_ce_iv
    analysis["atm_pe_iv"] = atm_pe_iv
    analysis["iv_skew"] = iv_skew

    reversals = ReversalEngine.calculate_fno_reversals(
        quotes=processed,
        spot_price=spot_price,
        atm_iv=avg_atm_iv,
        dte=dte_days
    )

    # ── Run 5-Pillar AladdinOptionBrain ───────────────────────────────────────
    brain_result = AladdinOptionBrain.evaluate_chain(
        symbol=fo_underlying,
        spot_price=spot_price,
        quotes=processed,
        analysis=analysis,
        reversals=reversals,
        dte_days=dte_days,
        lot_size=lot_size,
        underlying_tech=underlying_tech,
    )

    advanced_hedges = brain_result["hedges"]
    hedging_strategy = advanced_hedges.get("safe")
    top_picks = brain_result.get("top_picks", [])

    # Align buyer_strategy & seller_strategy with Multi-Pillar Aladdin picks (keeping 100% legacy fields)
    buyer_pick = next((p for p in top_picks if p.get("action") == "BUY"), None)
    seller_pick = next((p for p in top_picks if p.get("action") == "SELL"), None)

    if buyer_pick and brain_result["directional_bias"] != "RANGE_BOUND":
        buyer_strategy = {
            "name": buyer_pick["name"],
            "reason": buyer_pick["rationale"],
            "symbol": buyer_pick["symbol"],
            "strike": buyer_pick["strike"],
            "type": buyer_pick["type"],
            "action": "BUY",
            "entry": buyer_pick["entry"],
            "target": buyer_pick["target_1"],
            "sl": buyer_pick["sl"],
            "lot_size": lot_size,
            "conviction_score": buyer_pick["conviction_score"],
            "pop_pct": buyer_pick["pop_pct"],
            "reversal": reversals.get("R1" if buyer_pick["type"] == "CE" else "S1", 0),
            "reversal_data": reversals,
        }
    else:
        atm_ce = next((q for q in processed if q["strike"] == atm_out and q["type"] == "CE"), None)
        buyer_strategy = {
            "name": "Wait — Range-Bound / Theta Shield" if brain_result["theta_shield_active"] else "Wait — Sideways Consolidation",
            "reason": (
                f"5-Pillar Aladdin Bias is {brain_result['directional_bias']} (Conviction {brain_result['conviction_score']}%). "
                f"Use the Iron Condor / Defined-Risk Spread in Pick #2 instead of naked buying."
            ),
            "symbol": atm_ce["symbol"] if atm_ce else "",
            "strike": atm_out,
            "type": "CE",
            "action": "WAIT",
            "entry": 0.0,
            "target": 0.0,
            "sl": 0.0,
            "lot_size": lot_size,
            "conviction_score": brain_result["conviction_score"],
            "pop_pct": brain_result["win_probability_pct"],
            "reversal": reversals.get("R1", 0),
            "reversal_data": reversals,
        }

    if seller_pick:
        seller_strategy = {
            "name": seller_pick["name"],
            "reason": seller_pick["rationale"],
            "symbol": seller_pick["symbol"],
            "strike": seller_pick["strike"],
            "type": seller_pick["type"],
            "action": "SELL",
            "entry": seller_pick["entry"],
            "target": seller_pick["target_1"],
            "sl": seller_pick["sl"],
            "lot_size": lot_size,
            "conviction_score": seller_pick["conviction_score"],
            "pop_pct": seller_pick["pop_pct"],
            "margin_required": f"~ ₹{int(seller_pick['capital_required']):,}",
        }
    else:
        atm_ce = next((q for q in processed if q["strike"] == atm_out and q["type"] == "CE"), None)
        atm_pe = next((q for q in processed if q["strike"] == atm_out and q["type"] == "PE"), None)
        comb = round(float((atm_ce or {}).get("ltp") or 0) + float((atm_pe or {}).get("ltp") or 0), 2)
        seller_strategy = {
            "name": "ATM Straddle Sell (Range-Bound)",
            "reason": f"PCR {analysis['pcr']:.2f} — balanced flows. Combined ATM Straddle Premium: ₹{comb:.2f}.",
            "symbol": (atm_ce or {}).get("symbol", ""),
            "strike": atm_out,
            "type": "CE+PE",
            "action": "SELL STRADDLE",
            "entry": comb,
            "target": 0.05,
            "sl": round(comb * 1.8, 2),
            "lot_size": lot_size,
            "conviction_score": brain_result["conviction_score"],
            "pop_pct": brain_result["win_probability_pct"],
            "margin_required": f"~ ₹{int(spot_price * lot_size * 0.16):,}" if spot_price > 0 else "~ ₹1,30,000",
        }

    safe_analysis = {k: (v.item() if hasattr(v, 'item') else v) for k, v in analysis.items()}
    safe_analysis["india_vix"] = india_vix

    response_payload = {
        "symbol": fo_underlying,
        "spot_fyers_symbol": spot_fyers_sym,
        "spot_change_pct": round(spot_chg_pct, 2),
        "india_vix": india_vix,
        "lot_size": lot_size,
        "strike_step": step,
        "timestamp": datetime.now().isoformat(),
        "analysis": safe_analysis,
        "quotes": processed,
        "dte": round(dte_days, 2),
        "expiry_epoch": expiry_epoch,
        "atm_strike": atm_out,
        "spot_price": spot_price,
        "reversals": reversals,
        "buyer_strategy": buyer_strategy,
        "seller_strategy": seller_strategy,
        "hedging_strategy": hedging_strategy,
        "advanced_hedges": advanced_hedges,
        "aladdin_option_brain": brain_result,
    }
    _chain_cache[cache_key] = {"ts": time.time(), "data": response_payload}
    return response_payload


@router.post("/deploy-trade", status_code=201)
async def deploy_fno_trade(
    request: DeployFnoTradeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Deploy a single-leg or multi-leg F&O option strategy into Paper Trading.
    Tagged with experiment_arm='FNO_ALADDIN' so Equity Forward Testing Protocol
    v2.1.2 ('TOOL_TOP10') remains 100% isolated.
    """
    from datetime import date as dt_date
    fo_underlying, _, _ = normalize_underlying(request.underlying)
    if not request.legs:
        raise HTTPException(status_code=400, detail="At least one option leg is required.")

    # Resolve missing option symbols from chain master if needed
    missing_syms = [leg for leg in request.legs if not leg.symbol]
    chain_df = None
    if missing_syms:
        fetcher = OptionsDataFetcher()
        chain_df = await fetcher.get_nearest_expiry_chain_df(fo_underlying)

    resolved_legs = []
    total_capital_needed = 0.0
    for leg in request.legs:
        opt_sym = leg.symbol
        if not opt_sym and chain_df is not None and not chain_df.empty:
            match = chain_df[(chain_df[15] == float(leg.strike)) & (chain_df[16] == leg.type.upper())]
            if not match.empty:
                opt_sym = str(match.iloc[0][9])
        if not opt_sym:
            opt_sym = f"NSE:{fo_underlying}{int(leg.strike)}{leg.type.upper()}"

        qty = max(1, int(leg.qty)) * max(1, int(request.lot_size)) * max(1, int(request.lots))
        entry_px = max(0.05, float(leg.entry))
        invested = round(entry_px * qty, 2)
        total_capital_needed += invested

        is_buy = leg.action.upper() == "BUY"
        direction = "LONG" if is_buy else "SHORT"
        sl_val = float(leg.sl or 0.0)
        if sl_val <= 0:
            sl_val = round(entry_px * 0.72, 2) if is_buy else round(entry_px * 1.80, 2)
        tgt_val = float(leg.target or 0.0)
        if tgt_val <= 0:
            tgt_val = round(entry_px * 1.45, 2) if is_buy else round(max(0.05, entry_px * 0.30), 2)

        resolved_legs.append({
            "symbol": opt_sym,
            "direction": direction,
            "entry": entry_px,
            "qty": qty,
            "invested": invested,
            "sl": sl_val,
            "target": tgt_val,
            "leg": leg,
        })

    # Strict Rigid Capital Enforcement
    res_open = await db.execute(select(PaperTrade).where(PaperTrade.status == TradeStatus.OPEN))
    open_trades = res_open.scalars().all()
    res_closed = await db.execute(select(PaperTrade).where(PaperTrade.status != TradeStatus.OPEN))
    closed_trades = res_closed.scalars().all()

    realized_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
    total_invested_currently = sum(t.invested_amount for t in open_trades)
    available_cash = settings.DEFAULT_CAPITAL + realized_pnl - total_invested_currently

    if available_cash <= 0 or total_capital_needed > available_cash:
        raise HTTPException(
            status_code=400,
            detail=f"Rigid Fund Limit: Strategy requires ₹{total_capital_needed:,.2f}, available paper cash is ₹{max(0.0, available_cash):,.2f}. Close open trades before deploying."
        )

    deployed = []
    conv_tag = f" | Conviction {request.conviction_score:.1f}%" if request.conviction_score else ""
    note_str = f"[{request.strategy_name}{conv_tag}] {request.notes or ''}".strip()

    for item in resolved_legs:
        leg = item["leg"]
        strike_disp = int(leg.strike) if float(leg.strike).is_integer() else leg.strike
        trade = PaperTrade(
            symbol=item["symbol"],
            company_name=f"{fo_underlying} {strike_disp} {leg.type.upper()}",
            sector="F&O_OPTIONS",
            experiment_arm="FNO_ALADDIN",
            direction=item["direction"],
            entry_date=dt_date.today().strftime("%Y-%m-%d"),
            entry_price=item["entry"],
            quantity=item["qty"],
            invested_amount=item["invested"],
            stop_loss=item["sl"],
            stop_loss_fixed=item["sl"],
            target_price=item["target"],
            current_price=item["entry"],
            highest_price=item["entry"],
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            days_in_trade=0,
            status=TradeStatus.OPEN,
            notes=note_str,
        )
        db.add(trade)
        await db.flush()
        t_dict = trade.__dict__.copy()
        t_dict.pop("_sa_instance_state", None)
        deployed.append(t_dict)

    await db.commit()
    return {
        "status": "DEPLOYED",
        "strategy": request.strategy_name,
        "underlying": fo_underlying,
        "legs_count": len(deployed),
        "total_capital_used": round(total_capital_needed, 2),
        "trades": deployed,
    }


@router.post("/auto-trade/{symbol}")
async def run_fno_auto_pilot(
    symbol: str,
    req: Optional[AutoTradeRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Aladdin F&O Auto-Pilot:
    Evaluates the live option chain with the 5-Pillar AladdinOptionBrain.
    If conviction >= min_conviction and no open FNO_ALADDIN position exists for
    this underlying, automatically deploys Pick #1 into Paper Trading.
    """
    min_conv = req.min_conviction if req else 62.0
    fo_underlying, _, _ = normalize_underlying(symbol)

    chain = await get_option_chain(fo_underlying)
    if chain.get("error"):
        raise HTTPException(status_code=400, detail=chain["error"])

    brain = chain.get("aladdin_option_brain") or {}
    conviction = float(brain.get("conviction_score") or 0)
    top_picks = brain.get("top_picks") or []

    if conviction < min_conv:
        return {
            "status": "SKIPPED",
            "reason": f"Conviction {conviction:.1f}% is below threshold {min_conv:.1f}%. Protecting capital.",
            "conviction_score": conviction,
            "directional_bias": brain.get("directional_bias"),
        }

    if not top_picks:
        return {"status": "SKIPPED", "reason": "No liquid actionable option pick found in current chain."}

    # Check duplicate active FNO_ALADDIN trade for same underlying
    existing_stmt = select(PaperTrade).where(
        PaperTrade.status == TradeStatus.OPEN,
        PaperTrade.experiment_arm == "FNO_ALADDIN",
        PaperTrade.company_name.ilike(f"{fo_underlying} %"),
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        return {
            "status": "SKIPPED",
            "reason": f"Active F&O Auto-Pilot trade already open for {fo_underlying}.",
            "conviction_score": conviction,
        }

    pick = top_picks[0]
    lots = req.lots if (req and req.lots) else int(pick.get("recommended_lots") or 1)
    deploy_req = DeployFnoTradeRequest(
        underlying=fo_underlying,
        strategy_name=f"Auto-Pilot: {pick['name']}",
        lot_size=int(chain.get("lot_size") or 65),
        lots=lots,
        conviction_score=conviction,
        notes=pick.get("rationale"),
        legs=[DeployFnoLeg(**leg) for leg in (pick.get("legs") or [])],
    )
    res = await deploy_fno_trade(deploy_req, db)
    return {
        "status": "EXECUTED",
        "conviction_score": conviction,
        "pick": pick,
        **res,
    }


@router.get("/institutional-flow")
async def get_institutional_flow():
    """
    Aggregates real-time Institutional Smart Money positioning from live NIFTY & BANKNIFTY
    option chains (Put vs Call writing flow, OI dominance, IV Skew, Max Pain, and Money Flow Bias).
    """
    global _inst_flow_cache
    if _inst_flow_cache["data"] and (time.time() - _inst_flow_cache["ts"]) < 90:
        return _inst_flow_cache["data"]

    nifty_res, bank_res = await asyncio.gather(
        get_option_chain("NIFTY"),
        get_option_chain("BANKNIFTY"),
        return_exceptions=True,
    )

    indices_summary = []
    total_put_oi = 0
    total_call_oi = 0
    total_put_chng = 0
    total_call_chng = 0
    pcrs = []

    for label, res in [("NIFTY", nifty_res), ("BANKNIFTY", bank_res)]:
        if isinstance(res, dict) and not res.get("error"):
            an = res.get("analysis") or {}
            brain = res.get("aladdin_option_brain") or {}
            pe_oi = int(an.get("total_put_oi") or 0)
            ce_oi = int(an.get("total_call_oi") or 0)
            pe_chng = int(an.get("total_put_chng_oi") or 0)
            ce_chng = int(an.get("total_call_chng_oi") or 0)
            pcr_val = float(an.get("pcr") or 1.0)

            total_put_oi += pe_oi
            total_call_oi += ce_oi
            total_put_chng += pe_chng
            total_call_chng += ce_chng
            pcrs.append(pcr_val)

            indices_summary.append({
                "symbol": label,
                "spot_price": res.get("spot_price", 0),
                "spot_change_pct": res.get("spot_change_pct", 0),
                "pcr": pcr_val,
                "vol_pcr": an.get("vol_pcr", pcr_val),
                "avg_atm_iv": an.get("avg_atm_iv", 15.0),
                "iv_skew": an.get("iv_skew", 0.0),
                "sentiment": an.get("sentiment", "NEUTRAL"),
                "max_pain": an.get("max_pain", 0),
                "put_oi": pe_oi,
                "call_oi": ce_oi,
                "put_chng_oi": pe_chng,
                "call_chng_oi": ce_chng,
                "call_wall": an.get("highest_call_oi_strike", 0),
                "put_wall": an.get("highest_put_oi_strike", 0),
                "conviction_score": brain.get("conviction_score", 50.0),
                "directional_bias": brain.get("directional_bias", "RANGE_BOUND"),
            })

    combined_oi = total_put_oi + total_call_oi
    put_writing_share_pct = round((total_put_oi / combined_oi) * 100.0, 1) if combined_oi > 0 else 50.0
    call_writing_share_pct = round(100.0 - put_writing_share_pct, 1)
    agg_pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0

    if agg_pcr >= 1.12:
        inst_bias = "BULLISH"
        inst_reason = f"Institutional Option Writers hold more Put OI ({put_writing_share_pct}% Put Share | Aggregate Index PCR {agg_pcr:.2f}), creating a supportive floor."
    elif agg_pcr <= 0.88:
        inst_bias = "BEARISH"
        inst_reason = f"Heavy Call OI Overhead ({call_writing_share_pct}% Call Share | Aggregate Index PCR {agg_pcr:.2f}) indicates institutional resistance capping rallies."
    else:
        inst_bias = "RANGE_BOUND"
        inst_reason = f"Balanced Institutional Call/Put Writing (PCR {agg_pcr:.2f} | {put_writing_share_pct}% Put vs {call_writing_share_pct}% Call Share) points to Iron Condor / Range regime."

    payload = {
        "timestamp": datetime.now().isoformat(),
        "aggregate_pcr": agg_pcr,
        "put_writing_share_pct": put_writing_share_pct,
        "call_writing_share_pct": call_writing_share_pct,
        "total_index_put_oi": total_put_oi,
        "total_index_call_oi": total_call_oi,
        "net_intraday_oi_flow": total_put_chng - total_call_chng,
        "institutional_bias": inst_bias,
        "interpretation": inst_reason,
        "indices": indices_summary,
    }
    if indices_summary:
        _inst_flow_cache = {"ts": time.time(), "data": payload}
    return payload


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
