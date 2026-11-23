"use client";

import React from "react";
import Link from "next/link";
import {
  Activity,
  FlaskConical,
  BarChart2,
  TrendingDown,
  FileSearch,
  Building2,
  RefreshCw,
  BrainCircuit,
} from "lucide-react";

export const FNO_INDEX_OPTIONS = [
  { value: "NIFTY", label: "NIFTY 50" },
  { value: "BANKNIFTY", label: "BANK NIFTY" },
  { value: "FINNIFTY", label: "FIN NIFTY" },
  { value: "MIDCPNIFTY", label: "MIDCAP NIFTY" },
];

export const FNO_STOCK_OPTIONS = [
  { value: "RELIANCE", label: "RELIANCE (Reliance Ind.)" },
  { value: "HDFCBANK", label: "HDFCBANK (HDFC Bank)" },
  { value: "ICICIBANK", label: "ICICIBANK (ICICI Bank)" },
  { value: "SBIN", label: "SBIN (State Bank)" },
  { value: "INFY", label: "INFY (Infosys)" },
  { value: "TCS", label: "TCS (Tata Consultancy)" },
  { value: "BHARTIARTL", label: "BHARTIARTL (Airtel)" },
  { value: "TATAMOTORS", label: "TATAMOTORS (Tata Motors)" },
  { value: "HAL", label: "HAL (Hindustan Aero)" },
  { value: "BAJFINANCE", label: "BAJFINANCE (Bajaj Finance)" },
  { value: "LT", label: "LT (Larsen & Toubro)" },
  { value: "TRENT", label: "TRENT (Trent Ltd)" },
  { value: "SUNPHARMA", label: "SUNPHARMA (Sun Pharma)" },
  { value: "BSE", label: "BSE (BSE Ltd)" },
];

export function getSavedFnoSymbol(): string {
  if (typeof window === "undefined") return "NIFTY";
  try {
    const params = new URLSearchParams(window.location.search);
    const urlSym = params.get("symbol");
    if (urlSym) {
      const clean = urlSym.toUpperCase().trim();
      window.sessionStorage.setItem("tradematrix_fno_symbol", clean);
      return clean;
    }
    return window.sessionStorage.getItem("tradematrix_fno_symbol") || "NIFTY";
  } catch {
    return "NIFTY";
  }
}

export function saveFnoSymbol(sym: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem("tradematrix_fno_symbol", sym.toUpperCase().trim());
  } catch {
    // ignore storage errors
  }
}

interface FnoHeaderNavProps {
  activeTab: "chain" | "strategy" | "oi" | "pcr" | "analytics" | "fii";
  title: string;
  subtitle: string;
  symbol?: string;
  onSymbolChange?: (sym: string) => void;
  spotPrice?: number;
  spotChangePct?: number;
  atmStrike?: number;
  lotSize?: number;
  dte?: number;
  convictionScore?: number;
  directionalBias?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  showAtmInput?: boolean;
  atmInput?: number | "";
  onAtmInputChange?: (val: number | "") => void;
  rightExtra?: React.ReactNode;
}

const TABS = [
  { id: "chain", href: "/fno", label: "Option Chain & Brain", icon: Activity },
  { id: "strategy", href: "/fno/strategy-builder", label: "Strategy Builder", icon: FlaskConical },
  { id: "oi", href: "/fno/oi-analysis", label: "Open Interest", icon: BarChart2 },
  { id: "pcr", href: "/fno/pcr-analysis", label: "PCR & Volatility", icon: TrendingDown },
  { id: "analytics", href: "/fno/option-analysis", label: "Pro Analytics", icon: FileSearch },
  { id: "fii", href: "/fno/fii-dii", label: "FII / DII & Smart Money", icon: Building2 },
] as const;

export function FnoHeaderNav({
  activeTab,
  title,
  subtitle,
  symbol,
  onSymbolChange,
  spotPrice,
  spotChangePct,
  atmStrike,
  lotSize,
  dte,
  convictionScore,
  directionalBias,
  onRefresh,
  isRefreshing = false,
  showAtmInput = false,
  atmInput = "",
  onAtmInputChange,
  rightExtra,
}: FnoHeaderNavProps) {
  return (
    <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
      <div className="px-4 sm:px-6 py-4 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <BrainCircuit size={24} className="text-indigo-600" />
              {title}
            </h1>
            {convictionScore !== undefined && convictionScore > 0 && (
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  convictionScore >= 72
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : convictionScore >= 58
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-slate-100 text-slate-700 border-slate-200"
                }`}
              >
                Aladdin Conviction: {convictionScore.toFixed(0)}% ({directionalBias || "NEUTRAL"})
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs sm:text-sm text-slate-500 mt-1">
            <span>{subtitle}</span>
            {spotPrice && spotPrice > 0 ? (
              <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                Spot: ₹{spotPrice.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                {spotChangePct !== undefined && (
                  <span className={spotChangePct >= 0 ? "text-emerald-600" : "text-red-600"}>
                    ({spotChangePct >= 0 ? "+" : ""}
                    {spotChangePct.toFixed(2)}%)
                  </span>
                )}
              </span>
            ) : null}
            {atmStrike ? (
              <span className="font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                ATM: {atmStrike}
              </span>
            ) : null}
            {lotSize ? (
              <span className="font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                Lot Size: {lotSize}
              </span>
            ) : null}
            {dte !== undefined ? (
              <span className="font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                Expiry: {dte.toFixed(1)}d
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {symbol && onSymbolChange && (
            <select
              aria-label="Select F&O Symbol"
              className="bg-white border border-slate-300 text-slate-800 rounded-lg px-3 py-2 text-sm font-bold shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={symbol}
              onChange={(e) => {
                const next = e.target.value;
                saveFnoSymbol(next);
                onSymbolChange(next);
              }}
            >
              <optgroup label="Major Indices">
                {FNO_INDEX_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Top Liquid F&O Stocks">
                {FNO_STOCK_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </optgroup>
            </select>
          )}

          {showAtmInput && onAtmInputChange && (
            <input
              type="number"
              className="bg-white border border-slate-300 text-slate-800 rounded-lg px-3 py-2 text-sm w-28 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={atmInput}
              onChange={(e) =>
                onAtmInputChange(e.target.value === "" ? "" : Number(e.target.value))
              }
              placeholder="ATM Strike"
            />
          )}

          {rightExtra}

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white px-3.5 py-2 rounded-lg text-sm font-semibold shadow-sm transition-colors"
            >
              <RefreshCw size={15} className={isRefreshing ? "animate-spin" : ""} />
              {isRefreshing ? "Syncing..." : "Refresh"}
            </button>
          )}
        </div>
      </div>

      {/* UNIFIED 6-TAB HORIZONTAL NAVIGATION */}
      <div className="px-4 sm:px-6 flex items-center gap-5 overflow-x-auto border-t border-slate-100 bg-slate-50/70">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <Link
              key={tab.id}
              href={tab.href}
              className={`py-3 border-b-2 text-xs sm:text-sm whitespace-nowrap inline-flex items-center gap-1.5 transition-colors ${
                isActive
                  ? "border-indigo-600 text-indigo-700 font-bold"
                  : "border-transparent text-slate-600 hover:text-slate-900 font-medium"
              }`}
            >
              <Icon size={15} />
              {tab.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
