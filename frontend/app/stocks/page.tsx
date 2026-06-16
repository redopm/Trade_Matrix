"use client";

import { useState } from "react";
import { stocksApi, predictKronos } from "@/lib/api";
import { Search, TrendingUp, TrendingDown, CheckCircle2, XCircle, AlertCircle, Building2, Target, Crosshair, ActivitySquare } from "lucide-react";
import { ResponsiveContainer, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, Line } from "recharts";

function IndicatorRow({ label, value, good, unit = "" }: {
  label: string;
  value: number | null | undefined;
  good?: boolean;
  unit?: string;
}) {
  const color = good === undefined
    ? "text-slate-900 font-bold"
    : good
    ? "text-emerald-600 font-bold"
    : "text-red-600 font-bold";

  return (
    <div className="flex justify-between items-center py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-sm font-medium text-slate-500">
        {label}
      </span>
      <span className={`font-mono text-sm ${color}`}>
        {value != null ? `${value}${unit}` : "-"}
      </span>
    </div>
  );
}

export default function StocksPage() {
  const [query, setQuery] = useState("");
  const [stockData, setStockData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [predictionData, setPredictionData] = useState<any>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionDays, setPredictionDays] = useState(5);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setPredictionData(null);
    try {
      const res = await stocksApi.getSnapshot(query.trim().toUpperCase());
      setStockData(res.data);
    } catch (e: any) {
      setError(e.message);
      setStockData(null);
    } finally {
      setLoading(false);
    }
  };

  const handlePredict = async () => {
    if (!query.trim()) return;
    setIsPredicting(true);
    setPredictionData(null);
    try {
      const res = await predictKronos(`NSE:${query.trim().toUpperCase()}-EQ`, predictionDays);
      if (res.prediction && res.historical) {
        const combined = [
          ...res.historical.map((d: any) => ({
             date: d.timestamps.split(' ')[0],
             historical_close: d.close,
             predicted_close: null
          })),
          ...res.prediction.map((d: any) => ({
             date: d.timestamps.split(' ')[0],
             historical_close: null,
             predicted_close: d.close
          }))
        ];
        
        // Connect the lines by carrying over the last historical point
        if (res.historical.length > 0 && res.prediction.length > 0) {
            combined[res.historical.length].predicted_close = res.historical[res.historical.length - 1].close;
        }

        setPredictionData(combined);
      } else {
        alert("Prediction Error: " + JSON.stringify(res.error || res));
      }
    } catch (e) {
      console.error(e);
      alert("Failed to fetch prediction");
    }
    setIsPredicting(false);
  };

  const fund = stockData?.fundamentals || {};
  const tech = stockData?.technicals || {};

  return (
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Stock Lookup
        </h1>
        <p className="text-sm mt-2 text-slate-500 font-medium">
          Deep-dive analysis &bull; Fundamentals + Technical indicators
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-4 w-full max-w-3xl">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
            <Search size={20} />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter NSE symbol (e.g. RELIANCE, TCS, INFY)"
            className="w-full pl-12 pr-4 py-3.5 bg-white border border-slate-200 rounded-xl text-slate-900 font-bold placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all"
          />
        </div>
        <button 
          type="submit" 
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-xl text-sm font-bold shadow-sm transition-colors disabled:opacity-50 flex items-center gap-2"
          disabled={loading}
        >
          {loading ? (
            <><div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" /> Analyzing</>
          ) : (
            <><TrendingUp size={18} /> Analyze</>
          )}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-center gap-3 text-red-600 font-bold text-sm shadow-sm max-w-3xl">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      {stockData && (
        <div className="flex flex-col gap-6 animate-slide-in">
          {/* Header */}
          <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-3xl font-black text-slate-900">
                  {fund.symbol?.replace(".NS", "")}
                </h2>
                <p className="text-sm font-medium text-slate-500 mt-1 flex items-center gap-2">
                  <Building2 size={16} /> {fund.company_name} &bull; {fund.sector} &bull; {fund.industry}
                </p>
                <div className="flex items-center gap-4 mt-6">
                  <span className="text-4xl font-black font-mono text-emerald-600">
                    ₹{tech.current_price?.toFixed(2) ?? fund.current_price?.toFixed(2) ?? "-"}
                  </span>
                  {tech.rsi && (
                    <span className={`px-3 py-1.5 rounded-lg text-sm font-bold border ${
                      tech.rsi < 30 ? "bg-emerald-50 text-emerald-700 border-emerald-200" : 
                      tech.rsi > 70 ? "bg-red-50 text-red-700 border-red-200" : 
                      "bg-blue-50 text-blue-700 border-blue-200"
                    }`}>
                      RSI: {tech.rsi?.toFixed(1)}
                    </span>
                  )}
                  {fund.fundamentals_passed !== undefined && (
                    <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold border ${
                      fund.fundamentals_passed 
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200" 
                        : "bg-red-50 text-red-700 border-red-200"
                    }`}>
                      {fund.fundamentals_passed ? <CheckCircle2 size={16} /> : <XCircle size={16} />} 
                      {fund.fundamentals_passed ? "Fundamental Pass" : "Fundamental Fail"}
                    </span>
                  )}
                </div>
              </div>
              {fund.market_cap && (
                <div className="text-right p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Market Cap</div>
                  <div className="text-xl font-bold font-mono text-slate-700">
                    ₹{(fund.market_cap / 1e9).toFixed(0)}B
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Fundamentals */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 mb-6">
                <Building2 size={16} /> Fundamentals
              </div>
              <div className="space-y-1">
                <IndicatorRow label="ROCE" value={fund.roce} unit="%" good={fund.roce >= 15} />
                <IndicatorRow label="ROE" value={fund.roe} unit="%" good={fund.roe >= 15} />
                <IndicatorRow label="D/E Ratio" value={fund.debt_to_equity} good={fund.debt_to_equity <= 1} />
                <IndicatorRow label="P/E Ratio" value={fund.pe_ratio} />
                <IndicatorRow label="P/B Ratio" value={fund.pb_ratio} />
                <IndicatorRow label="Piotroski F" value={fund.piotroski_f_score} unit="/9" good={(fund.piotroski_f_score ?? 0) >= 7} />
                <IndicatorRow label="Altman Z" value={fund.altman_z_score} good={(fund.altman_z_score ?? 0) > 2.99} />
                <IndicatorRow label="EPS Growth" value={fund.eps_growth_yoy} unit="%" good={(fund.eps_growth_yoy ?? 0) >= 15} />
              </div>
            </div>

            {/* Technical */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 mb-6">
                <TrendingUp size={16} /> Technical Indicators
              </div>
              <div className="space-y-1">
                <IndicatorRow label="RSI (14)" value={tech.rsi} good={tech.rsi < 30} />
                <IndicatorRow label="200 EMA" value={tech.ema_200?.toFixed(2)} />
                <IndicatorRow label="50 EMA" value={tech.ema_50?.toFixed(2)} />
                <IndicatorRow label="ATR (14)" value={tech.atr?.toFixed(2)} />
                <IndicatorRow label="ADX" value={tech.adx?.toFixed(1)} good={(tech.adx ?? 0) >= 25} />
                <IndicatorRow label="MACD" value={tech.macd?.toFixed(3)} good={(tech.macd ?? 0) > 0} />
                <IndicatorRow label="BB Width" value={tech.bb_width?.toFixed(3)} />
                <IndicatorRow label="Volume Ratio" value={tech.volume_ratio?.toFixed(2)} good={(tech.volume_ratio ?? 0) >= 1} />
              </div>
            </div>

            {/* Trade Setup */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 mb-6">
                <TrendingDown size={16} /> Trade Setup
              </div>
              <div className="space-y-1 mb-8">
                {[
                  { label: "52W High", value: tech.week_52_high?.toFixed(2), prefix: "₹", color: "text-slate-900 font-bold" },
                  { label: "52W Low", value: tech.week_52_low?.toFixed(2), prefix: "₹", color: "text-slate-900 font-bold" },
                  { label: "From 52W High", value: tech.pct_from_52w_high?.toFixed(1), suffix: "%", color: "text-red-600 font-bold" },
                  { label: "ATR Stop Loss", value: tech.atr_stop_loss?.toFixed(2), prefix: "₹", color: "text-red-600 font-bold" },
                  { label: "Fixed SL (5%)", value: tech.fixed_stop_loss?.toFixed(2), prefix: "₹", color: "text-red-600 font-bold" },
                  { label: "Target (12%)", value: tech.target_price?.toFixed(2), prefix: "₹", color: "text-emerald-600 font-bold" },
                  { label: "R:R Ratio", value: tech.risk_reward_ratio?.toFixed(2), color: "text-amber-600 font-bold" },
                ].map((item) => (
                  <div key={item.label} className="flex justify-between items-center py-2.5 border-b border-slate-100 last:border-0">
                    <span className="text-sm font-medium text-slate-500">
                      {item.label}
                    </span>
                    <span className={`font-mono text-sm ${item.color}`}>
                      {item.value != null ? `${item.prefix ?? ""}${item.value}${item.suffix ?? ""}` : "-"}
                    </span>
                  </div>
                ))}
              </div>

              {/* Screener Filters */}
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Screener Filters</div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "ROCE>15%", pass: tech.passed_roce ?? fund.passed_roce },
                    { label: "D/E<1.0", pass: fund.passed_debt_to_equity },
                    { label: ">200 EMA", pass: tech.passed_ema_200 },
                    { label: "RSI<30", pass: tech.passed_rsi_oversold },
                  ].map((f) => (
                    <div
                      key={f.label}
                      className={`flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-bold border ${
                        f.pass 
                          ? "bg-emerald-50 text-emerald-700 border-emerald-100" 
                          : "bg-red-50 text-red-700 border-red-100"
                      }`}
                    >
                      {f.pass ? <CheckCircle2 size={14} /> : <XCircle size={14} />} {f.label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ========================================= */}
          {/* CASH MARKET MASTER ENGINE (PRO SECTION)   */}
          {/* ========================================= */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg text-white mt-4 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
               <Crosshair size={120} />
            </div>
            
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-blue-400 mb-6">
              <Target size={16} /> Institutional Master Engine (Pro)
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative z-10">
              
              {/* Pivot Matrix */}
              <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700 shadow-inner">
                <h3 className="text-sm font-bold text-slate-300 mb-4 border-b border-slate-700 pb-2">Advanced Pivot Matrix</h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-red-400 font-bold">R2 (Extreme Resistance)</span>
                    <span className="font-mono text-white font-bold">₹{tech.r2?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-orange-400 font-bold">R1 (First Resistance)</span>
                    <span className="font-mono text-white font-bold">₹{tech.r1?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm bg-blue-900/40 p-2 rounded border border-blue-800/50">
                    <span className="text-blue-300 font-black tracking-wide">MASTER PIVOT</span>
                    <span className="font-mono text-white font-black">₹{tech.pivot?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-emerald-400 font-bold">S1 (First Support)</span>
                    <span className="font-mono text-white font-bold">₹{tech.s1?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-emerald-600 font-bold">S2 (Extreme Support)</span>
                    <span className="font-mono text-white font-bold">₹{tech.s2?.toFixed(2) || "-"}</span>
                  </div>
                </div>
              </div>

              {/* Fibonacci Demand Zones */}
              <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700 shadow-inner">
                <h3 className="text-sm font-bold text-slate-300 mb-4 border-b border-slate-700 pb-2 flex justify-between">
                  <span>Fibonacci Demand & Supply</span>
                  {tech.fib_confluence && (
                    <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded animate-pulse border border-emerald-500/30">
                      Near {tech.fib_nearest_level}% Level
                    </span>
                  )}
                </h3>
                
                <div className="space-y-3">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-slate-400">Swing High (0%)</span>
                    <span className="font-mono text-slate-300">₹{tech.fib_swing_high?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-slate-400">Minor Retracement (38.2%)</span>
                    <span className="font-mono text-slate-300">₹{tech.fib_level_382?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-slate-400">Halfway (50.0%)</span>
                    <span className="font-mono text-slate-300">₹{tech.fib_level_500?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm bg-emerald-900/40 p-2 rounded border border-emerald-800/50 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                    <span className="text-emerald-400 font-black">GOLDEN RATIO (61.8%)</span>
                    <span className="font-mono text-emerald-300 font-black tracking-wide">₹{tech.fib_level_618?.toFixed(2) || "-"}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-slate-400">Swing Low (100%)</span>
                    <span className="font-mono text-slate-300">₹{tech.fib_swing_low?.toFixed(2) || "-"}</span>
                  </div>
                </div>
                <div className="mt-4 text-[10px] text-slate-500">
                  * 61.8% Golden Ratio acts as the strongest Institutional Demand Zone.
                </div>
              </div>

            </div>

            <div className="mt-8 bg-slate-800/50 rounded-xl p-5 border border-slate-700 shadow-inner relative z-10">
              <div className="flex justify-between items-center mb-6 border-b border-slate-700 pb-4">
                <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                  <ActivitySquare className="text-indigo-400" size={18} /> Kronos AI • Forecast
                </h3>
                <div className="flex items-center gap-3">
                  <select 
                    value={predictionDays} 
                    onChange={(e) => setPredictionDays(Number(e.target.value))}
                    className="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded px-2 py-2 outline-none"
                    disabled={isPredicting}
                  >
                    <option value={5}>5 Days</option>
                    <option value={10}>10 Days</option>
                    <option value={15}>15 Days</option>
                  </select>
                  <button
                    onClick={handlePredict}
                    disabled={isPredicting}
                    className={`px-4 py-2 rounded font-bold text-xs shadow transition-all flex items-center justify-center gap-2 ${
                      isPredicting ? 'bg-indigo-900/50 text-indigo-400 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    }`}
                  >
                    {isPredicting ? <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" /> : null}
                    {isPredicting ? 'Forecasting...' : 'Run Forecast'}
                  </button>
                </div>
              </div>

              {predictionData ? (
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={predictionData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                      <XAxis dataKey="date" stroke="#94a3b8" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                      <YAxis stroke="#94a3b8" tick={{fontSize: 10}} domain={['auto', 'auto']} tickFormatter={(val) => `₹${val}`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#f8fafc' }}
                      />
                      <Legend wrapperStyle={{fontSize: '12px'}} />
                      <Line type="monotone" dataKey="historical_close" name="Historical LTP" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="predicted_close" name={`AI Forecast (${predictionDays} Days)`} stroke="#10b981" strokeWidth={3} strokeDasharray="5 5" dot={{ r: 4, fill: '#10b981', strokeWidth: 0 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-slate-500 bg-slate-900/20 rounded-xl border border-slate-700/30 border-dashed">
                  <ActivitySquare size={32} className="mb-2 opacity-50" />
                  <p className="text-xs font-medium">Click "Run Forecast" to predict the {predictionDays}-day trajectory for {query}</p>
                </div>
              )}
            </div>
            
          </div>
        </div>
      )}

      {!stockData && !loading && !error && (
        <div className="bg-white border border-slate-200 rounded-xl p-16 flex flex-col items-center justify-center text-center shadow-sm max-w-3xl">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-6">
            <Search className="text-slate-300" size={32} />
          </div>
          <p className="text-2xl font-bold text-slate-900 mb-2">
            Search any NSE stock
          </p>
          <p className="text-sm font-medium text-slate-500 max-w-md mb-8">
            Get complete fundamental + technical analysis instantly. 
            View technical indicators, Piostroski score, and trade setup targets.
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            {["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"].map((sym) => (
              <button
                key={sym}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-lg transition-colors border border-slate-200"
                onClick={() => {
                  setQuery(sym);
                  stocksApi.getSnapshot(sym).then((r) => setStockData(r.data)).catch((e: any) => setError(e.message));
                }}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
