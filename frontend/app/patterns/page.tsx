"use client";

import { useEffect, useState } from "react";
import { patternsApi } from "@/lib/api";
import Image from "next/image";

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

const PATTERN_LABELS: Record<string, { label: string; emoji: string; color: string }> = {
  double_bottom: { label: "Double Bottom", emoji: "W", color: "var(--accent-green)" },
  hs_bottom: { label: "Inv. H&S", emoji: "⊓", color: "var(--accent-green)" },
  bull_flag: { label: "Bull Flag", emoji: "🚩", color: "var(--accent-green)" },
  cup_handle: { label: "Cup & Handle", emoji: "☕", color: "var(--accent-green)" },
  ascending_triangle: { label: "Asc. Triangle", emoji: "△", color: "var(--accent-green)" },
  double_top: { label: "Double Top", emoji: "M", color: "var(--accent-red)" },
  bear_flag: { label: "Bear Flag", emoji: "🚩", color: "var(--accent-red)" },
  descending_triangle: { label: "Desc. Triangle", emoji: "▽", color: "var(--accent-red)" },
  no_pattern: { label: "No Pattern", emoji: "—", color: "var(--text-muted)" },
};

function ConfidenceBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: "var(--bg-primary)" }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${value * 100}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono w-10" style={{ color }}>
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
  const meta = PATTERN_LABELS[pname] || { label: pname, emoji: "?", color: "var(--text-muted)" };
  const isSignificant = result.pattern_name && result.pattern_name !== "no_pattern";

  return (
    <tr className="animate-fade-in cursor-pointer" onClick={() => isSignificant && onChartClick(result)}>
      <td>
        <div className="font-bold" style={{ color: "var(--text-bright)" }}>
          {result.symbol.replace(".NS", "")}
        </div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          {result.detection_date}
        </div>
      </td>
      <td>
        {isSignificant ? (
          <div
            className="flex items-center gap-2 px-2 py-1 rounded-lg w-fit"
            style={{ background: `${meta.color}20`, border: `1px solid ${meta.color}40` }}
          >
            <span style={{ color: meta.color }}>{meta.emoji}</span>
            <span className="text-sm font-semibold" style={{ color: meta.color }}>
              {meta.label}
            </span>
          </div>
        ) : (
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>—</span>
        )}
      </td>
      <td className="w-40">
        {isSignificant ? (
          <ConfidenceBar value={result.confidence} color={meta.color} />
        ) : (
          <span style={{ color: "var(--text-muted)" }}>—</span>
        )}
      </td>
      <td>
        {result.is_confluence ? (
          <span className="badge-green px-3 py-1">🎯 Confluence</span>
        ) : result.is_bullish === true ? (
          <span className="badge-blue">Bullish</span>
        ) : result.is_bullish === false ? (
          <span className="badge-red">Bearish</span>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>—</span>
        )}
      </td>
      <td>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {result.model_used}
        </span>
      </td>
      <td>
        {isSignificant && (
          <button
            className="btn-ghost text-xs py-1 px-2"
            onClick={(e) => { e.stopPropagation(); onChartClick(result); }}
          >
            📈 Chart
          </button>
        )}
      </td>
    </tr>
  );
}

function ChartModal({ result, onClose }: { result: PatternResult; onClose: () => void }) {
  const pname = result.pattern_name || "no_pattern";
  const meta = PATTERN_LABELS[pname] || { label: pname, emoji: "?", color: "var(--text-muted)" };
  const chartUrl = `http://localhost:8000/api/v1/patterns/chart/${result.symbol.replace(".NS", "")}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.85)" }}
      onClick={onClose}
    >
      <div
        className="card max-w-4xl w-full p-6 animate-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-black" style={{ color: "var(--text-bright)" }}>
                {result.symbol.replace(".NS", "")}
              </h2>
              <div
                className="px-3 py-1 rounded-lg text-sm font-bold"
                style={{ background: `${meta.color}20`, color: meta.color, border: `1px solid ${meta.color}40` }}
              >
                {meta.emoji} {meta.label}
              </div>
              {result.is_confluence && (
                <span className="badge-green text-sm">🎯 Confluence Signal</span>
              )}
            </div>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Confidence: {(result.confidence * 100).toFixed(0)}% · {result.detection_date} · {result.model_used}
            </p>
          </div>
          <button onClick={onClose} className="text-xl" style={{ color: "var(--text-muted)" }}>✕</button>
        </div>

        {/* Chart Image */}
        <div
          className="rounded-xl overflow-hidden mb-4"
          style={{ background: "var(--bg-primary)", border: "1px solid var(--border-primary)" }}
        >
          <img
            src={chartUrl}
            alt={`${result.symbol} chart`}
            className="w-full"
            style={{ maxHeight: 400, objectFit: "contain" }}
          />
        </div>

        {/* All Pattern Scores */}
        {result.all_scores && Object.keys(result.all_scores).length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-muted)" }}>
              All Pattern Scores
            </div>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(result.all_scores)
                .sort(([, a], [, b]) => b - a)
                .map(([pattern, score]) => {
                  const m = PATTERN_LABELS[pattern];
                  return (
                    <div key={pattern} className="flex items-center gap-2">
                      <span className="text-xs w-32" style={{ color: "var(--text-secondary)" }}>
                        {m?.label || pattern}
                      </span>
                      <ConfidenceBar value={score} color={m?.color || "var(--text-muted)"} />
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
    <div className="flex flex-col gap-6 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black" style={{ color: "var(--text-bright)" }}>
            Pattern Recognition
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Phase 2 · XGBoost/CNN detector · 8 classical patterns
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <div className="flex gap-2">
            <input
              className="input-dark text-sm"
              placeholder="RELIANCE"
              value={searchSym}
              onChange={(e) => setSearchSym(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && detectSingle()}
              style={{ width: 140, padding: "8px 12px" }}
            />
            <button
              onClick={detectSingle}
              disabled={detecting || !modelReady}
              className="btn-ghost px-3 py-2 text-sm"
            >
              {detecting ? "..." : "🔍"}
            </button>
          </div>
          <button
            onClick={detectAll}
            disabled={loading || !modelReady}
            className="btn-primary px-4 py-2"
          >
            {loading ? "Scanning..." : "⚡ Detect All Signals"}
          </button>
        </div>
      </div>

      {!modelReady && (
        <div
          className="p-4 rounded-xl text-sm flex items-center gap-3"
          style={{
            background: "rgba(255,215,0,0.1)",
            border: "1px solid rgba(255,215,0,0.3)",
            color: "var(--accent-gold)",
          }}
        >
          <span className="text-xl">⚠️</span>
          <div>
            <strong>Model not trained yet.</strong>
            <span className="ml-2">
              Go to{" "}
              <a href="/training" className="underline" style={{ color: "var(--accent-blue)" }}>
                Training Pipeline
              </a>{" "}
              to train the pattern classifier first.
            </span>
          </div>
        </div>
      )}

      {/* Stats */}
      {results.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="stat-card card-green">
            <div className="stat-label">Confluence Signals</div>
            <div className="stat-value" style={{ color: "var(--accent-green)" }}>{confluenceCount}</div>
            <div className="stat-change">Phase 1 + Pattern both ✓</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Patterns Found</div>
            <div className="stat-value" style={{ color: "var(--accent-blue)" }}>{patternCount}</div>
            <div className="stat-change">of {results.length} scanned</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Detection Rate</div>
            <div className="stat-value" style={{ color: "var(--accent-gold)" }}>
              {results.length > 0 ? ((patternCount / results.length) * 100).toFixed(0) : 0}%
            </div>
            <div className="stat-change">Pattern hit rate</div>
          </div>
        </div>
      )}

      {/* Filters */}
      {results.length > 0 && (
        <div className="flex gap-2">
          {(["ALL", "CONFLUENCE", "BULLISH", "BEARISH"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`filter-chip ${filter === f ? "active" : ""}`}
            >
              {f === "CONFLUENCE" ? `🎯 ${f}` : f}
            </button>
          ))}
          <span className="ml-auto text-sm" style={{ color: "var(--text-muted)" }}>
            {filtered.length} results
          </span>
        </div>
      )}

      {/* Results Table */}
      {loading ? (
        <div className="card p-8">
          {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-12 rounded mb-2" />)}
        </div>
      ) : results.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="text-6xl mb-4">🔍</div>
          <p className="text-xl font-bold" style={{ color: "var(--text-bright)" }}>
            No detections yet
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
            {modelReady
              ? 'Click "⚡ Detect All Signals" to scan Phase 1 results for patterns'
              : "Train the model first, then run detection"}
          </p>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Pattern</th>
                  <th>Confidence</th>
                  <th>Signal</th>
                  <th>Model</th>
                  <th>Chart</th>
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
