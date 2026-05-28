"use client";

import { useEffect, useState } from "react";
import { dashboardApi, tradesApi, type PortfolioStats } from "@/lib/api";
import { 
  TrendingUp, 
  Target, 
  Briefcase, 
  Activity, 
  AlertTriangle,
  ChevronRight,
  SearchX
} from "lucide-react";
import Link from "next/link";

// --- Helper Functions ---
function formatINR(amount: number | null | undefined): string {
  if (amount == null) return "N/A";
  if (Math.abs(amount) >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (Math.abs(amount) >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "-";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

// --- Stat Card ---
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
  icon?: React.ReactNode;
}) {
  const bgColors = {
    green: "bg-emerald-50 text-emerald-600",
    red: "bg-red-50 text-red-600",
    blue: "bg-blue-50 text-blue-600",
    gold: "bg-amber-50 text-amber-600",
    purple: "bg-purple-50 text-purple-600",
  };
  const iconColor = accent ? bgColors[accent] : "bg-slate-50 text-slate-600";

  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-start justify-between">
      <div>
        <div className="text-sm font-semibold text-slate-500 mb-1">{label}</div>
        <div className="text-2xl font-bold text-slate-900 mb-1">{value}</div>
        {sub && (
          <div className="text-xs font-medium text-slate-400">
            {sub}
          </div>
        )}
      </div>
      {icon && (
        <div className={`p-3 rounded-xl ${iconColor}`}>
          {icon}
        </div>
      )}
    </div>
  );
}

// --- Signal Row ---
function SignalRow({ signal }: { signal: any }) {
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors group">
      <td className="py-3 px-4">
        <div>
          <div className="font-bold text-sm text-slate-900">
            {signal.symbol?.replace(".NS", "")}
          </div>
          <div className="text-xs text-slate-500 truncate max-w-[140px]">
            {signal.company_name}
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className="text-xs px-2.5 py-1 rounded-md bg-slate-100 text-slate-600 font-medium">
          {signal.sector || "-"}
        </span>
      </td>
      <td className="py-3 px-4">
        <span className="text-sm font-semibold text-slate-700">₹{signal.signal_price?.toFixed(2)}</span>
      </td>
      <td className="py-3 px-4">
        <span className={`font-mono text-sm font-semibold ${signal.rsi_14 < 20 ? "text-amber-500" : "text-blue-600"}`}>
          {signal.rsi_14?.toFixed(1) ?? "-"}
        </span>
      </td>
      <td className="py-3 px-4">
        <span className="font-mono text-sm font-semibold text-emerald-600">
          {signal.roce?.toFixed(1) ?? "-"}%
        </span>
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-amber-500">
            {signal.composite_score?.toFixed(1) ?? "-"}
          </span>
          <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div 
              className="h-full bg-amber-400 rounded-full"
              style={{ width: `${Math.min(100, (signal.composite_score / 100) * 100)}%` }}
            />
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className="font-mono text-sm font-semibold text-emerald-600">
          {signal.risk_reward_ratio?.toFixed(2) ?? "-"}
        </span>
      </td>
    </tr>
  );
}

// --- Main Dashboard ---
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
      <div className="p-8 flex flex-col gap-8 animate-pulse">
        <div className="h-10 bg-slate-200 w-64 rounded-xl" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-200 rounded-2xl" />
          ))}
        </div>
        <div className="h-96 bg-slate-200 rounded-2xl" />
      </div>
    );
  }

  const portfolioStats = stats;
  const screenerStats = summary?.screener || {};
  const topSignals = summary?.top_signals || recentSignals;
  const config = summary?.config || {};

  return (
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Dashboard
          </h1>
          <p className="text-sm mt-1 text-slate-500 font-medium">
            {new Date().toLocaleDateString("en-IN", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 px-3 py-1.5 rounded-full">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold text-emerald-700 uppercase tracking-wide">
              Live
            </span>
          </div>
          <div className="text-sm font-medium text-slate-500 bg-white border border-slate-200 px-4 py-1.5 rounded-full shadow-sm">
            Capital: <span className="text-slate-900 font-bold">{formatINR(config.capital)}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-xl flex items-start gap-3 text-red-800 shadow-sm">
          <AlertTriangle className="mt-0.5 text-red-500" size={18} />
          <div>
            <div className="font-bold text-sm">Backend not connected</div>
            <div className="text-sm opacity-90 mt-1">Start the backend server: <code>cd backend && start.bat</code></div>
            <div className="text-xs opacity-75 mt-2 font-mono">{error}</div>
          </div>
        </div>
      )}

      {/* --- Portfolio Stats --- */}
      <div>
        <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 px-1">
          Portfolio Performance
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <StatCard
            label="Total P&L"
            value={formatINR(portfolioStats?.total_pnl ?? 0)}
            sub={formatPct(portfolioStats?.total_return_pct)}
            accent={
              (portfolioStats?.total_pnl ?? 0) >= 0 ? "green" : "red"
            }
            icon={<TrendingUp size={24} />}
          />
          <StatCard
            label="Win Rate"
            value={`${portfolioStats?.win_rate?.toFixed(1) ?? "0.0"}%`}
            sub={`${portfolioStats?.winning_trades ?? 0}W / ${portfolioStats?.losing_trades ?? 0}L`}
            accent={
              (portfolioStats?.win_rate ?? 0) >= 50 ? "green" : "red"
            }
            icon={<Target size={24} />}
          />
          <StatCard
            label="Open Trades"
            value={String(portfolioStats?.open_trades ?? 0)}
            sub={`${portfolioStats?.total_trades ?? 0} total`}
            accent="blue"
            icon={<Briefcase size={24} />}
          />
          <StatCard
            label="Profit Factor"
            value={portfolioStats?.profit_factor?.toFixed(2) ?? "-"}
            sub="Gross P / Gross L"
            accent={
              (portfolioStats?.profit_factor ?? 0) >= 1.5 ? "green" : "gold"
            }
            icon={<Activity size={24} />}
          />
        </div>
      </div>

      {/* --- Screener Stats + Strategy Cards --- */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Screener Status */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-5">
            Screener Status
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-500">Last Run</span>
              <span className="text-sm font-semibold text-slate-900">
                {screenerStats.latest_run_date || "Not run yet"}
              </span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-500">Signals Today</span>
              <span className="text-sm font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                {screenerStats.passed_today ?? 0} passed
              </span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-500">Universe</span>
              <span className="text-sm font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                {config.universe || "NIFTY500"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-slate-500">Next Run</span>
              <span className="text-sm font-semibold text-slate-400">3:45 PM IST</span>
            </div>
          </div>
        </div>

        {/* Strategy Rules */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-5">
            Active Strategy Rules
          </div>
          <div className="space-y-3">
            {[
              { label: "ROCE", rule: "> 15%", color: "text-emerald-700 bg-emerald-50" },
              { label: "D/E Ratio", rule: "< 1.0", color: "text-emerald-700 bg-emerald-50" },
              { label: "Price vs 200 EMA", rule: "Above", color: "text-blue-700 bg-blue-50" },
              { label: "RSI (14)", rule: "< 30", color: "text-blue-700 bg-blue-50" },
              { label: "Stop Loss", rule: "2×ATR", color: "text-red-700 bg-red-50" },
              { label: "Target", rule: "12% or RSI>70", color: "text-amber-700 bg-amber-50" },
            ].map((rule) => (
              <div key={rule.label} className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-600">
                  {rule.label}
                </span>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-md ${rule.color}`}>
                  {rule.rule}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Exit Breakdown */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-5">
            Exit Breakdown
          </div>
          {portfolioStats?.exit_reasons ? (
            <div className="space-y-4">
              {[
                { label: "Target Hit (12%)", value: portfolioStats.exit_reasons.targets, color: "bg-emerald-500", text: "text-emerald-700" },
                { label: "RSI Overbought", value: portfolioStats.exit_reasons.rsi_exits, color: "bg-blue-500", text: "text-blue-700" },
                { label: "Stop Loss", value: portfolioStats.exit_reasons.sl_hits, color: "bg-red-500", text: "text-red-700" },
                { label: "Manual", value: portfolioStats.exit_reasons.manual, color: "bg-slate-400", text: "text-slate-600" },
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex justify-between items-center text-sm mb-1.5">
                    <span className="font-medium text-slate-500">{item.label}</span>
                    <span className={`font-bold ${item.text}`}>{item.value}</span>
                  </div>
                  <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${item.color}`}
                      style={{
                        width: `${Math.min(100, (item.value / Math.max(portfolioStats.closed_trades, 1)) * 100)}%`
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center pb-6">
              <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-3">
                <Target className="text-slate-300" size={24} />
              </div>
              <span className="text-sm font-medium text-slate-400">No closed trades yet</span>
            </div>
          )}
        </div>
      </div>

      {/* --- Top Signals Table --- */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Top Alpha Signals
            </h2>
            <p className="text-sm text-slate-500 font-medium mt-1">
              Stocks passing all screener filters, ranked by composite score
            </p>
          </div>
          <Link
            href="/screener"
            className="flex items-center gap-1 text-sm font-bold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-4 py-2 rounded-lg transition-colors"
          >
            View All <ChevronRight size={16} />
          </Link>
        </div>
        
        {topSignals.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
              <SearchX className="text-slate-300" size={32} />
            </div>
            <p className="text-base font-bold text-slate-700 mb-1">No signals yet</p>
            <p className="text-sm text-slate-500 font-medium max-w-sm">
              Go to the Screener tab and run a fresh scan to find new trading opportunities.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100">
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Symbol</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Sector</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Price</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">RSI(14)</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">ROCE</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Score</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">R:R</th>
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
