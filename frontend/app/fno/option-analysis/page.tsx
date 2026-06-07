"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import { AlertCircle, FileSearch, BarChart2, ActivitySquare } from "lucide-react";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  ReferenceLine
} from "recharts";

export default function OptionAnalysis() {
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
            <h3 className="font-bold text-red-900">Failed to load Option Analysis</h3>
            <p className="text-sm text-red-700 mt-1">{data.error}</p>
          </div>
        </div>
      </div>
    );
  }

  const { quotes, atm_strike } = data;

  // Get nearby strikes for charts (ATM +/- 15 strikes for a good wide view)
  const nearbyQuotes = quotes
    .filter((q: any) => Math.abs(q.strike - atm_strike) <= 1500)
    .sort((a: any, b: any) => a.strike - b.strike);

  const ceQuotes = nearbyQuotes.filter((q: any) => q.type === "CE");
  const peQuotes = nearbyQuotes.filter((q: any) => q.type === "PE");

  const chartData: any[] = [];
  const strikesSet = new Set<number>();
  ceQuotes.forEach((q: any) => strikesSet.add(q.strike));
  peQuotes.forEach((q: any) => strikesSet.add(q.strike));

  const strikesList = Array.from(strikesSet).sort((a, b) => a - b);

  strikesList.forEach(strike => {
    const ce = ceQuotes.find((q: any) => q.strike === strike);
    const pe = peQuotes.find((q: any) => q.strike === strike);

    const ce_oi = ce?.oi || 0;
    const pe_oi = pe?.oi || 0;
    
    // Put-Call Ratio per strike
    const strike_pcr = ce_oi > 0 ? Number((pe_oi / ce_oi).toFixed(2)) : 0;

    chartData.push({
      strike: strike,
      ce_oi: ce_oi,
      pe_oi: pe_oi,
      ce_chng_oi: ce?.chng_oi || 0,
      pe_chng_oi: pe?.chng_oi || 0,
      ce_iv: ce?.iv || 0,
      pe_iv: pe?.iv || 0,
      pcr: strike_pcr,
    });
  });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900 border border-gray-700 p-3 rounded-lg shadow-xl">
          <p className="font-bold text-white mb-2 border-b border-gray-700 pb-1">Strike: {label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
              <span className="text-gray-300">{entry.name}:</span>
              <span className="font-bold" style={{ color: entry.color }}>
                {entry.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      {/* HEADER */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <BarChart2 size={24} className="text-blue-600" /> Pro Option Analytics
            </h1>
            <p className="text-sm text-slate-500 mt-1">Institutional Data Visualization</p>
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
          <Link href="/fno/oi-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            Open Interest
          </Link>
          <Link href="/fno/pcr-analysis" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            PCR & Volatility
          </Link>
          <Link href="/fno/option-analysis" className="py-3 border-b-2 border-blue-600 text-blue-600 font-semibold text-sm whitespace-nowrap">
            Pro Analytics
          </Link>
          <Link href="/fno/fii-dii" className="py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 font-medium text-sm whitespace-nowrap">
            FII / DII Data
          </Link>
        </div>
      </div>

      <div className="p-6 max-w-7xl mx-auto space-y-6">
        
        {/* ROW 1: OI PROFILES */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Total OI Profile */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <ActivitySquare size={18} className="text-indigo-500" /> Total OI Profile (Concrete Walls)
              </h3>
              <p className="text-xs text-slate-500 mt-1">Identifies major Support (Green) and Resistance (Red) levels.</p>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                  <YAxis tick={{fontSize: 10}} tickFormatter={(val) => `${(val/100000).toFixed(1)}L`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{fontSize: '12px'}} />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" label={{ position: 'top', value: 'ATM', fill: '#64748b', fontSize: 10 }} />
                  <Bar dataKey="ce_oi" name="Call OI (Resistance)" fill="#ef4444" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="pe_oi" name="Put OI (Support)" fill="#10b981" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Change in OI Profile */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <ActivitySquare size={18} className="text-orange-500" /> Intraday Change in OI (Momentum)
              </h3>
              <p className="text-xs text-slate-500 mt-1">Tracks real-time institutional positioning. Negative bars indicate unwinding.</p>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                  <YAxis tick={{fontSize: 10}} tickFormatter={(val) => `${(val/100000).toFixed(1)}L`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{fontSize: '12px'}} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" />
                  <Bar dataKey="ce_chng_oi" name="Call Writers (Bears)" fill="#f87171" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="pe_chng_oi" name="Put Writers (Bulls)" fill="#34d399" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        {/* ROW 2: ADVANCED GREEKS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* IV Smile / Skew */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <ActivitySquare size={18} className="text-purple-500" /> IV Smile & Skew (Fear Indicator)
              </h3>
              <p className="text-xs text-slate-500 mt-1">If Puts IV is much higher than Calls IV, institutions are hedging against a crash.</p>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                  <YAxis tick={{fontSize: 10}} tickFormatter={(val) => `${val}%`} domain={['dataMin - 2', 'dataMax + 2']} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{fontSize: '12px'}} />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" label={{ position: 'top', value: 'ATM', fill: '#64748b', fontSize: 10 }} />
                  <Line type="monotone" dataKey="ce_iv" name="Call IV" stroke="#ef4444" strokeWidth={2} dot={{r: 2}} activeDot={{r: 6}} />
                  <Line type="monotone" dataKey="pe_iv" name="Put IV" stroke="#10b981" strokeWidth={2} dot={{r: 2}} activeDot={{r: 6}} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Strike-wise PCR */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <ActivitySquare size={18} className="text-teal-500" /> Strike-wise PCR Curve
              </h3>
              <p className="text-xs text-slate-500 mt-1">Peaks indicate extreme bullishness at that strike. Dips indicate extreme bearishness.</p>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPcr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                  <YAxis tick={{fontSize: 10}} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={1} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Neutral (1.0)', fill: '#ef4444', fontSize: 10 }} />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="pcr" name="Put-Call Ratio" stroke="#0ea5e9" strokeWidth={2} fillOpacity={1} fill="url(#colorPcr)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
