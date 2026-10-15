"use client";

import { useState, useEffect, useRef } from "react";
import { api, tradesApi } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Target, ShieldAlert, Zap,
  Search, Play, BarChart2, CheckCircle, XCircle, Clock,
  AlertCircle, ChevronDown, ChevronUp, RefreshCw, Star
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface ResearchSignal {
  symbol: string;
  company_name: string;
  sector: string;
  signal_type: string;
  action: string;
  current_price: number;
  entry_zone_low: number;
  entry_zone_high: number;
  stop_loss: number;
  stop_loss_pct: number;
  stop_loss_type: string;
  target_1: number;
  target_2: number;
  target_3: number;
  target_1_pct: number;
  target_2_pct: number;
  target_3_pct: number;
  rr_t2: number;
  rr_quality: string;
  suggested_qty: number;
  max_loss_amount: number;
  max_gain_t2: number;
  roce: number | null;
  debt_to_equity: number | null;
  piotroski_f_score: number | null;
  eps_growth_yoy: number | null;
  pe_ratio: number | null;
  roe: number | null;
  rsi: number | null;
  ema_200: number | null;
  adx: number | null;
  atr_pct: number | null;
  volume_ratio: number | null;
  composite_score: number;
  score?: number;
  confidence_label: string;
  bull_reasons: string[];
  caution_reasons: string[];
  passed_ema_200: boolean;
  passed_rsi: boolean;
  passed_roce: boolean;
}

interface RunStatus {
  run_id: string;
  status: string;
  progress_pct: number;
  total_symbols: number;
  processed: number;
  passed_filter1_liquidity: number;
  passed_filter2_fundamental: number;
  passed_filter3_technical: number;
  passed_filter4_rr: number;
  signals_count: number;
  current_symbol: string;
  mode: string;
}

interface SingleAnalysis {
  symbol: string;
  company_name: string;
  sector: string;
  verdict: string;
  verdict_reason: string;
  current_price: number;
  entry_price: number;
  entry_zone_low?: number;
  entry_zone_high?: number;
  stop_loss: number;
  stop_loss_pct: number;
  stop_loss_type?: string;
  target_1: number;
  target_1_pct?: number;
  target_2: number;
  target_3: number;
  target_2_pct: number;
  target_3_pct?: number;
  rr_t2: number;
  rr_quality: string;
  suggested_qty: number;
  total_investment?: number;
  max_loss_amount: number;
  max_gain_t2: number;
  fundamental: Record<string, any>;
  technical: Record<string, any>;
  filters: Record<string, boolean>;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "N/A";
  return n.toFixed(decimals);
}
function fmtINR(n: number | null | undefined): string {
  if (n == null) return "N/A";
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}
function fmtPct(n: number | null | undefined): string {
  if (n == null) return "N/A";
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function RRBadge({ quality }: { quality: string }) {
  const colors: Record<string, string> = {
    EXCELLENT: "bg-emerald-100 text-emerald-700 border border-emerald-200",
    GOOD: "bg-blue-100 text-blue-700 border border-blue-200",
    FAIR: "bg-amber-100 text-amber-700 border border-amber-200",
    POOR: "bg-red-100 text-red-700 border border-red-200",
  };
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${colors[quality] || colors.POOR}`}>
      {quality}
    </span>
  );
}

function ConfidenceBadge({ label, score }: { label: string; score: number }) {
  const colors: Record<string, string> = {
    "VERY HIGH": "bg-emerald-500 text-white",
    "HIGH": "bg-blue-500 text-white",
    "MEDIUM": "bg-amber-500 text-white",
    "LOW": "bg-slate-400 text-white",
  };
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${colors[label] || "bg-slate-400 text-white"}`}>
      <Star size={11} fill="currentColor" />
      {label} ({score}/100)
    </div>
  );
}

function FilterDot({ passed, label }: { passed: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      {passed ? (
        <CheckCircle size={13} className="text-emerald-500 flex-shrink-0" />
      ) : (
        <XCircle size={13} className="text-red-400 flex-shrink-0" />
      )}
      <span className={`text-xs ${passed ? "text-slate-700" : "text-slate-400"}`}>{label}</span>
    </div>
  );
}

// ── Signal Card ────────────────────────────────────────────────────────────

function SignalCard({ signal, capital }: { signal: ResearchSignal; capital: number }) {
  const [expanded, setExpanded] = useState(false);
  const [placingTrade, setPlacingTrade] = useState(false);
  const [tradeSuccess, setTradeSuccess] = useState(false);

  const riskAmount = signal.max_loss_amount || 0;
  const gainAmount = signal.max_gain_t2 || 0;

  const handleExecutePaperTrade = async () => {
    setPlacingTrade(true);
    try {
      await tradesApi.createCustomTrade({
        symbol: signal.symbol?.replace(".NS", ""),
        company_name: signal.company_name || signal.symbol?.replace(".NS", ""),
        direction: "LONG",
        entry_price: signal.current_price,
        quantity: signal.suggested_qty || 10,
        stop_loss: signal.stop_loss || 0,
        target_price: signal.target_2 || signal.target_1 || 0,
        notes: `Live Screener: Score ${signal.score}/100 | ${signal.rr_quality} R:R`
      });
      setTradeSuccess(true);
    } catch (e: any) {
      console.error("Failed to place paper trade:", e);
    } finally {
      setPlacingTrade(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm hover:shadow-md transition-all overflow-hidden">
      {/* Card Header */}
      <div className="p-5 pb-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg font-extrabold text-slate-900 tracking-tight">
                {signal.symbol?.replace(".NS", "")}
              </span>
              <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold px-2 py-0.5 rounded-full">
                {signal.action || "BUY"}
              </span>
              <span className="text-xs bg-blue-50 text-blue-600 font-semibold px-2 py-0.5 rounded-full">
                {signal.signal_type}
              </span>
            </div>
            <div className="text-sm text-slate-500 font-medium">{signal.company_name}</div>
            <div className="text-xs text-slate-400 mt-0.5">{signal.sector}</div>
          </div>
          <ConfidenceBadge label={signal.confidence_label} score={signal.composite_score} />
        </div>

        {/* Price Info */}
        <div className="flex items-baseline gap-2 mb-4">
          <span className="text-2xl font-black text-slate-900">₹{fmt(signal.current_price)}</span>
          <span className="text-sm text-slate-400">Current Price</span>
        </div>

        {/* Main Trade Parameters */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {/* Entry */}
          <div className="bg-blue-50 rounded-xl p-3 border border-blue-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-blue-500 mb-1">Entry Zone</div>
            <div className="text-sm font-bold text-blue-700">₹{fmt(signal.entry_zone_low)}</div>
            <div className="text-xs text-blue-500">to ₹{fmt(signal.entry_zone_high)}</div>
          </div>

          {/* Stop Loss */}
          <div className="bg-red-50 rounded-xl p-3 border border-red-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-red-500 mb-1">Stop Loss</div>
            <div className="text-sm font-bold text-red-700">₹{fmt(signal.stop_loss)}</div>
            <div className="text-xs text-red-400">{fmtPct(signal.stop_loss_pct)} ({signal.stop_loss_type})</div>
          </div>

          {/* Target 2 (Primary) */}
          <div className="bg-emerald-50 rounded-xl p-3 border border-emerald-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-500 mb-1">Target (Primary)</div>
            <div className="text-sm font-bold text-emerald-700">₹{fmt(signal.target_2)}</div>
            <div className="text-xs text-emerald-500">{fmtPct(signal.target_2_pct)}</div>
          </div>
        </div>

        {/* Targets Row */}
        <div className="flex gap-2 mb-4">
          <div className="flex-1 bg-slate-50 rounded-lg p-2 text-center border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">T1 (Book ~30%)</div>
            <div className="text-sm font-bold text-slate-700">₹{fmt(signal.target_1)}</div>
            <div className="text-xs text-emerald-600">{fmtPct(signal.target_1_pct)}</div>
          </div>
          <div className="flex-1 bg-slate-50 rounded-lg p-2 text-center border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">T2 (Book ~50%)</div>
            <div className="text-sm font-bold text-slate-700">₹{fmt(signal.target_2)}</div>
            <div className="text-xs text-emerald-600">{fmtPct(signal.target_2_pct)}</div>
          </div>
          <div className="flex-1 bg-slate-50 rounded-lg p-2 text-center border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">T3 (Trailing)</div>
            <div className="text-sm font-bold text-slate-700">₹{fmt(signal.target_3)}</div>
            <div className="text-xs text-emerald-600">{fmtPct(signal.target_3_pct)}</div>
          </div>
        </div>

        {/* Risk Stats Row */}
        <div className="flex items-center justify-between bg-slate-50 rounded-xl px-4 py-3 border border-slate-100">
          <div className="text-center">
            <div className="text-xs text-slate-500 font-medium">Risk:Reward</div>
            <div className="text-base font-black text-slate-800">1:{fmt(signal.rr_t2, 1)}</div>
          </div>
          <div className="w-px h-8 bg-slate-200" />
          <div className="text-center">
            <div className="text-xs text-slate-500 font-medium">Qty ({signal.suggested_qty} shares)</div>
            <div className="text-sm font-bold text-red-600">Max Loss: {fmtINR(riskAmount)}</div>
          </div>
          <div className="w-px h-8 bg-slate-200" />
          <div className="text-center">
            <div className="text-xs text-slate-500 font-medium">R:R Quality</div>
            <RRBadge quality={signal.rr_quality} />
          </div>
        </div>

        {/* 1-Click Take Live Paper Trade Button */}
        <div className="mt-3">
          <button
            onClick={handleExecutePaperTrade}
            disabled={placingTrade || tradeSuccess}
            className={`w-full py-2 px-3 font-bold rounded-lg text-xs flex items-center justify-center gap-1.5 shadow-xs transition-all ${
              tradeSuccess
                ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                : "bg-emerald-600 hover:bg-emerald-700 text-white"
            }`}
          >
            {placingTrade ? (
              <RefreshCw size={13} className="animate-spin" />
            ) : tradeSuccess ? (
              <CheckCircle size={13} className="text-emerald-600" />
            ) : (
              <Zap size={13} className="text-amber-300" />
            )}
            <span>
              {tradeSuccess
                ? "✓ Live Paper Trade Active (Tracking in Trades Tab)"
                : `⚡ Take Live Paper Trade (${signal.suggested_qty || 10} Qty @ ₹${fmt(signal.current_price)})`}
            </span>
          </button>
        </div>
      </div>

      {/* Filters Row */}
      <div className="px-5 pb-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3">
        <FilterDot passed={signal.passed_ema_200} label={`Price > 200 EMA (${fmt(signal.ema_200)})`} />
        <FilterDot passed={signal.passed_rsi} label={`RSI ${fmt(signal.rsi, 0)}`} />
        <FilterDot passed={signal.passed_roce} label={`ROCE ${fmt(signal.roce, 1)}%`} />
        <FilterDot passed={!!signal.adx && signal.adx >= 18} label={`ADX ${fmt(signal.adx, 0)}`} />
        <FilterDot passed={!!signal.volume_ratio && signal.volume_ratio >= 0.8} label={`Vol ${fmt(signal.volume_ratio, 1)}x avg`} />
      </div>

      {/* Expandable Details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-2.5 bg-slate-50 hover:bg-slate-100 transition-colors text-xs font-bold text-slate-500 border-t border-slate-100"
      >
        <span>Full Analysis Details</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="px-5 pb-5 pt-3 space-y-4 border-t border-slate-100">
          {/* Bull Reasons */}
          {signal.bull_reasons?.length > 0 && (
            <div>
              <div className="text-xs font-bold text-emerald-600 uppercase tracking-wider mb-2">✅ Why This Setup</div>
              <div className="space-y-1">
                {signal.bull_reasons.map((r, i) => (
                  <div key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>
                    {r}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Caution Reasons */}
          {signal.caution_reasons?.length > 0 && (
            <div>
              <div className="text-xs font-bold text-amber-600 uppercase tracking-wider mb-2">⚠️ Watch Out For</div>
              <div className="space-y-1">
                {signal.caution_reasons.map((r, i) => (
                  <div key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="text-amber-500 mt-0.5 flex-shrink-0">•</span>
                    {r}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fundamental + Technical Grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Fundamentals</div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-slate-500">ROCE</span><span className="font-bold text-slate-800">{fmt(signal.roce, 1)}%</span></div>
                <div className="flex justify-between"><span className="text-slate-500">D/E Ratio</span><span className="font-bold text-slate-800">{fmt(signal.debt_to_equity, 2)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Piotroski</span><span className="font-bold text-slate-800">{signal.piotroski_f_score ?? "N/A"}/9</span></div>
                <div className="flex justify-between"><span className="text-slate-500">EPS Growth</span><span className="font-bold text-slate-800">{fmtPct(signal.eps_growth_yoy)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">P/E Ratio</span><span className="font-bold text-slate-800">{fmt(signal.pe_ratio, 1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">ROE</span><span className="font-bold text-slate-800">{fmt(signal.roe, 1)}%</span></div>
              </div>
            </div>
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Technicals</div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-slate-500">RSI (14)</span><span className="font-bold text-slate-800">{fmt(signal.rsi, 1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">200 EMA</span><span className="font-bold text-slate-800">₹{fmt(signal.ema_200)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">ADX</span><span className="font-bold text-slate-800">{fmt(signal.adx, 1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">ATR</span><span className="font-bold text-slate-800">{fmt(signal.atr_pct, 2)}%</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Vol Ratio</span><span className="font-bold text-slate-800">{fmt(signal.volume_ratio, 2)}x</span></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Single Stock Analyze Panel ─────────────────────────────────────────────

function QuickAnalyzePanel({ mode }: { mode: string }) {
  const [symbol, setSymbol] = useState("");
  const [result, setResult] = useState<SingleAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [placingTrade, setPlacingTrade] = useState(false);
  const [tradeSuccess, setTradeSuccess] = useState(false);

  const handleExecutePaperTrade = async () => {
    if (!result || !result.entry_price) return;
    setPlacingTrade(true);
    try {
      await tradesApi.createCustomTrade({
        symbol: result.symbol?.replace(".NS", ""),
        company_name: result.company_name || result.symbol?.replace(".NS", ""),
        direction: "LONG",
        entry_price: result.entry_price,
        quantity: result.suggested_qty || 10,
        stop_loss: result.stop_loss || 0,
        target_price: result.target_2 || result.target_1 || 0,
        notes: `Live Research Setup: ${result.verdict} (${result.verdict_reason || 'Alpha Pullback'})`
      });
      setTradeSuccess(true);
    } catch (e: any) {
      setError(`Failed to create paper trade: ${e.message}`);
    } finally {
      setPlacingTrade(false);
    }
  };

  const handleAnalyze = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    setTradeSuccess(false);
    try {
      const res = await api.post(`/research/analyze/${symbol.trim().toUpperCase()}?mode=${mode}`);
      setResult(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to analyze stock");
    } finally {
      setLoading(false);
    }
  };

  const verdictColors: Record<string, string> = {
    BUY: "bg-emerald-50 border-emerald-200 text-emerald-700",
    WATCH: "bg-amber-50 border-amber-200 text-amber-700",
    SKIP: "bg-red-50 border-red-200 text-red-600",
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
      <div className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
        <Search size={15} className="text-blue-500" />
        Quick Stock Analysis
      </div>
      <div className="flex gap-2 mb-4">
        <input
          id="quick-analyze-input"
          type="text"
          placeholder="e.g. RELIANCE, TCS, INFY"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleAnalyze()}
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder-slate-400"
        />
        <button
          id="quick-analyze-btn"
          onClick={handleAnalyze}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 disabled:opacity-50"
        >
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
          Analyze
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 text-xs rounded-lg px-3 py-2">{error}</div>
      )}

      {result && (
        <div className="space-y-3">
          {/* Verdict Banner */}
          <div className={`border rounded-xl px-4 py-3 ${verdictColors[result.verdict] || verdictColors.SKIP}`}>
            <div className="font-black text-lg">{result.verdict} — {result.symbol?.replace(".NS", "")}</div>
            <div className="text-sm font-medium mt-0.5">{result.verdict_reason}</div>
            <div className="text-xs mt-1 opacity-70">{result.company_name} • {result.sector}</div>
          </div>

          {/* Trade Execution Levels */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3">
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>{result.verdict === "BUY" ? "🎯 Active Trade Plan" : "📐 Calculated Trade Levels (Reference)"}</span>
              <RRBadge quality={result.rr_quality || "GOOD"} />
            </div>

            <div className="grid grid-cols-4 gap-2 text-center mb-3">
              <div className="bg-blue-50/80 rounded-lg p-2 border border-blue-100">
                <div className="text-[10px] font-bold uppercase text-blue-600">Entry Zone</div>
                <div className="text-sm font-black text-blue-800">₹{fmt(result.entry_price)}</div>
                <div className="text-[9px] text-blue-500">₹{fmt(result.entry_zone_low)} - {fmt(result.entry_zone_high)}</div>
              </div>
              <div className="bg-red-50/80 rounded-lg p-2 border border-red-100">
                <div className="text-[10px] font-bold uppercase text-red-600">Stop Loss</div>
                <div className="text-sm font-black text-red-700">₹{fmt(result.stop_loss)}</div>
                <div className="text-[9px] text-red-500 font-semibold">{fmtPct(result.stop_loss_pct)} ({result.stop_loss_type || "ATR"})</div>
              </div>
              <div className="bg-emerald-50/80 rounded-lg p-2 border border-emerald-100">
                <div className="text-[10px] font-bold uppercase text-emerald-600">Target 1 (1:1)</div>
                <div className="text-sm font-black text-emerald-700">₹{fmt(result.target_1)}</div>
                <div className="text-[9px] text-emerald-500 font-semibold">{fmtPct(result.target_1_pct)}</div>
              </div>
              <div className="bg-emerald-100/70 rounded-lg p-2 border border-emerald-200">
                <div className="text-[10px] font-bold uppercase text-emerald-700">Target 2 (1:2) ⭐</div>
                <div className="text-sm font-black text-emerald-800">₹{fmt(result.target_2)}</div>
                <div className="text-[9px] text-emerald-600 font-semibold">{fmtPct(result.target_2_pct)}</div>
              </div>
            </div>

            {/* Position Sizing & Capital */}
            <div className="bg-white rounded-lg p-2.5 border border-slate-200 flex items-center justify-around text-center text-xs">
              <div>
                <div className="text-[10px] text-slate-400 font-medium">Suggested Qty</div>
                <div className="font-bold text-slate-800">{result.suggested_qty || "—"} shares</div>
              </div>
              <div className="w-px h-6 bg-slate-200" />
              <div>
                <div className="text-[10px] text-slate-400 font-medium">Capital Required</div>
                <div className="font-bold text-slate-800">{fmtINR(result.total_investment)}</div>
              </div>
              <div className="w-px h-6 bg-slate-200" />
              <div>
                <div className="text-[10px] text-slate-400 font-medium">Max Risk (SL)</div>
                <div className="font-bold text-red-600">-{fmtINR(result.max_loss_amount)}</div>
              </div>
              <div className="w-px h-6 bg-slate-200" />
              <div>
                <div className="text-[10px] text-slate-400 font-medium">Max Profit (T2)</div>
                <div className="font-bold text-emerald-600">+{fmtINR(result.max_gain_t2)}</div>
              </div>
            </div>

            {/* 1-Click Take Live Paper Trade Button */}
            {result.entry_price && (
              <div className="mt-2.5">
                <button
                  onClick={handleExecutePaperTrade}
                  disabled={placingTrade || tradeSuccess}
                  className={`w-full py-2.5 px-4 font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-sm transition-all ${
                    tradeSuccess
                      ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                      : "bg-emerald-600 hover:bg-emerald-700 text-white"
                  }`}
                >
                  {placingTrade ? (
                    <RefreshCw size={14} className="animate-spin" />
                  ) : tradeSuccess ? (
                    <CheckCircle size={14} className="text-emerald-600" />
                  ) : (
                    <Zap size={14} className="text-amber-300" />
                  )}
                  <span>
                    {tradeSuccess
                      ? "✓ Paper Trade Placed! Live in Trades Tab"
                      : `⚡ Take Live Paper Trade (${result.suggested_qty || 10} Qty @ ₹${fmt(result.entry_price)})`}
                  </span>
                </button>
              </div>
            )}
          </div>

          {/* Filter Summary */}
          <div className="space-y-1">
            <FilterDot passed={result.filters?.passed_roce} label={`ROCE: ${fmt(result.fundamental?.roce, 1)}%`} />
            <FilterDot passed={result.filters?.passed_debt_to_equity} label={`D/E: ${fmt(result.fundamental?.debt_to_equity, 2)}`} />
            <FilterDot passed={result.filters?.passed_ema_200} label={`Price > 200 EMA (${fmt(result.technical?.ema_200)})`} />
            <FilterDot passed={result.filters?.passed_rsi} label={`RSI: ${fmt(result.technical?.rsi, 1)}`} />
            <FilterDot passed={result.filters?.passed_rr} label={`R:R: 1:${fmt(result.rr_t2, 1)}`} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Progress Bar ───────────────────────────────────────────────────────────

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
      <div
        className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const [mode, setMode] = useState<"SWING" | "POSITIONAL" | "INTRADAY">("SWING");
  const [universe, setUniverse] = useState("NIFTY500");
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [signals, setSignals] = useState<ResearchSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [capital] = useState(100000);
  const [filterScore, setFilterScore] = useState(0);
  const [activeTab, setActiveTab] = useState<"screener" | "analyze">("analyze");
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleStartRun = async () => {
    setLoading(true);
    setError("");
    setSignals([]);
    setRunStatus(null);

    try {
      const res = await api.post("/research/run", { mode, universe });
      const runId = res.data.run_id;

      // Poll for status every 2 seconds
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await api.get(`/research/run/${runId}`);
          setRunStatus(statusRes.data);

          if (statusRes.data.status === "COMPLETED") {
            clearInterval(pollRef.current!);
            setLoading(false);
            // Fetch signals
            const sigRes = await api.get(`/research/signals/${runId}?limit=100`);
            setSignals(sigRes.data.signals || []);
          } else if (statusRes.data.status === "ERROR") {
            clearInterval(pollRef.current!);
            setLoading(false);
            setError("Run failed — check backend logs.");
          }
        } catch (e) {
          // Ignore polling errors
        }
      }, 2000);
    } catch (e: any) {
      setError(e.message || "Failed to start research run");
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const filteredSignals = signals.filter(s => s.composite_score >= filterScore);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-20">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black text-slate-900 flex items-center gap-2">
              <Zap size={20} className="text-blue-600" />
              Research Engine
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">Rule-based stock screener — Entry, SL, Target calculated automatically</p>
          </div>
          {/* Mode Toggle */}
          <div className="flex items-center gap-2 bg-slate-100 rounded-xl p-1">
            {(["SWING", "POSITIONAL", "INTRADAY"] as const).map(m => (
              <button
                key={m}
                id={`mode-${m.toLowerCase()}`}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  mode === m
                    ? "bg-white text-blue-700 shadow-sm border border-slate-200"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="bg-white border-b border-slate-200 px-6">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("analyze")}
            className={`py-3 text-sm font-bold border-b-2 transition-colors ${
              activeTab === "analyze" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            Quick Analyze
          </button>
          <button
            id="tab-screener"
            onClick={() => setActiveTab("screener")}
            className={`py-3 text-sm font-bold border-b-2 transition-colors ${
              activeTab === "screener" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            Full Screener
            {signals.length > 0 && (
              <span className="ml-2 bg-blue-100 text-blue-700 text-[10px] font-black px-1.5 py-0.5 rounded-full">
                {filteredSignals.length}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="p-6 max-w-7xl mx-auto">
        {activeTab === "analyze" && (
          <div className="max-w-xl">
            <QuickAnalyzePanel mode={mode} />
          </div>
        )}

        {activeTab === "screener" && (
          <div className="space-y-5">
            {/* Controls */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-4 flex-wrap">
                {/* Universe */}
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">Universe</label>
                  <select
                    value={universe}
                    onChange={e => setUniverse(e.target.value)}
                    className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="NIFTY50">Nifty 50 (Fast)</option>
                    <option value="NIFTY200">Nifty 200 (Balanced)</option>
                    <option value="NIFTY500">Nifty 500 (Full)</option>
                  </select>
                </div>

                {/* Min Score Filter */}
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">Min Score: {filterScore}</label>
                  <input
                    type="range"
                    min={0}
                    max={80}
                    step={5}
                    value={filterScore}
                    onChange={e => setFilterScore(Number(e.target.value))}
                    className="w-28"
                  />
                </div>

                {/* Start Button */}
                <button
                  id="start-screener-btn"
                  onClick={handleStartRun}
                  disabled={loading}
                  className="ml-auto flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-sm disabled:opacity-60 transition-all"
                >
                  {loading ? (
                    <RefreshCw size={15} className="animate-spin" />
                  ) : (
                    <Play size={15} />
                  )}
                  {loading ? "Running..." : "Start Research Scan"}
                </button>
              </div>
            </div>

            {/* Progress */}
            {runStatus && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-slate-700">
                    {runStatus.status === "COMPLETED" ? "✅ Scan Complete" : `⚡ Scanning ${runStatus.mode} universe...`}
                  </div>
                  <div className="text-xs text-slate-500">
                    {runStatus.processed}/{runStatus.total_symbols} stocks
                  </div>
                </div>
                <ProgressBar value={runStatus.progress_pct} />
                <div className="mt-3 grid grid-cols-4 gap-3 text-center">
                  <div className="bg-slate-50 rounded-lg p-2 border border-slate-100">
                    <div className="text-lg font-black text-slate-700">{runStatus.passed_filter1_liquidity}</div>
                    <div className="text-[9px] uppercase font-bold text-slate-400">Liquid</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-2 border border-blue-100">
                    <div className="text-lg font-black text-blue-700">{runStatus.passed_filter2_fundamental}</div>
                    <div className="text-[9px] uppercase font-bold text-blue-400">Fundamentals</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-2 border border-purple-100">
                    <div className="text-lg font-black text-purple-700">{runStatus.passed_filter3_technical}</div>
                    <div className="text-[9px] uppercase font-bold text-purple-400">Technical</div>
                  </div>
                  <div className="bg-emerald-50 rounded-lg p-2 border border-emerald-100">
                    <div className="text-lg font-black text-emerald-700">{runStatus.signals_count}</div>
                    <div className="text-[9px] uppercase font-bold text-emerald-400">Signals</div>
                  </div>
                </div>
                {runStatus.current_symbol && runStatus.status !== "COMPLETED" && (
                  <div className="text-xs text-slate-400 mt-2">Analyzing: {runStatus.current_symbol}</div>
                )}
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-xl px-4 py-3 flex items-center gap-2">
                <AlertCircle size={15} />
                {error}
              </div>
            )}

            {/* Signals Grid */}
            {filteredSignals.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-black text-slate-800 text-lg">
                    {filteredSignals.length} Signals Found
                  </h2>
                  <div className="text-xs text-slate-500">Sorted by Confidence Score</div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  {filteredSignals.map((sig, i) => (
                    <SignalCard key={sig.symbol + i} signal={sig} capital={capital} />
                  ))}
                </div>
              </div>
            )}

            {/* Empty State */}
            {runStatus?.status === "COMPLETED" && filteredSignals.length === 0 && (
              <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
                <div className="text-4xl mb-3">🔍</div>
                <div className="text-lg font-bold text-slate-600">No signals found</div>
                <div className="text-sm text-slate-400 mt-1">
                  Try lowering the Min Score filter or changing the mode/universe
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
