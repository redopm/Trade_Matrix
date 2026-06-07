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
  Check,
  Minus,
  X,
  Plus,
  TrendingUp,
  TrendingDown,
  Activity,
  ChevronDown,
  BarChart2,
  Globe,
  Layers,
  RefreshCw,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────
interface SectorInfo {
  count: number;
  symbols: string[];
}
interface UniverseData {
  total_stocks: number;
  total_sectors: number;
  sectors: Record<string, SectorInfo>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
        active
          ? "bg-indigo-600 text-white shadow-sm"
          : "bg-white text-slate-500 hover:bg-slate-100 border border-slate-200"
      }`}
    >
      {label}
    </button>
  );
}

function FilterBadge({ passed }: { passed: boolean }) {
  return (
    <span className={`flex items-center justify-center w-5 h-5 rounded-md ${passed ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-500"}`}>
      {passed ? <Check size={12} strokeWidth={3} /> : <Minus size={12} strokeWidth={3} />}
    </span>
  );
}

// ─── Static sector fallback (renders even if backend is down) ────────────────
const STATIC_SECTORS: Record<string, number> = {
  "Financial Services": 62,
  "Information Technology": 44,
  "Healthcare": 49,
  "Capital Goods": 47,
  "Automobile & Auto Components": 36,
  "Chemicals": 34,
  "Construction & Real Estate": 32,
  "Fast Moving Consumer Goods": 32,
  "Consumer Discretionary": 26,
  "Metals & Mining": 25,
  "Power": 18,
  "Oil Gas & Consumable Fuels": 16,
  "Textiles & Apparel": 16,
  "Transportation & Logistics": 14,
  "Cement & Construction Materials": 14,
  "Agriculture & Food Processing": 14,
  "Telecommunication": 11,
  "Media & Entertainment": 9,
  "Diversified": 4,
};


function SectorDropdown({
  universe,
  selectedSector,
  onSelect,
}: {
  universe: UniverseData | null;
  selectedSector: string | null;
  onSelect: (sector: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const label = selectedSector
    ? `${selectedSector} (${universe?.sectors[selectedSector]?.count ?? 0})`
    : `All Sectors (${universe?.total_stocks ?? "..."} stocks)`;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 bg-white border border-slate-200 hover:border-indigo-400 text-slate-700 font-bold text-sm px-4 py-2.5 rounded-xl shadow-sm transition-all min-w-[260px] justify-between"
      >
        <span className="flex items-center gap-2">
          <Layers size={15} className="text-indigo-500" />
          {label}
        </span>
        <ChevronDown size={16} className={`text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-50 top-full mt-2 left-0 w-[320px] bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden">
          {/* All Sectors option */}
          <button
            onClick={() => { onSelect(null); setOpen(false); }}
            className={`w-full flex items-center justify-between px-4 py-3 text-sm font-bold transition-colors border-b border-slate-100 ${
              selectedSector === null ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50 text-slate-700"
            }`}
          >
            <span className="flex items-center gap-2">
              <Globe size={14} />
              All Sectors
            </span>
            <span className="text-xs font-mono bg-slate-100 px-2 py-0.5 rounded-full text-slate-500">
              {universe?.total_stocks ?? 0} stocks
            </span>
          </button>

          {/* Sector list */}
          <div className="max-h-[380px] overflow-y-auto">
            {universe &&
              Object.entries(universe.sectors).map(([sector, info]) => (
                <button
                  key={sector}
                  onClick={() => { onSelect(sector); setOpen(false); }}
                  className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors ${
                    selectedSector === sector
                      ? "bg-indigo-50 text-indigo-700 font-bold"
                      : "hover:bg-slate-50 text-slate-600 font-semibold"
                  }`}
                >
                  <span>{sector}</span>
                  <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${
                    selectedSector === sector ? "bg-indigo-100 text-indigo-600" : "bg-slate-100 text-slate-500"
                  }`}>
                    {info.count} stocks
                  </span>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sector Stock List ────────────────────────────────────────────────────────
function SectorStockList({ sector, universe }: { sector: string; universe: UniverseData }) {
  const symbols = universe.sectors[sector]?.symbols ?? [];
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/60">
        <div className="flex items-center gap-2">
          <BarChart2 size={16} className="text-indigo-500" />
          <span className="font-bold text-slate-800 text-sm">{sector}</span>
          <span className="text-xs text-slate-400 font-medium">— {symbols.length} stocks in universe</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 p-4">
        {symbols.map((sym) => (
          <span
            key={sym}
            className="text-xs font-bold font-mono bg-slate-50 border border-slate-200 text-slate-600 px-2.5 py-1 rounded-lg hover:border-indigo-300 hover:text-indigo-600 transition-colors cursor-default"
          >
            {sym.replace(".NS", "")}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Progress Panel ───────────────────────────────────────────────────────────
function ScreenerProgress({ status, onClose }: { status: ScreenerRunStatus; onClose: () => void }) {
  const isDone = status.status === "COMPLETED" || status.status === "FAILED";
  return (
    <div className={`rounded-xl p-5 border shadow-sm ${
      status.status === "FAILED" ? "border-red-200 bg-red-50" :
      status.status === "COMPLETED" ? "border-emerald-200 bg-emerald-50" :
      "border-indigo-200 bg-indigo-50"
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {!isDone && <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />}
          <span className={`font-bold text-sm ${
            status.status === "RUNNING" ? "text-indigo-700" :
            status.status === "COMPLETED" ? "text-emerald-700" : "text-red-700"
          }`}>
            {status.status === "RUNNING" ? `Scanning ${status.current_symbol || "..."}` :
             status.status === "COMPLETED" ? `✅ Complete! Found ${status.passed} signals` :
             "❌ Screener Failed"}
          </span>
        </div>
        {isDone && (
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        )}
      </div>
      <div className="w-full bg-white/60 h-2 rounded-full overflow-hidden mb-3">
        <div
          className={`h-full transition-all duration-500 ${
            status.status === "FAILED" ? "bg-red-500" :
            status.status === "COMPLETED" ? "bg-emerald-500" : "bg-indigo-500"
          }`}
          style={{ width: `${status.progress_pct}%` }}
        />
      </div>
      <div className="grid grid-cols-4 gap-3 text-sm">
        <div className="bg-white/70 rounded-lg p-2 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-0.5">Progress</div>
          <div className="font-mono font-bold text-indigo-700 text-xs">{status.processed}/{status.total_symbols}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-2 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-0.5">Signals</div>
          <div className="font-mono font-bold text-emerald-700 text-xs">{status.passed}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-2 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-0.5">Failed Data</div>
          <div className="font-mono font-bold text-red-600 text-xs">{status.failed_data}</div>
        </div>
        <div className="bg-white/70 rounded-lg p-2 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-0.5">Market</div>
          <div className="font-mono font-bold text-slate-700 text-xs">{status.market_regime || "—"}</div>
        </div>
      </div>
    </div>
  );
}

// ─── Signal Detail Modal ──────────────────────────────────────────────────────
function SignalDetailModal({ signal, onClose, onTrade }: { signal: Signal; onClose: () => void; onTrade: (id: number) => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-8 border border-slate-200" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-2xl font-black text-slate-900">{signal.symbol?.replace(".NS", "")}</h3>
            <p className="text-sm font-medium text-slate-500 mt-1">
              {signal.company_name} &bull; <span className="text-indigo-600 font-bold">{signal.sector}</span> &bull; {(signal as any).interval || "1D"}
            </p>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
            <X size={24} />
          </button>
        </div>

        <div className="mb-6">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Filter Results</div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: signal.direction === "SHORT" ? "ROCE < 20%" : "ROCE > 15%", passed: signal.passed_roce, value: `${signal.roce?.toFixed(1) ?? "N/A"}%` },
              { label: signal.direction === "SHORT" ? "D/E > 0.5" : "D/E < 1.0", passed: signal.passed_debt_to_equity, value: signal.debt_to_equity?.toFixed(2) ?? "N/A" },
              { label: signal.direction === "SHORT" ? "Price < 200 EMA" : "Price > 200 EMA", passed: signal.passed_ema_200, value: `₹${signal.ema_200?.toFixed(0) ?? "N/A"}` },
              { label: signal.direction === "SHORT" ? "RSI > 65" : "RSI < 30", passed: signal.passed_rsi, value: signal.rsi_14?.toFixed(1) ?? "N/A" },
              { label: "Piotroski ≥ 7", passed: signal.passed_piotroski, value: `${signal.piotroski_f_score ?? "N/A"}/9` },
              { label: "Event Risk OK", passed: signal.passed_earnings_blackout, value: "±3 days" },
            ].map((f) => (
              <div key={f.label} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div>
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">{f.label}</div>
                  <div className="text-sm font-mono font-bold text-slate-900 mt-0.5">{f.value}</div>
                </div>
                {f.passed ? <CheckCircle2 size={18} className="text-emerald-500" /> : <XCircle size={18} className="text-red-500" />}
              </div>
            ))}
          </div>
        </div>

        <div className="mb-6">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Trade Parameters</div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-xl bg-blue-50 border border-blue-100">
              <div className="text-[11px] font-bold text-blue-600 uppercase mb-1">Entry</div>
              <div className="font-mono font-bold text-slate-900">₹{signal.suggested_entry?.toFixed(2) ?? "-"}</div>
            </div>
            <div className="p-3 rounded-xl bg-red-50 border border-red-100">
              <div className="text-[11px] font-bold text-red-600 uppercase mb-1">Stop Loss</div>
              <div className="font-mono font-bold text-red-700">₹{signal.suggested_sl?.toFixed(2) ?? "-"}</div>
            </div>
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100">
              <div className="text-[11px] font-bold text-emerald-600 uppercase mb-1">Target</div>
              <div className="font-mono font-bold text-emerald-700">₹{signal.suggested_target?.toFixed(2) ?? "-"}</div>
            </div>
          </div>
          <div className="text-center mt-4 p-3 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-sm font-bold text-slate-700">
              Risk:Reward = <span className="text-amber-600">{signal.risk_reward_ratio?.toFixed(2) ?? "-"}</span>
            </span>
          </div>
        </div>

        {signal.passed_all && !signal.is_traded && (
          <button
            className="w-full flex justify-center items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3.5 rounded-xl transition-colors shadow-sm"
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

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function ScreenerPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [runStatus, setRunStatus] = useState<ScreenerRunStatus | null>(null);
  const [passedOnly, setPassedOnly] = useState(true);
  const [directionFilter, setDirectionFilter] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"composite_score" | "rsi_14" | "roce">("composite_score");
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [viewChartSymbol, setViewChartSymbol] = useState<string | null>(null);
  const [tradeSuccess, setTradeSuccess] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [marketRegime, setMarketRegime] = useState<any>(null);
  const [universe, setUniverse] = useState<UniverseData | null>(null);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load universe (sectors) — with static fallback if backend is slow
  useEffect(() => {
    const controller = new AbortController();
    screenerApi.getSectorBreakdown()
      .then((r) => setUniverse(r.data))
      .catch(() => {
        // Backend timeout or down — build minimal universe from static data
        const fallbackSectors: Record<string, SectorInfo> = {};
        Object.entries(STATIC_SECTORS).forEach(([s, count]) => {
          fallbackSectors[s] = { count, symbols: [] };
        });
        setUniverse({
          total_stocks: Object.values(STATIC_SECTORS).reduce((a, b) => a + b, 0),
          total_sectors: Object.keys(STATIC_SECTORS).length,
          sectors: fallbackSectors,
        });
      });
    return () => controller.abort();
  }, []);

  const loadMarketRegime = async () => {
    try {
      const res = await screenerApi.getMarketRegime();
      setMarketRegime(res.data);
    } catch (e) {
      console.error("Failed to load market regime", e);
    }
  };

  const loadSignals = useCallback(async () => {
    setApiError(null);
    try {
      const res = await screenerApi.getResults({
        passed_only: passedOnly,
        sort_by: sortBy,
        page_size: 500,
        direction: directionFilter || undefined,
        sector: selectedSector || undefined,
      });
      setSignals(res.data.items || []);
    } catch (e: any) {
      const msg = e?.message || "Failed to load signals";
      console.error("loadSignals error:", msg);
      setApiError(msg);
    } finally {
      setLoading(false);
    }
  }, [passedOnly, sortBy, directionFilter, selectedSector]);

  useEffect(() => {
    loadSignals();
    loadMarketRegime();
  }, [loadSignals]);

  // Auto-refresh signals when user comes back to this tab
  // (e.g. after cancelling a trade on the Trades page)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        loadSignals();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [loadSignals]);

  const startScreener = async () => {
    try {
      // Prefer sending sector name (lightweight) over full symbol list
      const payload: { symbols?: string[]; sector?: string } = {};
      if (selectedSector) {
        // Use symbol list only if we got it from API, else send sector name
        const sectorSymbols = universe?.sectors[selectedSector]?.symbols;
        if (sectorSymbols && sectorSymbols.length > 0) {
          payload.symbols = sectorSymbols;
        } else {
          payload.sector = selectedSector;  // Backend resolves it
        }
      }
      // No sector selected → send empty body (full universe on backend)

      const res = await screenerApi.startRun(Object.keys(payload).length ? payload : undefined);
      const runId = res.data.run_id;

      if (wsRef.current) wsRef.current.close();
      wsRef.current = createScreenerWebSocket(
        runId,
        (data) => {
          setRunStatus(data);
          if (data.status === "COMPLETED") loadSignals();
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
      setTradeSuccess("Trade added to paper portfolio!");
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

  const sectorStockCount = selectedSector && universe
    ? universe.sectors[selectedSector]?.count
    : universe?.total_stocks;

  return (
    <div className="p-8 flex flex-col gap-6 bg-slate-50 min-h-screen">

      {/* ── Header ── */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Alpha Screener</h1>
          <p className="text-sm mt-1 text-slate-500 font-medium">
            NSE Universe &bull; {universe?.total_stocks ?? "..."} stocks across {universe?.total_sectors ?? "..."} sectors
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Refresh button */}
          <button
            onClick={() => { loadSignals(); loadMarketRegime(); }}
            title="Refresh signals"
            className="p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-500 hover:text-indigo-600 transition-colors shadow-sm"
          >
            <RefreshCw size={16} />
          </button>

          {/* Sector Dropdown */}
          <SectorDropdown
            universe={universe}
            selectedSector={selectedSector}
            onSelect={setSelectedSector}
          />

          {/* Run Button */}
          <button
            onClick={startScreener}
            disabled={runStatus?.status === "RUNNING"}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-sm transition-all"
          >
            {runStatus?.status === "RUNNING" ? (
              <><div className="w-2 h-2 rounded-full bg-white animate-pulse" /> Scanning...</>
            ) : (
              <><PlayCircle size={18} /> {selectedSector ? `Run: ${selectedSector}` : "Run Full Screener"}</>
            )}
          </button>
        </div>
      </div>

      {/* ── Toast ── */}
      {tradeSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 p-4 rounded-xl flex items-center gap-3 shadow-sm font-bold text-sm">
          <CheckCircle2 size={18} /> {tradeSuccess}
        </div>
      )}

      {/* ── API Error Banner ── */}
      {apiError && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center justify-between shadow-sm text-sm">
          <div className="flex items-center gap-3">
            <XCircle size={18} className="shrink-0" />
            <span><span className="font-bold">API Error:</span> {apiError}</span>
          </div>
          <button onClick={() => setApiError(null)} className="text-red-400 hover:text-red-600 ml-4">
            <X size={16} />
          </button>
        </div>
      )}

      {/* ── Market Regime ── */}
      {marketRegime && (
        <div className={`p-4 rounded-xl border flex items-center justify-between shadow-sm ${
          marketRegime.regime === "BULLISH" ? "bg-emerald-50 border-emerald-200" :
          marketRegime.regime === "BEARISH" ? "bg-red-50 border-red-200" :
          "bg-slate-100 border-slate-300"
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${
              marketRegime.regime === "BULLISH" ? "bg-emerald-100 text-emerald-700" :
              marketRegime.regime === "BEARISH" ? "bg-red-100 text-red-700" :
              "bg-slate-200 text-slate-700"
            }`}>
              {marketRegime.regime === "BULLISH" ? <TrendingUp size={22} /> :
               marketRegime.regime === "BEARISH" ? <TrendingDown size={22} /> :
               <Activity size={22} />}
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 flex items-center gap-2">
                Market: {marketRegime.regime}
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-white/50 text-slate-700">
                  {Math.round(marketRegime.confidence * 100)}%
                </span>
              </h2>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5">
                {/* Nifty 50 */}
                <span className="text-xs font-medium text-slate-600">
                  Nifty&nbsp;50: <span className="font-bold">₹{marketRegime.nifty_price?.toLocaleString("en-IN")}</span>
                </span>

                {/* Nifty Bank */}
                {marketRegime.nifty_bank && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs font-medium text-slate-600">
                      Bank&nbsp;Nifty: <span className="font-bold">₹{marketRegime.nifty_bank?.toLocaleString("en-IN")}</span>
                    </span>
                  </>
                )}

                {/* Sensex */}
                {marketRegime.sensex && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs font-medium text-slate-600">
                      Sensex: <span className="font-bold">₹{marketRegime.sensex?.toLocaleString("en-IN")}</span>
                    </span>
                  </>
                )}

                {/* VIX — colour coded */}
                <span className="text-slate-300">•</span>
                <span className="text-xs font-medium text-slate-600">
                  VIX:{" "}
                  {marketRegime.vix ? (
                    <span className={`font-bold ${
                      marketRegime.vix < 15 ? "text-emerald-600" :
                      marketRegime.vix < 20 ? "text-amber-600"   :
                      "text-red-600"
                    }`}>
                      {marketRegime.vix.toFixed(2)}
                    </span>
                  ) : (
                    <span className="font-bold text-slate-400">N/A</span>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Progress ── */}
      {runStatus && (
        <ScreenerProgress status={runStatus} onClose={() => setRunStatus(null)} />
      )}

      {/* ── Sector Stock Universe (shown when sector selected) ── */}
      {selectedSector && universe && (
        <SectorStockList sector={selectedSector} universe={universe} />
      )}

      {/* ── Filters Bar ── */}
      <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 pl-1">View:</div>
        <div className="flex gap-1">
          <FilterChip label="Passed Only" active={passedOnly} onClick={() => setPassedOnly(true)} />
          <FilterChip label="All Screened" active={!passedOnly} onClick={() => setPassedOnly(false)} />
        </div>

        <div className="w-px h-5 bg-slate-200" />

        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Direction:</div>
        <div className="flex gap-1">
          <FilterChip label="All" active={directionFilter === null} onClick={() => setDirectionFilter(null)} />
          <FilterChip label="LONG" active={directionFilter === "LONG"} onClick={() => setDirectionFilter("LONG")} />
          <FilterChip label="SHORT" active={directionFilter === "SHORT"} onClick={() => setDirectionFilter("SHORT")} />
        </div>

        <div className="w-px h-5 bg-slate-200" />

        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Sort:</div>
        <div className="flex gap-1">
          <FilterChip label="Score" active={sortBy === "composite_score"} onClick={() => setSortBy("composite_score")} />
          <FilterChip label="RSI" active={sortBy === "rsi_14"} onClick={() => setSortBy("rsi_14")} />
          <FilterChip label="ROCE" active={sortBy === "roce"} onClick={() => setSortBy("roce")} />
        </div>

        <div className="ml-auto text-sm font-bold text-slate-400 pr-2">
          {sortedSignals.length} results
          {selectedSector && (
            <span className="ml-2 text-indigo-500">• {selectedSector}</span>
          )}
        </div>
      </div>

      {/* ── Sector Summary Cards (when no sector selected) ── */}
      {!selectedSector && universe && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {Object.entries(universe.sectors).map(([sector, info]) => (
            <button
              key={sector}
              onClick={() => setSelectedSector(sector)}
              className="bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-md rounded-xl p-3 text-left transition-all group"
            >
              <div className="text-[11px] font-bold text-slate-500 group-hover:text-indigo-600 transition-colors leading-tight mb-1">{sector}</div>
              <div className="font-mono font-black text-lg text-slate-900">{info.count}</div>
              <div className="text-[10px] text-slate-400 font-medium">stocks</div>
            </button>
          ))}
        </div>
      )}

      {/* ── Results Table ── */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-14 bg-slate-100 rounded-lg mb-3 animate-pulse" />
          ))}
        </div>
      ) : sortedSignals.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
            <SearchX className="text-slate-300" size={32} />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-2">No signals found</p>
          <p className="text-sm font-medium text-slate-500 max-w-sm mb-6">
            {selectedSector
              ? `Run the screener for the "${selectedSector}" sector to find signals.`
              : "Run the full screener to scan all stocks."}
          </p>
          <button
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-6 py-2.5 rounded-xl transition-colors"
            onClick={startScreener}
          >
            {selectedSector ? `Run ${selectedSector} Screener` : "Run Full Screener"}
          </button>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead>
                <tr className="bg-slate-50/70 border-b border-slate-100">
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Symbol</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Sector</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Dir</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Price</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">RSI</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">EMA 200</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">ROCE</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">D/E</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">F-Score</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">AI Signal</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Score</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Filters</th>
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedSignals.map((sig, i) => (
                  <tr
                    key={sig.id || i}
                    className="border-b border-slate-100 hover:bg-indigo-50/20 cursor-pointer transition-colors"
                    onClick={() => setSelectedSignal(sig)}
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-sm text-slate-900">{sig.symbol?.replace(".NS", "")}</div>
                      <div className="text-[11px] font-medium text-slate-400 max-w-[100px] truncate">{sig.company_name}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-[11px] font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-lg">{sig.sector || "—"}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        sig.direction === "LONG" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                      }`}>
                        {sig.direction || "LONG"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm font-semibold text-slate-700">₹{sig.signal_price?.toFixed(2)}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-mono text-sm font-bold ${(sig.rsi_14 ?? 100) < 30 ? "text-blue-600 bg-blue-50 px-2 py-0.5 rounded" : "text-slate-600"}`}>
                        {sig.rsi_14?.toFixed(1) ?? "—"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-semibold text-slate-600">₹{sig.ema_200?.toFixed(0) ?? "—"}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                        {sig.roce?.toFixed(1) ?? "—"}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-semibold text-slate-600">{sig.debt_to_equity?.toFixed(2) ?? "—"}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-mono text-sm font-bold ${(sig.piotroski_f_score ?? 0) >= 7 ? "text-emerald-600" : "text-amber-600"}`}>
                        {sig.piotroski_f_score ?? "—"}/9
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {sig.pattern_name && sig.pattern_name !== "no_pattern" ? (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                          sig.passed_all ? "bg-indigo-50 text-indigo-700 border-indigo-200" : "bg-slate-50 text-slate-500 border-slate-200"
                        }`}>
                          {sig.pattern_name.replace(/_/g, " ").toUpperCase()}
                          <span className="opacity-70 ml-1 font-mono">{((sig.pattern_confidence ?? 0) * 100).toFixed(0)}%</span>
                        </span>
                      ) : (
                        <span className="text-sm font-medium text-slate-300">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm font-bold text-amber-600">{sig.composite_score?.toFixed(1) ?? "—"}</span>
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
                          className="flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold py-1.5 px-2.5 rounded-lg transition-colors"
                          onClick={() => handleTrade(sig.id)}
                        >
                          <Plus size={11} /> Trade
                        </button>
                      ) : sig.is_traded ? (
                        <span className="text-[11px] font-bold text-slate-400 bg-slate-50 border border-slate-100 px-2 py-1 rounded">Traded</span>
                      ) : (
                        <span className="text-[11px] font-bold text-red-500 bg-red-50 border border-red-100 px-2 py-1 rounded">Failed</span>
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
        <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} onTrade={handleTrade} />
      )}

      {viewChartSymbol && (
        <ChartModal symbol={viewChartSymbol} chartPath="" onClose={() => setViewChartSymbol(null)} />
      )}
    </div>
  );
}
