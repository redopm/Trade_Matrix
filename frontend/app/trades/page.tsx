"use client";

import { useEffect, useState } from "react";
import { tradesApi, type Trade, type PortfolioStats } from "@/lib/api";

function formatINR(amount: number | null | undefined, decimals = 0): string {
  if (amount == null) return "—";
  const formatted = Math.abs(amount).toLocaleString("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
  return `${amount < 0 ? "-" : ""}₹${formatted}`;
}

function pnlColor(v: number | null | undefined): string {
  if (v == null) return "var(--text-muted)";
  if (v > 0) return "var(--accent-green)";
  if (v < 0) return "var(--accent-red)";
  return "var(--text-muted)";
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    OPEN: "badge-blue",
    CLOSED_TARGET: "badge-green",
    CLOSED_SL: "badge-red",
    CLOSED_RSI: "badge-purple",
    CLOSED_MANUAL: "",
    CANCELLED: "",
  };
  const labels: Record<string, string> = {
    OPEN: "Open",
    CLOSED_TARGET: "Target ✓",
    CLOSED_SL: "SL Hit",
    CLOSED_RSI: "RSI Exit",
    CLOSED_MANUAL: "Manual",
    CANCELLED: "Cancelled",
  };
  return (
    <span className={styles[status] || "badge-gold"}>
      {labels[status] || status}
    </span>
  );
}

function TradeRow({
  trade,
  onClose,
}: {
  trade: Trade;
  onClose: (id: number) => void;
}) {
  const pnl = trade.unrealized_pnl ?? trade.realized_pnl;
  const pnlPct = trade.unrealized_pnl_pct ?? trade.realized_pnl_pct;
  const isOpen = trade.status === "OPEN";

  return (
    <tr className="animate-fade-in">
      <td>
        <div>
          <div className="font-bold text-sm" style={{ color: "var(--text-bright)" }}>
            {trade.symbol?.replace(".NS", "")}
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            {trade.entry_date} · {trade.days_in_trade ?? 0}d
          </div>
        </div>
      </td>
      <td>
        <StatusBadge status={trade.status} />
      </td>
      <td>
        <div>
          <div className="font-mono font-bold" style={{ color: "var(--text-primary)" }}>
            ₹{trade.entry_price?.toFixed(2)}
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            {trade.quantity} qty
          </div>
        </div>
      </td>
      <td>
        <div className="font-mono font-bold" style={{ color: "var(--accent-red)" }}>
          ₹{trade.stop_loss?.toFixed(2)}
        </div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          ATR-based
        </div>
      </td>
      <td>
        <div className="font-mono font-bold" style={{ color: "var(--accent-green)" }}>
          ₹{trade.target_price?.toFixed(2)}
        </div>
      </td>
      <td>
        {trade.current_price ? (
          <div>
            <div className="font-mono font-bold" style={{ color: "var(--text-primary)" }}>
              ₹{trade.current_price?.toFixed(2)}
            </div>
            {trade.current_rsi && (
              <div
                className="text-xs font-mono"
                style={{
                  color:
                    trade.current_rsi > 70
                      ? "var(--accent-gold)"
                      : "var(--text-muted)",
                }}
              >
                RSI: {trade.current_rsi?.toFixed(1)}
              </div>
            )}
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>—</span>
        )}
      </td>
      <td>
        {pnl != null ? (
          <div>
            <div
              className="font-mono font-bold text-sm"
              style={{ color: pnlColor(pnl) }}
            >
              {formatINR(pnl)}
            </div>
            <div
              className="text-xs font-mono font-bold"
              style={{ color: pnlColor(pnlPct) }}
            >
              {pnlPct != null
                ? `${pnlPct >= 0 ? "+" : ""}${pnlPct?.toFixed(2)}%`
                : "—"}
            </div>
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>—</span>
        )}
      </td>
      <td>
        {isOpen && (
          <button
            className="btn-ghost text-xs py-1"
            style={{ color: "var(--accent-red)", borderColor: "rgba(255,68,102,0.3)" }}
            onClick={() => onClose(trade.id)}
          >
            Close
          </button>
        )}
        {!isOpen && trade.exit_reason && (
          <span
            className="text-xs max-w-24 truncate block"
            style={{ color: "var(--text-muted)" }}
            title={trade.exit_reason}
          >
            {trade.exit_reason}
          </span>
        )}
      </td>
    </tr>
  );
}

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "OPEN" | "CLOSED">("ALL");
  const [updating, setUpdating] = useState(false);

  const load = async () => {
    try {
      const [tradesRes, statsRes] = await Promise.all([
        tradesApi.listTrades({ page_size: 100 }),
        tradesApi.getStats(),
      ]);
      setTrades(tradesRes.data.items || []);
      setStats(statsRes.data);
    } catch (e) {
      console.error("Failed to load trades:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCloseTrade = async (id: number) => {
    if (!confirm("Close this trade at current market price?")) return;
    try {
      await tradesApi.closeTrade(id, undefined, "Manual close");
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleUpdateAll = async () => {
    setUpdating(true);
    try {
      await tradesApi.updateAll();
      setTimeout(() => {
        load();
        setUpdating(false);
      }, 3000);
    } catch (e: any) {
      alert(`Error: ${e.message}`);
      setUpdating(false);
    }
  };

  const filtered = trades.filter((t) => {
    if (filter === "OPEN") return t.status === "OPEN";
    if (filter === "CLOSED") return t.status !== "OPEN";
    return true;
  });

  return (
    <div className="flex flex-col gap-6 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black" style={{ color: "var(--text-bright)" }}>
            Paper Trades
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Virtual trade tracker · ATR-based SL · RSI exit
          </p>
        </div>
        <button
          onClick={handleUpdateAll}
          disabled={updating}
          className="btn-primary flex items-center gap-2 px-4 py-2"
        >
          {updating ? (
            <>
              <div className="live-indicator" />
              Updating...
            </>
          ) : (
            "🔄 Update P&L"
          )}
        </button>
      </div>

      {/* Portfolio Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="stat-card card-green">
            <div className="stat-label">Realized P&L</div>
            <div
              className="stat-value"
              style={{ color: (stats.realized_pnl ?? 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}
            >
              {formatINR(stats.realized_pnl)}
            </div>
            <div className="stat-change" style={{ color: "var(--text-muted)" }}>
              {stats.closed_trades} closed trades
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Unrealized P&L</div>
            <div
              className="stat-value"
              style={{ color: (stats.unrealized_pnl ?? 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}
            >
              {formatINR(stats.unrealized_pnl)}
            </div>
            <div className="stat-change" style={{ color: "var(--text-muted)" }}>
              {stats.open_trades} open positions
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Win Rate</div>
            <div
              className="stat-value"
              style={{ color: (stats.win_rate ?? 0) >= 50 ? "var(--accent-green)" : "var(--accent-red)" }}
            >
              {stats.win_rate?.toFixed(1)}%
            </div>
            <div className="stat-change" style={{ color: "var(--text-muted)" }}>
              {stats.winning_trades}W / {stats.losing_trades}L
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Expectancy</div>
            <div
              className="stat-value"
              style={{ color: (stats.expectancy ?? 0) >= 0 ? "var(--accent-green)" : "var(--accent-red)" }}
            >
              {stats.expectancy?.toFixed(2) ?? "—"}%
            </div>
            <div className="stat-change" style={{ color: "var(--text-muted)" }}>
              Per trade average
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        {(["ALL", "OPEN", "CLOSED"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`filter-chip ${filter === f ? "active" : ""}`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-sm" style={{ color: "var(--text-muted)" }}>
          {filtered.length} trades
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="card p-8">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-14 rounded mb-2" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-5xl mb-4">📊</div>
          <p className="text-lg font-bold" style={{ color: "var(--text-bright)" }}>
            No trades yet
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
            Run the screener, find signals, and add them as paper trades
          </p>
          <a href="/screener" className="btn-primary inline-block mt-4 px-6 py-2">
            Go to Screener
          </a>
        </div>
      ) : (
        <div className="card">
          <div className="table-container rounded-xl border-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Entry</th>
                  <th>Stop Loss</th>
                  <th>Target</th>
                  <th>Current</th>
                  <th>P&L</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade) => (
                  <TradeRow
                    key={trade.id}
                    trade={trade}
                    onClose={handleCloseTrade}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
