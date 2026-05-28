"use client";

import { useEffect, useState } from "react";
import { patternsApi } from "@/lib/api";
import { 
  Search, 
  ScanSearch, 
  AlertCircle, 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  LineChart, 
  X,
  Target
} from "lucide-react";

interface PatternResult {
  symbol: string;
  pattern_name: string | null;
  confidence: number;
  is_bullish: boolean | null;
  is_confluence: boolean;
  chart_path: string | null;
  model_used: string;
  all_scores: Record<string, number>;
  detection_date: string;
  features?: Record<string, number>;
}

const PATTERN_LABELS: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  double_bottom: { label: "Double Bottom", icon: <Activity size={16} />, color: "text-emerald-600 bg-emerald-50" },
  hs_bottom: { label: "Inv. H&S", icon: <TrendingUp size={16} />, color: "text-emerald-600 bg-emerald-50" },
  bull_flag: { label: "Bull Flag", icon: <TrendingUp size={16} />, color: "text-emerald-600 bg-emerald-50" },
  cup_handle: { label: "Cup & Handle", icon: <Activity size={16} />, color: "text-emerald-600 bg-emerald-50" },
  ascending_triangle: { label: "Asc. Triangle", icon: <TrendingUp size={16} />, color: "text-emerald-600 bg-emerald-50" },
  double_top: { label: "Double Top", icon: <Activity size={16} />, color: "text-red-600 bg-red-50" },
  bear_flag: { label: "Bear Flag", icon: <TrendingDown size={16} />, color: "text-red-600 bg-red-50" },
  descending_triangle: { label: "Desc. Triangle", icon: <TrendingDown size={16} />, color: "text-red-600 bg-red-50" },
  no_pattern: { label: "No Pattern", icon: <Target size={16} />, color: "text-slate-500 bg-slate-50" },
};

function ConfidenceBar({ value, colorClass }: { value: number; colorClass: string }) {
  const isGreen = colorClass.includes("emerald");
  const isRed = colorClass.includes("red");
  const barColor = isGreen ? "bg-emerald-500" : isRed ? "bg-red-500" : "bg-slate-400";
  const textColor = isGreen ? "text-emerald-700" : isRed ? "text-red-700" : "text-slate-600";

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className={`text-xs font-bold w-12 ${textColor}`}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function PatternCard({ result, onChartClick }: {
  result: PatternResult;
  onChartClick: (result: PatternResult) => void;
}) {
  const pname = result.pattern_name || "no_pattern";
  const meta = PATTERN_LABELS[pname] || PATTERN_LABELS.no_pattern;
  const isSignificant = result.pattern_name && result.pattern_name !== "no_pattern";

  return (
    <tr 
      className={`border-b border-slate-100 transition-colors ${isSignificant ? "hover:bg-blue-50/50 cursor-pointer" : ""}`}
      onClick={() => isSignificant && onChartClick(result)}
    >
      <td className="py-4 px-4">
        <div className="font-bold text-slate-900">
          {result.symbol.replace(".NS", "")}
        </div>
        <div className="text-xs text-slate-500 font-medium">
          {result.detection_date}
        </div>
      </td>
      <td className="py-4 px-4">
        {isSignificant ? (
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md w-fit font-bold text-xs ${meta.color}`}>
            {meta.icon}
            <span>{meta.label}</span>
          </div>
        ) : (
          <span className="text-sm font-medium text-slate-400">-</span>
        )}
      </td>
      <td className="w-48 py-4 px-4">
        {isSignificant ? (
          <ConfidenceBar value={result.confidence} colorClass={meta.color} />
        ) : (
          <span className="text-sm font-medium text-slate-400">-</span>
        )}
      </td>
      <td className="py-4 px-4">
        {result.is_confluence ? (
          <span className="text-xs font-bold text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-md border border-emerald-200">
            Confluence
          </span>
        ) : result.is_bullish === true ? (
          <span className="text-xs font-bold text-blue-700 bg-blue-100 px-2.5 py-1 rounded-md">
            Bullish
          </span>
        ) : result.is_bullish === false ? (
          <span className="text-xs font-bold text-red-700 bg-red-100 px-2.5 py-1 rounded-md">
            Bearish
          </span>
        ) : (
          <span className="text-sm font-medium text-slate-400">-</span>
        )}
      </td>
      <td className="py-4 px-4">
        <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-1 rounded">
          {result.model_used}
        </span>
      </td>
      <td className="py-4 px-4">
        {isSignificant && (
          <button
            className="flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded transition-colors"
            onClick={(e) => { e.stopPropagation(); onChartClick(result); }}
          >
            <LineChart size={14} /> Chart
          </button>
        )}
      </td>
    </tr>
  );
}

function ChartModal({ result, onClose }: { result: PatternResult; onClose: () => void }) {
  const pname = result.pattern_name || "no_pattern";
  const meta = PATTERN_LABELS[pname] || PATTERN_LABELS.no_pattern;
  const chartUrl = `http://localhost:8000/api/v1/patterns/chart/${result.symbol.replace(".NS", "")}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl max-w-4xl w-full p-8 border border-slate-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-black text-slate-900">
                {result.symbol.replace(".NS", "")}
              </h2>
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold ${meta.color}`}>
                {meta.icon} {meta.label}
              </div>
              {result.is_confluence && (
                <span className="text-sm font-bold text-emerald-700 bg-emerald-100 px-3 py-1.5 rounded-lg border border-emerald-200">
                  Confluence Signal
                </span>
              )}
            </div>
            <p className="text-sm mt-2 text-slate-500 font-medium">
              Confidence: <strong className="text-slate-700">{(result.confidence * 100).toFixed(0)}%</strong> &bull; {result.detection_date} &bull; {result.model_used}
            </p>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
            <X size={24} />
          </button>
        </div>

        {/* Chart Image */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden mb-6 flex justify-center p-4">
          <img
            src={chartUrl}
            alt={`${result.symbol} chart`}
            className="w-full max-h-[400px] object-contain rounded-lg shadow-sm"
          />
        </div>

        {/* All Pattern Scores */}
        {result.all_scores && Object.keys(result.all_scores).length > 0 && (
          <div className="bg-slate-50 p-5 rounded-xl border border-slate-100">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">
              All Pattern Scores
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-3">
              {Object.entries(result.all_scores)
                .sort(([, a], [, b]) => b - a)
                .map(([pattern, score]) => {
                  const m = PATTERN_LABELS[pattern] || PATTERN_LABELS.no_pattern;
                  return (
                    <div key={pattern} className="flex items-center justify-between">
                      <span className="text-sm font-medium text-slate-600 w-32">
                        {m.label}
                      </span>
                      <div className="flex-1 ml-4">
                        <ConfidenceBar value={score} colorClass={m.color} />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PatternsPage() {
  const [results, setResults] = useState<PatternResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [modelReady, setModelReady] = useState(false);
  const [selectedResult, setSelectedResult] = useState<PatternResult | null>(null);
  const [filter, setFilter] = useState<"ALL" | "CONFLUENCE" | "BULLISH" | "BEARISH">("ALL");
  const [searchSym, setSearchSym] = useState("");
  const [detecting, setDetecting] = useState(false);

  useEffect(() => {
    patternsApi.getStatus().then((res) => {
      setModelReady(res.data.model?.is_ready);
    }).catch(() => {});
  }, []);

  const detectAll = async () => {
    setLoading(true);
    try {
      const res = await patternsApi.detectAll(50);
      setResults(res.data.results || []);
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const detectSingle = async () => {
    if (!searchSym.trim()) return;
    setDetecting(true);
    try {
      const res = await patternsApi.detect(searchSym.trim(), true);
      setResults((prev) => {
        const existing = prev.findIndex((r) => r.symbol === res.data.symbol);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = res.data;
          return updated;
        }
        return [res.data, ...prev];
      });
      if (res.data.pattern_name !== "no_pattern") {
        setSelectedResult(res.data);
      }
    } catch (e: any) {
      alert(`Detection failed: ${e.message}`);
    } finally {
      setDetecting(false);
    }
  };

  const filtered = results.filter((r) => {
    if (filter === "CONFLUENCE") return r.is_confluence;
    if (filter === "BULLISH") return r.is_bullish === true;
    if (filter === "BEARISH") return r.is_bullish === false;
    return true;
  });

  const confluenceCount = results.filter((r) => r.is_confluence).length;
  const patternCount = results.filter((r) => r.pattern_name && r.pattern_name !== "no_pattern").length;

  return (
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Pattern Recognition
          </h1>
          <p className="text-sm mt-2 text-slate-500 font-medium">
            Phase 2 &bull; XGBoost/CNN detector &bull; 8 classical patterns
          </p>
        </div>
        <div className="flex gap-4 items-center">
          <div className="flex gap-2 bg-white border border-slate-200 p-1 rounded-lg shadow-sm">
            <input
              className="px-3 py-1.5 text-sm font-medium text-slate-700 outline-none w-32 bg-transparent"
              placeholder="RELIANCE"
              value={searchSym}
              onChange={(e) => setSearchSym(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && detectSingle()}
            />
            <button
              onClick={detectSingle}
              disabled={detecting || !modelReady}
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-bold rounded-md transition-colors disabled:opacity-50"
            >
              {detecting ? "..." : <Search size={16} />}
            </button>
          </div>
          <button
            onClick={detectAll}
            disabled={loading || !modelReady}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50"
          >
            {loading ? "Scanning..." : <><ScanSearch size={18} /> Detect All Signals</>}
          </button>
        </div>
      </div>

      {!modelReady && (
        <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-start gap-3 text-amber-800 shadow-sm">
          <AlertCircle className="text-amber-500 mt-0.5" size={20} />
          <div>
            <strong className="text-sm font-bold">Model not trained yet.</strong>
            <span className="text-sm font-medium ml-2 opacity-90">
              Go to{" "}
              <a href="/training" className="underline text-blue-600 font-bold hover:text-blue-800">
                Training Pipeline
              </a>{" "}
              to train the pattern classifier first.
            </span>
          </div>
        </div>
      )}

      {/* Stats */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-xl border border-emerald-200 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10 text-emerald-600">
              <Activity size={64} />
            </div>
            <div className="text-sm font-bold text-slate-500 mb-1 relative z-10">Confluence Signals</div>
            <div className="text-3xl font-black text-emerald-600 mb-1 relative z-10">{confluenceCount}</div>
            <div className="text-xs font-bold text-emerald-700 bg-emerald-50 inline-block px-2 py-0.5 rounded relative z-10">Phase 1 + Pattern</div>
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-sm font-bold text-slate-500 mb-1">Patterns Found</div>
            <div className="text-3xl font-black text-blue-600 mb-1">{patternCount}</div>
            <div className="text-xs font-medium text-slate-400">of {results.length} scanned</div>
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-sm font-bold text-slate-500 mb-1">Detection Rate</div>
            <div className="text-3xl font-black text-amber-600 mb-1">
              {results.length > 0 ? ((patternCount / results.length) * 100).toFixed(0) : 0}%
            </div>
            <div className="text-xs font-medium text-slate-400">Pattern hit rate</div>
          </div>
        </div>
      )}

      {/* Filters */}
      {results.length > 0 && (
        <div className="flex items-center gap-3 bg-white p-2 rounded-xl border border-slate-200 shadow-sm w-fit">
          {(["ALL", "CONFLUENCE", "BULLISH", "BEARISH"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 text-sm font-bold rounded-lg transition-colors ${
                filter === f 
                  ? f === "CONFLUENCE" 
                    ? "bg-emerald-100 text-emerald-700" 
                    : "bg-slate-800 text-white" 
                  : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {f === "CONFLUENCE" ? "Confluence" : f}
            </button>
          ))}
          <div className="h-6 w-px bg-slate-200 mx-2"></div>
          <span className="text-sm font-medium text-slate-400 pr-3">
            {filtered.length} results
          </span>
        </div>
      )}

      {/* Results Table */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          {[...Array(5)].map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg mb-3 animate-pulse" />)}
        </div>
      ) : results.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-16 flex flex-col items-center justify-center text-center shadow-sm">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
            <ScanSearch className="text-slate-300" size={32} />
          </div>
          <p className="text-xl font-bold text-slate-900 mb-2">
            No detections yet
          </p>
          <p className="text-sm font-medium text-slate-500 max-w-md">
            {modelReady
              ? "Click 'Detect All Signals' to scan your Phase 1 screener results for classical chart patterns."
              : "Train the model first in the Training Pipeline, then run detection."}
          </p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100">
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Symbol</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Pattern</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Confidence</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Signal</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Model</th>
                  <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <PatternCard key={`${r.symbol}_${r.detection_date}`} result={r} onChartClick={setSelectedResult} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedResult && (
        <ChartModal result={selectedResult} onClose={() => setSelectedResult(null)} />
      )}
    </div>
  );
}
