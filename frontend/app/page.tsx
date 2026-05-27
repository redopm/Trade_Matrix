"use client";

import { useEffect, useState } from "react";
import { dashboardApi, tradesApi, type PortfolioStats, type Signal } from "@/lib/api";

// ── Helper Functions ──────────────────────────────────────────────────────────
function formatINR(amount: number | null | undefined): string {
  if (amount == null) return "N/A";
  if (Math.abs(amount) >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (Math.abs(amount) >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

function pnlClass(v: number | null | undefined): string {
  if (v == null || v === 0) return "pnl-neutral";
  return v > 0 ? "pnl-positive" : "pnl-negative";
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  accent,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "green" | "red" | "blue" | "gold" | "purple";
  icon?: string;
}) {
  const accentColors = {
    green: "var(--accent-green)",
    red: "var(--accent-red)",
    blue: "var(--accent-blue)",
    gold: "var(--accent-gold)",
    purple: "var(--accent-purple)",
  };
  const color = accent ? accentColors[accent] : "var(--text-bright)";

  return (
    <div className="stat-card">
      <div className="flex items-start justify-between">
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value mt-2" style={{ color }}>
            {value}
          </div>
          {sub && (
            <div className="stat-change" style={{ color: "var(--text-muted)" }}>
              {sub}
            </div>
          )}
        </div>
        {icon && (
          <div
            className="text-2xl p-2 rounded-xl"
            style={{ background: "rgba(255,255,255,0.04)" }}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Signal Row ────────────────────────────────────────────────────────────────
function SignalRow({ signal }: { signal: any }) {
  return (
    <tr className="animate-fade-in">
      <td>
        <div>
          <div className="font-bold text-sm" style={{ color: "var(--text-bright)" }}>
            {signal.symbol?.replace(".NS", "")}
          </div>
          <div
            className="text-xs truncate max-w-32"
            style={{ color: "var(--text-muted)" }}
          >
            {signal.company_name}
          </div>
        </div>
      </td>
      <td>
        <span
          className="text-xs px-2 py-0.5 rounded"
          style={{
            background: "rgba(255,255,255,0.05)",
            color: "var(--text-secondary)",
          }}
        >
          {signal.sector || "—"}
        </span>
      </td>
      <td>
        <span className="price-display">₹{signal.signal_price?.toFixed(2)}</span>
      </td>
      <td>
        <span
          className="font-mono text-sm"
          style={{
            color:
              signal.rsi_14 < 20
                ? "var(--accent-gold)"
                : "var(--accent-blue)",
          }}
        >
          {signal.rsi_14?.toFixed(1) ?? "—"}
        </span>
      </td>
      <td>
        <span className="font-mono text-sm" style={{ color: "var(--accent-green)" }}>
          {signal.roce?.toFixed(1) ?? "—"}%
        </span>
      </td>
      <td>
        <div
          className="flex items-center gap-1 font-mono text-sm font-bold"
          style={{ color: "var(--accent-gold)" }}
        >
          {signal.composite_score?.toFixed(1) ?? "—"}
          <div
            className="h-1.5 rounded-full ml-1"
            style={{
              width: `${Math.min(60, (signal.composite_score / 100) * 60)}px`,
              background: "var(--gradient-gold)",
              opacity: 0.7,
            }}
          />
        </div>
      </td>
      <td>
        <span className="font-mono text-sm" style={{ color: "var(--accent-green)" }}>
          {signal.risk_reward_ratio?.toFixed(2) ?? "—"}
        </span>
      </td>
    </tr>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [recentSignals, setRecentSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [summaryRes, statsRes, signalsRes] = await Promise.all([
          dashboardApi.getSummary(),
          tradesApi.getStats(),
          dashboardApi.getRecentSignals(8),
        ]);
        setSummary(summaryRes.data);
        setStats(statsRes.data);
        setRecentSignals(signalsRes.data);
      } catch (e: any) {
        setError(e.message || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="skeleton h-10 w-64 rounded-xl" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-xl" />
          ))}
        </div>
        <div className="skeleton h-64 rounded-xl" />
      </div>
    );
  }

  const portfolioStats = stats;
  const screenerStats = summary?.screener || {};
  const topSignals = summary?.top_signals || recentSignals;
  const config = summary?.config || {};

  return (
    <div className="flex flex-col gap-6 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-3xl font-black tracking-tight"
            style={{ color: "var(--text-bright)" }}
          >
            Dashboard
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            {new Date().toLocaleDateString("en-IN", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="live-indicator" />
          <span className="text-sm font-medium" style={{ color: "var(--accent-green)" }}>
            Live
          </span>
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            Capital: {formatINR(config.capital)}
          </span>
        </div>
      </div>

      {error && (
        <div
          className="p-4 rounded-xl text-sm"
          style={{
            background: "rgba(255, 68, 102, 0.1)",
            border: "1px solid rgba(255, 68, 102, 0.3)",
            color: "var(--accent-red)",
          }}
        >
          ⚠️ Backend not connected. Start the backend server: <code>cd backend && start.bat</code>
          <br />
          <span style={{ color: "var(--text-muted)" }}>
            Error: {error}
          </span>
        </div>
      )}

      {/* ── Portfolio Stats ────────────────────────────────────────────────── */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest mb-3"
          style={{ color: "var(--text-muted)" }}>
          Portfolio Performance
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Total P&L"
            value={formatINR(portfolioStats?.total_pnl ?? 0)}
            sub={formatPct(portfolioStats?.total_return_pct)}
            accent={
              (portfolioStats?.total_pnl ?? 0) >= 0 ? "green" : "red"
            }
            icon="💰"
          />
          <StatCard
            label="Win Rate"
            value={`${portfolioStats?.win_rate?.toFixed(1) ?? "0.0"}%`}
            sub={`${portfolioStats?.winning_trades ?? 0}W / ${portfolioStats?.losing_trades ?? 0}L`}
            accent={
              (portfolioStats?.win_rate ?? 0) >= 50 ? "green" : "red"
            }
            icon="🎯"
          />
          <StatCard
            label="Open Trades"
            value={String(portfolioStats?.open_trades ?? 0)}
            sub={`${portfolioStats?.total_trades ?? 0} total`}
            accent="blue"
            icon="📈"
          />
          <StatCard
            label="Profit Factor"
            value={portfolioStats?.profit_factor?.toFixed(2) ?? "—"}
            sub="Gross P / Gross L"
            accent={
              (portfolioStats?.profit_factor ?? 0) >= 1.5 ? "green" : "gold"
            }
            icon="⚡"
          />
        </div>
      </div>

      {/* ── Screener Stats + Strategy Cards ────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Screener Status */}
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--text-muted)" }}>
            Screener Status
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Last Run
              </span>
              <span className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                {screenerStats.latest_run_date || "Not run yet"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Signals Today
              </span>
              <span
                className="font-mono text-sm font-bold"
                style={{ color: "var(--accent-green)" }}
              >
                {screenerStats.passed_today ?? 0} passed
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Universe
              </span>
              <span className="font-mono text-sm" style={{ color: "var(--accent-blue)" }}>
                {config.universe || "NIFTY500"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Next Run
              </span>
              <span className="font-mono text-sm" style={{ color: "var(--text-muted)" }}>
                3:45 PM IST
              </span>
            </div>
          </div>
        </div>

        {/* Strategy Rules */}
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--text-muted)" }}>
            Active Strategy Rules
          </div>
          <div className="space-y-2">
            {[
              { label: "ROCE", rule: "> 15%", type: "fundamental", color: "var(--accent-green)" },
              { label: "D/E Ratio", rule: "< 1.0", type: "fundamental", color: "var(--accent-green)" },
              { label: "Price vs 200 EMA", rule: "Above", type: "technical", color: "var(--accent-blue)" },
              { label: "RSI (14)", rule: "< 30", type: "technical", color: "var(--accent-blue)" },
              { label: "Stop Loss", rule: "2×ATR", type: "risk", color: "var(--accent-red)" },
              { label: "Target", rule: "12% or RSI>70", type: "risk", color: "var(--accent-gold)" },
            ].map((rule) => (
              <div key={rule.label} className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {rule.label}
                </span>
                <span
                  className="font-mono text-xs font-bold px-2 py-0.5 rounded"
                  style={{
                    color: rule.color,
                    background: `${rule.color}15`,
                  }}
                >
                  {rule.rule}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Exit Breakdown */}
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "var(--text-muted)" }}>
            Exit Breakdown
          </div>
          {portfolioStats?.exit_reasons ? (
            <div className="space-y-3">
              {[
                {
                  label: "Target Hit (12%)",
                  value: portfolioStats.exit_reasons.targets,
                  color: "var(--accent-green)",
                },
                {
                  label: "RSI Overbought",
                  value: portfolioStats.exit_reasons.rsi_exits,
                  color: "var(--accent-blue)",
                },
                {
                  label: "Stop Loss",
                  value: portfolioStats.exit_reasons.sl_hits,
                  color: "var(--accent-red)",
                },
                {
                  label: "Manual",
                  value: portfolioStats.exit_reasons.manual,
                  color: "var(--text-muted)",
                },
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span style={{ color: "var(--text-secondary)" }}>{item.label}</span>
                    <span style={{ color: item.color }} className="font-bold">
                      {item.value}
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.min(100, (item.value / Math.max(portfolioStats.closed_trades, 1)) * 100)}%`,
                        background: item.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div
              className="text-sm text-center py-6"
              style={{ color: "var(--text-muted)" }}
            >
              No closed trades yet
            </div>
          )}
        </div>
      </div>

      {/* ── Top Signals Table ───────────────────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between p-5 border-b"
          style={{ borderColor: "var(--border-primary)" }}>
          <div>
            <h2 className="font-bold" style={{ color: "var(--text-bright)" }}>
              Top Alpha Signals
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              Stocks passing all screener filters, ranked by composite score
            </p>
          </div>
          <a
            href="/screener"
            className="btn-ghost text-xs"
          >
            View All →
          </a>
        </div>
        {topSignals.length === 0 ? (
          <div className="p-10 text-center">
            <div className="text-4xl mb-3">🔍</div>
            <p style={{ color: "var(--text-secondary)" }}>No signals yet</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Go to Screener and run it to find opportunities
            </p>
          </div>
        ) : (
          <div className="table-container rounded-none border-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Sector</th>
                  <th>Price</th>
                  <th>RSI(14)</th>
                  <th>ROCE</th>
                  <th>Score</th>
                  <th>R:R</th>
                </tr>
              </thead>
              <tbody>
                {topSignals.map((sig: any, i: number) => (
                  <SignalRow key={sig.id || i} signal={sig} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
