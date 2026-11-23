"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain, predictKronos } from "@/lib/api";
import { AlertCircle, ActivitySquare, Shield, Zap } from "lucide-react";
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
  ReferenceLine,
} from "recharts";
import { FnoHeaderNav, getSavedFnoSymbol } from "@/components/FnoHeaderNav";

export default function OptionAnalysis() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPredictionSymbol, setSelectedPredictionSymbol] = useState<string>("NSE:NIFTY50-INDEX");
  const [predictionData, setPredictionData] = useState<any>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionDays, setPredictionDays] = useState(5);

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
      if (res?.spot_fyers_symbol) {
        setSelectedPredictionSymbol(res.spot_fyers_symbol);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleSymbolChange = (next: string) => {
    setSymbol(next);
    setPredictionData(null);
    loadData(next);
  };

  const handlePredict = async () => {
    if (!selectedPredictionSymbol) return;
    setIsPredicting(true);
    setPredictionData(null);
    try {
      const json = await predictKronos(selectedPredictionSymbol, predictionDays);
      if (json.prediction && json.historical) {
        const combined = [
          ...json.historical.map((d: any) => ({
            date: d.timestamps.split(" ")[0],
            historical_close: d.close,
            predicted_close: null,
          })),
          ...json.prediction.map((d: any) => ({
            date: d.timestamps.split(" ")[0],
            historical_close: null,
            predicted_close: d.close,
          })),
        ];
        setPredictionData(combined);
      } else {
        alert("Prediction Error: " + JSON.stringify(json.error || json));
      }
    } catch (e) {
      console.error(e);
      alert("Failed to fetch prediction");
    }
    setIsPredicting(false);
  };

  const quotes = data?.quotes || [];
  const atm_strike = data?.atm_strike || 0;
  const reversals = data?.reversals || {};
  const brain = data?.aladdin_option_brain || {};

  // Slice ATM ± 10 strikes cleanly for both indices and F&O equities
  const allStrikes: number[] = Array.from(
    new Set<number>(quotes.map((q: any) => Number(q.strike)))
  ).sort((a, b) => a - b);
  const atmIdx = allStrikes.indexOf(Number(atm_strike));
  const strikesList =
    atmIdx >= 0
      ? allStrikes.slice(Math.max(0, atmIdx - 10), Math.min(allStrikes.length, atmIdx + 11))
      : allStrikes.slice(0, 21);

  const chartData = strikesList.map((strike) => {
    const ce = quotes.find((q: any) => q.strike === strike && q.type === "CE");
    const pe = quotes.find((q: any) => q.strike === strike && q.type === "PE");
    const ce_oi = ce?.oi || 0;
    const pe_oi = pe?.oi || 0;
    const strike_pcr = ce_oi > 0 ? Number((pe_oi / ce_oi).toFixed(2)) : 0;

    return {
      strike,
      ce_oi,
      pe_oi,
      ce_chng_oi: ce?.chng_oi || 0,
      pe_chng_oi: pe?.chng_oi || 0,
      ce_iv: ce?.iv || 0,
      pe_iv: pe?.iv || 0,
      pcr: strike_pcr,
    };
  });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900 border border-gray-700 p-3 rounded-lg shadow-xl">
          <p className="font-bold text-white mb-2 border-b border-gray-700 pb-1">
            Strike: {label}
          </p>
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
      <FnoHeaderNav
        activeTab="analytics"
        title="Pro Option Analytics"
        subtitle="OI Walls, Change-in-OI Momentum, IV Skew & Kronos AI Trajectory"
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
              <h3 className="font-bold text-red-900">Failed to load Option Analysis</h3>
              <p className="text-sm text-red-700 mt-1">{data.error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
          {/* STRUCTURAL LEVELS SUMMARY STRIP */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs font-bold text-slate-400 uppercase flex items-center gap-1">
                <Shield size={13} className="text-emerald-600" /> Support Wall (S1 / S2)
              </div>
              <div className="text-xl font-black text-emerald-700 mt-1">
                {reversals.S1 || "-"} / {reversals.S2 || "-"}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs font-bold text-slate-400 uppercase flex items-center gap-1">
                <Shield size={13} className="text-red-600" /> Resistance Wall (R1 / R2)
              </div>
              <div className="text-xl font-black text-red-600 mt-1">
                {reversals.R1 || "-"} / {reversals.R2 || "-"}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs font-bold text-slate-400 uppercase flex items-center gap-1">
                <Zap size={13} className="text-purple-600" /> Zero Gamma Flip Pivot
              </div>
              <div className="text-xl font-black text-purple-700 mt-1">
                {reversals.zero_gamma || "-"}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-xs font-bold text-slate-400 uppercase">Max Pain Magnet</div>
              <div className="text-xl font-black text-indigo-700 mt-1">
                {reversals.max_pain || data?.analysis?.max_pain || "-"}
              </div>
            </div>
          </div>

          {/* ROW 1: OI PROFILES */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <ActivitySquare size={18} className="text-indigo-500" /> Total OI Profile ({symbol})
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Identifies institutional Support (Green) and Resistance (Red) walls.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{ fontSize: 10 }} tickMargin={10} minTickGap={20} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(val) => `${(val / 100000).toFixed(1)}L`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                  <ReferenceLine
                    x={atm_strike}
                    stroke="#94a3b8"
                    strokeDasharray="3 3"
                    label={{ position: "top", value: "ATM", fill: "#64748b", fontSize: 10 }}
                  />
                  <Bar dataKey="ce_oi" name="Call OI (Resistance)" fill="#ef4444" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="pe_oi" name="Put OI (Support)" fill="#10b981" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <ActivitySquare size={18} className="text-orange-500" /> Intraday Change in OI ({symbol})
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Tracks live institutional fresh writing vs short covering per strike.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{ fontSize: 10 }} tickMargin={10} minTickGap={20} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(val) => `${(val / 100000).toFixed(1)}L`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" />
                  <Bar dataKey="ce_chng_oi" name="Call Writers (Bears)" fill="#f87171" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="pe_chng_oi" name="Put Writers (Bulls)" fill="#34d399" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ROW 2: IV SMILE & STRIKE PCR */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <ActivitySquare size={18} className="text-purple-500" /> IV Smile & Skew (Fear Gauge)
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  When Put IV rises sharply above Call IV, institutions are buying crash protection.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{ fontSize: 10 }} tickMargin={10} minTickGap={20} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(val) => `${val}%`} domain={["dataMin - 2", "dataMax + 2"]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
                  <ReferenceLine
                    x={atm_strike}
                    stroke="#94a3b8"
                    strokeDasharray="3 3"
                    label={{ position: "top", value: "ATM", fill: "#64748b", fontSize: 10 }}
                  />
                  <Line type="monotone" dataKey="ce_iv" name="Call IV" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 6 }} />
                  <Line type="monotone" dataKey="pe_iv" name="Put IV" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="mb-4">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <ActivitySquare size={18} className="text-teal-500" /> Strike-wise PCR Curve
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Peaks show strong Put-written support strikes; troughs show strong Call resistance.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPcr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="strike" tick={{ fontSize: 10 }} tickMargin={10} minTickGap={20} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine
                    y={1}
                    stroke="#ef4444"
                    strokeDasharray="3 3"
                    label={{ position: "insideTopLeft", value: "Neutral (1.0)", fill: "#ef4444", fontSize: 10 }}
                  />
                  <ReferenceLine x={atm_strike} stroke="#94a3b8" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="pcr" name="Put-Call Ratio" stroke="#0ea5e9" strokeWidth={2} fillOpacity={1} fill="url(#colorPcr)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ROW 3: KRONOS AI PREDICTION */}
          <div className="bg-gradient-to-r from-slate-900 to-indigo-900 p-6 rounded-2xl border border-indigo-500/30 shadow-xl">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <ActivitySquare className="text-indigo-400" /> Kronos AI Price Trajectory Forecast
                </h3>
                <p className="text-indigo-200 text-sm mt-1">
                  Forecasts underlying direction for {symbol} ({selectedPredictionSymbol}) over the next {predictionDays} trading days.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={predictionDays}
                  onChange={(e) => setPredictionDays(Number(e.target.value))}
                  className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none"
                  disabled={isPredicting}
                >
                  <option value={5}>5 Days</option>
                  <option value={10}>10 Days</option>
                  <option value={15}>15 Days</option>
                </select>
                <select
                  className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none"
                  value={selectedPredictionSymbol}
                  onChange={(e) => setSelectedPredictionSymbol(e.target.value)}
                >
                  {data?.spot_fyers_symbol && (
                    <option value={data.spot_fyers_symbol}>
                      Active ({symbol})
                    </option>
                  )}
                  <option value="NSE:NIFTY50-INDEX">NIFTY 50</option>
                  <option value="NSE:NIFTYBANK-INDEX">BANK NIFTY</option>
                  <option value="NSE:FINNIFTY-INDEX">FIN NIFTY</option>
                  <option value="NSE:MIDCPNIFTY-INDEX">MIDCAP NIFTY</option>
                </select>
                <button
                  onClick={handlePredict}
                  disabled={!selectedPredictionSymbol || isPredicting}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 text-white px-5 py-2 rounded-lg font-medium transition-all shadow-lg flex items-center gap-2"
                >
                  {isPredicting && (
                    <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  )}
                  {isPredicting ? "Predicting..." : "Predict Trajectory"}
                </button>
              </div>
            </div>

            {predictionData && (
              <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={predictionData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} tickMargin={10} minTickGap={25} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} domain={["auto", "auto"]} tickFormatter={(val) => `₹${val}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc", borderRadius: "8px" }}
                      itemStyle={{ color: "#f8fafc" }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="historical_close" name="Historical Close" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="predicted_close" name={`AI Forecast (${predictionDays} Days)`} stroke="#10b981" strokeWidth={3} strokeDasharray="5 5" dot={{ r: 4, fill: "#10b981", strokeWidth: 0 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
