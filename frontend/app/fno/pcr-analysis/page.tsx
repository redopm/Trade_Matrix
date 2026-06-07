"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import { AlertCircle, TrendingDown, Gauge, Activity, AlertTriangle } from "lucide-react";
import Link from "next/link";

export default function PcrAnalysis() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("NIFTY"); // Dynamic symbol state

  useEffect(() => {
    loadData();
  }, [symbol]);

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
            <h3 className="font-bold text-red-900">Failed to load PCR Data</h3>
            <p className="text-sm text-red-700 mt-1">{data.error}</p>
          </div>
        </div>
      </div>
    );
  }

  const { analysis } = data;
  const pcr = analysis?.pcr || 1.0;
  
  // PCR Gauge logic - Strict Interpretation
  let pcrZone = "Perfectly Neutral";
  let pcrColor = "text-slate-500 bg-slate-100 border-slate-200";
  let gaugePct = 50;
  
  if (pcr < 0.6) {
    pcrZone = "Extremely Oversold (Reversal Expected)";
    pcrColor = "text-emerald-700 bg-emerald-50 border-emerald-200";
    gaugePct = 10;
  } else if (pcr < 0.85) {
    pcrZone = "Strong Bearish Trend";
    pcrColor = "text-red-600 bg-red-50 border-red-200";
    gaugePct = 25;
  } else if (pcr < 1.0) {
    pcrZone = "Mildly Bearish (More Calls Written)";
    pcrColor = "text-orange-500 bg-orange-50 border-orange-200";
    gaugePct = 40;
  } else if (pcr === 1.0) {
    pcrZone = "Perfectly Neutral";
    pcrColor = "text-slate-600 bg-slate-50 border-slate-200";
    gaugePct = 50;
  } else if (pcr <= 1.15) {
    pcrZone = "Mildly Bullish (More Puts Written)";
    pcrColor = "text-teal-600 bg-teal-50 border-teal-200";
    gaugePct = 60;
  } else if (pcr <= 1.5) {
    pcrZone = "Strong Bullish Trend";
    pcrColor = "text-emerald-600 bg-emerald-50 border-emerald-200";
    gaugePct = 75;
  } else {
    pcrZone = "Extremely Overbought (Reversal Expected)";
    pcrColor = "text-red-700 bg-red-50 border-red-200";
    gaugePct = 90;
  }

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      {/* HEADER */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <TrendingDown size={24} className="text-blue-600" /> PCR & Volatility
            </h1>
            <p className="text-sm text-slate-500 mt-1">Put-Call Ratio & Implied Volatility</p>
          </div>
          <div className="flex items-center gap-4">
            <select 
              className="bg-white border border-slate-300 text-slate-800 rounded-lg px-4 py-2 text-sm font-bold shadow-sm"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              <option value="NIFTY">NIFTY 50</option>
              <option value="BANKNIFTY">BANK NIFTY</option>
              <option value="FINNIFTY">FINNIFTY</option>
              <option value="MIDCPNIFTY">MIDCPNIFTY</option>
            </select>
            <div className={`px-4 py-2 rounded-lg border font-bold text-sm ${
              analysis?.sentiment?.includes('BULL') ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
              analysis?.sentiment?.includes('BEAR') ? "text-red-600 bg-red-50 border-red-200" :
              "text-slate-600 bg-slate-50 border-slate-200"
            }`}>
              Sentiment: {analysis?.sentiment || "NEUTRAL"}
            </div>
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
          <Link href="/fno/oi-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Open Interest
          </Link>
          <Link href="/fno/pcr-analysis" className="py-3 border-b-2 border-blue-600 text-blue-600 font-semibold text-sm whitespace-nowrap">
            PCR & Volatility
          </Link>
          <Link href="/fno/option-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Option Analysis
          </Link>
          <Link href="/fno/fii-dii" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            FII / DII Data
          </Link>
        </div>
      </div>

      <div className="p-6 max-w-5xl mx-auto space-y-6">
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* PCR GAUGE CARD */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col items-center justify-center relative overflow-hidden">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 absolute top-6 left-6">PCR Gauge</h2>
            
            <div className="mt-8 mb-4 relative w-64 h-32 overflow-hidden flex items-end justify-center">
              {/* Semicircle Track */}
              <div className="absolute top-0 w-64 h-64 rounded-full border-[30px] border-slate-100"></div>
              
              {/* Colored Segments Overlay (CSS approximation) */}
              <div className="absolute top-0 w-64 h-64 rounded-full border-[30px] border-transparent border-t-emerald-400 border-r-red-400 transform -rotate-45 opacity-20"></div>

              {/* Needle */}
              <div 
                className="absolute bottom-0 w-1 h-32 bg-slate-800 origin-bottom rounded-t-full transition-all duration-1000 ease-out z-10"
                style={{ transform: `rotate(${Math.min(Math.max((gaugePct / 100) * 180 - 90, -90), 90)}deg)` }}
              >
                <div className="w-3 h-3 bg-slate-800 rounded-full absolute -bottom-1.5 -left-1"></div>
              </div>

              <div className="z-20 text-4xl font-black text-slate-800 bg-white px-4 pt-4 rounded-t-full mt-10">
                {pcr.toFixed(2)}
              </div>
            </div>
            
            <div className={`mt-2 px-4 py-2 rounded-full border text-sm font-bold ${pcrColor}`}>
              {pcrZone}
            </div>

            <p className="text-center text-xs text-slate-500 mt-6 max-w-xs">
              Put-Call Ratio (PCR) divides Put OI by Call OI. <br/>
              &lt; 0.6 means high Call writing (Oversold). <br/>
              &gt; 1.5 means high Put writing (Overbought).
            </p>
          </div>

          {/* VOLATILITY CARD */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
             <div>
                <div className="flex items-center gap-2 mb-6">
                  <Activity className="text-indigo-500" />
                  <h2 className="text-lg font-bold text-slate-800">Implied Volatility (IV)</h2>
                </div>
                
                <div className="space-y-6">
                  <div className="flex justify-between items-end border-b border-slate-100 pb-4">
                    <div>
                      <div className="text-xs font-bold uppercase text-slate-400 mb-1">Average ATM IV</div>
                      <div className="text-3xl font-black text-slate-800">
                        {analysis?.avg_atm_iv ? analysis.avg_atm_iv.toFixed(1) + "%" : "14.5%"}
                      </div>
                    </div>
                    {analysis?.avg_atm_iv > 20 ? (
                      <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded flex items-center gap-1"><AlertTriangle size={12}/> HIGH</span>
                    ) : (
                      <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded flex items-center gap-1">NORMAL</span>
                    )}
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                     <h3 className="text-sm font-bold text-slate-800 mb-2">Option Premium Status</h3>
                     <p className="text-sm text-slate-600">
                        {analysis?.avg_atm_iv > 20 
                          ? "Premiums are highly inflated. Best for Option Selling (Credit Spreads). Option Buying carries high Theta decay risk."
                          : "Premiums are fairly priced. Good environment for Directional Option Buying or Debit Spreads."}
                     </p>
                  </div>
                </div>
             </div>
             
             <div className="mt-6 flex gap-4 text-xs font-medium text-slate-500">
                <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> Low IV (&lt; 15) = Cheap Premiums</div>
                <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-red-500"></div> High IV (&gt; 20) = Expensive</div>
             </div>
          </div>
        </div>

      </div>
    </div>
  );
}
