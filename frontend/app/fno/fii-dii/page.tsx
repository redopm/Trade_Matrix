"use client";

import React from "react";
import { Building2, TrendingUp, TrendingDown, Info } from "lucide-react";
import Link from "next/link";

export default function FiiDiiData() {
  // Mock data since Fyers doesn't provide FII/DII. 
  // In a real scenario, this would come from an NSE scraper API.
  const fiiDiiData = {
    date: "Latest Trading Session",
    cash: {
      fii_net: -1250.50,
      dii_net: 2100.25
    },
    fno: {
      index_futures_long: 120000,
      index_futures_short: 180000,
      net_contracts: -60000
    }
  };

  const longShortRatio = fiiDiiData.fno.index_futures_long / (fiiDiiData.fno.index_futures_long + fiiDiiData.fno.index_futures_short);
  const isBullish = longShortRatio > 0.5;

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      {/* HEADER */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Building2 size={24} className="text-blue-600" /> Institutional Activity
            </h1>
            <p className="text-sm text-slate-500 mt-1">FII & DII Cash & F&O Data</p>
          </div>
          <div className={`px-4 py-2 rounded-lg border font-bold text-sm ${
            isBullish ? "text-emerald-600 bg-emerald-50 border-emerald-200" : "text-red-600 bg-red-50 border-red-200"
          }`}>
            Institutional Bias: {isBullish ? "BULLISH" : "BEARISH"}
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
          <Link href="/fno/pcr-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            PCR & Volatility
          </Link>
          <Link href="/fno/option-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Option Analysis
          </Link>
          <Link href="/fno/fii-dii" className="py-3 border-b-2 border-blue-600 text-blue-600 font-semibold text-sm whitespace-nowrap">
            FII / DII Data
          </Link>
        </div>
      </div>

      <div className="p-6 max-w-6xl mx-auto space-y-6">
        
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-start gap-3">
          <Info className="text-blue-600 mt-0.5" size={20} />
          <div>
            <h3 className="font-bold text-blue-900">Data Source Notice</h3>
            <p className="text-sm text-blue-800 mt-1">
              Fyers API does not provide real-time Institutional data. This page currently displays a structural template. In a production environment, this would integrate with an NSE Data Scraper API.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* CASH MARKET */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h2 className="font-bold text-slate-800 uppercase tracking-wider text-sm">Cash Market (Equities)</h2>
              <p className="text-xs text-slate-500 mt-0.5">{fiiDiiData.date}</p>
            </div>
            <div className="p-6 space-y-6">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold text-slate-700">FII Net Activity</span>
                  <span className={`font-black ${fiiDiiData.cash.fii_net > 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {fiiDiiData.cash.fii_net > 0 ? "+" : ""}₹{fiiDiiData.cash.fii_net} Cr
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className={`h-full ${fiiDiiData.cash.fii_net > 0 ? "bg-emerald-500" : "bg-red-500"}`} style={{ width: "100%" }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold text-slate-700">DII Net Activity</span>
                  <span className={`font-black ${fiiDiiData.cash.dii_net > 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {fiiDiiData.cash.dii_net > 0 ? "+" : ""}₹{fiiDiiData.cash.dii_net} Cr
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div className={`h-full ${fiiDiiData.cash.dii_net > 0 ? "bg-emerald-500" : "bg-red-500"}`} style={{ width: "100%" }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* F&O MARKET (INDEX FUTURES) */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h2 className="font-bold text-slate-800 uppercase tracking-wider text-sm">F&O Market (Index Futures)</h2>
              <p className="text-xs text-slate-500 mt-0.5">FII Long vs Short Positioning</p>
            </div>
            <div className="p-6">
              
              <div className="flex items-center justify-between mb-8">
                <div className="text-center">
                  <div className="text-2xl font-black text-emerald-600 flex items-center justify-center gap-1">
                    <TrendingUp size={20}/> {fiiDiiData.fno.index_futures_long}
                  </div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-1">Long Contracts</div>
                </div>
                
                <div className="text-center">
                  <div className="text-3xl font-black text-slate-800">
                    {(longShortRatio * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-1">Long Ratio</div>
                </div>

                <div className="text-center">
                  <div className="text-2xl font-black text-red-600 flex items-center justify-center gap-1">
                    <TrendingDown size={20}/> {fiiDiiData.fno.index_futures_short}
                  </div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-1">Short Contracts</div>
                </div>
              </div>

              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 text-center">
                 <h3 className="text-sm font-bold text-slate-800 mb-1">Interpretation</h3>
                 <p className="text-sm text-slate-600">
                    {isBullish 
                      ? "FIIs are carrying more LONG contracts than SHORT contracts. This indicates a structurally Bullish bias for the upcoming sessions."
                      : "FIIs are carrying more SHORT contracts. This heavy short positioning indicates they expect the market to fall."}
                 </p>
              </div>

            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
