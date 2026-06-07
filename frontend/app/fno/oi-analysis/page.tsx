"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import { AlertCircle, BarChart2, TrendingUp, TrendingDown, Swords, Magnet } from "lucide-react";
import Link from "next/link";

export default function OiAnalysis() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const symbol = "NIFTY"; 

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchOptionChain(symbol);
      setData(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex-1 min-h-screen bg-slate-50/50 p-6 flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin" />
      </div>
    );
  }

  if (data?.error) {
    return (
      <div className="flex-1 min-h-screen bg-slate-50/50 p-6">
        <div className="bg-red-50 border border-red-200 p-6 rounded-xl flex items-start gap-4">
          <AlertCircle className="text-red-600 mt-1" />
          <div>
            <h3 className="font-bold text-red-900">Failed to load OI Data</h3>
            <p className="text-sm text-red-700 mt-1">{data.error}</p>
          </div>
        </div>
      </div>
    );
  }

  const { analysis, quotes, atm_strike } = data;
  
  // Aggregate Data
  const oiByStrike: Record<number, any> = {};
  let totalCeChngOi = 0;
  let totalPeChngOi = 0;
  let totalCeOi = 0;
  let totalPeOi = 0;

  quotes.forEach((q: any) => {
    if (!oiByStrike[q.strike]) {
      oiByStrike[q.strike] = { strike: q.strike, ceOi: 0, peOi: 0, ceChngOi: 0, peChngOi: 0 };
    }
    if (q.type === "CE") {
      oiByStrike[q.strike].ceOi += q.oi;
      oiByStrike[q.strike].ceChngOi += q.chng_oi || 0;
      totalCeChngOi += Math.max(0, q.chng_oi || 0); // Only positive buildup for meter
      totalCeOi += q.oi;
    } else {
      oiByStrike[q.strike].peOi += q.oi;
      oiByStrike[q.strike].peChngOi += q.chng_oi || 0;
      totalPeChngOi += Math.max(0, q.chng_oi || 0); // Only positive buildup for meter
      totalPeOi += q.oi;
    }
  });

  const sortedStrikes = Object.keys(oiByStrike).map(Number).sort((a, b) => a - b);
  const nearbyStrikes = sortedStrikes.filter(s => Math.abs(s - atm_strike) <= 400);

  // Tug of War percentages
  const totalChngOi = totalCeChngOi + totalPeChngOi;
  const bearsPower = totalChngOi > 0 ? (totalCeChngOi / totalChngOi) * 100 : 50;
  const bullsPower = totalChngOi > 0 ? (totalPeChngOi / totalChngOi) * 100 : 50;

  // Magnet / Gauge logic
  const resistance = analysis?.highest_call_oi_strike || atm_strike + 200;
  const support = analysis?.highest_put_oi_strike || atm_strike - 200;
  const range = resistance - support;
  const spotPosition = range > 0 ? ((atm_strike - support) / range) * 100 : 50;

  // Buildup Logic (Proxy without price change)
  const getBuildupStatus = (type: "CE" | "PE", chngOi: number, strike: number, atm: number) => {
    if (chngOi > 10000) {
      return type === "CE" ? "Short Buildup 🔴" : "Short Buildup 🟢"; // Option Selling is dominant
    } else if (chngOi < -10000) {
      return type === "CE" ? "Short Covering 🚀" : "Long Unwinding 🩸"; // Sellers running or Buyers booking
    }
    return "Neutral ⚪";
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      {/* HEADER */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <BarChart2 size={24} className="text-blue-600" /> Pro OI Analysis
            </h1>
            <p className="text-sm text-slate-500 mt-1">Buildup & Footprint Tracking</p>
          </div>
          <div className="text-right">
            <div className="text-sm font-bold text-slate-800 flex items-center justify-end gap-2">
              ATM: {atm_strike}
            </div>
            <div className="text-xs text-slate-500">Current Market Center</div>
          </div>
        </div>
        
        {/* HORIZONTAL TAB NAVIGATION */}
        <div className="px-6 flex items-center gap-6 overflow-x-auto border-t border-slate-100">
          <Link href="/fno" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Option Chain
          </Link>
          <Link href="/fno/strategy-builder" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Strategy Builder
          </Link>
          <Link href="/fno/oi-analysis" className="py-3 border-b-2 border-blue-600 text-blue-600 font-semibold text-sm whitespace-nowrap">
            Pro OI Analysis
          </Link>
          <Link href="/fno/pcr-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            PCR & Volatility
          </Link>
          <Link href="/fno/option-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Pro Analytics
          </Link>
          <Link href="/fno/fii-dii" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            FII / DII Data
          </Link>
        </div>
      </div>

      <div className="p-6 max-w-7xl mx-auto space-y-6">
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* TUG OF WAR METER */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex justify-between items-end mb-6">
              <div>
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <Swords size={20} className="text-amber-500" /> Tug of War (Intraday Bulls vs Bears)
                </h3>
                <p className="text-xs text-slate-500 mt-1">Comparing fresh Call Writing vs Put Writing today.</p>
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
              
              {/* Center Line */}
              <div className="absolute left-1/2 top-0 bottom-0 w-1 bg-white shadow-[0_0_10px_rgba(0,0,0,0.3)]"></div>
            </div>
            
            <div className="flex justify-between mt-3 text-xs font-semibold">
              <span className="text-red-600 flex items-center gap-1"><TrendingDown size={14}/> Fresh Call OI: {(totalCeChngOi/100000).toFixed(1)}L</span>
              <span className="text-slate-400">Total PCR: {(totalPeOi / totalCeOi).toFixed(2)}</span>
              <span className="text-emerald-600 flex items-center gap-1">Fresh Put OI: {(totalPeChngOi/100000).toFixed(1)}L <TrendingUp size={14}/></span>
            </div>
          </div>

          {/* MAGNET GAUGE */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex justify-between items-end mb-6">
              <div>
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <Magnet size={20} className="text-blue-500" /> Market Magnet Test (Live)
                </h3>
                <p className="text-xs text-slate-500 mt-1">Distance between Spot Price and nearest Institutional Walls.</p>
              </div>
            </div>
            
            <div className="px-4 pt-2">
              <div className="relative w-full h-2 bg-slate-200 rounded-full">
                
                {/* Support Point */}
                <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center">
                  <div className="w-4 h-4 bg-emerald-500 rounded-full border-2 border-white shadow-md"></div>
                  <div className="mt-2 text-xs font-bold text-emerald-600">S1: {support}</div>
                </div>

                {/* Spot Price Pointer */}
                <div 
                  className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center z-10 transition-all duration-500"
                  style={{ left: `${Math.max(5, Math.min(95, spotPosition))}%` }}
                >
                  <div className="bg-slate-800 text-white text-xs font-bold px-2 py-1 rounded shadow-lg mb-1 relative top-[-24px]">
                    LTP: {atm_strike}
                    <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
                  </div>
                  <div className="w-3 h-3 bg-blue-600 rounded-full border-2 border-white shadow-md absolute top-1/2 -translate-y-1/2"></div>
                </div>

                {/* Resistance Point */}
                <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 flex flex-col items-center">
                  <div className="w-4 h-4 bg-red-500 rounded-full border-2 border-white shadow-md"></div>
                  <div className="mt-2 text-xs font-bold text-red-600">R1: {resistance}</div>
                </div>
              </div>
            </div>
            
            <div className="mt-10 text-center text-xs text-slate-500">
              {spotPosition < 30 ? "⚠️ Market is heavily testing the Support Zone." : 
               spotPosition > 70 ? "⚠️ Market is heavily testing the Resistance Zone." : 
               "Market is trading safely in the middle of the range."}
            </div>
          </div>
        </div>

        {/* BUILDUP ANALYZER TABLE */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-5 border-b border-slate-100 bg-slate-50">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
               The Buildup Analyzer (Near ATM)
            </h3>
            <p className="text-xs text-slate-500 mt-1">Tracks Intraday Smart Money Footprints strike-by-strike.</p>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-center">
              <thead>
                <tr className="bg-slate-100/50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4 font-medium text-right">Call OI Chg</th>
                  <th className="py-3 px-4 font-bold text-red-600 text-right border-r border-slate-200">Call Buildup</th>
                  <th className="py-3 px-4 font-black text-slate-800 bg-white border-r border-slate-200">STRIKE</th>
                  <th className="py-3 px-4 font-bold text-emerald-600 text-left">Put Buildup</th>
                  <th className="py-3 px-4 font-medium text-left">Put OI Chg</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {nearbyStrikes.map((strike) => {
                  const data = oiByStrike[strike];
                  const ceStatus = getBuildupStatus("CE", data.ceChngOi, strike, atm_strike);
                  const peStatus = getBuildupStatus("PE", data.peChngOi, strike, atm_strike);
                  const isAtm = strike === atm_strike;
                  
                  return (
                    <tr key={strike} className={`hover:bg-slate-50 transition-colors ${isAtm ? 'bg-amber-50/30' : ''}`}>
                      {/* CE Side */}
                      <td className={`py-3 px-4 text-right ${data.ceChngOi < 0 ? 'text-emerald-500 font-bold' : 'text-slate-500'}`}>
                        {data.ceChngOi > 0 ? "+" : ""}{(data.ceChngOi/1000).toFixed(1)}k
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-slate-700 border-r border-slate-200">
                        {ceStatus}
                      </td>
                      
                      {/* STRIKE */}
                      <td className={`py-3 px-4 font-black border-r border-slate-200 ${isAtm ? 'bg-amber-100 text-amber-900' : 'bg-slate-50 text-slate-800'}`}>
                        {strike} {isAtm && <span className="text-[10px] ml-1 opacity-70">ATM</span>}
                      </td>
                      
                      {/* PE Side */}
                      <td className="py-3 px-4 text-left font-semibold text-slate-700">
                        {peStatus}
                      </td>
                      <td className={`py-3 px-4 text-left ${data.peChngOi < 0 ? 'text-red-500 font-bold' : 'text-slate-500'}`}>
                        {data.peChngOi > 0 ? "+" : ""}{(data.peChngOi/1000).toFixed(1)}k
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
