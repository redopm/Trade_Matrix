"use client";

import React, { useState, useEffect } from "react";
import { fetchOptionChain } from "@/lib/api";
import { AlertCircle, Target, ShieldAlert, ArrowRight, Activity, Zap, Shield, HelpCircle, Layers, Plus } from "lucide-react";

export default function StrategyBuilder() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("safe");
  
  // Custom Combo State
  const [customLegs, setCustomLegs] = useState<any[]>([]);
  const [selectedStrike, setSelectedStrike] = useState("");
  const [selectedType, setSelectedType] = useState("CE");
  const [selectedAction, setSelectedAction] = useState("BUY");

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
            <h3 className="font-bold text-red-900">Failed to load Strategy Data</h3>
            <p className="text-sm text-red-700 mt-1">{data.error}</p>
          </div>
        </div>
      </div>
    );
  }

  const { advanced_hedges, analysis, quotes, buyer_strategy, seller_strategy } = data;
  const sentiment = analysis?.sentiment || "NEUTRAL";
  
  const auto_pilot = advanced_hedges?.auto_pilot;
  
  // Resolve which hedge to show based on the active tab
  let current_hedge = null;
  if (advanced_hedges) {
    if (activeTab === "auto_pilot" && auto_pilot) {
      current_hedge = advanced_hedges[auto_pilot.recommended_key];
    } else {
      current_hedge = advanced_hedges[activeTab];
    }
  }
  const allStrikes = Array.from(new Set(quotes.map((q: any) => q.strike))).sort((a: any, b: any) => a - b) as number[];

  const getSentimentColor = (s: string) => {
    if (s.includes("BULL")) return "text-emerald-600 bg-emerald-50 border-emerald-200";
    if (s.includes("BEAR")) return "text-red-600 bg-red-50 border-red-200";
    return "text-slate-600 bg-slate-50 border-slate-200";
  };

  const handleAddCustomLeg = () => {
    if (!selectedStrike) return;
    const strikeNum = parseFloat(selectedStrike);
    const quote = quotes.find((q: any) => q.strike === strikeNum && q.type === selectedType);
    if (quote) {
      setCustomLegs([...customLegs, {
        action: selectedAction,
        type: selectedType,
        strike: strikeNum,
        entry: quote.ltp,
        qty: 1
      }]);
    }
  };

  const calculateCustomMetrics = () => {
    let netPremium = 0;
    customLegs.forEach(leg => {
      if (leg.action === 'BUY') netPremium += leg.entry;
      else netPremium -= leg.entry;
    });
    return { netPremium: netPremium.toFixed(2) };
  };

  const customMetrics = calculateCustomMetrics();

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      {/* HEADER */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Layers size={24} className="text-blue-600" /> Strategy Builder
            </h1>
            <p className="text-sm text-slate-500 mt-1">Pre-built Hedging Algorithms & Custom Combo</p>
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
              sentiment.includes('BULL') ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
              sentiment.includes('BEAR') ? "text-red-600 bg-red-50 border-red-200" :
              "text-slate-600 bg-slate-50 border-slate-200"
            }`}>
              AI Sentiment: {sentiment}
            </div>
          </div>
        </div>
        
        {/* HEDGE TABS */}
        <div className="px-6 flex items-center gap-2 overflow-x-auto border-t border-slate-100 py-3">
          <button 
            onClick={() => setActiveTab('safe')}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${activeTab === 'safe' ? 'bg-blue-600 text-white shadow-md' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
          >
            Safe Hedge
          </button>
          <button 
            onClick={() => setActiveTab('pro')}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${activeTab === 'pro' ? 'bg-purple-600 text-white shadow-md' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
          >
            High Profit (Pro)
          </button>
          <button 
            onClick={() => setActiveTab('zero_loss')}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${activeTab === 'zero_loss' ? 'bg-emerald-600 text-white shadow-md' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
          >
            Zero Loss (Arbitrage)
          </button>
          <button 
            onClick={() => setActiveTab('sideways')}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${activeTab === 'sideways' ? 'bg-orange-500 text-white shadow-md' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
          >
            Sideways (Iron Condor)
          </button>
          <button 
            onClick={() => setActiveTab('breakout')}
            className={`px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${activeTab === 'breakout' ? 'bg-rose-600 text-white shadow-md' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
          >
            Breakout (Straddle)
          </button>
        </div>
      </div>

      <div className="p-6 max-w-6xl mx-auto space-y-6">
        
        {/* AI HEDGING STRATEGY CARD */}
        {current_hedge && (
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden">
            <div className={`px-6 py-4 flex justify-between items-center ${
              activeTab === 'safe' ? 'bg-gradient-to-r from-blue-600 to-indigo-700' :
              activeTab === 'pro' ? 'bg-gradient-to-r from-purple-600 to-fuchsia-700' :
              activeTab === 'zero_loss' ? 'bg-gradient-to-r from-emerald-600 to-teal-700' :
              'bg-gradient-to-r from-orange-500 to-amber-600'
            }`}>
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Shield size={20} /> AI Strategy: {current_hedge.name}
                </h2>
                <p className="text-white/80 text-sm mt-1">{current_hedge.reason}</p>
              </div>
              <div className="bg-white/20 px-4 py-2 rounded-lg border border-white/30 backdrop-blur-sm text-white">
                <div className="text-xs font-semibold opacity-80 uppercase tracking-wider">Margin Req.</div>
                <div className="text-lg font-bold">{current_hedge.margin_required}</div>
              </div>
            </div>
            
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Legs List */}
                <div className="space-y-3">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Strategy Legs</div>
                  {current_hedge.legs.map((leg: any, idx: number) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${leg.action === 'BUY' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                          {leg.action} {leg.qty && `${leg.qty}x`}
                        </span>
                        <span className="font-bold text-slate-800">{leg.strike} {leg.type}</span>
                      </div>
                      <div className="font-medium text-slate-600">
                        ₹{leg.entry.toFixed(2)}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50">
                    <div className="text-xs font-bold text-emerald-600 uppercase mb-1">Max Profit</div>
                    <div className="text-xl font-black text-emerald-700">
                      {typeof current_hedge.max_profit === 'number' ? `₹${(current_hedge.max_profit * 50).toFixed(0)}` : current_hedge.max_profit}
                    </div>
                    {typeof current_hedge.max_profit === 'number' && <div className="text-xs text-emerald-600 mt-1">({current_hedge.max_profit} pts)</div>}
                  </div>
                  <div className="p-4 rounded-xl border border-red-200 bg-red-50">
                    <div className="text-xs font-bold text-red-600 uppercase mb-1">Max Loss</div>
                    <div className="text-xl font-black text-red-700">
                      {typeof current_hedge.max_loss === 'number' ? `₹${(current_hedge.max_loss * 50).toFixed(0)}` : current_hedge.max_loss}
                    </div>
                    {typeof current_hedge.max_loss === 'number' && <div className="text-xs text-red-600 mt-1">({current_hedge.max_loss} pts)</div>}
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <div className="text-xs font-bold text-slate-500 uppercase mb-1">Net Premium</div>
                    <div className="text-lg font-bold text-slate-800">
                      {current_hedge.net_premium > 0 ? `Pay ₹${current_hedge.net_premium}` : `Receive ₹${Math.abs(current_hedge.net_premium)}`}
                    </div>
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <div className="text-xs font-bold text-slate-500 uppercase mb-1">Risk : Reward</div>
                    <div className="text-lg font-bold text-slate-800">{current_hedge.risk_reward}</div>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-slate-100 flex justify-end">
                <button className={`px-6 py-2.5 text-white font-bold rounded-lg transition-colors flex items-center gap-2 shadow-sm ${
                  activeTab === 'safe' ? 'bg-blue-600 hover:bg-blue-700' :
                  activeTab === 'pro' ? 'bg-purple-600 hover:bg-purple-700' :
                  activeTab === 'zero_loss' ? 'bg-emerald-600 hover:bg-emerald-700' :
                  'bg-orange-500 hover:bg-orange-600'
                }`}>
                  Execute Hedge <ArrowRight size={16} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* CUSTOM COMBO BUILDER */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mt-8">
          <div className="p-5 border-b border-slate-100 bg-slate-50">
            <h3 className="font-bold text-slate-900 text-lg">Build Custom Combination</h3>
            <p className="text-sm text-slate-500">Add multiple legs to calculate custom net premium</p>
          </div>
          
          <div className="p-6">
            <div className="flex flex-wrap items-end gap-4 mb-6">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Action</label>
                <select 
                  className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                  value={selectedAction} onChange={(e) => setSelectedAction(e.target.value)}
                >
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Strike</label>
                <select 
                  className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                  value={selectedStrike} onChange={(e) => setSelectedStrike(e.target.value)}
                >
                  <option value="">-- Select Strike --</option>
                  {allStrikes.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Type</label>
                <select 
                  className="bg-white border border-slate-300 rounded px-3 py-2 text-sm font-medium"
                  value={selectedType} onChange={(e) => setSelectedType(e.target.value)}
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
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {customLegs.map((leg, i) => (
                      <tr key={i}>
                        <td className="px-4 py-3 font-bold">
                          <span className={leg.action === 'BUY' ? 'text-blue-600' : 'text-red-600'}>{leg.action}</span>
                        </td>
                        <td className="px-4 py-3 font-bold text-slate-800">{leg.strike} {leg.type}</td>
                        <td className="px-4 py-3 text-slate-600">₹{leg.entry.toFixed(2)}</td>
                        <td className="px-4 py-3 text-right">
                          <button 
                            onClick={() => setCustomLegs(customLegs.filter((_, idx) => idx !== i))}
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
                      <td colSpan={2} className="px-4 py-3 font-bold text-slate-800 text-right">Net Premium:</td>
                      <td colSpan={2} className="px-4 py-3 font-black text-lg text-slate-900">
                        {parseFloat(customMetrics.netPremium) > 0 ? `Pay ₹${customMetrics.netPremium}` : `Receive ₹${Math.abs(parseFloat(customMetrics.netPremium))}`}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* DYNAMIC LEG EXPLANATION CARDS */}
        {current_hedge && current_hedge.legs && current_hedge.legs.length > 0 && (
          <div className="mt-8">
            <h3 className="font-bold text-slate-900 text-lg mb-4 px-1">Strategy Execution Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {current_hedge.legs.map((leg: any, idx: number) => {
                const isBuy = leg.action === 'BUY';
                const target = isBuy ? (leg.entry * 1.5).toFixed(2) : '0.05';
                const sl = isBuy ? (leg.entry * 0.5).toFixed(2) : (leg.entry * 2.0).toFixed(2);
                
                return (
                  <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
                    <div className={`p-4 border-b flex items-center gap-3 ${isBuy ? 'bg-blue-50/50 border-blue-100' : 'bg-red-50/50 border-red-100'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isBuy ? 'bg-blue-100 text-blue-600' : 'bg-red-100 text-red-600'}`}>
                        {isBuy ? <Zap size={16} /> : <Activity size={16} />}
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-900">Leg {idx + 1}: {isBuy ? 'Option Buyer' : 'Option Seller'}</h3>
                        <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">{current_hedge.name}</p>
                      </div>
                    </div>
                    <div className="p-5 flex-1">
                      <div className="flex items-end gap-3 mb-4">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${isBuy ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'}`}>
                          {leg.action} {leg.qty && `${leg.qty}x`}
                        </span>
                        <span className="text-xl font-black tracking-tight text-slate-800">
                          {leg.strike} {leg.type}
                        </span>
                        <span className="text-slate-500 mb-0.5 font-medium">@ ₹{leg.entry.toFixed(2)}</span>
                      </div>
                      
                      <div className="space-y-2.5">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-500 flex items-center gap-2"><Target size={14}/> Target</span>
                          <span className="font-bold text-emerald-600">₹{target}</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-500 flex items-center gap-2"><ShieldAlert size={14}/> Stop Loss</span>
                          <span className="font-bold text-red-600">₹{sl}</span>
                        </div>
                        <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-100">
                          <span className="text-slate-500 flex items-center gap-2" title="Lower Support (S2) & Upper Support (S1)"><HelpCircle size={14}/> Support (S2 - S1)</span>
                          <span className="font-bold text-emerald-700">
                            {data.reversals ? `${data.reversals.S2} - ${data.reversals.S1}` : (analysis?.highest_put_oi_strike || "N/A")}
                            {data.reversals?.concrete_wall_support && ' 🔥'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-500 flex items-center gap-2" title="Lower Resistance (R1) & Upper Resistance (R2)"><HelpCircle size={14}/> Resistance (R1 - R2)</span>
                          <span className="font-bold text-red-700">
                            {data.reversals ? `${data.reversals.R1} - ${data.reversals.R2}` : (analysis?.highest_call_oi_strike || "N/A")}
                            {data.reversals?.concrete_wall_resistance && ' 🔥'}
                          </span>
                        </div>
                        {data.reversals && data.reversals.zero_gamma > 0 && (
                          <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-slate-500">⚡ Master Pivot (Zero Gamma)</span>
                              <span className="font-semibold text-purple-600">{data.reversals.zero_gamma}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-slate-500">📊 Volume POC</span>
                              <span className="font-semibold text-blue-600">{data.reversals.volume_poc}</span>
                            </div>
                            {data.reversals.max_pain > 0 && (
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-500">🧲 Max Pain (Magnet)</span>
                                <span className="font-semibold text-indigo-600">{data.reversals.max_pain}</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-50 border-t border-slate-100">
                      <button className={`w-full py-2 text-white text-sm font-bold rounded-lg transition-colors shadow-sm ${isBuy ? 'bg-blue-600 hover:bg-blue-700' : 'bg-rose-600 hover:bg-rose-700'}`}>
                        Execute Leg {idx + 1}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}


      </div>
    </div>
  );
}

