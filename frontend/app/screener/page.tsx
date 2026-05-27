"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  screenerApi,
  tradesApi,
  createScreenerWebSocket,
  type Signal,
  type ScreenerRunStatus,
} from "@/lib/api";

// ── Filter Pill ────────────────────────────────────────────────────────────────
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
    <button onClick={onClick} className={`filter-chip ${active ? "active" : ""}`}>
      {label}
    </button>
  );
}

// ── Filter Badge (pass/fail indicator) ────────────────────────────────────────
function FilterBadge({ passed }: { passed: boolean }) {
  return (
    <span className={`indicator-pill ${passed ? "indicator-pass" : "indicator-fail"}`}>
      {passed ? "✓" : "✗"}
    </span>
  );
}

// ── Progress Panel ─────────────────────────────────────────────────────────────
function ScreenerProgress({
  status,
  onClose,
}: {
  status: ScreenerRunStatus;
  onClose: () => void;
}) {
  const isDone = status.status === "COMPLETED" || status.status === "FAILED";

  return (
    <div
      className="card p-5 border"
      style={{
        borderColor:
          status.status === "FAILED"
            ? "rgba(255,68,102,0.3)"
            : status.status === "COMPLETED"
            ? "rgba(0,245,160,0.3)"
            : "rgba(79,172,254,0.3)",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {!isDone && <div className="live-indicator" />}
          <span className="font-bold text-sm" style={{ color: "var(--text-bright)" }}>
            {status.status === "RUNNING"
              ? "Screener Running..."
              : status.status === "COMPLETED"
              ? "✅ Screener Complete!"
              : "❌ Screener Failed"}
          </span>
        </div>
        {isDone && (
          <button
            onClick={onClose}
            className="text-xs"
            style={{ color: "var(--text-muted)" }}
          >
            ✕ Dismiss
          </button>
        )}
      </div>

      <div className="progress-bar mb-3">
        <div className="progress-fill" style={{ width: `${status.progress_pct}%` }} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
            Progress
          </div>
          <div className="font-mono font-bold" style={{ color: "var(--accent-blue)" }}>
            {status.processed}/{status.total_symbols} ({status.progress_pct}%)
          </div>
        </div>
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
            Passed All Filters
          </div>
          <div className="font-mono font-bold" style={{ color: "var(--accent-green)" }}>
            {status.passed} signals
          </div>
        </div>
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
            Current Symbol
          </div>
          <div
            className="font-mono text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            {status.current_symbol || "—"}
          </div>
        </div>
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
            Failed (Data/Fund/Tech)
          </div>
          <div className="font-mono text-xs" style={{ color: "var(--accent-red)" }}>
            {status.failed_data}/{status.failed_fundamental}/{status.failed_technical}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Signal Detail Modal ────────────────────────────────────────────────────────
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
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="card p-6 max-w-lg w-full mx-4 animate-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3
              className="text-xl font-black"
              style={{ color: "var(--text-bright)" }}
            >
              {signal.symbol?.replace(".NS", "")}
            </h3>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {signal.company_name} · {signal.sector}
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--text-muted)" }} className="text-xl">
            ✕
          </button>
        </div>

        {/* Filter Grid */}
        <div className="mb-5">
          <div
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "var(--text-muted)" }}
          >
            Filter Results
          </div>
          <div className="grid grid-cols-2 gap-2">
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
                className="flex items-center justify-between p-2 rounded-lg"
                style={{ background: "rgba(255,255,255,0.03)" }}
              >
                <div>
                  <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {f.label}
                  </div>
                  <div
                    className="text-sm font-mono font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {f.value}
                  </div>
                </div>
                <FilterBadge passed={f.passed} />
              </div>
            ))}
          </div>
        </div>

        {/* Trade Parameters */}
        <div className="mb-5">
          <div
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: "var(--text-muted)" }}
          >
            Suggested Trade Parameters
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-xl" style={{ background: "rgba(79,172,254,0.08)" }}>
              <div className="text-xs mb-1" style={{ color: "var(--accent-blue)" }}>
                Entry
              </div>
              <div
                className="font-mono font-bold"
                style={{ color: "var(--text-bright)" }}
              >
                ₹{signal.suggested_entry?.toFixed(2) ?? "—"}
              </div>
            </div>
            <div className="p-3 rounded-xl" style={{ background: "rgba(255,68,102,0.08)" }}>
              <div className="text-xs mb-1" style={{ color: "var(--accent-red)" }}>
                Stop Loss (ATR)
              </div>
              <div className="font-mono font-bold" style={{ color: "var(--accent-red)" }}>
                ₹{signal.suggested_sl?.toFixed(2) ?? "—"}
              </div>
            </div>
            <div className="p-3 rounded-xl" style={{ background: "rgba(0,245,160,0.08)" }}>
              <div className="text-xs mb-1" style={{ color: "var(--accent-green)" }}>
                Target (12%)
              </div>
              <div className="font-mono font-bold" style={{ color: "var(--accent-green)" }}>
                ₹{signal.suggested_target?.toFixed(2) ?? "—"}
              </div>
            </div>
          </div>
          <div className="text-center mt-3">
            <span
              className="text-sm font-bold font-mono"
              style={{ color: "var(--accent-gold)" }}
            >
              R:R = {signal.risk_reward_ratio?.toFixed(2) ?? "—"}
            </span>
            <span className="text-xs ml-2" style={{ color: "var(--text-muted)" }}>
              (Target ÷ Risk)
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        {signal.passed_all && !signal.is_traded && (
          <button
            className="btn-primary w-full text-sm py-3"
            onClick={() => onTrade(signal.id)}
          >
            📊 Add to Paper Trades
          </button>
        )}
        {signal.is_traded && (
          <div
            className="text-center py-2 text-sm font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            ✅ Already added to paper trades
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Screener Page ─────────────────────────────────────────────────────────
export default function ScreenerPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [runStatus, setRunStatus] = useState<ScreenerRunStatus | null>(null);
  const [passedOnly, setPassedOnly] = useState(true);
  const [sortBy, setSortBy] = useState<"composite_score" | "rsi_14" | "roce">(
    "composite_score"
  );
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
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

      // Connect WebSocket for real-time progress
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
      setTradeSuccess("Trade added to paper portfolio! 🎉");
      setSelectedSignal(null);
      setTimeout(() => setTradeSuccess(null), 4000);
      loadSignals();
    } catch (e: any) {
      alert(`Failed to create trade: ${e.message}`);
    }
  };

  const sortedSignals = [...signals].sort((a, b) => {
    if (sortBy === "composite_score")
      return (b.composite_score ?? 0) - (a.composite_score ?? 0);
    if (sortBy === "rsi_14") return (a.rsi_14 ?? 99) - (b.rsi_14 ?? 99);
    if (sortBy === "roce") return (b.roce ?? 0) - (a.roce ?? 0);
    return 0;
  });

  return (
    <div className="flex flex-col gap-6 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black" style={{ color: "var(--text-bright)" }}>
            Alpha Screener
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Nifty 500 · Fundamental + Technical Filter Engine
          </p>
        </div>
        <button
          onClick={startScreener}
          className="btn-primary flex items-center gap-2 px-5 py-2.5"
          disabled={runStatus?.status === "RUNNING"}
        >
          {runStatus?.status === "RUNNING" ? (
            <>
              <div className="live-indicator" />
              Running...
            </>
          ) : (
            <>⚡ Run Screener</>
          )}
        </button>
      </div>

      {/* Success Toast */}
      {tradeSuccess && (
        <div
          className="p-4 rounded-xl text-sm font-medium animate-fade-in"
          style={{
            background: "rgba(0, 245, 160, 0.1)",
            border: "1px solid rgba(0, 245, 160, 0.3)",
            color: "var(--accent-green)",
          }}
        >
          {tradeSuccess}
        </div>
      )}

      {/* Progress Panel */}
      {runStatus && (
        <ScreenerProgress
          status={runStatus}
          onClose={() => setRunStatus(null)}
        />
      )}

      {/* Filters Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div
          className="text-xs font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}
        >
          View:
        </div>
        <FilterChip
          label="Passed Only"
          active={passedOnly}
          onClick={() => setPassedOnly(true)}
        />
        <FilterChip
          label="All Screened"
          active={!passedOnly}
          onClick={() => setPassedOnly(false)}
        />
        <div className="ml-4 text-xs font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}>
          Sort:
        </div>
        <FilterChip
          label="Score ↓"
          active={sortBy === "composite_score"}
          onClick={() => setSortBy("composite_score")}
        />
        <FilterChip
          label="RSI ↑"
          active={sortBy === "rsi_14"}
          onClick={() => setSortBy("rsi_14")}
        />
        <FilterChip
          label="ROCE ↓"
          active={sortBy === "roce"}
          onClick={() => setSortBy("roce")}
        />
        <div className="ml-auto text-sm" style={{ color: "var(--text-muted)" }}>
          {signals.length} results
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 flex-wrap text-xs" style={{ color: "var(--text-muted)" }}>
        <span>Filter columns:</span>
        <span className="indicator-pill indicator-pass">✓ ROCE</span>
        <span className="indicator-pill indicator-pass">✓ D/E</span>
        <span className="indicator-pill indicator-pass">✓ EMA</span>
        <span className="indicator-pill indicator-pass">✓ RSI</span>
        <span className="indicator-pill indicator-pass">✓ F-Score</span>
        <span className="indicator-pill indicator-pass">✓ Event</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="card p-8 text-center">
          <div className="skeleton h-8 w-48 mx-auto mb-4 rounded" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-12 rounded mb-2" />
          ))}
        </div>
      ) : sortedSignals.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-5xl mb-4">🔍</div>
          <p className="text-lg font-bold" style={{ color: "var(--text-bright)" }}>
            No signals found
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
            Run the screener to find stocks passing all filters
          </p>
          <button className="btn-primary mt-4 px-6 py-2" onClick={startScreener}>
            ⚡ Run Screener Now
          </button>
        </div>
      ) : (
        <div className="card">
          <div className="table-container rounded-xl border-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Price</th>
                  <th>RSI(14)</th>
                  <th>200 EMA</th>
                  <th>ROCE</th>
                  <th>D/E</th>
                  <th>F-Score</th>
                  <th>Score</th>
                  <th>R:R</th>
                  <th>Filters</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedSignals.map((sig, i) => (
                  <tr
                    key={sig.id || i}
                    className="cursor-pointer"
                    onClick={() => setSelectedSignal(sig)}
                    style={{
                      animationDelay: `${i * 30}ms`,
                    }}
                  >
                    <td>
                      <div>
                        <div
                          className="font-bold text-sm"
                          style={{ color: "var(--text-bright)" }}
                        >
                          {sig.symbol?.replace(".NS", "")}
                        </div>
                        <div
                          className="text-xs max-w-32 truncate"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {sig.company_name}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="price-display">
                        ₹{sig.signal_price?.toFixed(2)}
                      </span>
                    </td>
                    <td>
                      <span
                        className="font-mono text-sm font-bold"
                        style={{
                          color:
                            (sig.rsi_14 ?? 100) < 20
                              ? "var(--accent-gold)"
                              : "var(--accent-blue)",
                        }}
                      >
                        {sig.rsi_14?.toFixed(1) ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                        ₹{sig.ema_200?.toFixed(0) ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span
                        className="font-mono text-sm font-bold"
                        style={{ color: "var(--accent-green)" }}
                      >
                        {sig.roce?.toFixed(1) ?? "—"}%
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                        {sig.debt_to_equity?.toFixed(2) ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span
                        className="font-mono text-sm font-bold"
                        style={{
                          color:
                            (sig.piotroski_f_score ?? 0) >= 7
                              ? "var(--accent-green)"
                              : "var(--accent-red)",
                        }}
                      >
                        {sig.piotroski_f_score ?? "—"}/9
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <span
                          className="font-mono text-sm font-bold"
                          style={{ color: "var(--accent-gold)" }}
                        >
                          {sig.composite_score?.toFixed(1) ?? "—"}
                        </span>
                        <div className="progress-bar" style={{ width: "40px" }}>
                          <div
                            className="progress-fill"
                            style={{
                              width: `${sig.composite_score ?? 0}%`,
                              background: "var(--gradient-gold)",
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td>
                      <span
                        className="font-mono text-sm font-bold"
                        style={{ color: "var(--accent-blue)" }}
                      >
                        {sig.risk_reward_ratio?.toFixed(2) ?? "—"}
                      </span>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1">
                        <FilterBadge passed={sig.passed_roce} />
                        <FilterBadge passed={sig.passed_debt_to_equity} />
                        <FilterBadge passed={sig.passed_ema_200} />
                        <FilterBadge passed={sig.passed_rsi} />
                        <FilterBadge passed={sig.passed_piotroski} />
                        <FilterBadge passed={sig.passed_earnings_blackout} />
                      </div>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {sig.passed_all && !sig.is_traded ? (
                        <button
                          className="btn-ghost text-xs py-1 px-2"
                          onClick={() => handleTrade(sig.id)}
                          style={{
                            borderColor: "rgba(0, 245, 160, 0.3)",
                            color: "var(--accent-green)",
                          }}
                        >
                          + Trade
                        </button>
                      ) : sig.is_traded ? (
                        <span
                          className="text-xs"
                          style={{ color: "var(--text-muted)" }}
                        >
                          Traded
                        </span>
                      ) : (
                        <span
                          className="badge-red text-xs"
                        >
                          ✗
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

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
          onTrade={handleTrade}
        />
      )}
    </div>
  );
}
