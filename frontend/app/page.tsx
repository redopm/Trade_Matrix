"use client";

import { useEffect, useState } from "react";
import { dashboardApi, tradesApi, aladdinApi, forwardTestApi, type PortfolioStats } from "@/lib/api";
import { 
  TrendingUp, 
  Target, 
  Briefcase, 
  Activity, 
  AlertTriangle,
  ChevronRight,
  SearchX,
  BrainCircuit,
  Sparkles,
  Zap,
  ArrowUpRight,
  ShieldCheck,
  RefreshCw,
  CheckCircle2,
  TrendingDown,
  FlaskConical,
  Scale,
  Database
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
  const sym = signal.symbol?.replace(".NS", "");
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors group">
      <td className="py-3 px-4">
        <div>
          <div className="font-bold text-sm text-slate-900">
            {sym}
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
      <td className="py-3 px-4 text-right">
        <Link
          href={`/aladdin?symbol=${sym}`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold transition-all shadow-sm border border-indigo-200"
        >
          <BrainCircuit size={13} />
          Aladdin
        </Link>
      </td>
    </tr>
  );
}

// --- Main Dashboard ---
export default function DashboardPage() {
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [recentSignals, setRecentSignals] = useState<any[]>([]);
  const [aiPicks, setAiPicks] = useState<any[]>([]);
  const [scorecard, setScorecard] = useState<any>(null);
  const [cohorts, setCohorts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshingPicks, setRefreshingPicks] = useState(false);
  const [deployingSymbol, setDeployingSymbol] = useState<string | null>(null);
  const [deploySuccess, setDeploySuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (isManualRefresh: boolean = false) => {
    try {
      const [summaryRes, statsRes, signalsRes, aiPicksRes, scorecardRes, cohortsRes] = await Promise.allSettled([
        dashboardApi.getSummary(),
        tradesApi.getStats(),
        dashboardApi.getRecentSignals(8),
        dashboardApi.getAiPicks(isManualRefresh),
        forwardTestApi.getScorecard(),
        forwardTestApi.getCohorts(),
      ]);

      if (summaryRes.status === "fulfilled") setSummary(summaryRes.value.data);
      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (signalsRes.status === "fulfilled") setRecentSignals(signalsRes.value.data);
      if (aiPicksRes.status === "fulfilled") {
        setAiPicks(aiPicksRes.value.data || (summaryRes.status === "fulfilled" ? summaryRes.value.data?.ai_picks : []));
      }
      if (scorecardRes.status === "fulfilled") setScorecard(scorecardRes.value);
      if (cohortsRes.status === "fulfilled") setCohorts(cohortsRes.value || []);
    } catch (e: any) {
      setError(e.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
      setRefreshingPicks(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => loadData(false), 60000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshAiPicks = async () => {
    setRefreshingPicks(true);
    await loadData(true);
  };

  const handleDeployTrade = async (pick: any) => {
    setDeployingSymbol(pick.symbol);
    try {
      const qty = Math.max(1, Math.floor(10000 / pick.current_price));
      await aladdinApi.deploy({
        symbol: pick.symbol,
        company_name: pick.company_name,
        sector: pick.sector || "General",
        entry_price: pick.current_price,
        stop_loss: pick.stop_loss,
        target_price: pick.target_1,
        quantity: qty,
        notes: `Aladdin Top Pick: Conviction ${pick.composite_score}% | Target ₹${pick.target_1}`
      });
      setDeploySuccess(`Successfully opened trade for ${pick.symbol} (${qty} shares)! View in Trading Desk.`);
      setTimeout(() => setDeploySuccess(null), 5000);
    } catch (err: any) {
      alert("Deploy failed: " + (err.message || "Unknown error"));
    } finally {
      setDeployingSymbol(null);
    }
  };

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
          <div className="text-sm font-medium text-slate-500 bg-white border border-slate-200 px-4 py-1.5 rounded-full shadow-sm flex items-center gap-4">
            <div>
              Available:{" "}
              <span className="text-slate-900 font-bold">
                {formatINR(
                  portfolioStats?.available_cash !== undefined
                    ? portfolioStats.available_cash
                    : Math.max(
                        0,
                        (config.capital || portfolioStats?.capital || 1000000) +
                          (portfolioStats?.realized_pnl || 0) -
                          (portfolioStats?.total_invested || 0)
                      )
                )}
              </span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <div className="text-xs">
              Invested:{" "}
              <span className="text-slate-700 font-bold">
                {formatINR(portfolioStats?.total_invested || 0)}
              </span>
            </div>
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

      {/* --- Aladdin AI High-Conviction Future Setups --- */}
      <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 border border-indigo-900/60 rounded-2xl p-6 sm:p-7 shadow-xl text-white relative overflow-hidden">
        {/* Ambient Glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-bold uppercase tracking-wider">
                <BrainCircuit size={14} className="text-indigo-400" />
                Ranked Watchlist (Descriptive Algorithm)
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-semibold border border-emerald-500/30">
                Forward Protocol v2.1 Active
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
              Ranked Watchlist (Descriptive Algorithm)
              <Sparkles size={20} className="text-amber-400" />
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl">
              Descriptive 5-Pillar Ranking: Price Geometry + Technical Momentum + Forensic Health + F&O Smart Money + Macro Regime. Pre-registered empirical forward trial in progress.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleRefreshAiPicks}
              disabled={refreshingPicks}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-white/15 text-xs font-bold text-white transition-all disabled:opacity-50"
            >
              <RefreshCw size={14} className={refreshingPicks ? "animate-spin text-indigo-400" : "text-slate-300"} />
              {refreshingPicks ? "Analyzing Stocks..." : "Refresh AI Picks"}
            </button>
            <Link
              href="/aladdin"
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-xs font-bold text-white transition-all shadow-md shadow-indigo-500/20"
            >
              Deep MRI Scanner <ChevronRight size={14} />
            </Link>
          </div>
        </div>

        {deploySuccess && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm font-semibold flex items-center gap-2 animate-fadeIn">
            <CheckCircle2 size={18} className="text-emerald-400" />
            {deploySuccess}
          </div>
        )}

        {/* AI Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 relative z-10">
          {aiPicks.slice(0, 3).map((pick: any) => {
            const score = pick.composite_score || 0;
            const isHighConviction = score >= 75;
            const isMedium = score >= 65 && score < 75;
            const rawBadge = String(pick.verdict_badge || pick.verdict || "NEUTRAL");
            const cleanBadge = rawBadge.replace(/\s*\(.*?\)/g, "").trim();
            const isDefensive = rawBadge.toLowerCase().includes("defensive") || pick.verdict === "DEFENSIVE_REGIME";

            return (
              <div
                key={pick.symbol}
                className={`bg-slate-800/90 hover:bg-slate-800 border ${
                  isHighConviction 
                    ? "border-emerald-500/50 shadow-emerald-950/20 shadow-xl" 
                    : isDefensive
                      ? "border-rose-900/60 shadow-lg"
                      : "border-slate-700/80 shadow-lg"
                } rounded-2xl p-5 transition-all flex flex-col justify-between group`}
              >
                <div>
                  {/* Card Header Row 1: Symbol + Sector & AI Score */}
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-lg font-black text-white tracking-wide shrink-0">{pick.symbol}</span>
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-700/80 text-slate-300 max-w-[110px] truncate shrink-0">
                        {pick.sector || "LargeCap"}
                      </span>
                    </div>

                    {/* AI Score Badge */}
                    <div className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-black shadow-sm shrink-0 ${
                      isHighConviction 
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" 
                        : isMedium 
                          ? "bg-blue-500/20 text-blue-400 border border-blue-500/40" 
                          : "bg-amber-500/10 text-amber-300 border border-amber-500/30"
                    }`}>
                      <Zap size={12} className={isHighConviction ? "text-emerald-400" : isMedium ? "text-blue-400" : "text-amber-400"} />
                      {score.toFixed(1)}% AI
                    </div>
                  </div>

                  {/* Card Header Row 2: Company Name & Setup Badge */}
                  <div className="flex items-center justify-between gap-2 mb-3 min-w-0">
                    <div className="text-xs text-slate-400 truncate max-w-[170px]" title={pick.company_name}>
                      {pick.company_name}
                    </div>
                    <span 
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded shrink-0 ${
                        isHighConviction 
                          ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20" 
                          : isMedium 
                            ? "text-blue-400 bg-blue-500/10 border border-blue-500/20" 
                            : isDefensive 
                              ? "text-rose-400 bg-rose-500/10 border border-rose-500/20"
                              : "text-slate-300 bg-slate-700/60 border border-slate-600/50"
                      }`}
                      title={cleanBadge}
                    >
                      {cleanBadge}
                    </span>
                  </div>

                  {/* Conviction Hurdle Notice */}
                  {!isHighConviction && (
                    <div className={`mb-3.5 px-3 py-1.5 rounded-lg border text-[11px] flex items-center justify-between font-medium gap-2 ${
                      isDefensive 
                        ? "bg-rose-500/10 border-rose-500/20 text-rose-300"
                        : "bg-amber-500/10 border-amber-500/20 text-amber-300"
                    }`}>
                      <span className="truncate">
                        {isDefensive ? "Defensive Regime: Trend Weak" : "Wait for 75+ Score Breakout"}
                      </span>
                      <span className="font-bold text-[10px] uppercase tracking-wider shrink-0 px-1.5 py-0.5 rounded bg-white/5 border border-white/10">
                        {isDefensive ? "Defense" : "Watchlist"}
                      </span>
                    </div>
                  )}

                  {/* Price & Market Stage */}
                  <div className="flex items-center justify-between py-2.5 border-y border-slate-700/60 mb-3.5 gap-2">
                    <div>
                      <span className="text-[11px] text-slate-400 font-medium block">Current Price</span>
                      <span className="text-xl font-bold text-white">₹{pick.current_price?.toFixed(2)}</span>
                    </div>
                    <div className="text-right min-w-0">
                      <span className="text-[11px] text-slate-400 font-medium block">Market Stage</span>
                      <span className="text-xs font-bold text-amber-400 px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20 inline-block truncate max-w-[130px] align-middle" title={pick.market_phase?.replace(/_/g, " ") || "MARKUP"}>
                        {pick.market_phase?.replace(/_/g, " ") || "MARKUP"}
                      </span>
                    </div>
                  </div>

                  {/* Target & Stop Loss Roadmap */}
                  <div className="grid grid-cols-2 gap-3 mb-3.5">
                    <div className="bg-emerald-950/30 border border-emerald-800/40 p-2.5 rounded-xl">
                      <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider flex items-center justify-between">
                        <span>Target 1</span>
                        <span className="text-xs font-bold">+{pick.target_1_pct?.toFixed(1)}%</span>
                      </div>
                      <div className="text-sm font-black text-white mt-0.5">₹{pick.target_1?.toFixed(2)}</div>
                    </div>

                    <div className="bg-rose-950/30 border border-rose-800/40 p-2.5 rounded-xl">
                      <div className="text-[10px] text-rose-400 font-bold uppercase tracking-wider flex items-center justify-between">
                        <span>Stop Loss</span>
                        <span className="text-xs font-bold">-{pick.stop_loss_pct?.toFixed(1)}%</span>
                      </div>
                      <div className="text-sm font-black text-white mt-0.5">₹{pick.stop_loss?.toFixed(2)}</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 mb-4 px-1">
                    <span>Risk:Reward: <strong className="text-slate-200">{pick.risk_reward_ratio || "1:2.0"}</strong></span>
                    <span>Horizon: <strong className="text-slate-200">{String(pick.time_horizon || "5-20 Days").replace(/Trading Days/i, "Days").replace(/to/i, "-")}</strong></span>
                  </div>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-700/60 mt-auto">
                  <Link
                    href={`/aladdin?symbol=${pick.symbol}`}
                    className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-xs font-bold text-indigo-200 hover:text-white transition-all text-center"
                  >
                    <BrainCircuit size={14} />
                    Aladdin MRI
                  </Link>

                  {isHighConviction ? (
                    <button
                      onClick={() => handleDeployTrade(pick)}
                      disabled={deployingSymbol === pick.symbol}
                      className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-xs font-bold text-white transition-all shadow-sm disabled:opacity-50"
                    >
                      <Zap size={14} className={deployingSymbol === pick.symbol ? "animate-bounce" : ""} />
                      {deployingSymbol === pick.symbol ? "Deploying..." : "Quick Deploy"}
                    </button>
                  ) : (
                    <Link
                      href={`/aladdin?symbol=${pick.symbol}`}
                      className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-bold text-slate-300 hover:text-white transition-all text-center"
                    >
                      <span>Wait / Monitor</span>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* --- Forward Validation Protocol v2.1 (Institutional Pre-Registered Trial) --- */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-7 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 text-xs font-bold border border-indigo-100 flex items-center gap-1.5">
                <FlaskConical size={14} />
                Protocol v2.1 Active
              </span>
              <span className="px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-100">
                Protocol v2.1.1
              </span>
              <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-semibold">
                Statutory Friction: 0.385%
              </span>
              <span className="px-2.5 py-1 rounded-md bg-amber-50 text-amber-800 text-xs font-semibold border border-amber-200">
                Rigid Pool: ₹10,00,000 (Max 3 Active Cohorts)
              </span>
            </div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
              Empirical Forward Validation Protocol
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                K=9 Target Cohorts
              </span>
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-3xl">
              Strict empirical testing: Tool Top 10 evaluated against exact universe equal-weight net return, 1,000 pseudo-random Monte Carlo baskets, and 1,000 sector-matched control baskets from Nifty 100. Fixed 90-day holding horizon calculated offline via Ledger A (Shadow Research) with dividend-adjusted returns.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <div className="text-right">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Evaluation Horizon</div>
              <div className="text-sm font-bold text-slate-800">12 Months (Oct 2026 – Oct 2027)</div>
            </div>
          </div>
        </div>

        {/* 4 Protocol Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 my-6">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Primary Metric</div>
            <div className="text-lg font-black text-slate-900">Tool Net − Universe Exact Net (Δ)</div>
            <div className="text-xs text-slate-500 mt-1">Evaluated across cohorts against exact universe & 1,000 MC baskets</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Standard Error & Power</div>
            <div className="text-lg font-black text-indigo-700">SE = s<sub>Δ</sub> / √K</div>
            <div className="text-xs text-slate-500 mt-1">Min detectable edge: +3.85% / 90d (~16.2% p.a.)</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Execution Architecture</div>
            <div className="text-lg font-black text-slate-900">Dual-Ledger Separation</div>
            <div className="text-xs text-slate-500 mt-1">Ledger A (Shadow 90d) | Ledger B (Live ATR SL Desk)</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Pre-Registered Sunset</div>
            <div className="text-lg font-black text-amber-700">Protected Until K ≥ 9</div>
            <div className="text-xs text-slate-500 mt-1">Single rule: CI_lower &gt; 0.0% &amp; Mean Δ ≥ +1.0%</div>
          </div>
        </div>

        {/* Cohort Summary Table */}
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Database size={13} className="text-indigo-600" />
              Pre-Registered Cohort Ledger ({cohorts.length} Cohort{cohorts.length === 1 ? "" : "s"} Frozen)
            </div>
            <div className="text-xs text-slate-500">
              Next Cohort 1 Freeze: <strong>Monday, 02 November 2026</strong> (NSE Session Open)
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border border-slate-100 rounded-lg overflow-hidden">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Batch ID</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Regime</th>
                  <th className="py-2.5 px-3">Nifty Base</th>
                  <th className="py-2.5 px-3">Universe</th>
                  <th className="py-2.5 px-3">Live Invested (Ledger B)</th>
                  <th className="py-2.5 px-3">Git SHA</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cohorts.map((c: any) => (
                  <tr key={c.batch_id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{c.batch_id}</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                        c.cohort_type === "PILOT" 
                          ? "bg-amber-100 text-amber-800" 
                          : "bg-indigo-100 text-indigo-800"
                      }`}>
                        {c.cohort_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                        c.regime === "DEFENSIVE" ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"
                      }`}>
                        {c.regime}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-semibold">₹{c.nifty_base_price?.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-slate-600">{c.eligible_universe_count} stocks</td>
                    <td className="py-2.5 px-3 font-bold text-slate-900">₹{c.total_allocated_inr?.toLocaleString("en-IN")}</td>
                    <td className="py-2.5 px-3 font-mono text-slate-500">{c.scoring_git_hash}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-bold text-[10px] uppercase">
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {cohorts.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-slate-400">
                      Cohort 0 Pilot freeze executing... Refresh to view live ledger.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
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
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Action</th>
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
