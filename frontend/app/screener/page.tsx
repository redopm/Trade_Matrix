"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  screenerApi,
  tradesApi,
  createScreenerWebSocket,
  type ScreenerRunStatus,
  type Signal,
} from "@/lib/api";
import { ChartModal } from "@/components/ChartModal";
import { 
  CheckCircle2, 
  XCircle, 
  PlayCircle, 
  SearchX, 
  ArrowUp, 
  ArrowDown, 
  Minus,
  Check,
  X,
  Plus
} from "lucide-react";

// --- Filter Pill ---
function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button 
      onClick={onClick} 
      className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors ${
        active 
          ? "bg-slate-800 text-white shadow-sm" 
          : "bg-white text-slate-500 hover:bg-slate-100 border border-slate-200"
      }`}
    >
      {label}
    </button>
  );
}

// --- Filter Badge (pass/fail indicator) ---
function FilterBadge({ passed }: { passed: boolean }) {
  return (
    <span className={`flex items-center justify-center w-5 h-5 rounded-md ${passed ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-500"}`}>
      {passed ? <Check size={12} strokeWidth={3} /> : <Minus size={12} strokeWidth={3} />}
    </span>
  );
}

// --- Progress Panel ---
function ScreenerProgress({
  status,
  onClose,
}: {
  status: ScreenerRunStatus;
  onClose: () => void;
}) {
  const isDone = status.status === "COMPLETED" || status.status === "FAILED";

  return (
    <div className={`bg-white rounded-xl p-6 border shadow-sm ${
      status.status === "FAILED" ? "border-red-200 bg-red-50" :
      status.status === "COMPLETED" ? "border-emerald-200 bg-emerald-50" :
      "border-blue-200"
    }`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {!isDone && <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />}
          <span className={`font-bold text-sm ${
            status.status === "RUNNING" ? "text-blue-700" :
            status.status === "COMPLETED" ? "text-emerald-700" :
            "text-red-700"
          }`}>
            {status.status === "RUNNING" ? "Screener Running..." :
             status.status === "COMPLETED" ? "Screener Complete!" :
             "Screener Failed"}
          </span>
        </div>
        {isDone && (
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        )}
      </div>

      <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden mb-4">
        <div 
          className={`h-full transition-all duration-300 ${
            status.status === "FAILED" ? "bg-red-500" :
            status.status === "COMPLETED" ? "bg-emerald-500" :
            "bg-blue-500"
          }`}
          style={{ width: `${status.progress_pct}%` }} 
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm bg-white p-4 rounded-lg border border-slate-100">
        <div>
          <div className="text-xs font-semibold text-slate-500 mb-1">Progress</div>
          <div className="font-mono font-bold text-blue-600">
            {status.processed}/{status.total_symbols} ({status.progress_pct}%)
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-500 mb-1">Passed All Filters</div>
          <div className="font-mono font-bold text-emerald-600">
            {status.passed} signals
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-500 mb-1">Current Symbol</div>
          <div className="font-mono text-xs font-bold text-slate-700">
            {status.current_symbol || "-"}
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-500 mb-1">Failed (Data/Fund/Tech)</div>
          <div className="font-mono text-xs font-bold text-red-600">
            {status.failed_data}/{status.failed_fundamental}/{status.failed_technical}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Signal Detail Modal ---
function SignalDetailModal({
  signal,
  onClose,
  onTrade,
}: {
  signal: Signal;
  onClose: () => void;
  onTrade: (signalId: number) => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-8 border border-slate-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-2xl font-black text-slate-900">
              {signal.symbol?.replace(".NS", "")}
            </h3>
            <p className="text-sm font-medium text-slate-500 mt-1">
              {signal.company_name} &bull; {signal.sector}
            </p>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
            <X size={24} />
          </button>
        </div>

        {/* Filter Grid */}
        <div className="mb-6">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
            Filter Results
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "ROCE > 15%", passed: signal.passed_roce, value: `${signal.roce?.toFixed(1) ?? "N/A"}%` },
              { label: "D/E < 1.0", passed: signal.passed_debt_to_equity, value: signal.debt_to_equity?.toFixed(2) ?? "N/A" },
              { label: "Price > 200 EMA", passed: signal.passed_ema_200, value: `₹${signal.ema_200?.toFixed(0) ?? "N/A"}` },
              { label: "RSI < 30", passed: signal.passed_rsi, value: signal.rsi_14?.toFixed(1) ?? "N/A" },
              { label: "Piotroski ≥ 7", passed: signal.passed_piotroski, value: `${signal.piotroski_f_score ?? "N/A"}/9` },
              { label: "Event Risk OK", passed: signal.passed_earnings_blackout, value: "±3 days" },
            ].map((f) => (
              <div
                key={f.label}
                className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100"
              >
                <div>
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    {f.label}
                  </div>
                  <div className="text-sm font-mono font-bold text-slate-900 mt-0.5">
                    {f.value}
                  </div>
                </div>
                {f.passed ? (
                  <CheckCircle2 size={18} className="text-emerald-500" />
                ) : (
                  <XCircle size={18} className="text-red-500" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Trade Parameters */}
        <div className="mb-6">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
            Suggested Trade Parameters
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-xl bg-blue-50 border border-blue-100">
              <div className="text-[11px] font-bold text-blue-600 uppercase mb-1">Entry</div>
              <div className="font-mono font-bold text-slate-900">
                ₹{signal.suggested_entry?.toFixed(2) ?? "-"}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-red-50 border border-red-100">
              <div className="text-[11px] font-bold text-red-600 uppercase mb-1">Stop Loss</div>
              <div className="font-mono font-bold text-red-700">
                ₹{signal.suggested_sl?.toFixed(2) ?? "-"}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100">
              <div className="text-[11px] font-bold text-emerald-600 uppercase mb-1">Target</div>
              <div className="font-mono font-bold text-emerald-700">
                ₹{signal.suggested_target?.toFixed(2) ?? "-"}
              </div>
            </div>
          </div>
          <div className="text-center mt-4 p-3 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-sm font-bold text-slate-700">
              Risk:Reward = <span className="text-amber-600">{signal.risk_reward_ratio?.toFixed(2) ?? "-"}</span>
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        {signal.passed_all && !signal.is_traded && (
          <button
            className="w-full flex justify-center items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white font-bold py-3.5 rounded-xl transition-colors shadow-sm"
            onClick={() => onTrade(signal.id)}
          >
            <Plus size={18} /> Add to Paper Trades
          </button>
        )}
        {signal.is_traded && (
          <div className="w-full text-center py-3.5 bg-slate-100 text-slate-500 font-bold rounded-xl border border-slate-200">
            Already added to paper trades
          </div>
        )}
      </div>
    </div>
  );
}

// --- Main Screener Page ---
export default function ScreenerPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [runStatus, setRunStatus] = useState<ScreenerRunStatus | null>(null);
  const [passedOnly, setPassedOnly] = useState(true);
  const [sortBy, setSortBy] = useState<"composite_score" | "rsi_14" | "roce">("composite_score");
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [viewChartSymbol, setViewChartSymbol] = useState<string | null>(null);
  const [tradeSuccess, setTradeSuccess] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadSignals = useCallback(async () => {
    try {
      const res = await screenerApi.getResults({
        passed_only: passedOnly,
        sort_by: sortBy,
        page_size: 100,
      });
      setSignals(res.data.items || []);
    } catch (e) {
      console.error("Failed to load signals:", e);
    } finally {
      setLoading(false);
    }
  }, [passedOnly, sortBy]);

  useEffect(() => {
    loadSignals();
  }, [loadSignals]);

  const startScreener = async () => {
    try {
      const res = await screenerApi.startRun();
      const runId = res.data.run_id;

      if (wsRef.current) wsRef.current.close();
      wsRef.current = createScreenerWebSocket(
        runId,
        (data) => {
          setRunStatus(data);
          if (data.status === "COMPLETED") {
            loadSignals();
          }
        },
        () => console.log("WS closed")
      );
    } catch (e: any) {
      alert(`Failed to start screener: ${e.message}`);
    }
  };

  const handleTrade = async (signalId: number) => {
    try {
      await tradesApi.createTrade(signalId);
      setTradeSuccess("Trade added to paper portfolio successfully!");
      setSelectedSignal(null);
      setTimeout(() => setTradeSuccess(null), 4000);
      loadSignals();
    } catch (e: any) {
      alert(`Failed to create trade: ${e.message}`);
    }
  };

  const sortedSignals = [...signals].sort((a, b) => {
    if (sortBy === "composite_score") return (b.composite_score ?? 0) - (a.composite_score ?? 0);
    if (sortBy === "rsi_14") return (a.rsi_14 ?? 99) - (b.rsi_14 ?? 99);
    if (sortBy === "roce") return (b.roce ?? 0) - (a.roce ?? 0);
    return 0;
  });

  return (
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Alpha Screener
          </h1>
          <p className="text-sm mt-2 text-slate-500 font-medium">
            Nifty 500 &bull; Fundamental + Technical Filter Engine
          </p>
        </div>
        <button
          onClick={startScreener}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50"
          disabled={runStatus?.status === "RUNNING"}
        >
          {runStatus?.status === "RUNNING" ? (
            <><div className="w-2 h-2 rounded-full bg-white animate-pulse" /> Running...</>
          ) : (
            <><PlayCircle size={18} /> Run Screener</>
          )}
        </button>
      </div>

      {/* Success Toast */}
      {tradeSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 p-4 rounded-xl flex items-center gap-3 shadow-sm font-bold text-sm">
          <CheckCircle2 size={18} /> {tradeSuccess}
        </div>
      )}

      {/* Progress Panel */}
      {runStatus && (
        <ScreenerProgress status={runStatus} onClose={() => setRunStatus(null)} />
      )}

      {/* Filters Bar */}
      <div className="flex items-center gap-4 bg-white p-2 rounded-xl border border-slate-200 shadow-sm w-fit">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 pl-2">View:</div>
        <div className="flex gap-1">
          <FilterChip label="Passed Only" active={passedOnly} onClick={() => setPassedOnly(true)} />
          <FilterChip label="All Screened" active={!passedOnly} onClick={() => setPassedOnly(false)} />
        </div>
        
        <div className="w-px h-6 bg-slate-200 mx-1"></div>
        
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Sort:</div>
        <div className="flex gap-1">
          <FilterChip label="Score" active={sortBy === "composite_score"} onClick={() => setSortBy("composite_score")} />
          <FilterChip label="RSI" active={sortBy === "rsi_14"} onClick={() => setSortBy("rsi_14")} />
          <FilterChip label="ROCE" active={sortBy === "roce"} onClick={() => setSortBy("roce")} />
        </div>

        <div className="w-px h-6 bg-slate-200 mx-1"></div>
        
        <div className="text-sm font-bold text-slate-400 pr-3">
          {signals.length} results
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 flex-wrap text-xs font-bold text-slate-500">
        <span className="uppercase tracking-wider mr-2">Filter columns:</span>
        <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded border border-emerald-100">ROCE</span>
        <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded border border-emerald-100">D/E</span>
        <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-100">EMA</span>
        <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-100">RSI</span>
        <span className="px-2 py-1 bg-amber-50 text-amber-700 rounded border border-amber-100">F-Score</span>
        <span className="px-2 py-1 bg-slate-100 text-slate-700 rounded border border-slate-200">Event</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          {[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-lg mb-3 animate-pulse" />)}
        </div>
      ) : sortedSignals.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
            <SearchX className="text-slate-300" size={32} />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-2">No signals found</p>
          <p className="text-sm font-medium text-slate-500 max-w-sm mb-6">
            None of the stocks passed your active screener filters. Try running the screener to fetch fresh data.
          </p>
          <button className="bg-slate-900 hover:bg-slate-800 text-white font-bold px-6 py-2.5 rounded-lg transition-colors" onClick={startScreener}>
            Run Screener Now
          </button>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100">
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Symbol</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Price</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">RSI(14)</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">200 EMA</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">ROCE</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">D/E</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">F-Score</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Pattern</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Score</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">R:R</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Filters</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedSignals.map((sig, i) => (
                  <tr
                    key={sig.id || i}
                    className="border-b border-slate-100 hover:bg-blue-50/30 cursor-pointer transition-colors"
                    onClick={() => setSelectedSignal(sig)}
                  >
                    <td className="py-3 px-4">
                      <div>
                        <div className="font-bold text-sm text-slate-900">
                          {sig.symbol?.replace(".NS", "")}
                        </div>
                        <div className="text-[11px] font-medium text-slate-500 max-w-[120px] truncate">
                          {sig.company_name}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm font-semibold text-slate-700">₹{sig.signal_price?.toFixed(2)}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-mono text-sm font-bold ${(sig.rsi_14 ?? 100) < 30 ? "text-blue-600 bg-blue-50 px-2 py-0.5 rounded" : "text-slate-600"}`}>
                        {sig.rsi_14?.toFixed(1) ?? "-"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-semibold text-slate-600">
                        ₹{sig.ema_200?.toFixed(0) ?? "-"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                        {sig.roce?.toFixed(1) ?? "-"}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-semibold text-slate-600">
                        {sig.debt_to_equity?.toFixed(2) ?? "-"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-mono text-sm font-bold ${(sig.piotroski_f_score ?? 0) >= 7 ? "text-emerald-600" : "text-amber-600"}`}>
                        {sig.piotroski_f_score ?? "-"}/9
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {sig.pattern_name && sig.pattern_name !== "no_pattern" ? (
                        <div className="flex flex-col gap-1 items-start">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${(sig.pattern_confidence ?? 0) >= 0.70 ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200"}`}>
                            {sig.pattern_name.replace("_", " ").toUpperCase()}
                            <span className="opacity-70 ml-1 font-mono">{((sig.pattern_confidence ?? 0) * 100).toFixed(0)}%</span>
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm font-medium text-slate-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-amber-600">
                          {sig.composite_score?.toFixed(1) ?? "-"}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-bold text-blue-600">
                        {sig.risk_reward_ratio?.toFixed(2) ?? "-"}
                      </span>
                    </td>
                    <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1">
                        <FilterBadge passed={sig.passed_roce} />
                        <FilterBadge passed={sig.passed_debt_to_equity} />
                        <FilterBadge passed={sig.passed_ema_200} />
                        <FilterBadge passed={sig.passed_rsi} />
                        <FilterBadge passed={sig.passed_piotroski} />
                        <FilterBadge passed={sig.passed_earnings_blackout} />
                      </div>
                    </td>
                    <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                      {sig.passed_all && !sig.is_traded ? (
                        <button
                          className="flex items-center gap-1 bg-white border border-slate-300 hover:border-slate-900 hover:bg-slate-900 hover:text-white text-slate-700 text-[11px] font-bold py-1 px-2 rounded transition-colors"
                          onClick={() => handleTrade(sig.id)}
                        >
                          <Plus size={12} /> Trade
                        </button>
                      ) : sig.is_traded ? (
                        <span className="text-[11px] font-bold text-slate-400 bg-slate-50 border border-slate-100 px-2 py-1 rounded">
                          Traded
                        </span>
                      ) : (
                        <span className="text-[11px] font-bold text-red-500 bg-red-50 border border-red-100 px-2 py-1 rounded">
                          Failed
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedSignal && (
        <SignalDetailModal
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
          onTrade={handleTrade}
        />
      )}

      {viewChartSymbol && (
        <ChartModal
          symbol={viewChartSymbol}
          chartPath=""
          onClose={() => setViewChartSymbol(null)}
        />
      )}
    </div>
  );
}
