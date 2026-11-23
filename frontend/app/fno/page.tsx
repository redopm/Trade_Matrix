"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  AlertCircle,
  BrainCircuit,
  Zap,
  ShieldCheck,
  TrendingUp,
  CheckCircle2,
  Bot,
  Briefcase,
  ArrowUpRight,
} from "lucide-react";
import { fetchOptionChain, fnoApi, tradesApi, predictKronos } from "@/lib/api";
import { FnoHeaderNav, getSavedFnoSymbol } from "@/components/FnoHeaderNav";

export default function FnoDashboard() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [atmStrike, setAtmStrike] = useState<number | "">("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [strikeRadius, setStrikeRadius] = useState(12);
  const [selectedTrade, setSelectedTrade] = useState<{
    role: "BUYER" | "SELLER";
    strategy: any;
  } | null>(null);
  const [isTrading, setIsTrading] = useState(false);
  const [autoPilotRunning, setAutoPilotRunning] = useState(false);
  const [actionBanner, setActionBanner] = useState<{
    type: "success" | "info" | "error";
    text: string;
  } | null>(null);
  const [openFnoTrades, setOpenFnoTrades] = useState<any[]>([]);
  const [kronosPrediction, setKronosPrediction] = useState<any>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionDays, setPredictionDays] = useState(5);
  const [debouncedAtmStrike, setDebouncedAtmStrike] = useState<number | string>("");

  useEffect(() => {
    const saved = getSavedFnoSymbol();
    setSymbol(saved);
  }, []);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedAtmStrike(atmStrike);
    }, 500);
    return () => clearTimeout(handler);
  }, [atmStrike]);

  const loadOpenFnoTrades = async () => {
    try {
      const res = await tradesApi.getOpenTrades();
      const list = (res.data || []).filter(
        (t: any) =>
          (t.symbol || "").endsWith("CE") ||
          (t.symbol || "").endsWith("PE") ||
          (t.sector || "").startsWith("F&O")
      );
      setOpenFnoTrades(list);
    } catch {
      // ignore trade list errors
    }
  };

  const loadData = async (showLoader = true, targetSym = symbol) => {
    if (showLoader) setLoading(true);
    else setIsRefreshing(true);
    try {
      const atm = typeof atmStrike === "number" ? atmStrike : undefined;
      const [res] = await Promise.all([
        fetchOptionChain(targetSym, atm),
        loadOpenFnoTrades(),
      ]);
      setData(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
    setIsRefreshing(false);
  };

  useEffect(() => {
    loadData(true, symbol);

    const interval = setInterval(() => {
      const now = new Date();
      const day = now.getDay();
      const timeInMinutes = now.getHours() * 60 + now.getMinutes();
      const isMarketOpen =
        day >= 1 && day <= 5 && timeInMinutes >= 555 && timeInMinutes <= 930;
      if (isMarketOpen) {
        loadData(false, symbol);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [symbol, debouncedAtmStrike]);

  const handleSymbolChange = (nextSym: string) => {
    setSymbol(nextSym);
    setAtmStrike("");
    setSelectedTrade(null);
    setKronosPrediction(null);
  };

  const handleDeployPick = async (pick: any) => {
    setIsTrading(true);
    setActionBanner(null);
    try {
      const res = await fnoApi.deployTrade({
        underlying: symbol,
        strategy_name: pick.name,
        lot_size: data?.lot_size || pick.lot_size || 65,
        lots: pick.recommended_lots || 1,
        conviction_score: pick.conviction_score,
        notes: pick.rationale,
        legs: pick.legs || [
          {
            symbol: pick.symbol,
            action: pick.action,
            type: pick.type,
            strike: pick.strike,
            entry: pick.entry,
            sl: pick.sl,
            target: pick.target_1 || pick.target,
            qty: 1,
          },
        ],
      });
      setActionBanner({
        type: "success",
        text: `Deployed ${res.data.strategy} (${res.data.legs_count} leg) into Paper Portfolio — Capital ₹${Number(
          res.data.total_capital_used || 0
        ).toLocaleString("en-IN")}`,
      });
      await loadOpenFnoTrades();
    } catch (e: any) {
      setActionBanner({
        type: "error",
        text: "Failed to deploy trade: " + (e.message || "Unknown error"),
      });
    }
    setIsTrading(false);
  };

  const handleRunAutoPilot = async () => {
    setAutoPilotRunning(true);
    setActionBanner(null);
    try {
      const res = await fnoApi.autoTrade(symbol, 62.0);
      const body = res.data;
      if (body.status === "EXECUTED") {
        setActionBanner({
          type: "success",
          text: `Aladdin Auto-Pilot Executed ${body.strategy} (${body.conviction_score}% conviction) into F&O Paper Trading!`,
        });
        await loadOpenFnoTrades();
      } else {
        setActionBanner({
          type: "info",
          text: `Auto-Pilot (${symbol}): ${body.reason}`,
        });
      }
    } catch (e: any) {
      setActionBanner({
        type: "error",
        text: "Auto-Pilot error: " + (e.message || "Unknown error"),
      });
    }
    setAutoPilotRunning(false);
  };

  const handlePlaceTrade = async (role: "BUYER" | "SELLER", strategy: any) => {
    setIsTrading(true);
    setActionBanner(null);
    try {
      const q = data?.quotes?.find(
        (x: any) => x.strike === strategy.strike && x.type === strategy.type
      );
      if (!q && !strategy.symbol)
        throw new Error("Could not find contract symbol for this strike");

      const legSymbol = strategy.symbol || q?.symbol;
      const entryPx = Number(strategy.entry || q?.ltp || 0);
      const lotSize = data?.lot_size || q?.lot_size || 65;

      const res = await fnoApi.deployTrade({
        underlying: symbol,
        strategy_name: strategy.name || `${symbol} ${strategy.strike} ${strategy.type}`,
        lot_size: lotSize,
        lots: 1,
        conviction_score: strategy.conviction_score || data?.aladdin_option_brain?.conviction_score,
        notes: `Deployed from Option Chain as ${role}`,
        legs: [
          {
            symbol: legSymbol,
            action: role === "BUYER" ? "BUY" : "SELL",
            type: strategy.type === "CE+PE" ? "CE" : strategy.type,
            strike: strategy.strike,
            entry: entryPx,
            sl: Number(strategy.sl || 0),
            target: Number(strategy.target || 0),
            qty: 1,
          },
        ],
      });
      setActionBanner({
        type: "success",
        text: `Placed Paper Trade for ${legSymbol} (Qty ${lotSize}) — Capital ₹${Number(
          res.data.total_capital_used || 0
        ).toLocaleString("en-IN")}`,
      });
      setSelectedTrade(null);
      await loadOpenFnoTrades();
    } catch (e: any) {
      setActionBanner({
        type: "error",
        text: "Error placing trade: " + (e.message || "Unknown error"),
      });
    }
    setIsTrading(false);
  };

  const allStrikes = Array.from(
    new Set(data?.quotes?.map((q: any) => q.strike) || [])
  ).sort((a: any, b: any) => a - b) as number[];

  const centerStrike =
    data?.atm_strike || (typeof atmStrike === "number" ? atmStrike : null);

  let displayStrikes = allStrikes;
  if (centerStrike && allStrikes.includes(centerStrike)) {
    const atmIndex = allStrikes.indexOf(centerStrike);
    const start = Math.max(0, atmIndex - strikeRadius);
    const end = Math.min(allStrikes.length, atmIndex + strikeRadius + 1);
    displayStrikes = allStrikes.slice(start, end);
  }

  const brain = data?.aladdin_option_brain;
  const topPicks = brain?.top_picks || [];

  const getSentimentColor = (sentiment: string) => {
    if (sentiment?.includes("BULLISH") || sentiment?.includes("OVERSOLD"))
      return "text-emerald-600";
    if (sentiment?.includes("BEARISH") || sentiment?.includes("OVERBOUGHT"))
      return "text-red-600";
    return "text-slate-600";
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-14">
      <FnoHeaderNav
        activeTab="chain"
        title="Aladdin F&O Terminal"
        subtitle="5-Pillar Option Conviction Brain, Greeks & Automated Paper Execution"
        symbol={symbol}
        onSymbolChange={handleSymbolChange}
        spotPrice={data?.spot_price}
        spotChangePct={data?.spot_change_pct}
        atmStrike={data?.atm_strike}
        lotSize={data?.lot_size}
        dte={data?.dte}
        convictionScore={brain?.conviction_score}
        directionalBias={brain?.directional_bias}
        onRefresh={() => loadData(true, symbol)}
        isRefreshing={loading || isRefreshing}
        showAtmInput={true}
        atmInput={atmStrike}
        onAtmInputChange={setAtmStrike}
        rightExtra={
          <button
            onClick={handleRunAutoPilot}
            disabled={autoPilotRunning || loading || !!data?.error}
            className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-3.5 py-2 rounded-lg text-sm font-bold shadow-sm transition-colors"
          >
            <Bot size={16} />
            {autoPilotRunning ? "Scanning..." : "Run Auto-Pilot"}
          </button>
        }
      />

      {actionBanner && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-4">
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-sm font-medium ${
              actionBanner.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : actionBanner.type === "error"
                ? "bg-red-50 border-red-200 text-red-800"
                : "bg-blue-50 border-blue-200 text-blue-800"
            }`}
          >
            <div className="flex items-center gap-2">
              {actionBanner.type === "success" ? (
                <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle size={18} className="shrink-0" />
              )}
              <span>{actionBanner.text}</span>
            </div>
            <button
              onClick={() => setActionBanner(null)}
              className="text-xs font-bold opacity-70 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <div className="animate-spin rounded-full h-11 w-11 border-4 border-slate-200 border-t-indigo-600" />
          <p className="text-sm text-slate-500 font-medium">
            Computing 5-Pillar Option Conviction & Black-Scholes Greeks for {symbol}...
          </p>
        </div>
      ) : data?.error ? (
        <div className="max-w-4xl mx-auto p-6">
          <div className="bg-red-50 border border-red-200 text-red-800 p-5 rounded-xl flex items-start gap-3">
            <AlertCircle className="shrink-0 mt-0.5 text-red-600" />
            <div>
              <h3 className="font-bold">Option Chain Unavailable</h3>
              <p className="text-sm mt-1">{data.error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
          {/* ALADDIN OPTION BRAIN HERO + 5-PILLAR BREAKDOWN */}
          {brain && (
            <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl border border-indigo-500/30 shadow-xl overflow-hidden">
              <div className="p-5 sm:p-6 border-b border-white/10 flex flex-col lg:flex-row justify-between gap-5">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-200 text-xs font-bold">
                      <BrainCircuit size={14} /> ALADDIN OPTION BRAIN
                    </span>
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        brain.directional_bias === "BULLISH"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/30"
                          : brain.directional_bias === "BEARISH"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-400/30"
                          : "bg-amber-500/20 text-amber-300 border border-amber-400/30"
                      }`}
                    >
                      {brain.directional_bias} • MODE:{" "}
                      {String(brain.recommended_mode || "").replace(/_/g, " ")}
                    </span>
                    {brain.theta_shield_active && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/25 border border-amber-400/40 text-amber-200 text-xs font-bold">
                        <ShieldCheck size={13} /> THETA SHIELD ACTIVE ({data.dte?.toFixed(1)}d Left)
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-baseline gap-4 pt-1">
                    <div>
                      <span className="text-3xl sm:text-4xl font-black text-white">
                        {brain.conviction_score}%
                      </span>
                      <span className="ml-2 text-xs font-bold uppercase tracking-wider text-indigo-300">
                        Conviction (Grade {brain.grade})
                      </span>
                    </div>
                    <div className="text-xs sm:text-sm text-slate-300 flex flex-wrap gap-3">
                      <span>
                        Est. Win Prob (PoP):{" "}
                        <strong className="text-emerald-300">
                          {brain.win_probability_pct}%
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        RSI(14):{" "}
                        <strong className="text-white">
                          {brain.underlying_technicals?.rsi_14}
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        EMA20 / EMA50:{" "}
                        <strong className="text-white">
                          {brain.underlying_technicals?.ema_20} /{" "}
                          {brain.underlying_technicals?.ema_50}
                        </strong>
                      </span>
                    </div>
                  </div>
                </div>

                {/* 5-PILLAR SCORE CARDS */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 lg:max-w-2xl w-full">
                  {brain.pillars?.map((p: any) => {
                    const pct = Math.round((p.score / p.max) * 100);
                    return (
                      <div
                        key={p.key}
                        title={p.status}
                        className="bg-white/5 border border-white/10 rounded-xl p-2.5 flex flex-col justify-between"
                      >
                        <div className="text-[10px] font-semibold text-slate-300 leading-tight">
                          {p.label}
                        </div>
                        <div className="mt-2">
                          <div className="flex justify-between items-baseline text-xs font-bold">
                            <span className="text-white">
                              {p.score}/{p.max}
                            </span>
                            <span className="text-indigo-300">{pct}%</span>
                          </div>
                          <div className="w-full bg-white/10 h-1.5 rounded-full mt-1 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                pct >= 75
                                  ? "bg-emerald-400"
                                  : pct >= 55
                                  ? "bg-indigo-400"
                                  : "bg-amber-400"
                              }`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* TOP 3 RANKED HIGH-ACCURACY OPTION PICKS */}
              <div className="p-5 sm:p-6 bg-slate-900/50">
                <div className="flex justify-between items-center mb-3">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-indigo-200 flex items-center gap-2">
                    <TrendingUp size={16} className="text-emerald-400" /> Top High-Probability
                    Aladdin Setups ({symbol} • Lot Size {data?.lot_size})
                  </h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {topPicks.map((pick: any) => (
                    <div
                      key={pick.rank}
                      className={`rounded-xl p-4 border flex flex-col justify-between transition-all ${
                        pick.rank === 1
                          ? "bg-indigo-950/80 border-amber-400/50 shadow-lg"
                          : "bg-white/5 border-white/10"
                      }`}
                    >
                      <div>
                        <div className="flex justify-between items-start gap-2 mb-2">
                          <span
                            className={`text-[10px] font-extrabold px-2 py-0.5 rounded uppercase ${
                              pick.rank === 1
                                ? "bg-amber-400 text-slate-950"
                                : "bg-indigo-500/30 text-indigo-200 border border-indigo-400/30"
                            }`}
                          >
                            #{pick.rank} • {pick.tag}
                          </span>
                          <span className="text-xs font-bold text-emerald-300">
                            PoP {pick.pop_pct}%
                          </span>
                        </div>
                        <h3 className="font-bold text-white text-base">{pick.name}</h3>
                        <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                          {pick.rationale}
                        </p>

                        <div className="grid grid-cols-3 gap-2 mt-3 text-xs bg-black/25 p-2.5 rounded-lg border border-white/5">
                          <div>
                            <div className="text-slate-400 text-[10px]">Entry</div>
                            <div className="font-bold text-white">₹{pick.entry}</div>
                          </div>
                          <div>
                            <div className="text-slate-400 text-[10px]">Target 1</div>
                            <div className="font-bold text-emerald-400">
                              ₹{pick.target_1 ?? pick.target}
                            </div>
                          </div>
                          <div>
                            <div className="text-slate-400 text-[10px]">Stop Loss</div>
                            <div className="font-bold text-rose-400">₹{pick.sl}</div>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-300 mt-2.5">
                          <span>Lots: {pick.recommended_lots} ({pick.recommended_lots * (data?.lot_size || pick.lot_size)} qty)</span>
                          <span>Delta: {pick.delta}</span>
                          <span>IV: {pick.iv}%</span>
                          <span>Cap: ₹{Number(pick.capital_required || 0).toLocaleString("en-IN")}</span>
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeployPick(pick)}
                        disabled={isTrading}
                        className={`mt-4 w-full py-2 rounded-lg font-bold text-xs flex items-center justify-center gap-1.5 transition-colors ${
                          pick.rank === 1
                            ? "bg-amber-400 hover:bg-amber-300 text-slate-950"
                            : "bg-indigo-600 hover:bg-indigo-500 text-white"
                        } disabled:opacity-50`}
                      >
                        <Zap size={14} /> Deploy Algo Paper Trade
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ACTIVE F&O PAPER POSITIONS STRIP */}
          {openFnoTrades.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 sm:p-5">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                  <Briefcase size={16} className="text-indigo-600" /> Active F&O Paper Positions (
                  {openFnoTrades.length})
                </h3>
                <Link
                  href="/trades"
                  className="text-xs font-bold text-indigo-600 hover:underline inline-flex items-center gap-1"
                >
                  Open Trading Desk <ArrowUpRight size={13} />
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {openFnoTrades.map((t: any) => (
                  <div
                    key={t.id}
                    className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex justify-between items-center text-xs"
                  >
                    <div>
                      <div className="font-bold text-slate-900">{t.company_name}</div>
                      <div className="text-slate-500 mt-0.5">
                        {t.direction} {t.quantity} qty @ ₹{t.entry_price} (SL: ₹{t.stop_loss} |
                        Tgt: ₹{t.target_price})
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`font-black ${
                          (t.unrealized_pnl || 0) >= 0 ? "text-emerald-600" : "text-red-600"
                        }`}
                      >
                        {(t.unrealized_pnl || 0) >= 0 ? "+" : ""}₹
                        {Number(t.unrealized_pnl || 0).toFixed(2)}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        LTP ₹{t.current_price || t.entry_price}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TOP ANALYTICS KPI CARDS */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-slate-500 text-xs font-bold uppercase mb-1">
                OI PCR / Vol PCR
              </div>
              <div
                className={`text-2xl font-black ${
                  data?.analysis?.pcr >= 1 ? "text-emerald-600" : "text-red-600"
                }`}
              >
                {data?.analysis?.pcr}{" "}
                <span className="text-sm font-semibold text-slate-400">
                  / {data?.analysis?.vol_pcr ?? "-"}
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-1.5">
                Put writing floor vs Call ceiling ratio.
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-slate-500 text-xs font-bold uppercase mb-1">
                Live ATM IV & Skew
              </div>
              <div className="text-2xl font-black text-amber-600">
                {data?.analysis?.avg_atm_iv ? `${data.analysis.avg_atm_iv}%` : "N/A"}
                <span className="text-xs font-semibold text-slate-500 ml-2">
                  (Skew {data?.analysis?.iv_skew >= 0 ? "+" : ""}
                  {data?.analysis?.iv_skew}%)
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-1.5">
                Low IV favors Buying; High IV favors Spreads/Selling.
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-slate-500 text-xs font-bold uppercase mb-1">
                Put Support / Call Resistance
              </div>
              <div className="text-xl font-black mt-1">
                <span className="text-emerald-600">
                  {data?.analysis?.highest_put_oi_strike || "N/A"}
                </span>
                <span className="text-slate-400 mx-1.5">/</span>
                <span className="text-red-600">
                  {data?.analysis?.highest_call_oi_strike || "N/A"}
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-2">
                Max Pain Magnet: <strong>{data?.reversals?.max_pain || "-"}</strong>
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-slate-500 text-xs font-bold uppercase mb-1">
                OI Sentiment & Gamma Flip
              </div>
              <div className={`text-xl font-black mt-1 ${getSentimentColor(data?.analysis?.sentiment)}`}>
                {data?.analysis?.sentiment?.replace(/_/g, " ")}
              </div>
              <div className="text-xs text-slate-500 mt-2">
                Zero Gamma Flip: <strong>{data?.reversals?.zero_gamma || "-"}</strong>
              </div>
            </div>
          </div>

          {/* FULL INTERACTIVE OPTION CHAIN TABLE */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-slate-900 px-4 py-3 border-b border-slate-800 flex justify-between items-center text-xs sm:text-sm">
              <div className="font-bold text-emerald-400">CALLS (CE)</div>
              <div className="font-semibold text-indigo-200">
                Click highlighted ★ BEST BUY / SELL cells for Strategy & Quick Order
              </div>
              <div className="font-bold text-rose-400">PUTS (PE)</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs sm:text-sm text-center">
                <thead className="bg-slate-100 text-slate-600 sticky top-0 z-10 border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-2 border-r border-slate-200">Theta</th>
                    <th className="py-2.5 px-2 border-r border-slate-200">Delta</th>
                    <th className="py-2.5 px-2 border-r border-slate-200">IV</th>
                    <th className="py-2.5 px-2 border-r border-slate-200">Vol</th>
                    <th className="py-2.5 px-2 border-r border-slate-200">OI (Chg)</th>
                    <th className="py-2.5 px-2 font-bold text-slate-900 border-r border-slate-200">
                      LTP
                    </th>

                    <th className="py-2.5 px-3 bg-slate-200 font-black text-slate-900 border-x border-slate-300">
                      <div className="flex items-center justify-center gap-1.5">
                        STRIKE
                        <button
                          onClick={() => setStrikeRadius((r) => r + 2)}
                          className="px-1.5 py-0.5 rounded bg-white hover:bg-slate-50 text-indigo-600 border border-slate-300 text-[10px]"
                          title="Show more strikes"
                        >
                          ↕
                        </button>
                      </div>
                    </th>

                    <th className="py-2.5 px-2 font-bold text-slate-900 border-l border-slate-200">
                      LTP
                    </th>
                    <th className="py-2.5 px-2 border-l border-slate-200">OI (Chg)</th>
                    <th className="py-2.5 px-2 border-l border-slate-200">Vol</th>
                    <th className="py-2.5 px-2 border-l border-slate-200">IV</th>
                    <th className="py-2.5 px-2 border-l border-slate-200">Delta</th>
                    <th className="py-2.5 px-2 border-l border-slate-200">Theta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {displayStrikes.map((strike, index) => {
                    const ce =
                      data?.quotes?.find((q: any) => q.strike === strike && q.type === "CE") || {};
                    const pe =
                      data?.quotes?.find((q: any) => q.strike === strike && q.type === "PE") || {};
                    const isATM = centerStrike !== null && strike === centerStrike;
                    const isCeItm = centerStrike !== null && strike < centerStrike;
                    const isPeItm = centerStrike !== null && strike > centerStrike;

                    const buyerStrategy = data?.buyer_strategy;
                    const sellerStrategy = data?.seller_strategy;

                    const isCeBuy =
                      buyerStrategy?.strike === strike &&
                      buyerStrategy?.type === "CE" &&
                      buyerStrategy?.action === "BUY";
                    const isCeSell =
                      sellerStrategy?.strike === strike && sellerStrategy?.type === "CE";
                    const isPeBuy =
                      buyerStrategy?.strike === strike &&
                      buyerStrategy?.type === "PE" &&
                      buyerStrategy?.action === "BUY";
                    const isPeSell =
                      sellerStrategy?.strike === strike &&
                      (sellerStrategy?.type === "PE" || sellerStrategy?.type === "CE+PE");

                    const showSpotPrice =
                      data?.spot_price > 0 &&
                      strike > data.spot_price &&
                      (index === 0 || displayStrikes[index - 1] <= data.spot_price);

                    const getHighlightClass = (isBuy: boolean, isSell: boolean, baseColor: string) => {
                      if (isBuy)
                        return `cursor-pointer ring-2 ring-amber-400 bg-amber-100 text-amber-950 font-black relative hover:bg-amber-200`;
                      if (isSell)
                        return `cursor-pointer ring-2 ring-fuchsia-500 bg-fuchsia-100 text-fuchsia-950 font-black relative hover:bg-fuchsia-200`;
                      return baseColor;
                    };

                    const isCeMaxOi = data?.analysis?.highest_call_oi_strike === strike;
                    const isPeMaxOi = data?.analysis?.highest_put_oi_strike === strike;

                    const peVal = pe.oi && pe.oi !== 0 ? pe.oi : pe.volume;
                    const ceVal = ce.oi && ce.oi !== 0 ? ce.oi : ce.volume;
                    const strikePcrVal = (peVal || 0) / (ceVal || 1);
                    const strikePcr = strikePcrVal > 99 ? "∞" : strikePcrVal.toFixed(2);

                    const fmtOi = (oi: number, chg: number) => (
                      <div className="leading-tight">
                        <div>{oi ? (oi / 1000).toFixed(0) + "k" : "-"}</div>
                        {chg !== 0 && (
                          <div
                            className={`text-[10px] ${
                              chg > 0 ? "text-emerald-600" : "text-rose-500"
                            }`}
                          >
                            {chg > 0 ? "+" : ""}
                            {(chg / 1000).toFixed(0)}k
                          </div>
                        )}
                      </div>
                    );

                    return (
                      <React.Fragment key={strike}>
                        {showSpotPrice && (
                          <tr className="h-0 p-0 m-0">
                            <td
                              colSpan={13}
                              className="h-0 p-0 m-0 relative border-t-2 border-dashed border-indigo-500"
                            >
                              <div className="absolute left-1/2 -translate-x-1/2 -top-2.5 bg-indigo-600 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full shadow z-20 whitespace-nowrap">
                                SPOT: ₹{data.spot_price.toFixed(2)}
                              </div>
                            </td>
                          </tr>
                        )}
                        <tr
                          className={
                            isATM
                              ? "bg-indigo-50 font-bold"
                              : "hover:bg-slate-50 transition-colors"
                          }
                        >
                          <td className={`py-2 px-2 ${isCeItm && !isATM ? "bg-amber-50/60" : ""} text-slate-500`}>
                            {ce.theta ?? "-"}
                          </td>
                          <td className={`py-2 px-2 ${isCeItm && !isATM ? "bg-amber-50/60" : ""} text-blue-700 font-medium`}>
                            {ce.delta ?? "-"}
                          </td>
                          <td className={`py-2 px-2 ${isCeItm && !isATM ? "bg-amber-50/60" : ""} text-slate-600`}>
                            {ce.iv ?? "-"}
                          </td>
                          <td className={`py-2 px-2 ${isCeItm && !isATM ? "bg-amber-50/60" : ""} text-slate-500`}>
                            {ce.volume ? (ce.volume / 1000).toFixed(0) + "k" : "-"}
                          </td>
                          <td
                            className={`py-2 px-2 ${isCeItm && !isATM ? "bg-amber-50/60" : ""} ${
                              isCeMaxOi ? "bg-red-100 text-red-800 font-bold" : "text-slate-700"
                            }`}
                          >
                            {fmtOi(ce.oi || 0, ce.chng_oi || 0)}
                          </td>
                          <td
                            onClick={() => {
                              if (isCeBuy) setSelectedTrade({ role: "BUYER", strategy: buyerStrategy });
                              else if (isCeSell)
                                setSelectedTrade({ role: "SELLER", strategy: sellerStrategy });
                            }}
                            className={`py-2 px-2 ${
                              isCeItm && !isATM ? "bg-amber-50/60" : ""
                            } font-bold ${getHighlightClass(isCeBuy, isCeSell, "text-emerald-700")}`}
                          >
                            {isCeBuy && (
                              <span className="block text-[9px] text-amber-800 font-extrabold">
                                ★ BUY
                              </span>
                            )}
                            {isCeSell && (
                              <span className="block text-[9px] text-fuchsia-800 font-extrabold">
                                ★ SELL
                              </span>
                            )}
                            {ce.ltp ? ce.ltp.toFixed(2) : "-"}
                          </td>

                          <td
                            className={`py-2 px-3 font-black border-x border-slate-200 ${
                              isATM
                                ? "bg-indigo-600 text-white"
                                : "bg-slate-100 text-slate-800"
                            }`}
                          >
                            <div>{strike}</div>
                            <div
                              className={`text-[10px] font-medium ${
                                isATM ? "text-indigo-100" : "text-slate-500"
                              }`}
                            >
                              PCR {strikePcr}
                            </div>
                          </td>

                          <td
                            onClick={() => {
                              if (isPeBuy) setSelectedTrade({ role: "BUYER", strategy: buyerStrategy });
                              else if (isPeSell)
                                setSelectedTrade({ role: "SELLER", strategy: sellerStrategy });
                            }}
                            className={`py-2 px-2 ${
                              isPeItm && !isATM ? "bg-indigo-50/50" : ""
                            } font-bold ${getHighlightClass(isPeBuy, isPeSell, "text-rose-700")}`}
                          >
                            {isPeBuy && (
                              <span className="block text-[9px] text-amber-800 font-extrabold">
                                ★ BUY
                              </span>
                            )}
                            {isPeSell && (
                              <span className="block text-[9px] text-fuchsia-800 font-extrabold">
                                ★ SELL
                              </span>
                            )}
                            {pe.ltp ? pe.ltp.toFixed(2) : "-"}
                          </td>
                          <td
                            className={`py-2 px-2 ${isPeItm && !isATM ? "bg-indigo-50/50" : ""} ${
                              isPeMaxOi ? "bg-emerald-100 text-emerald-800 font-bold" : "text-slate-700"
                            }`}
                          >
                            {fmtOi(pe.oi || 0, pe.chng_oi || 0)}
                          </td>
                          <td className={`py-2 px-2 ${isPeItm && !isATM ? "bg-indigo-50/50" : ""} text-slate-500`}>
                            {pe.volume ? (pe.volume / 1000).toFixed(0) + "k" : "-"}
                          </td>
                          <td className={`py-2 px-2 ${isPeItm && !isATM ? "bg-indigo-50/50" : ""} text-slate-600`}>
                            {pe.iv ?? "-"}
                          </td>
                          <td className={`py-2 px-2 ${isPeItm && !isATM ? "bg-indigo-50/50" : ""} text-blue-700 font-medium`}>
                            {pe.delta ?? "-"}
                          </td>
                          <td className={`py-2 px-2 ${isPeItm && !isATM ? "bg-indigo-50/50" : ""} text-slate-500`}>
                            {pe.theta ?? "-"}
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TRADE DETAILS SLIDE-OVER CARD */}
      {selectedTrade && (
        <div className="fixed top-20 right-6 z-50 w-[400px] max-w-[92vw] max-h-[calc(100vh-6rem)] flex flex-col">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-y-auto flex flex-col">
            <div
              className={`p-4 border-b flex justify-between items-center ${
                selectedTrade.role === "BUYER" ? "bg-amber-50 border-amber-200" : "bg-fuchsia-50 border-fuchsia-200"
              }`}
            >
              <h3 className="font-bold text-sm text-slate-900">
                {selectedTrade.role === "BUYER"
                  ? "🎯 Aladdin Buyer Signal"
                  : "🛡️ Aladdin Seller Signal"}
              </h3>
              <button
                onClick={() => setSelectedTrade(null)}
                className="text-slate-500 hover:text-slate-900 font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xl font-black text-slate-900">
                  {selectedTrade.strategy.strike} {selectedTrade.strategy.type}
                </span>
                <span className="px-2.5 py-1 rounded text-xs font-bold bg-indigo-100 text-indigo-800">
                  {selectedTrade.strategy.action}
                </span>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-200">
                {selectedTrade.strategy.reason}
              </p>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-slate-50 p-2.5 rounded border border-slate-200">
                  <div className="text-slate-500">Entry</div>
                  <div className="font-bold text-slate-900">
                    ₹{Number(selectedTrade.strategy.entry || 0).toFixed(2)}
                  </div>
                </div>
                <div className="bg-emerald-50 p-2.5 rounded border border-emerald-200">
                  <div className="text-emerald-700">Target</div>
                  <div className="font-bold text-emerald-700">
                    ₹{selectedTrade.strategy.target}
                  </div>
                </div>
                <div className="bg-red-50 p-2.5 rounded border border-red-200">
                  <div className="text-red-700">Stop Loss</div>
                  <div className="font-bold text-red-700">₹{selectedTrade.strategy.sl}</div>
                </div>
              </div>

              {data?.reversals && (
                <div className="text-xs space-y-1.5 bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <div className="font-bold text-slate-700 border-b border-slate-200 pb-1">
                    Institutional Reversal Levels
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Support (S1 / S2)</span>
                    <span className="font-bold text-emerald-700">
                      {data.reversals.S1} / {data.reversals.S2}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Resistance (R1 / R2)</span>
                    <span className="font-bold text-red-700">
                      {data.reversals.R1} / {data.reversals.R2}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Zero Gamma / Max Pain</span>
                    <span className="font-bold text-indigo-700">
                      {data.reversals.zero_gamma} / {data.reversals.max_pain}
                    </span>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => handlePlaceTrade(selectedTrade.role, selectedTrade.strategy)}
                  disabled={isTrading}
                  className="flex-1 py-2.5 rounded-lg font-bold text-sm bg-indigo-600 hover:bg-indigo-700 text-white shadow transition-colors disabled:opacity-50"
                >
                  {isTrading ? "Deploying..." : "⚡ Deploy Algo Paper Trade"}
                </button>
                <button
                  onClick={async () => {
                    setIsPredicting(true);
                    setKronosPrediction(null);
                    const dte = Math.max(1, Math.ceil(data?.dte || 5));
                    setPredictionDays(dte);
                    const q = data?.quotes?.find(
                      (x: any) =>
                        x.strike === selectedTrade.strategy.strike &&
                        x.type === selectedTrade.strategy.type
                    );
                    if (q?.symbol) {
                      const res = await predictKronos(q.symbol, dte);
                      if (res.error) alert(res.error);
                      else setKronosPrediction(res);
                    } else {
                      alert("Could not find symbol for this strike");
                    }
                    setIsPredicting(false);
                  }}
                  disabled={isPredicting}
                  className="px-3.5 py-2.5 rounded-lg font-bold text-xs bg-slate-800 hover:bg-slate-700 text-white disabled:opacity-50"
                >
                  {isPredicting ? "🤖..." : "🤖 Kronos"}
                </button>
              </div>

              {kronosPrediction?.prediction && (
                <div className="bg-slate-900 text-white p-3 rounded-lg text-xs">
                  <div className="font-bold text-indigo-300 mb-2 flex justify-between">
                    <span>Kronos {predictionDays}D Option Forecast</span>
                    <button onClick={() => setKronosPrediction(null)}>✕</button>
                  </div>
                  <div className="space-y-1">
                    {kronosPrediction.prediction.map((p: any, i: number) => (
                      <div key={i} className="flex justify-between bg-slate-800 px-2 py-1 rounded">
                        <span>{String(p.timestamps).split(" ")[0]}</span>
                        <span className="font-bold text-emerald-400">
                          ₹{Number(p.close).toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
