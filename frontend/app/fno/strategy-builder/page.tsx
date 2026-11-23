"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain, fnoApi } from "@/lib/api";
import {
  AlertCircle,
  Target,
  ShieldAlert,
  ArrowRight,
  Activity,
  Zap,
  Shield,
  HelpCircle,
  Plus,
  CheckCircle2,
} from "lucide-react";
import { FnoHeaderNav, getSavedFnoSymbol } from "@/components/FnoHeaderNav";

export default function StrategyBuilder() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("safe");
  const [deploying, setDeploying] = useState(false);
  const [statusBanner, setStatusBanner] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Custom Combo State
  const [customLegs, setCustomLegs] = useState<any[]>([]);
  const [selectedStrike, setSelectedStrike] = useState("");
  const [selectedType, setSelectedType] = useState("CE");
  const [selectedAction, setSelectedAction] = useState("BUY");

  useEffect(() => {
    const saved = getSavedFnoSymbol();
    setSymbol(saved);
    loadData(saved);
  }, []);

  const loadData = async (targetSym: string = symbol) => {
    setLoading(true);
    try {
      const res = await fetchOptionChain(targetSym);
      setData(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleSymbolChange = (next: string) => {
    setSymbol(next);
    setCustomLegs([]);
    setSelectedStrike("");
    loadData(next);
  };

  const advanced_hedges = data?.advanced_hedges;
  const analysis = data?.analysis || {};
  const brain = data?.aladdin_option_brain || {};
  const quotes = data?.quotes || [];
  const lotSize = data?.lot_size || 65;
  const auto_pilot = advanced_hedges?.auto_pilot;

  let current_hedge: any = null;
  if (advanced_hedges) {
    if (activeTab === "auto_pilot" && auto_pilot) {
      current_hedge = advanced_hedges[auto_pilot.recommended_key];
    } else {
      current_hedge = advanced_hedges[activeTab];
    }
  }

  const allStrikes = Array.from(new Set(quotes.map((q: any) => q.strike))).sort(
    (a: any, b: any) => a - b
  ) as number[];

  const handleAddCustomLeg = () => {
    if (!selectedStrike) return;
    const strikeNum = parseFloat(selectedStrike);
    const quote = quotes.find(
      (q: any) => q.strike === strikeNum && q.type === selectedType
    );
    if (quote) {
      setCustomLegs([
        ...customLegs,
        {
          symbol: quote.symbol,
          action: selectedAction,
          type: selectedType,
          strike: strikeNum,
          entry: quote.ltp,
          qty: 1,
        },
      ]);
    }
  };

  const handleDeployStrategy = async (strategyName: string, legs: any[]) => {
    if (!legs || legs.length === 0) return;
    setDeploying(true);
    setStatusBanner(null);
    try {
      const enrichedLegs = legs.map((leg) => {
        const match = quotes.find(
          (q: any) => q.strike === leg.strike && q.type === leg.type
        );
        const isBuy = leg.action === "BUY";
        return {
          symbol: leg.symbol || match?.symbol || "",
          action: leg.action,
          type: leg.type,
          strike: leg.strike,
          entry: Number(leg.entry),
          sl: isBuy ? Number((leg.entry * 0.65).toFixed(2)) : Number((leg.entry * 1.8).toFixed(2)),
          target: isBuy
            ? Number((leg.entry * 1.45).toFixed(2))
            : Number(Math.max(0.05, leg.entry * 0.3).toFixed(2)),
          qty: leg.qty || 1,
        };
      });

      const res = await fnoApi.deployTrade({
        underlying: symbol,
        strategy_name: strategyName,
        lot_size: lotSize,
        lots: 1,
        conviction_score: brain?.conviction_score,
        notes: `Deployed from Strategy Builder (${legs.length} legs)`,
        legs: enrichedLegs,
      });

      setStatusBanner({
        type: "success",
        text: `Deployed "${res.data.strategy}" (${res.data.legs_count} leg${
          res.data.legs_count > 1 ? "s" : ""
        }) in Paper Portfolio — Capital ₹${Number(
          res.data.total_capital_used || 0
        ).toLocaleString("en-IN")}`,
      });
    } catch (e: any) {
      setStatusBanner({
        type: "error",
        text: e.message || "Failed to deploy strategy",
      });
    }
    setDeploying(false);
  };

  const customMetrics = (() => {
    let netPremium = 0;
    customLegs.forEach((leg) => {
      if (leg.action === "BUY") netPremium += leg.entry;
      else netPremium -= leg.entry;
    });
    return { netPremium: netPremium.toFixed(2) };
  })();

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      <FnoHeaderNav
        activeTab="strategy"
        title="Hedge & Strategy Builder"
        subtitle="Risk-Defined Multi-Leg Spreads, Iron Condors & Custom Execution"
        symbol={symbol}
        onSymbolChange={handleSymbolChange}
        spotPrice={data?.spot_price}
        spotChangePct={data?.spot_change_pct}
        atmStrike={data?.atm_strike}
        lotSize={lotSize}
        dte={data?.dte}
        convictionScore={brain?.conviction_score}
        directionalBias={brain?.directional_bias}
        onRefresh={() => loadData(symbol)}
        isRefreshing={loading}
      />

      {/* HEDGE STRATEGY TABS */}
      <div className="bg-white border-b border-slate-200 px-4 sm:px-6 py-3 flex items-center gap-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("safe")}
          className={`px-4 py-1.5 rounded-lg font-semibold text-xs sm:text-sm transition-colors whitespace-nowrap ${
            activeTab === "safe"
              ? "bg-blue-600 text-white shadow-sm"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Safe Spread Hedge
        </button>
        <button
          onClick={() => setActiveTab("pro")}
          className={`px-4 py-1.5 rounded-lg font-semibold text-xs sm:text-sm transition-colors whitespace-nowrap ${
            activeTab === "pro"
              ? "bg-purple-600 text-white shadow-sm"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          High Profit (Butterfly)
        </button>
        <button
          onClick={() => setActiveTab("zero_loss")}
          className={`px-4 py-1.5 rounded-lg font-semibold text-xs sm:text-sm transition-colors whitespace-nowrap ${
            activeTab === "zero_loss"
              ? "bg-emerald-600 text-white shadow-sm"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Ratio Backspread
        </button>
        <button
          onClick={() => setActiveTab("sideways")}
          className={`px-4 py-1.5 rounded-lg font-semibold text-xs sm:text-sm transition-colors whitespace-nowrap ${
            activeTab === "sideways"
              ? "bg-orange-500 text-white shadow-sm"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Sideways (Iron Condor)
        </button>
        <button
          onClick={() => setActiveTab("breakout")}
          className={`px-4 py-1.5 rounded-lg font-semibold text-xs sm:text-sm transition-colors whitespace-nowrap ${
            activeTab === "breakout"
              ? "bg-rose-600 text-white shadow-sm"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Breakout (Straddle)
        </button>
      </div>

      {statusBanner && (
        <div className="max-w-6xl mx-auto px-6 pt-4">
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-sm font-medium ${
              statusBanner.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            <div className="flex items-center gap-2">
              {statusBanner.type === "success" ? (
                <CheckCircle2 size={18} className="text-emerald-600" />
              ) : (
                <AlertCircle size={18} className="text-red-600" />
              )}
              <span>{statusBanner.text}</span>
            </div>
            <button onClick={() => setStatusBanner(null)} className="text-xs font-bold">
              ✕
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="p-12 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-indigo-600 animate-spin" />
        </div>
      ) : data?.error ? (
        <div className="p-6 max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 p-6 rounded-xl flex items-start gap-4">
            <AlertCircle className="text-red-600 mt-1" />
            <div>
              <h3 className="font-bold text-red-900">Failed to load Strategy Data</h3>
              <p className="text-sm text-red-700 mt-1">{data.error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
          {auto_pilot && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div>
                <div className="text-xs font-bold uppercase text-indigo-700">
                  Auto-Pilot Suggested Regime: {auto_pilot.regime_name}
                </div>
                <p className="text-sm text-indigo-950 mt-0.5">{auto_pilot.reasoning}</p>
              </div>
              <button
                onClick={() => setActiveTab(auto_pilot.recommended_key || "safe")}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shrink-0"
              >
                Select Recommended ({auto_pilot.recommended_key})
              </button>
            </div>
          )}

          {/* AI HEDGING STRATEGY CARD */}
          {current_hedge && (
            <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
              <div
                className="px-6 py-4 flex justify-between items-center flex-wrap gap-3"
                style={{
                  background:
                    activeTab === "safe"
                      ? "linear-gradient(to right, #2563eb, #4338ca)"
                      : activeTab === "pro"
                      ? "linear-gradient(to right, #9333ea, #c026d3)"
                      : activeTab === "zero_loss"
                      ? "linear-gradient(to right, #059669, #0d9488)"
                      : activeTab === "breakout"
                      ? "linear-gradient(to right, #dc2626, #e11d48)"
                      : "linear-gradient(to right, #f97316, #d97706)",
                }}
              >
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Shield size={20} /> {current_hedge.name}
                  </h2>
                  <p className="text-white/85 text-sm mt-1">{current_hedge.reason}</p>
                </div>
                <div className="flex items-center gap-3">
                  {current_hedge.expiry && (
                    <div className="bg-white/20 px-3 py-1.5 rounded-lg border border-white/30 text-white text-xs font-bold">
                      {current_hedge.expiry}
                    </div>
                  )}
                  <div className="bg-white/20 px-4 py-2 rounded-lg border border-white/30 text-white">
                    <div className="text-xs font-semibold opacity-80 uppercase">Margin Est.</div>
                    <div className="text-base font-bold">{current_hedge.margin_required}</div>
                  </div>
                </div>
              </div>

              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-3">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                      Strategy Legs (Lot Size: {lotSize})
                    </div>
                    {current_hedge.legs.map((leg: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`px-2 py-1 rounded text-xs font-bold ${
                              leg.action === "BUY"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {leg.action} {leg.qty && `${leg.qty}x`}
                          </span>
                          <span className="font-bold text-slate-800">
                            {leg.strike} {leg.type}
                          </span>
                        </div>
                        <div className="font-medium text-slate-700">₹{leg.entry.toFixed(2)}</div>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50">
                      <div className="text-xs font-bold text-emerald-600 uppercase mb-1">
                        Max Profit / Lot
                      </div>
                      <div className="text-xl font-black text-emerald-700">
                        {typeof current_hedge.max_profit === "number"
                          ? `₹${(current_hedge.max_profit * lotSize).toLocaleString("en-IN", {
                              maximumFractionDigits: 0,
                            })}`
                          : current_hedge.max_profit}
                      </div>
                      {typeof current_hedge.max_profit === "number" && (
                        <div className="text-xs text-emerald-600 mt-1">
                          ({current_hedge.max_profit} pts × {lotSize})
                        </div>
                      )}
                    </div>
                    <div className="p-4 rounded-xl border border-red-200 bg-red-50">
                      <div className="text-xs font-bold text-red-600 uppercase mb-1">
                        Max Loss / Lot
                      </div>
                      <div className="text-xl font-black text-red-700">
                        {typeof current_hedge.max_loss === "number"
                          ? `₹${(current_hedge.max_loss * lotSize).toLocaleString("en-IN", {
                              maximumFractionDigits: 0,
                            })}`
                          : current_hedge.max_loss}
                      </div>
                      {typeof current_hedge.max_loss === "number" && (
                        <div className="text-xs text-red-600 mt-1">
                          ({current_hedge.max_loss} pts × {lotSize})
                        </div>
                      )}
                    </div>
                    <div className="p-4 rounded-xl border border-slate-200 bg-white">
                      <div className="text-xs font-bold text-slate-500 uppercase mb-1">
                        Net Premium
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {current_hedge.net_premium < 0 ? (
                          <span className="text-emerald-600">
                            Receive ₹{Math.abs(current_hedge.net_premium)}
                          </span>
                        ) : (
                          <span className="text-red-600">Pay ₹{current_hedge.net_premium}</span>
                        )}
                      </div>
                    </div>
                    <div className="p-4 rounded-xl border border-slate-200 bg-white">
                      <div className="text-xs font-bold text-slate-500 uppercase mb-1">
                        Risk : Reward
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {current_hedge.risk_reward}
                      </div>
                    </div>
                    {current_hedge.breakeven_range && (
                      <div className="col-span-2 p-4 rounded-xl border border-blue-200 bg-blue-50">
                        <div className="text-xs font-bold text-blue-600 uppercase mb-1">
                          ⚡ Breakeven Range
                        </div>
                        <div className="text-base font-bold text-blue-800">
                          {current_hedge.breakeven_range}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-6 pt-5 border-t border-slate-100 flex justify-end">
                  <button
                    onClick={() => handleDeployStrategy(current_hedge.name, current_hedge.legs)}
                    disabled={deploying}
                    className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold rounded-lg transition-colors flex items-center gap-2 shadow-sm"
                  >
                    {deploying ? "Deploying..." : "Execute Multi-Leg Hedge (Paper)"}{" "}
                    <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* CUSTOM COMBO BUILDER */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-5 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-900 text-lg">Build Custom Multi-Leg Combo</h3>
              <p className="text-sm text-slate-500">
                Combine strikes on {symbol} and deploy directly into Paper Trading
              </p>
            </div>

            <div className="p-6">
              <div className="flex flex-wrap items-end gap-4 mb-6">
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                    Action
                  </label>
                  <select
                    className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                    value={selectedAction}
                    onChange={(e) => setSelectedAction(e.target.value)}
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                    Strike
                  </label>
                  <select
                    className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                    value={selectedStrike}
                    onChange={(e) => setSelectedStrike(e.target.value)}
                  >
                    <option value="">-- Select Strike --</option>
                    {allStrikes.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                    Type
                  </label>
                  <select
                    className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value)}
                  >
                    <option value="CE">CE</option>
                    <option value="PE">PE</option>
                  </select>
                </div>
                <button
                  onClick={handleAddCustomLeg}
                  disabled={!selectedStrike}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded font-bold text-sm flex items-center gap-2 disabled:opacity-50"
                >
                  <Plus size={16} /> Add Leg
                </button>
              </div>

              {customLegs.length > 0 && (
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-xs">
                      <tr>
                        <th className="px-4 py-3">Action</th>
                        <th className="px-4 py-3">Strike & Type</th>
                        <th className="px-4 py-3">Entry Price</th>
                        <th className="px-4 py-3 text-right">Remove</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {customLegs.map((leg, i) => (
                        <tr key={i}>
                          <td className="px-4 py-3 font-bold">
                            <span className={leg.action === "BUY" ? "text-blue-600" : "text-red-600"}>
                              {leg.action}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-bold text-slate-800">
                            {leg.strike} {leg.type}
                          </td>
                          <td className="px-4 py-3 text-slate-600">₹{leg.entry.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() =>
                                setCustomLegs(customLegs.filter((_, idx) => idx !== i))
                              }
                              className="text-red-500 hover:text-red-700 text-xs font-bold"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-50 border-t border-slate-200">
                      <tr>
                        <td colSpan={2} className="px-4 py-3 font-bold text-slate-800 text-right">
                          Net Premium ({lotSize} lot):
                        </td>
                        <td className="px-4 py-3 font-black text-base text-slate-900">
                          {parseFloat(customMetrics.netPremium) > 0
                            ? `Pay ₹${customMetrics.netPremium}`
                            : `Receive ₹${Math.abs(parseFloat(customMetrics.netPremium))}`}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() =>
                              handleDeployStrategy(`Custom ${symbol} Combo`, customLegs)
                            }
                            disabled={deploying}
                            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs"
                          >
                            ⚡ Deploy Custom Combo
                          </button>
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* INDIVIDUAL LEG CARDS */}
          {current_hedge?.legs?.length > 0 && (
            <div>
              <h3 className="font-bold text-slate-900 text-lg mb-4 px-1">
                Individual Leg Execution Details
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {current_hedge.legs.map((leg: any, idx: number) => {
                  const isBuy = leg.action === "BUY";
                  const target = isBuy
                    ? (leg.entry * 1.45).toFixed(2)
                    : Math.max(0.05, leg.entry * 0.3).toFixed(2);
                  const sl = isBuy ? (leg.entry * 0.65).toFixed(2) : (leg.entry * 1.8).toFixed(2);

                  return (
                    <div
                      key={idx}
                      className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col"
                    >
                      <div
                        className={`p-4 border-b flex items-center gap-3 ${
                          isBuy ? "bg-blue-50/50 border-blue-100" : "bg-red-50/50 border-red-100"
                        }`}
                      >
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            isBuy ? "bg-blue-100 text-blue-600" : "bg-red-100 text-red-600"
                          }`}
                        >
                          {isBuy ? <Zap size={16} /> : <Activity size={16} />}
                        </div>
                        <div>
                          <h3 className="font-bold text-slate-900">
                            Leg {idx + 1}: {isBuy ? "Option Buyer" : "Option Seller"}
                          </h3>
                          <p className="text-[10px] text-slate-500 font-medium uppercase">
                            {current_hedge.name}
                          </p>
                        </div>
                      </div>
                      <div className="p-5 flex-1">
                        <div className="flex items-end gap-3 mb-4">
                          <span
                            className={`px-2 py-1 rounded text-xs font-bold ${
                              isBuy ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-800"
                            }`}
                          >
                            {leg.action} {leg.qty && `${leg.qty}x`}
                          </span>
                          <span className="text-xl font-black text-slate-800">
                            {leg.strike} {leg.type}
                          </span>
                          <span className="text-slate-500 mb-0.5 font-medium">
                            @ ₹{leg.entry.toFixed(2)}
                          </span>
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-slate-500 flex items-center gap-2">
                              <Target size={14} /> Target
                            </span>
                            <span className="font-bold text-emerald-600">₹{target}</span>
                          </div>
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-slate-500 flex items-center gap-2">
                              <ShieldAlert size={14} /> Stop Loss
                            </span>
                            <span className="font-bold text-red-600">₹{sl}</span>
                          </div>
                          <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-100">
                            <span className="text-slate-500 flex items-center gap-2">
                              <HelpCircle size={14} /> Support / Resist
                            </span>
                            <span className="font-bold text-slate-700">
                              {data.reversals
                                ? `${data.reversals.S1} / ${data.reversals.R1}`
                                : `${analysis?.highest_put_oi_strike || "-"} / ${
                                    analysis?.highest_call_oi_strike || "-"
                                  }`}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="p-3 bg-slate-50 border-t border-slate-100">
                        <button
                          onClick={() =>
                            handleDeployStrategy(`${current_hedge.name} - Leg ${idx + 1}`, [leg])
                          }
                          disabled={deploying}
                          className={`w-full py-2 text-white text-sm font-bold rounded-lg transition-colors shadow-sm disabled:opacity-50 ${
                            isBuy ? "bg-blue-600 hover:bg-blue-700" : "bg-rose-600 hover:bg-rose-700"
                          }`}
                        >
                          Execute Leg {idx + 1} (Paper)
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
