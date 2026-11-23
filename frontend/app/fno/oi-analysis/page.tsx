"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import {
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Swords,
  Magnet,
} from "lucide-react";
import { FnoHeaderNav, getSavedFnoSymbol } from "@/components/FnoHeaderNav";

const getBuildupBadge = (buildup: string) => {
  if (buildup === "Long Buildup" || buildup === "Active Buying") {
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  }
  if (buildup === "Short Buildup" || buildup === "Active Selling") {
    return "bg-rose-100 text-rose-800 border-rose-200";
  }
  if (buildup === "Short Covering") {
    return "bg-blue-100 text-blue-800 border-blue-200";
  }
  if (buildup === "Long Unwinding") {
    return "bg-amber-100 text-amber-800 border-amber-200";
  }
  return "bg-slate-100 text-slate-600 border-slate-200";
};

export default function OiAnalysis() {
  const [symbol, setSymbol] = useState<string>("NIFTY");
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
  const quotes = data?.quotes || [];
  const atm_strike = data?.atm_strike || 0;
  const spot_price = data?.spot_price || 0;

  // Aggregate Data per strike
  const oiByStrike: Record<number, any> = {};
  let totalCeChngOi = 0;
  let totalPeChngOi = 0;
  let totalCeOi = 0;
  let totalPeOi = 0;

  quotes.forEach((q: any) => {
    if (!oiByStrike[q.strike]) {
      oiByStrike[q.strike] = {
        strike: q.strike,
        ceOi: 0,
        peOi: 0,
        ceChngOi: 0,
        peChngOi: 0,
        ceBuildup: "Neutral",
        peBuildup: "Neutral",
        ceLtpChgPct: 0,
        peLtpChgPct: 0,
      };
    }
    if (q.type === "CE") {
      oiByStrike[q.strike].ceOi += q.oi || 0;
      oiByStrike[q.strike].ceChngOi += q.chng_oi || 0;
      oiByStrike[q.strike].ceBuildup = q.buildup || "Neutral";
      oiByStrike[q.strike].ceLtpChgPct = q.price_chg_pct || 0;
      totalCeChngOi += Math.max(0, q.chng_oi || 0);
      totalCeOi += q.oi || 0;
    } else {
      oiByStrike[q.strike].peOi += q.oi || 0;
      oiByStrike[q.strike].peChngOi += q.chng_oi || 0;
      oiByStrike[q.strike].peBuildup = q.buildup || "Neutral";
      oiByStrike[q.strike].peLtpChgPct = q.price_chg_pct || 0;
      totalPeChngOi += Math.max(0, q.chng_oi || 0);
      totalPeOi += q.oi || 0;
    }
  });

  const sortedStrikes = Object.keys(oiByStrike)
    .map(Number)
    .sort((a, b) => a - b);
  const atmIdx = sortedStrikes.indexOf(atm_strike);
  const nearbyStrikes =
    atmIdx >= 0
      ? sortedStrikes.slice(Math.max(0, atmIdx - 7), Math.min(sortedStrikes.length, atmIdx + 8))
      : sortedStrikes.slice(0, 15);

  const totalChngOi = totalCeChngOi + totalPeChngOi;
  const bearsPower = totalChngOi > 0 ? (totalCeChngOi / totalChngOi) * 100 : 50;
  const bullsPower = totalChngOi > 0 ? (totalPeChngOi / totalChngOi) * 100 : 50;

  const resistance = analysis?.highest_call_oi_strike || atm_strike + 200;
  const support = analysis?.highest_put_oi_strike || atm_strike - 200;
  const range = resistance - support;
  const actualSpot = spot_price || atm_strike;
  const spotPosition = range > 0 ? ((actualSpot - support) / range) * 100 : 50;

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      <FnoHeaderNav
        activeTab="oi"
        title="Pro OI & Buildup Analysis"
        subtitle="Real-time Intraday 4-Quadrant Footprint Tracking"
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
              <h3 className="font-bold text-red-900">Failed to load OI Data</h3>
              <p className="text-sm text-red-700 mt-1">{data.error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* TUG OF WAR METER */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex justify-between items-end mb-6">
                <div>
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <Swords size={20} className="text-amber-500" /> Tug of War (Fresh Writers Flow)
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Comparing intraday Call OI addition vs Put OI addition on {symbol}.
                  </p>
                </div>
              </div>

              <div className="relative h-8 bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                <div
                  className="h-full bg-gradient-to-r from-red-600 to-red-400 flex items-center justify-start px-4 text-white font-bold text-sm transition-all duration-1000"
                  style={{ width: `${bearsPower}%` }}
                >
                  {bearsPower > 15 && `Bears ${bearsPower.toFixed(0)}%`}
                </div>
                <div
                  className="h-full bg-gradient-to-l from-emerald-600 to-emerald-400 flex items-center justify-end px-4 text-white font-bold text-sm transition-all duration-1000"
                  style={{ width: `${bullsPower}%` }}
                >
                  {bullsPower > 15 && `Bulls ${bullsPower.toFixed(0)}%`}
                </div>
                <div className="absolute left-1/2 top-0 bottom-0 w-1 bg-white shadow-[0_0_10px_rgba(0,0,0,0.3)]" />
              </div>

              <div className="flex justify-between mt-3 text-xs font-semibold">
                <span className="text-red-600 flex items-center gap-1">
                  <TrendingDown size={14} /> Fresh Call OI: {(totalCeChngOi / 100000).toFixed(2)}L
                </span>
                <span className="text-slate-600">
                  OI PCR: {totalCeOi > 0 ? (totalPeOi / totalCeOi).toFixed(2) : "1.00"} | Vol PCR:{" "}
                  {analysis?.vol_pcr ?? "-"}
                </span>
                <span className="text-emerald-600 flex items-center gap-1">
                  Fresh Put OI: {(totalPeChngOi / 100000).toFixed(2)}L <TrendingUp size={14} />
                </span>
              </div>
            </div>

            {/* MAGNET GAUGE */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex justify-between items-end mb-6">
                <div>
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <Magnet size={20} className="text-blue-500" /> Call / Put Wall Magnet Test
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Live Spot relative to Highest Put Wall (Support) & Call Wall (Resistance).
                  </p>
                </div>
              </div>

              <div className="px-4 pt-2">
                <div className="relative w-full h-2 bg-slate-200 rounded-full">
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center">
                    <div className="w-4 h-4 bg-emerald-500 rounded-full border-2 border-white shadow-md" />
                    <div className="mt-2 text-xs font-bold text-emerald-600">S1: {support}</div>
                  </div>

                  <div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center z-10 transition-all duration-500"
                    style={{ left: `${Math.max(5, Math.min(95, spotPosition))}%` }}
                  >
                    <div className="bg-slate-800 text-white text-xs font-bold px-2 py-1 rounded shadow-lg mb-1 relative top-[-24px]">
                      {actualSpot.toFixed(2)}
                      <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
                    </div>
                    <div className="w-3 h-3 bg-blue-600 rounded-full border-2 border-white shadow-md absolute top-1/2 -translate-y-1/2" />
                  </div>

                  <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 flex flex-col items-center">
                    <div className="w-4 h-4 bg-red-500 rounded-full border-2 border-white shadow-md" />
                    <div className="mt-2 text-xs font-bold text-red-600">R1: {resistance}</div>
                  </div>
                </div>
              </div>

              <div className="mt-10 text-center text-xs text-slate-600 font-medium">
                {spotPosition < 30
                  ? "Testing Institutional Put Support Wall (High Bounce / Breakdown Alert)."
                  : spotPosition > 70
                  ? "Testing Institutional Call Resistance Wall (Breakout or Rejection Zone)."
                  : `Trading inside Institutional Range (Max Pain Anchor: ${analysis?.max_pain || atm_strike}).`}
              </div>
            </div>
          </div>

          {/* 4-QUADRANT BUILDUP ANALYZER TABLE */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-5 border-b border-slate-100 bg-slate-50 flex flex-wrap justify-between items-center gap-2">
              <div>
                <h3 className="font-bold text-slate-800">
                  4-Quadrant OI Buildup Analyzer ({symbol})
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Combines real-time Exchange Change in OI + Option Price % change strike-by-strike.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
                <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">Long Buildup</span>
                <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800">Short Buildup</span>
                <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800">Short Covering</span>
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800">Long Unwinding</span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm text-center">
                <thead>
                  <tr className="bg-slate-100/60 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-4 font-medium text-right">Call Total OI</th>
                    <th className="py-3 px-4 font-medium text-right">Call OI Chg</th>
                    <th className="py-3 px-4 font-bold text-red-600 text-right border-r border-slate-200">
                      Call Footprint
                    </th>
                    <th className="py-3 px-4 font-black text-slate-800 bg-white border-r border-slate-200">
                      STRIKE
                    </th>
                    <th className="py-3 px-4 font-bold text-emerald-600 text-left">Put Footprint</th>
                    <th className="py-3 px-4 font-medium text-left">Put OI Chg</th>
                    <th className="py-3 px-4 font-medium text-left">Put Total OI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {nearbyStrikes.map((strike) => {
                    const row = oiByStrike[strike];
                    const isAtm = strike === atm_strike;

                    return (
                      <tr
                        key={strike}
                        className={`hover:bg-slate-50 transition-colors ${
                          isAtm ? "bg-indigo-50/40" : ""
                        }`}
                      >
                        <td className="py-3 px-4 text-right text-slate-600 font-medium">
                          {(row.ceOi / 1000).toFixed(1)}k
                        </td>
                        <td
                          className={`py-3 px-4 text-right font-semibold ${
                            row.ceChngOi < 0
                              ? "text-emerald-600"
                              : row.ceChngOi > 0
                              ? "text-rose-600"
                              : "text-slate-400"
                          }`}
                        >
                          {row.ceChngOi > 0 ? "+" : ""}
                          {(row.ceChngOi / 1000).toFixed(1)}k
                        </td>
                        <td className="py-3 px-4 text-right border-r border-slate-200">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-bold border ${getBuildupBadge(
                              row.ceBuildup
                            )}`}
                          >
                            {row.ceBuildup}
                          </span>
                        </td>

                        <td
                          className={`py-3 px-4 font-black border-r border-slate-200 ${
                            isAtm ? "bg-indigo-100 text-indigo-900" : "bg-slate-50 text-slate-800"
                          }`}
                        >
                          {strike}{" "}
                          {isAtm && <span className="text-[10px] ml-1 opacity-75">ATM</span>}
                        </td>

                        <td className="py-3 px-4 text-left">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-bold border ${getBuildupBadge(
                              row.peBuildup
                            )}`}
                          >
                            {row.peBuildup}
                          </span>
                        </td>
                        <td
                          className={`py-3 px-4 text-left font-semibold ${
                            row.peChngOi > 0
                              ? "text-emerald-600"
                              : row.peChngOi < 0
                              ? "text-rose-600"
                              : "text-slate-400"
                          }`}
                        >
                          {row.peChngOi > 0 ? "+" : ""}
                          {(row.peChngOi / 1000).toFixed(1)}k
                        </td>
                        <td className="py-3 px-4 text-left text-slate-600 font-medium">
                          {(row.peOi / 1000).toFixed(1)}k
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
