"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { fetchOptionChain, tradesApi, predictKronos } from "@/lib/api";

export default function FnoDashboard() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [atmStrike, setAtmStrike] = useState<number | "">("");  // Empty = fetch all (no filter)
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [strikeRadius, setStrikeRadius] = useState(12); // Default to ±12 strikes
  const [selectedTrade, setSelectedTrade] = useState<{role: 'BUYER'|'SELLER', strategy: any} | null>(null);
  const [isTrading, setIsTrading] = useState(false);
  const [kronosPrediction, setKronosPrediction] = useState<any>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionDays, setPredictionDays] = useState(5);
  const [marketStatus, setMarketStatus] = useState<{isOpen: boolean, message: string} | null>(null);

  const [debouncedAtmStrike, setDebouncedAtmStrike] = useState<number | string>("");

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedAtmStrike(atmStrike);
    }, 500);
    return () => clearTimeout(handler);
  }, [atmStrike]);

  useEffect(() => {
    const checkMarket = () => {
      const now = new Date();
      const day = now.getDay();
      const timeInMinutes = now.getHours() * 60 + now.getMinutes();
      const isOpen = day >= 1 && day <= 5 && timeInMinutes >= 555 && timeInMinutes <= 930;
      
      let message = "Closed";
      if (isOpen) {
        const remaining = 930 - timeInMinutes;
        const hrs = Math.floor(remaining / 60);
        const mins = remaining % 60;
        message = `Closes in ${hrs}h ${mins}m`;
      } else if (day >= 1 && day <= 5 && timeInMinutes < 555) {
        const remaining = 555 - timeInMinutes;
        const hrs = Math.floor(remaining / 60);
        const mins = remaining % 60;
        message = `Opens in ${hrs}h ${mins}m`;
      }
      setMarketStatus({ isOpen, message });
    };
    
    checkMarket();
    const interval = setInterval(checkMarket, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    loadData(true);
    
    // Auto-refresh every 60 seconds ONLY if market is open to prevent Fyers API rate limits
    const interval = setInterval(() => {
      const now = new Date();
      const day = now.getDay();
      const timeInMinutes = now.getHours() * 60 + now.getMinutes();
      
      // Market is open Mon-Fri (1-5), 9:15 AM (555) to 3:30 PM (930)
      const isMarketOpen = day >= 1 && day <= 5 && timeInMinutes >= 555 && timeInMinutes <= 930;
      
      if (isMarketOpen) {
        loadData(false);
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [symbol, debouncedAtmStrike]);

  const loadData = async (showLoader = true) => {
    if (showLoader) setLoading(true);
    else setIsRefreshing(true);
    try {
      const atm = typeof atmStrike === "number" ? atmStrike : undefined;
      const res = await fetchOptionChain(symbol, atm);
      setData(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
    setIsRefreshing(false);
  };

  const getSentimentColor = (sentiment: string) => {
    if (sentiment?.includes("BULLISH") || sentiment?.includes("OVERSOLD")) return "text-green-400";
    if (sentiment?.includes("BEARISH") || sentiment?.includes("OVERBOUGHT")) return "text-red-400";
    return "text-gray-400";
  };

  const handlePlaceTrade = async (role: 'BUYER' | 'SELLER', strategy: any) => {
    setIsTrading(true);
    try {
      const q = data?.quotes?.find((x:any) => x.strike === strategy.strike && x.type === strategy.type);
      if(!q || !q.symbol) throw new Error("Could not find symbol for this strike");
      
      const req = {
         symbol: q.symbol,
         company_name: `${symbol} ${strategy.strike} ${strategy.type}`,
         direction: role === 'BUYER' ? "LONG" : "SHORT",
         entry_price: q.ltp,
         quantity: 50, // default lot size
         notes: `Traded from Option Chain as ${role}`
      };
      await tradesApi.createCustomTrade(req);
      alert(`Successfully placed Paper Trade for ${q.symbol}!`);
      setSelectedTrade(null);
    } catch (e: any) {
      alert("Error placing trade: " + (e.message || "Unknown error"));
    }
    setIsTrading(false);
  };

  // Group quotes by strike
  const allStrikes = Array.from(new Set(data?.quotes?.map((q: any) => q.strike) || [])).sort((a: any, b: any) => a - b) as number[];
  
  // Always use the backend's calculated ATM strike to center the table, falling back to the local input state.
  const centerStrike = data?.atm_strike || (typeof atmStrike === "number" ? atmStrike : null);
  
  // Only show centerStrike ± strikeRadius strikes
  let displayStrikes = allStrikes;
  if (centerStrike && allStrikes.includes(centerStrike)) {
    const atmIndex = allStrikes.indexOf(centerStrike);
    const start = Math.max(0, atmIndex - strikeRadius);
    const end = Math.min(allStrikes.length, atmIndex + strikeRadius + 1);
    displayStrikes = allStrikes.slice(start, end);
  }

  return (
    <div className="p-8 max-w-7xl mx-auto text-gray-100 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
            F&O Options Engine
          </h1>
          {data?.timestamp && (
            <p className="text-xs text-gray-400 mt-1">Live Data: {new Date(data.timestamp).toLocaleTimeString()}</p>
          )}
        </div>
        <div className="flex gap-4">
          <select 
            className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2"
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value);
              setAtmStrike(""); // Reset ATM when symbol changes
            }}
          >
            <option value="NIFTY">NIFTY 50</option>
            <option value="BANKNIFTY">BANK NIFTY</option>
            <option value="FINNIFTY">FINNIFTY</option>
            <option value="MIDCPNIFTY">MIDCPNIFTY</option>
          </select>

          <input 
            type="number" 
            className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 w-32"
            value={atmStrike}
            onChange={(e) => setAtmStrike(Number(e.target.value))}
            placeholder="ATM Strike"
          />
          <div className="flex items-center gap-2">
            {(() => {
              const now = new Date();
              const day = now.getDay();
              const timeInMinutes = now.getHours() * 60 + now.getMinutes();
              const isMarketOpen = day >= 1 && day <= 5 && timeInMinutes >= 555 && timeInMinutes <= 930;
              
              if (!isMarketOpen) {
                return (
                  <span className="text-xs text-red-400 bg-red-900/30 px-2 py-1 rounded border border-red-800 flex items-center gap-1 font-semibold">
                    <div className="w-1.5 h-1.5 bg-red-400 rounded-full"></div> Market Closed
                  </span>
                );
              }
              if (isRefreshing) {
                return (
                  <span className="text-xs text-blue-400 animate-pulse flex items-center gap-1 font-semibold">
                    <div className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div> Live Syncing...
                  </span>
                );
              }
              return null;
            })()}
            <button onClick={() => loadData(true)} className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors ml-2">
              Refresh
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      ) : data?.error ? (
        <div className="bg-red-900/50 text-red-200 p-4 rounded-lg">{data.error}</div>
      ) : (
        <div className="space-y-8">
          {/* Top Analytics Cards */}
          <div className="grid grid-cols-4 gap-6">
            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg flex flex-col justify-between">
              <div>
                <div className="text-gray-400 text-sm mb-1 font-semibold flex items-center gap-2">📊 PCR & Trend</div>
                <div className={`text-3xl font-bold ${data?.analysis?.pcr > 1 ? 'text-green-400' : 'text-red-400'}`}>
                  {data?.analysis?.pcr}
                </div>
              </div>
              <div className="text-xs text-gray-400 mt-2 bg-gray-900/50 p-2 rounded">
                PCR &gt; 1 indicates Bullishness. High PCR means strong put writing (support).
              </div>
            </div>
            
            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg flex flex-col justify-between">
              <div>
                <div className="text-gray-400 text-sm mb-1 font-semibold flex items-center gap-2">⚡ IV (ATM Volatility)</div>
                <div className="text-2xl font-bold text-amber-400">
                  {data?.quotes && data.quotes.length > 0 ? (data.quotes.find((q:any)=> q.strike === data.atm_strike && q.type === 'CE')?.iv || 'N/A') : '-'}
                </div>
              </div>
              <div className="text-xs text-gray-400 mt-2 bg-gray-900/50 p-2 rounded">
                High IV = Expensive Premiums (Favors Sellers).<br/>Low IV = Cheap Premiums (Favors Buyers).
              </div>
            </div>

            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg flex flex-col justify-between">
              <div>
                <div className="text-gray-400 text-sm mb-1 font-semibold flex items-center gap-2">🛡️ OI Dynamics</div>
                <div className="text-xl font-bold">
                  <span className="text-green-400">{data?.analysis?.highest_put_oi_strike || 'N/A'}</span>
                  <span className="text-gray-500 mx-2">/</span>
                  <span className="text-red-400">{data?.analysis?.highest_call_oi_strike || 'N/A'}</span>
                </div>
              </div>
              <div className="text-xs text-gray-400 mt-2 bg-gray-900/50 p-2 rounded">
                Strongest Support (PE) vs Strongest Resistance (CE).
              </div>
            </div>

            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg flex flex-col justify-between">
              <div>
                <div className="text-gray-400 text-sm mb-1 font-semibold flex items-center gap-2">🧠 AI Sentiment</div>
                <div className={`text-2xl font-bold ${getSentimentColor(data?.analysis?.sentiment)}`}>
                  {data?.analysis?.sentiment}
                </div>
              </div>
              <div className="text-xs text-gray-400 mt-2 bg-gray-900/50 p-2 rounded">
                Calculated by AI based on Options buildup, PCR, and momentum.
              </div>
            </div>
          </div>

          {/* Option Chain Table (Fyers Style) */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-2xl">
            <div className="bg-gray-900 px-4 py-3 border-b border-gray-700 flex justify-between">
              <div className="font-semibold text-green-400">CALLS</div>
              <div className="font-semibold text-blue-300">Days to Expiry: {data?.dte}</div>
              <div className="font-semibold text-red-400">PUTS</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-center">
                <thead className="bg-gray-800 text-gray-400 sticky top-0 shadow-md z-10">
                  <tr>
                    {/* Calls */}
                    <th className="py-3 px-2 border-r border-gray-700/50">Vega</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">Theta</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">Gamma</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">Delta</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">IV</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">Vol</th>
                    <th className="py-3 px-2 border-r border-gray-700/50">OI</th>
                    <th className="py-3 px-2 font-bold text-white border-r border-gray-700/50">LTP</th>
                    
                    {/* Center Strike */}
                    <th className="py-3 px-4 bg-gray-900 font-bold text-gray-200 border-x border-gray-700/50">
                      <div className="flex items-center justify-center gap-2">
                        STRIKE
                        <button 
                          onClick={() => setStrikeRadius(r => r + 1)}
                          className="px-2 py-0.5 rounded-full bg-gray-800 hover:bg-gray-700 text-blue-400 hover:text-white transition-colors border border-gray-700 text-xs shadow-sm"
                          title="Show more strikes"
                        >
                          ↕
                        </button>
                      </div>
                    </th>
                    
                    {/* Puts */}
                    <th className="py-3 px-2 font-bold text-white border-l border-gray-700/50">LTP</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">OI</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">Vol</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">IV</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">Delta</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">Gamma</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">Theta</th>
                    <th className="py-3 px-2 border-l border-gray-700/50">Vega</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700/50">
                  {displayStrikes.map((strike, index) => {
                    const ce = data?.quotes?.find((q: any) => q.strike === strike && q.type === 'CE') || {};
                    const pe = data?.quotes?.find((q: any) => q.strike === strike && q.type === 'PE') || {};
                    const isATM = centerStrike !== null && strike === centerStrike;
                    const isCeItm = centerStrike !== null && strike < centerStrike;
                    const isPeItm = centerStrike !== null && strike > centerStrike;
                    
                    const buyerStrategy = data?.buyer_strategy;
                    const sellerStrategy = data?.seller_strategy;
                    
                    const isCeBuy = buyerStrategy?.strike === strike && buyerStrategy?.type === 'CE' && buyerStrategy?.action === 'BUY';
                    const isCeSell = sellerStrategy?.strike === strike && sellerStrategy?.type === 'CE';
                    const isPeBuy = buyerStrategy?.strike === strike && buyerStrategy?.type === 'PE' && buyerStrategy?.action === 'BUY';
                    const isPeSell = sellerStrategy?.strike === strike && (sellerStrategy?.type === 'PE' || sellerStrategy?.type === 'CE+PE');

                    const showSpotPrice = data?.spot_price > 0 && strike > data.spot_price && (index === 0 || displayStrikes[index - 1] <= data.spot_price);

                    const getHighlightClass = (isBuy: boolean, isSell: boolean, baseColor: string) => {
                      if (isBuy) return `cursor-pointer ring-2 ring-yellow-400 bg-yellow-400/20 shadow-[0_0_15px_rgba(250,204,21,0.6)] animate-pulse relative hover:bg-yellow-400/40 ${baseColor}`;
                      if (isSell) return `cursor-pointer ring-2 ring-fuchsia-500 bg-fuchsia-500/20 shadow-[0_0_15px_rgba(217,70,239,0.5)] animate-pulse relative hover:bg-fuchsia-500/40 ${baseColor}`;
                      return baseColor;
                    };
                    
                    // ATM row styling
                    const rowBgClass = isATM 
                      ? "bg-slate-200 text-slate-900 shadow-[0_0_15px_rgba(255,255,255,0.2)] z-10 relative font-bold" 
                      : "hover:bg-gray-700/30 transition-colors";
                      
                    // Text colors for ATM vs Normal
                    const textColor = isATM ? "text-slate-800" : "text-gray-500";
                    const deltaColor = isATM ? "text-blue-700" : "text-blue-400";
                    const ltpCeColor = isATM ? "text-green-600 drop-shadow-sm" : "text-green-400";
                    const ltpPeColor = isATM ? "text-red-600 drop-shadow-sm" : "text-red-400";

                    // Max Highlights
                    const isCeMaxOi = data?.analysis?.highest_call_oi_strike === strike;
                    const isPeMaxOi = data?.analysis?.highest_put_oi_strike === strike;
                    const isCeMaxVol = Math.max(...(data?.quotes?.filter((q:any)=>q.type==='CE').map((q:any)=>q.volume)||[])) === ce.volume && ce.volume > 0;
                    const isPeMaxVol = Math.max(...(data?.quotes?.filter((q:any)=>q.type==='PE').map((q:any)=>q.volume)||[])) === pe.volume && pe.volume > 0;

                    // Strike PCR
                    const peVal = pe.oi && pe.oi !== 0 ? pe.oi : pe.volume;
                    const ceVal = ce.oi && ce.oi !== 0 ? ce.oi : ce.volume;
                    const strikePcrVal = (peVal || 0) / (ceVal || 1);
                    const strikePcr = strikePcrVal > 99 ? '∞' : strikePcrVal.toFixed(2);

                    return (
                      <React.Fragment key={strike}>
                        {showSpotPrice && (
                          <tr className="h-0 p-0 m-0">
                            <td colSpan={17} className="h-0 p-0 m-0 relative border-t-2 border-dashed border-blue-500">
                               <div className="absolute left-1/2 -translate-x-1/2 -top-2.5 bg-blue-600 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow z-20 flex items-center gap-1">
                                 <div className="w-1.5 h-1.5 bg-blue-300 rounded-full animate-pulse"></div>
                                 SPOT: {data.spot_price.toFixed(2)}
                               </div>
                            </td>
                          </tr>
                        )}
                        <tr className={rowBgClass}>
                        {/* Calls Side */}
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${textColor}`}>{ce.vega !== undefined && ce.vega !== null ? ce.vega : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${textColor}`}>{ce.theta !== undefined && ce.theta !== null ? ce.theta : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${textColor}`}>{ce.gamma !== undefined && ce.gamma !== null ? ce.gamma : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${deltaColor}`}>{ce.delta !== undefined && ce.delta !== null ? ce.delta : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${textColor}`}>{ce.iv !== undefined && ce.iv !== null ? ce.iv : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${isCeMaxVol ? 'bg-blue-500/20 text-blue-300 font-bold border border-blue-500/50' : textColor}`}>{ce.volume !== undefined && ce.volume !== null ? ce.volume : '-'}</td>
                        <td className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/15' : ''} ${isCeMaxOi ? 'bg-red-500/20 text-red-400 font-bold border border-red-500/50' : (isATM ? 'text-amber-700' : 'text-yellow-500/80')}`}>{ce.oi !== undefined && ce.oi !== null ? ce.oi : '-'}</td>
                        <td 
                          onClick={() => {
                            if (isCeBuy) setSelectedTrade({role: 'BUYER', strategy: buyerStrategy});
                            else if (isCeSell) setSelectedTrade({role: 'SELLER', strategy: sellerStrategy});
                          }}
                          className={`py-2 px-2 ${isCeItm && !isATM ? 'bg-amber-900/20' : ''} font-semibold ${getHighlightClass(isCeBuy, isCeSell, ltpCeColor)}`}
                        >
                          {isCeBuy && <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] bg-yellow-400 text-yellow-900 px-1 py-0.5 rounded font-bold whitespace-nowrap z-10 shadow">★ BEST BUY</span>}
                          {isCeSell && <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] bg-fuchsia-500 text-white px-1 py-0.5 rounded font-bold whitespace-nowrap z-10 shadow">★ BEST SELL</span>}
                          {ce.ltp?.toFixed(2) || '-'}
                        </td>
                        
                        {/* Center Strike */}
                        <td className={`py-1 px-4 font-bold ${isATM ? 'bg-white text-blue-600 text-lg border-y-2 border-slate-300' : 'bg-gray-900/50 text-gray-200'} leading-tight`}>
                          <div className="flex flex-col items-center justify-center">
                            <span>{strike}</span>
                            <span className={`text-[10px] font-medium ${isATM ? 'text-blue-400' : 'text-gray-500'}`}>PCR: {strikePcr}</span>
                          </div>
                        </td>
                        
                        {/* Puts Side */}
                        <td 
                          onClick={() => {
                            if (isPeBuy) setSelectedTrade({role: 'BUYER', strategy: buyerStrategy});
                            else if (isPeSell) setSelectedTrade({role: 'SELLER', strategy: sellerStrategy});
                          }}
                          className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/20' : ''} font-semibold ${getHighlightClass(isPeBuy, isPeSell, ltpPeColor)}`}
                        >
                          {isPeBuy && <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] bg-yellow-400 text-yellow-900 px-1 py-0.5 rounded font-bold whitespace-nowrap z-10 shadow">★ BEST BUY</span>}
                          {isPeSell && <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] bg-fuchsia-500 text-white px-1 py-0.5 rounded font-bold whitespace-nowrap z-10 shadow">★ BEST SELL</span>}
                          {pe.ltp?.toFixed(2) || '-'}
                        </td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${isPeMaxOi ? 'bg-red-500/20 text-red-400 font-bold border border-red-500/50' : (isATM ? 'text-amber-700' : 'text-yellow-500/80')}`}>{pe.oi !== undefined && pe.oi !== null ? pe.oi : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${isPeMaxVol ? 'bg-blue-500/20 text-blue-300 font-bold border border-blue-500/50' : textColor}`}>{pe.volume !== undefined && pe.volume !== null ? pe.volume : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${textColor}`}>{pe.iv !== undefined && pe.iv !== null ? pe.iv : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${deltaColor}`}>{pe.delta !== undefined && pe.delta !== null ? pe.delta : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${textColor}`}>{pe.gamma !== undefined && pe.gamma !== null ? pe.gamma : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${textColor}`}>{pe.theta !== undefined && pe.theta !== null ? pe.theta : '-'}</td>
                        <td className={`py-2 px-2 ${isPeItm && !isATM ? 'bg-indigo-900/15' : ''} ${textColor}`}>{pe.vega !== undefined && pe.vega !== null ? pe.vega : '-'}</td>
                      </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Trade Details Mini-Card */}
      {selectedTrade && (
        <div className="fixed top-20 right-6 z-50 w-[420px] max-h-[calc(100vh-6rem)] flex flex-col animate-in slide-in-from-top-5 fade-in duration-300">
          <div className={`border rounded-xl shadow-[0_0_40px_rgba(0,0,0,0.6)] overflow-y-auto flex flex-col custom-scrollbar ${selectedTrade.role === 'BUYER' ? 'bg-gray-800 border-yellow-500/50' : 'bg-gray-800 border-fuchsia-500/50'}`}>
            <div className={`p-3 border-b flex justify-between items-center ${selectedTrade.role === 'BUYER' ? 'bg-yellow-500/10 border-yellow-500/20' : 'bg-fuchsia-500/10 border-fuchsia-500/20'}`}>
              <h3 className={`font-bold text-sm flex items-center gap-2 ${selectedTrade.role === 'BUYER' ? 'text-yellow-400' : 'text-fuchsia-400'}`}>
                {selectedTrade.role === 'BUYER' ? '🎯 Buyer Strategy' : '🛡️ Seller Strategy'}
              </h3>
              <button onClick={() => setSelectedTrade(null)} className="text-gray-400 hover:text-white transition-colors">✕</button>
            </div>
            
            <div className="p-4 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xl font-bold text-white">{selectedTrade.strategy.strike} {selectedTrade.strategy.type}</span>
                <span className={`px-2 py-1 rounded text-xs font-bold ${selectedTrade.role === 'BUYER' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-fuchsia-500/20 text-fuchsia-300'}`}>
                  {selectedTrade.strategy.action}
                </span>
              </div>
              
              <p className="text-xs text-gray-300 leading-relaxed bg-gray-900/50 p-2 rounded border border-gray-700/50">
                {selectedTrade.strategy.reason}
              </p>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-900/40 p-2 rounded border border-gray-700/30">
                  <div className="text-gray-500 mb-0.5">Entry</div>
                  <div className="font-bold text-white">₹{selectedTrade.strategy.entry?.toFixed(2)}</div>
                </div>
                <div className="bg-green-900/10 p-2 rounded border border-green-900/30">
                  <div className="text-gray-500 mb-0.5">Target</div>
                  <div className="font-bold text-green-400">₹{selectedTrade.strategy.target}</div>
                </div>
                <div className="bg-red-900/10 p-2 rounded border border-red-900/30">
                  <div className="text-gray-500 mb-0.5">Stoploss</div>
                  <div className="font-bold text-red-400">₹{selectedTrade.strategy.sl}</div>
                </div>
              </div>

              <div className="text-xs space-y-2 mt-4 bg-gray-900/60 p-3 rounded-lg border border-gray-700/50">
                <div className="font-bold text-gray-400 mb-2 border-b border-gray-700 pb-1">FII Institutional Reversals</div>
                
                {data?.reversals ? (
                  <>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">S1 (Adjusted Gamma Wall)</span>
                      <span className={`font-bold ${data.reversals.concrete_wall_support ? 'text-emerald-300 bg-emerald-900/40 px-2 py-0.5 rounded border border-emerald-500/50' : 'text-emerald-400'}`}>
                        {data.reversals.S1}
                        {data.reversals.concrete_wall_support && ' 🔥 Concrete Wall'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500">S2 (Volatility Limit)</span>
                      <span className="font-bold text-emerald-600/80">{data.reversals.S2}</span>
                    </div>
                    
                    <div className="my-2 border-t border-gray-800 border-dashed"></div>

                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">R1 (Adjusted Gamma Wall)</span>
                      <span className={`font-bold ${data.reversals.concrete_wall_resistance ? 'text-red-300 bg-red-900/40 px-2 py-0.5 rounded border border-red-500/50' : 'text-red-400'}`}>
                        {data.reversals.R1}
                        {data.reversals.concrete_wall_resistance && ' 🔥 Concrete Wall'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500">R2 (Volatility Limit)</span>
                      <span className="font-bold text-red-600/80">{data.reversals.R2}</span>
                    </div>

                    <div className="mt-3 pt-2 border-t border-gray-800 space-y-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-purple-400 font-semibold">⚡ Master Pivot (Zero Gamma)</span>
                        <span className="font-bold text-purple-400">{data.reversals.zero_gamma}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-blue-400 font-semibold">📊 Volume POC</span>
                        <span className="font-bold text-blue-400">{data.reversals.volume_poc}</span>
                      </div>
                      {data.reversals.max_pain > 0 && (
                        <div className="flex justify-between items-center">
                          <span className="text-indigo-400 font-semibold">🧲 Max Pain (Magnet)</span>
                          <span className="font-bold text-indigo-400">{data.reversals.max_pain}</span>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Strong Support</span>
                      <span className="font-bold text-emerald-400">{data?.analysis?.highest_put_oi_strike || "N/A"}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Strong Resistance</span>
                      <span className="font-bold text-red-400">{data?.analysis?.highest_call_oi_strike || "N/A"}</span>
                    </div>
                  </>
                )}
              </div>

              {selectedTrade.role === 'SELLER' && (
                <div className="text-xs bg-orange-900/20 text-orange-300 p-2 rounded border border-orange-900/30">
                  <span className="font-semibold text-orange-400">Margin Required:</span> {selectedTrade.strategy.margin_required}
                </div>
              )}

              <div className="flex gap-2">
                <button 
                  onClick={() => handlePlaceTrade(selectedTrade.role, selectedTrade.strategy)}
                  disabled={isTrading}
                  className={`flex-1 py-2.5 rounded font-bold text-sm shadow transition-all ${
                    isTrading ? 'opacity-50 cursor-not-allowed bg-gray-600' :
                    selectedTrade.role === 'BUYER' 
                      ? 'bg-yellow-500 hover:bg-yellow-400 text-yellow-950' 
                      : 'bg-fuchsia-600 hover:bg-fuchsia-500 text-white'
                  }`}
                >
                  {isTrading ? 'Executing...' : '⚡ Trade Now (Paper)'}
                </button>
                <button 
                  onClick={async () => {
                    setIsPredicting(true);
                    setKronosPrediction(null);
                    
                    const expiryEpoch = data?.expiry_epoch || (Date.now() / 1000 + 5 * 86400);
                    const dte = Math.max(1, Math.ceil((expiryEpoch - Date.now() / 1000) / 86400));
                    setPredictionDays(dte);

                    // Find symbol of this strike
                    const q = data?.quotes?.find((x:any) => x.strike === selectedTrade.strategy.strike && x.type === selectedTrade.strategy.type);
                    if(q && q.symbol) {
                        const res = await predictKronos(q.symbol, dte);
                        if(res.error) alert(res.error);
                        else setKronosPrediction(res);
                    } else {
                        alert("Could not find symbol for this strike");
                    }
                    setIsPredicting(false);
                  }}
                  disabled={isPredicting}
                  className={`px-4 py-2.5 rounded font-bold text-sm shadow transition-all flex items-center justify-center gap-1 ${isPredicting ? 'bg-indigo-800 text-indigo-400 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}`}
                >
                  {isPredicting ? '🤖...' : '🤖 Predict (DTE)'}
                </button>
              </div>

              {kronosPrediction && kronosPrediction.prediction && (
                <div className="mt-4 bg-gray-900/60 p-3 rounded-lg border border-indigo-500/50 animate-in fade-in zoom-in-95">
                  <div className="font-bold text-indigo-400 mb-2 flex justify-between">
                    <span>🤖 Kronos {predictionDays}-Day Forecast (To Expiry)</span>
                    <button onClick={() => setKronosPrediction(null)} className="text-gray-500 hover:text-white">✕</button>
                  </div>
                  <div className="space-y-1">
                    {kronosPrediction.prediction?.map((p: any, i: number) => {
                      const prevClose = i === 0 
                        ? (kronosPrediction.historical[kronosPrediction.historical.length-1]?.close || 0) 
                        : kronosPrediction.prediction[i-1].close;
                      
                      const isUp = p.close >= prevClose;
                      
                      return (
                        <div key={i} className="flex justify-between text-xs text-gray-300 bg-gray-800/50 px-2 py-1.5 rounded">
                          <span>{p.timestamps.split(' ')[0]}</span>
                          <span className={isUp ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                             ₹{p.close.toFixed(2)}
                             <span className="text-[10px] ml-1 opacity-70">
                                {isUp ? '▲' : '▼'} {Math.abs(((p.close - prevClose) / prevClose) * 100).toFixed(1)}%
                             </span>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
