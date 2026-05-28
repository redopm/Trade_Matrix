"use client";

import { useEffect, useState } from "react";
import { tradesApi, type Trade, type PortfolioStats } from "@/lib/api";
import { 
  Briefcase, 
  RefreshCw, 
  Target, 
  Activity, 
  TrendingUp, 
  TrendingDown,
  XCircle,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import Link from "next/link";

function formatINR(amount: number | null | undefined, decimals = 0): string {
  if (amount == null) return "-";
  const formatted = Math.abs(amount).toLocaleString("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
  return `${amount < 0 ? "-" : ""}₹${formatted}`;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    OPEN: { label: "Open", color: "bg-blue-100 text-blue-700 border-blue-200", icon: <Activity size={12} /> },
    CLOSED_TARGET: { label: "Target Hit", color: "bg-emerald-100 text-emerald-700 border-emerald-200", icon: <CheckCircle2 size={12} /> },
    CLOSED_SL: { label: "SL Hit", color: "bg-red-100 text-red-700 border-red-200", icon: <XCircle size={12} /> },
    CLOSED_RSI: { label: "RSI Exit", color: "bg-purple-100 text-purple-700 border-purple-200", icon: <Target size={12} /> },
    CLOSED_MANUAL: { label: "Manual", color: "bg-slate-100 text-slate-700 border-slate-200", icon: <AlertCircle size={12} /> },
    CANCELLED: { label: "Cancelled", color: "bg-slate-100 text-slate-500 border-slate-200", icon: <XCircle size={12} /> },
  };
  const badge = config[status] || { label: status, color: "bg-slate-100 text-slate-700", icon: null };
  
  return (
    <span className={`flex items-center gap-1 w-fit px-2.5 py-1 rounded-md text-[11px] font-bold border uppercase tracking-wider ${badge.color}`}>
      {badge.icon} {badge.label}
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
    <tr className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
      <td className="py-4 px-4">
        <div>
          <div className="font-bold text-sm text-slate-900">
            {trade.symbol?.replace(".NS", "")}
          </div>
          <div className="text-xs font-medium text-slate-500">
            {trade.entry_date} &bull; {trade.days_in_trade ?? 0}d
          </div>
        </div>
      </td>
      <td className="py-4 px-4">
        <StatusBadge status={trade.status} />
      </td>
      <td className="py-4 px-4">
        <div>
          <div className="font-mono font-bold text-slate-700">
            ₹{trade.entry_price?.toFixed(2)}
          </div>
          <div className="text-xs font-medium text-slate-400">
            {trade.quantity} qty
          </div>
        </div>
      </td>
      <td className="py-4 px-4">
        <div className="font-mono font-bold text-red-600">
          ₹{trade.stop_loss?.toFixed(2)}
        </div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          ATR-based
        </div>
      </td>
      <td className="py-4 px-4">
        <div className="font-mono font-bold text-emerald-600">
          ₹{trade.target_price?.toFixed(2)}
        </div>
      </td>
      <td className="py-4 px-4">
        {trade.current_price ? (
          <div>
            <div className="font-mono font-bold text-slate-800">
              ₹{trade.current_price?.toFixed(2)}
            </div>
            {trade.current_rsi && (
              <div
                className={`text-[11px] font-mono font-bold mt-0.5 ${
                  trade.current_rsi > 70 ? "text-amber-500" : "text-slate-400"
                }`}
              >
                RSI: {trade.current_rsi?.toFixed(1)}
              </div>
            )}
          </div>
        ) : (
          <span className="text-slate-300 font-bold">-</span>
        )}
      </td>
      <td className="py-4 px-4">
        {pnl != null ? (
          <div>
            <div className={`font-mono font-bold text-sm ${pnl > 0 ? "text-emerald-600" : pnl < 0 ? "text-red-600" : "text-slate-500"}`}>
              {formatINR(pnl)}
            </div>
            <div className={`text-[11px] font-mono font-bold ${pnlPct != null && pnlPct > 0 ? "text-emerald-500" : pnlPct != null && pnlPct < 0 ? "text-red-500" : "text-slate-400"}`}>
              {pnlPct != null ? `${pnlPct >= 0 ? "+" : ""}${pnlPct?.toFixed(2)}%` : "-"}
            </div>
          </div>
        ) : (
          <span className="text-slate-300 font-bold">-</span>
        )}
      </td>
      <td className="py-4 px-4">
        {isOpen && (
          <button
            className="text-xs font-bold px-3 py-1.5 rounded bg-white text-red-600 border border-red-200 hover:bg-red-50 hover:border-red-300 transition-colors"
            onClick={() => onClose(trade.id)}
          >
            Close
          </button>
        )}
        {!isOpen && trade.exit_reason && (
          <span
            className="text-xs font-medium text-slate-400 max-w-[120px] truncate block"
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
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Paper Trades
          </h1>
          <p className="text-sm mt-2 text-slate-500 font-medium">
            Virtual trade tracker &bull; ATR-based SL &bull; RSI exit
          </p>
        </div>
        <button
          onClick={handleUpdateAll}
          disabled={updating}
          className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50"
        >
          {updating ? (
            <><RefreshCw size={16} className="animate-spin" /> Updating...</>
          ) : (
            <><RefreshCw size={16} /> Update P&amp;L</>
          )}
        </button>
      </div>

      {/* Portfolio Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-5 text-emerald-600">
              <TrendingUp size={64} />
            </div>
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 relative z-10">Realized P&amp;L</div>
            <div className={`text-2xl font-black mb-1 relative z-10 ${(stats.realized_pnl ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {formatINR(stats.realized_pnl)}
            </div>
            <div className="text-xs font-medium text-slate-400 relative z-10">
              {stats.closed_trades} closed trades
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Unrealized P&amp;L</div>
            <div className={`text-2xl font-black mb-1 ${(stats.unrealized_pnl ?? 0) >= 0 ? "text-blue-600" : "text-red-600"}`}>
              {formatINR(stats.unrealized_pnl)}
            </div>
            <div className="text-xs font-medium text-slate-400">
              {stats.open_trades} open positions
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Win Rate</div>
            <div className={`text-2xl font-black mb-1 ${(stats.win_rate ?? 0) >= 50 ? "text-emerald-600" : "text-red-600"}`}>
              {stats.win_rate?.toFixed(1)}%
            </div>
            <div className="text-xs font-medium text-slate-400">
              {stats.winning_trades}W / {stats.losing_trades}L
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Expectancy</div>
            <div className={`text-2xl font-black mb-1 ${(stats.expectancy ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {stats.expectancy?.toFixed(2) ?? "-"}%
            </div>
            <div className="text-xs font-medium text-slate-400">
              Per trade average
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3 bg-white p-2 rounded-xl border border-slate-200 shadow-sm w-fit">
        {(["ALL", "OPEN", "CLOSED"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 text-sm font-bold rounded-lg transition-colors ${
              filter === f 
                ? "bg-slate-800 text-white shadow-sm" 
                : "bg-transparent text-slate-500 hover:bg-slate-100"
            }`}
          >
            {f}
          </button>
        ))}
        <div className="w-px h-6 bg-slate-200 mx-2"></div>
        <span className="text-sm font-bold text-slate-400 pr-3">
          {filtered.length} trades
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-100 rounded-lg mb-3 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
            <Briefcase className="text-slate-300" size={32} />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-2">
            No trades yet
          </p>
          <p className="text-sm font-medium text-slate-500 max-w-sm mb-6">
            Run the screener, find high-quality signals, and add them to your paper trading portfolio.
          </p>
          <Link href="/screener" className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-6 py-2.5 rounded-lg transition-colors shadow-sm">
            Go to Screener
          </Link>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100">
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Symbol</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Status</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Entry</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Stop Loss</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Target</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Current</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">P&amp;L</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Action</th>
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
