"use client";

import { useEffect, useState, useRef } from "react";
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
  AlertCircle,
  Trash2,
  Loader2,
  Check,
  X,
  Radio,
  Clock,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";

function formatINR(amount: number | null | undefined, decimals = 2): string {
  if (amount == null) return "-";
  const formatted = Math.abs(amount).toLocaleString("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
  return `${amount < 0 ? "-" : ""}₹${formatted}`;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    OPEN:          { label: "Open",       color: "bg-blue-50 text-blue-700 border-blue-200",          icon: <Activity size={12} className="animate-pulse text-blue-500" /> },
    CLOSED_TARGET: { label: "Target Hit", color: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: <CheckCircle2 size={12} /> },
    CLOSED_SL:     { label: "SL Hit",     color: "bg-red-50 text-red-700 border-red-200",              icon: <XCircle size={12} /> },
    CLOSED_RSI:    { label: "RSI Exit",   color: "bg-purple-50 text-purple-700 border-purple-200",    icon: <Target size={12} /> },
    CLOSED_MANUAL: { label: "Manual",     color: "bg-slate-100 text-slate-700 border-slate-200",       icon: <AlertCircle size={12} /> },
    CANCELLED:     { label: "Cancelled",  color: "bg-slate-100 text-slate-500 border-slate-200",       icon: <XCircle size={12} /> },
  };
  const badge = config[status] || { label: status, color: "bg-slate-100 text-slate-700 border-slate-200", icon: null };
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border uppercase tracking-wider ${badge.color}`}>
      {badge.icon} {badge.label}
    </span>
  );
}

function TradeRow({
  trade,
  closingId,
  isClosing,
  onInitiateClose,
  onConfirmClose,
  onCancelClose,
  deletingId,
  isDeleting,
  onInitiateDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  trade: Trade;
  closingId: number | null;
  isClosing: boolean;
  onInitiateClose: (id: number) => void;
  onConfirmClose: (trade: Trade) => void;
  onCancelClose: () => void;
  deletingId: number | null;
  isDeleting: boolean;
  onInitiateDelete: (id: number) => void;
  onConfirmDelete: (id: number) => void;
  onCancelDelete: () => void;
}) {
  const pnl = trade.unrealized_pnl ?? trade.realized_pnl;
  const pnlPct = trade.unrealized_pnl_pct ?? trade.realized_pnl_pct;
  const isOpen = trade.status === "OPEN";
  const isConfirmingClose = closingId === trade.id;
  const isConfirmingDelete = deletingId === trade.id;

  const currentPrice = trade.current_price ?? trade.entry_price;
  const slDistPct = currentPrice && trade.stop_loss
    ? (((currentPrice - trade.stop_loss) / currentPrice) * 100)
    : null;
  const targetDistPct = currentPrice && trade.target_price
    ? (((trade.target_price - currentPrice) / currentPrice) * 100)
    : null;

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50/70 transition-colors">
      {/* Symbol & Date */}
      <td className="py-4 px-4">
        <div>
          <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
            <span>{trade.symbol?.replace(".NS", "")}</span>
            {isOpen && (
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" title="Live Active Position" />
            )}
          </div>
          <div className="text-xs font-medium text-slate-500 flex items-center gap-1 mt-0.5">
            <span>{trade.entry_date}</span>
            <span>&bull;</span>
            <span>{trade.days_in_trade ?? 0}d held</span>
          </div>
        </div>
      </td>

      {/* Status */}
      <td className="py-4 px-4">
        <StatusBadge status={trade.status} />
      </td>

      {/* Entry Price & Qty */}
      <td className="py-4 px-4">
        <div>
          <div className="font-mono font-bold text-slate-800">
            ₹{trade.entry_price?.toFixed(2)}
          </div>
          <div className="text-xs font-medium text-slate-500">
            {trade.quantity} shares &bull; {formatINR(trade.invested_amount, 0)}
          </div>
        </div>
      </td>

      {/* Stop Loss */}
      <td className="py-4 px-4">
        <div>
          <div className="font-mono font-bold text-red-600">
            ₹{trade.stop_loss?.toFixed(2)}
          </div>
          {isOpen && slDistPct != null && (
            <div className="text-[10px] font-semibold text-slate-400">
              {slDistPct > 0 ? `${slDistPct.toFixed(1)}% buffer` : "SL Breached"}
            </div>
          )}
        </div>
      </td>

      {/* Target Price */}
      <td className="py-4 px-4">
        <div>
          <div className="font-mono font-bold text-emerald-600">
            ₹{trade.target_price?.toFixed(2)}
          </div>
          {isOpen && targetDistPct != null && (
            <div className="text-[10px] font-semibold text-emerald-600/80">
              {targetDistPct > 0 ? `${targetDistPct.toFixed(1)}% away` : "Target Met"}
            </div>
          )}
        </div>
      </td>

      {/* Current Live Price */}
      <td className="py-4 px-4">
        {trade.current_price ? (
          <div>
            <div className="font-mono font-bold text-slate-900 flex items-center gap-1.5">
              <span>₹{trade.current_price?.toFixed(2)}</span>
            </div>
            {trade.current_rsi && (
              <div
                className={`text-[10px] font-mono font-bold mt-0.5 inline-block px-1.5 py-0.5 rounded ${
                  trade.current_rsi >= 70 
                    ? "bg-amber-100 text-amber-800" 
                    : trade.current_rsi <= 35 
                    ? "bg-blue-100 text-blue-800" 
                    : "bg-slate-100 text-slate-600"
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

      {/* P&L */}
      <td className="py-4 px-4">
        {pnl != null ? (
          <div>
            <div className={`font-mono font-extrabold text-sm flex items-center gap-1 ${
              pnl > 0 ? "text-emerald-600" : pnl < 0 ? "text-rose-600" : "text-slate-600"
            }`}>
              {pnl > 0 ? <TrendingUp size={14} /> : pnl < 0 ? <TrendingDown size={14} /> : null}
              {formatINR(pnl, 2)}
            </div>
            <div className={`text-[11px] font-mono font-bold ${
              pnlPct != null && pnlPct > 0 
                ? "text-emerald-600" 
                : pnlPct != null && pnlPct < 0 
                ? "text-rose-600" 
                : "text-slate-400"
            }`}>
              {pnlPct != null ? `${pnlPct >= 0 ? "+" : ""}${pnlPct?.toFixed(2)}%` : "-"}
            </div>
          </div>
        ) : (
          <span className="text-slate-300 font-bold">-</span>
        )}
      </td>

      {/* Action Column */}
      <td className="py-4 px-4">
        <div className="flex items-center gap-2">
          {/* Close Action for OPEN trades */}
          {isOpen && (
            <div>
              {isConfirmingClose ? (
                <div className="flex items-center gap-1.5 animate-in fade-in duration-200">
                  <button
                    disabled={isClosing}
                    onClick={() => onConfirmClose(trade)}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white shadow-sm transition-all disabled:opacity-50"
                  >
                    {isClosing ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Check size={12} />
                    )}
                    <span>Confirm @ ₹{currentPrice.toFixed(1)}</span>
                  </button>
                  <button
                    disabled={isClosing}
                    onClick={onCancelClose}
                    className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200 transition-colors"
                    title="Cancel"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => onInitiateClose(trade.id)}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 hover:border-rose-300 transition-all shadow-sm"
                >
                  Close
                </button>
              )}
            </div>
          )}

          {/* Delete Action for CLOSED trades */}
          {!isOpen && (
            <div>
              {isConfirmingDelete ? (
                <div className="flex items-center gap-1.5 animate-in fade-in duration-200">
                  <button
                    disabled={isDeleting}
                    onClick={() => onConfirmDelete(trade.id)}
                    className="px-2.5 py-1 text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white rounded-md shadow-sm transition-all flex items-center gap-1"
                  >
                    {isDeleting ? <Loader2 size={12} className="animate-spin" /> : "Delete"}
                  </button>
                  <button
                    disabled={isDeleting}
                    onClick={onCancelDelete}
                    className="p-1 text-slate-400 hover:text-slate-600"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <button
                  className="p-1.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                  title="Delete from database"
                  onClick={() => onInitiateDelete(trade.id)}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          )}

          {/* Exit Reason Note */}
          {!isOpen && trade.exit_reason && (
            <span
              className="text-xs font-medium text-slate-500 max-w-[120px] truncate block"
              title={trade.exit_reason}
            >
              {trade.exit_reason}
            </span>
          )}
        </div>
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
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);
  
  // Interactive confirmation states
  const [closingId, setClosingId] = useState<number | null>(null);
  const [isClosing, setIsClosing] = useState<boolean>(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [tradesRes, statsRes] = await Promise.all([
        tradesApi.listTrades({ page_size: 100 }),
        tradesApi.getStats(),
      ]);
      setTrades(tradesRes.data.items || []);
      setStats(statsRes.data);
      setLastSync(new Date());
    } catch (e) {
      console.error("Failed to load trades:", e);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // Initial load
  useEffect(() => { 
    setMounted(true);
    setLastSync(new Date());
    load(); 
  }, []);

  // Market Hours helper: NSE trading session 09:00 AM to 04:00 PM (16:00) IST
  const isMarketActive = () => {
    try {
      const now = new Date();
      const istStr = now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" });
      const istDate = new Date(istStr);
      const day = istDate.getDay();
      if (day === 0 || day === 6) return false; // Weekend closed
      const hour = istDate.getHours();
      const min = istDate.getMinutes();
      const totalMinutes = hour * 60 + min;
      // 09:00 AM (540 min) to 16:00 PM (960 min)
      return totalMinutes >= 540 && totalMinutes <= 960;
    } catch {
      return true;
    }
  };

  // Auto-refresh interval (every 10 seconds during market hours up to 4:00 PM IST)
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(async () => {
      // User constraint: Stop auto tick sync after 4:00 PM IST
      if (!isMarketActive()) {
        return;
      }

      // Only trigger price update if there are OPEN positions and not currently closing/deleting
      const hasOpen = trades.some((t) => t.status === "OPEN");
      if (hasOpen && !isClosing && !isDeleting) {
        try {
          // Trigger async background update (sync=false) to avoid proxy timeout/socket hang up
          await tradesApi.updateAll(false);
          await load(true);
        } catch (err) {
          console.debug("Auto-refresh silent error:", err);
        }
      } else {
        await load(true);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [autoRefresh, trades.length, isClosing, isDeleting]);

  // Handle manual full update
  const handleUpdateAll = async () => {
    setUpdating(true);
    try {
      await tradesApi.updateAll(true);
      await load(true);
      setNotification({ type: "success", message: "Live market prices & P&L updated successfully!" });
    } catch (e: any) {
      setNotification({ type: "error", message: `Update failed: ${e.message}` });
    } finally {
      setUpdating(false);
      setTimeout(() => setNotification(null), 4000);
    }
  };

  // Close Trade Workflow
  const handleInitiateClose = (id: number) => {
    setDeletingId(null);
    setClosingId(id);
  };

  const handleCancelClose = () => {
    setClosingId(null);
  };

  const handleConfirmClose = async (trade: Trade) => {
    setIsClosing(true);
    try {
      const exitPrice = trade.current_price || trade.entry_price;
      await tradesApi.closeTrade(trade.id, exitPrice, "Manual close from trades dashboard");
      setNotification({
        type: "success",
        message: `Successfully closed ${trade.symbol.replace(".NS", "")} at ₹${exitPrice.toFixed(2)}.`
      });
      setClosingId(null);
      await load(true);
    } catch (e: any) {
      setNotification({
        type: "error",
        message: `Failed to close trade: ${e.message}`
      });
    } finally {
      setIsClosing(false);
      setTimeout(() => setNotification(null), 5000);
    }
  };

  // Delete Trade Workflow
  const handleInitiateDelete = (id: number) => {
    setClosingId(null);
    setDeletingId(id);
  };

  const handleCancelDelete = () => {
    setDeletingId(null);
  };

  const handleConfirmDelete = async (id: number) => {
    setIsDeleting(true);
    try {
      await tradesApi.deleteTrade(id);
      setNotification({ type: "success", message: "Trade record deleted permanently." });
      setDeletingId(null);
      await load(true);
    } catch (e: any) {
      setNotification({ type: "error", message: `Failed to delete trade: ${e.message}` });
    } finally {
      setIsDeleting(false);
      setTimeout(() => setNotification(null), 4000);
    }
  };

  // Bulk Delete Closed Trades
  const handleDeleteAllClosed = async () => {
    const closedCount = trades.filter((t) => t.status !== "OPEN").length;
    if (closedCount === 0) return;
    if (!window.confirm(`Delete ALL ${closedCount} closed trades permanently from the database?`)) return;
    try {
      const res = await tradesApi.deleteAllClosed();
      setNotification({ type: "success", message: `Deleted ${res.data.deleted_count} closed trade records.` });
      await load(true);
    } catch (e: any) {
      setNotification({ type: "error", message: `Error: ${e.message}` });
    } finally {
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const filtered = trades.filter((t) => {
    if (filter === "OPEN") return t.status === "OPEN";
    if (filter === "CLOSED") return t.status !== "OPEN";
    return true;
  });

  const closedCount = trades.filter((t) => t.status !== "OPEN").length;
  const openCount = trades.filter((t) => t.status === "OPEN").length;

  return (
    <div className="p-8 flex flex-col gap-8 bg-slate-50/80 min-h-screen">
      {/* Toast Notification Banner */}
      {notification && (
        <div className={`p-4 rounded-xl border flex items-center justify-between shadow-sm animate-in fade-in slide-in-from-top-2 duration-200 ${
          notification.type === "success" 
            ? "bg-emerald-50 border-emerald-200 text-emerald-800" 
            : "bg-rose-50 border-rose-200 text-rose-800"
        }`}>
          <div className="flex items-center gap-2.5 font-semibold text-sm">
            {notification.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{notification.message}</span>
          </div>
          <button 
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-slate-600 p-1 rounded"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
              Paper Trading Desk
            </h1>
            {openCount > 0 && (
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                {openCount} Active {openCount === 1 ? "Position" : "Positions"}
              </span>
            )}
          </div>
          <p className="text-sm mt-1 text-slate-500 font-medium">
            Live tick tracking &bull; Dynamic ATR Stop Loss &bull; RSI Overbought Exit
          </p>
        </div>

        {/* Live Controls Bar */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Auto Refresh Toggle */}
          <div className="flex items-center gap-2 bg-white px-3.5 py-2 rounded-xl border border-slate-200 shadow-sm text-xs font-bold text-slate-700">
            <div className="flex items-center gap-1.5">
              <span className={`w-2.5 h-2.5 rounded-full ${!isMarketActive() ? "bg-amber-400" : autoRefresh ? "bg-emerald-500 animate-pulse" : "bg-slate-300"}`} />
              <span>
                {!isMarketActive() ? "Market Closed (Idle > 4 PM)" : "Live Tick Sync (10s)"}
              </span>
            </div>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-2 py-0.5 rounded text-[11px] font-extrabold transition-colors ${
                !isMarketActive()
                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                  : autoRefresh 
                    ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200" 
                    : "bg-slate-200 text-slate-600 hover:bg-slate-300"
              }`}
              title={!isMarketActive() ? "Auto-sync paused after 4:00 PM IST market close" : "Toggle 10s auto tick refresh"}
            >
              {!isMarketActive() ? "PAUSED (>4PM)" : autoRefresh ? "ON" : "PAUSED"}
            </button>
          </div>

          {/* Clear closed trades button */}
          {closedCount > 0 && (
            <button
              onClick={handleDeleteAllClosed}
              className="flex items-center gap-1.5 bg-white border border-rose-200 text-rose-600 hover:bg-rose-50 px-3.5 py-2 rounded-xl text-xs font-bold transition-colors shadow-sm"
            >
              <Trash2 size={14} />
              Clear {closedCount} Closed
            </button>
          )}

          {/* Manual Update P&L Button */}
          <button
            onClick={handleUpdateAll}
            disabled={updating}
            className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-sm transition-all disabled:opacity-50"
          >
            <RefreshCw size={14} className={updating ? "animate-spin" : ""} />
            <span>{updating ? "Updating Live..." : "Refresh P&L"}</span>
          </button>
        </div>
      </div>

      {/* Portfolio Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {/* Realized P&L */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-5 text-emerald-600">
              <TrendingUp size={64} />
            </div>
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 relative z-10">Realized P&amp;L</div>
            <div className={`text-2xl font-black mb-1 relative z-10 ${(stats.realized_pnl ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {formatINR(stats.realized_pnl)}
            </div>
            <div className="text-xs font-medium text-slate-400 relative z-10">
              {stats.closed_trades} closed positions
            </div>
          </div>
          
          {/* Unrealized P&L */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Unrealized P&amp;L (Live)</div>
            <div className={`text-2xl font-black mb-1 ${(stats.unrealized_pnl ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {formatINR(stats.unrealized_pnl)}
            </div>
            <div className="text-xs font-medium text-slate-400">
              {stats.open_trades} active {stats.open_trades === 1 ? "position" : "positions"}
            </div>
          </div>
          
          {/* Win Rate */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Win Rate</div>
            <div className={`text-2xl font-black mb-1 ${(stats.win_rate ?? 0) >= 50 ? "text-emerald-600" : "text-slate-800"}`}>
              {stats.win_rate?.toFixed(1)}%
            </div>
            <div className="text-xs font-medium text-slate-400">
              {stats.winning_trades}W &bull; {stats.losing_trades}L
            </div>
          </div>
          
          {/* Expectancy */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Trade Expectancy</div>
            <div className={`text-2xl font-black mb-1 ${(stats.expectancy ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {stats.expectancy != null ? `${stats.expectancy >= 0 ? "+" : ""}${stats.expectancy.toFixed(2)}%` : "-"}
            </div>
            <div className="text-xs font-medium text-slate-400">Expected return per trade</div>
          </div>
        </div>
      )}

      {/* Filter and Count */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-2 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm w-fit">
          {(["ALL", "OPEN", "CLOSED"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${
                filter === f 
                  ? "bg-slate-900 text-white shadow-sm" 
                  : "bg-transparent text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f === "ALL" ? "All Trades" : f === "OPEN" ? `Open (${openCount})` : `Closed (${closedCount})`}
            </button>
          ))}
          <div className="w-px h-5 bg-slate-200 mx-1" />
          <span className="text-xs font-bold text-slate-400 px-2">
            Showing {filtered.length}
          </span>
        </div>

        {/* Sync Timestamp */}
        <div className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
          <Clock size={13} />
          <span suppressHydrationWarning>
            Last sync: {mounted && lastSync ? lastSync.toLocaleTimeString("en-IN") : "--:--:--"}
          </span>
        </div>
      </div>

      {/* Trades Table */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-100 rounded-xl mb-3 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
            <Briefcase className="text-slate-400" size={32} />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-1.5">No trades in this view</p>
          <p className="text-sm font-medium text-slate-500 max-w-sm mb-6">
            Find high-probability swing trades on the Research desk and deploy them to live paper tracking with 1 click.
          </p>
          <Link href="/research" className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-6 py-2.5 rounded-xl text-sm transition-colors shadow-sm">
            Open Research Desk
          </Link>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-100">
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Symbol</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Status</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Entry / Qty</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Stop Loss</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Target</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Live Price</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">P&amp;L</th>
                  <th className="py-3.5 px-4 text-xs font-bold uppercase tracking-wider text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filtered.map((trade) => (
                  <TradeRow
                    key={trade.id}
                    trade={trade}
                    closingId={closingId}
                    isClosing={isClosing && closingId === trade.id}
                    onInitiateClose={handleInitiateClose}
                    onConfirmClose={handleConfirmClose}
                    onCancelClose={handleCancelClose}
                    deletingId={deletingId}
                    isDeleting={isDeleting && deletingId === trade.id}
                    onInitiateDelete={handleInitiateDelete}
                    onConfirmDelete={handleConfirmDelete}
                    onCancelDelete={handleCancelDelete}
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
