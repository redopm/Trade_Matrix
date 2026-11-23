"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import { AlertCircle, Activity, AlertTriangle, ShieldCheck } from "lucide-react";
import { FnoHeaderNav, getSavedFnoSymbol } from "@/components/FnoHeaderNav";

export default function PcrAnalysis() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

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
    loadData(next);
  };

  const analysis = data?.analysis || {};
  const brain = data?.aladdin_option_brain || {};
  const pcr = Number(analysis?.pcr || 1.0);
  const volPcr = Number(analysis?.vol_pcr || pcr);
  const atmIv = Number(analysis?.avg_atm_iv || 15.0);
  const ivSkew = Number(analysis?.iv_skew || 0.0);
  const indiaVix = Number(data?.india_vix || analysis?.india_vix || 0);

  let pcrZone = "Neutral Consolidation";
  let pcrColor = "text-slate-600 bg-slate-100 border-slate-200";
  let gaugePct = 50;

  if (pcr < 0.65) {
    pcrZone = "Deeply Oversold / Heavy Call Overhead";
    pcrColor = "text-rose-700 bg-rose-50 border-rose-200";
    gaugePct = 15;
  } else if (pcr < 0.90) {
    pcrZone = "Bearish Trend (Call Writers Active)";
    pcrColor = "text-red-600 bg-red-50 border-red-200";
    gaugePct = 30;
  } else if (pcr <= 1.12) {
    pcrZone = "Range-Bound / Sideways Equilibrium";
    pcrColor = "text-slate-700 bg-slate-100 border-slate-200";
    gaugePct = 50;
  } else if (pcr <= 1.45) {
    pcrZone = "Bullish Trend (Put Writers Supporting)";
    pcrColor = "text-emerald-700 bg-emerald-50 border-emerald-200";
    gaugePct = 72;
  } else {
    pcrZone = "Extremely Overbought (Strong Put Base)";
    pcrColor = "text-teal-700 bg-teal-50 border-teal-200";
    gaugePct = 88;
  }

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      <FnoHeaderNav
        activeTab="pcr"
        title="PCR & Implied Volatility Lab"
        subtitle="Live OI PCR, Volume PCR, ATM IV & Put-Call Skew Regime"
        symbol={symbol}
        onSymbolChange={handleSymbolChange}
        spotPrice={data?.spot_price}
        spotChangePct={data?.spot_change_pct}
        atmStrike={data?.atm_strike}
        lotSize={data?.lot_size}
        dte={data?.dte}
        convictionScore={brain?.conviction_score}
        directionalBias={brain?.directional_bias}
        onRefresh={() => loadData(symbol)}
        isRefreshing={loading}
      />

      {loading ? (
        <div className="p-12 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-indigo-600 animate-spin" />
        </div>
      ) : data?.error ? (
        <div className="p-6 max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 p-6 rounded-xl flex items-start gap-4">
            <AlertCircle className="text-red-600 mt-1" />
            <div>
              <h3 className="font-bold text-red-900">Failed to load PCR Data</h3>
              <p className="text-sm text-red-700 mt-1">{data.error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* PCR GAUGE CARD */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col items-center justify-center relative overflow-hidden">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 self-start">
                OI Put-Call Ratio ({symbol})
              </h2>

              <div className="mt-6 mb-4 relative w-64 h-32 overflow-hidden flex items-end justify-center">
                <div className="absolute top-0 w-64 h-64 rounded-full border-[28px] border-slate-100" />
                <div className="absolute top-0 w-64 h-64 rounded-full border-[28px] border-transparent border-t-emerald-400 border-r-red-400 transform -rotate-45 opacity-25" />

                <div
                  className="absolute bottom-0 w-1 h-32 bg-slate-800 origin-bottom rounded-t-full transition-all duration-1000 ease-out z-10"
                  style={{
                    transform: `rotate(${Math.min(Math.max((gaugePct / 100) * 180 - 90, -90), 90)}deg)`,
                  }}
                >
                  <div className="w-3 h-3 bg-slate-800 rounded-full absolute -bottom-1.5 -left-1" />
                </div>

                <div className="z-20 text-4xl font-black text-slate-800 bg-white px-4 pt-3 rounded-t-full mt-10">
                  {pcr.toFixed(2)}
                </div>
              </div>

              <div className={`mt-2 px-4 py-1.5 rounded-full border text-sm font-bold ${pcrColor}`}>
                {pcrZone}
              </div>

              <div className="grid grid-cols-2 gap-4 w-full mt-6 pt-4 border-t border-slate-100 text-center">
                <div>
                  <div className="text-xs text-slate-400 font-semibold uppercase">Volume PCR</div>
                  <div className="text-xl font-black text-indigo-700">{volPcr.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400 font-semibold uppercase">India VIX</div>
                  <div className="text-xl font-black text-amber-600">
                    {indiaVix > 0 ? indiaVix.toFixed(2) : "—"}
                  </div>
                </div>
              </div>
            </div>

            {/* LIVE ATM IMPLIED VOLATILITY & SKEW CARD */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <Activity className="text-indigo-600" />
                    <h2 className="text-lg font-bold text-slate-800">
                      Implied Volatility & Skew
                    </h2>
                  </div>
                  {atmIv > 19 ? (
                    <span className="px-2.5 py-1 bg-red-100 text-red-700 text-xs font-bold rounded flex items-center gap-1">
                      <AlertTriangle size={12} /> HIGH IV
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded flex items-center gap-1">
                      <ShieldCheck size={12} /> HEALTHY IV
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3 mb-5">
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <div className="text-[11px] font-bold uppercase text-slate-400">Live ATM IV</div>
                    <div className="text-2xl font-black text-slate-900 mt-1">
                      {atmIv.toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <div className="text-[11px] font-bold uppercase text-slate-400">ATM Call / Put IV</div>
                    <div className="text-sm font-bold text-slate-800 mt-2">
                      {Number(analysis?.atm_ce_iv || atmIv).toFixed(1)}% /{" "}
                      {Number(analysis?.atm_pe_iv || atmIv).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <div className="text-[11px] font-bold uppercase text-slate-400">IV Skew (PE-CE)</div>
                    <div
                      className={`text-xl font-black mt-1 ${
                        ivSkew > 2.5 ? "text-amber-600" : "text-indigo-700"
                      }`}
                    >
                      {ivSkew >= 0 ? "+" : ""}
                      {ivSkew.toFixed(1)}%
                    </div>
                  </div>
                </div>

                <div className="bg-indigo-50/70 rounded-xl p-4 border border-indigo-100">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="text-sm font-bold text-indigo-950">
                      Aladdin Strategy Mode Recommendation
                    </h3>
                    <span className="text-xs font-bold px-2 py-0.5 bg-indigo-600 text-white rounded">
                      {brain?.recommended_mode?.replace(/_/g, " ") || "BALANCED"}
                    </span>
                  </div>
                  <p className="text-sm text-indigo-900/80">
                    {brain?.theta_shield_active
                      ? `Theta Shield Active (${data?.dte?.toFixed(1)}d left to expiry): Naked option buying carries rapid decay. Use Defined-Risk Spreads or Credit Writing.`
                      : atmIv > 19
                      ? "ATM IV is elevated — option premiums are expensive. Credit Spreads & Iron Condors offer higher probability."
                      : "Implied Volatility is favorable for Directional Option Buying (ITM/ATM Delta ~0.58) or Debit Spreads."}
                  </p>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-4 text-xs font-medium text-slate-500">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  Low IV (&lt;15%) = Cheap Options (Buyers Edge)
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-red-500" />
                  High IV (&gt;19%) = Rich Premiums (Sellers Edge)
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
