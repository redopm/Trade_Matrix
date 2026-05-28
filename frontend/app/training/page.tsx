"use client";

import { useState, useEffect, useRef } from "react";
import { patternsApi } from "@/lib/api";

type Stage = "idle" | "download" | "labeling" | "training" | "done" | "error";

interface ProgressEvent {
  stage: Stage;
  pct: number;
  message: string;
  timestamp?: string;
}

interface ModelStatus {
  model: {
    is_ready: boolean;
    cv_accuracy?: number;
    n_samples?: number;
    n_classes?: number;
    classes?: string[];
    trained_at?: string;
    top_features?: [string, number][];
    model_size_kb?: number;
  };
  labels: { total: number; by_pattern: Record<string, number>; by_source: Record<string, number> };
  gemini_quota: {
    used_today: number;
    daily_limit: number;
    remaining: number;
    is_exhausted: boolean;
  };
}

const STAGE_LABELS: Record<string, string> = {
  idle: "Ready",
  download: "📥 Downloading stock data",
  labeling: "🤖 Gemini Vision labeling",
  training: "🧠 Training XGBoost model",
  done: "✅ Complete",
  error: "❌ Error",
};

const STAGE_ORDER: Stage[] = ["download", "labeling", "training", "done"];

function StageIndicator({ stage, active, pct }: { stage: Stage; active: string; pct?: number }) {
  const labels: Record<string, string> = {
    download: "Download Data",
    labeling: "Gemini Label",
    training: "Train Model",
    done: "Complete",
  };
  const done = STAGE_ORDER.indexOf(stage) < STAGE_ORDER.indexOf(active as unknown as Stage);
  return (
    <div className="flex flex-col items-center gap-2 flex-1">
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all duration-500"
        style={{
          background: done
            ? "var(--accent-green)"
            : stage === active
            ? "var(--accent-blue)"
            : "var(--bg-card)",
          borderColor: done
            ? "var(--accent-green)"
            : stage === active
            ? "var(--accent-blue)"
            : "var(--border-primary)",
          color: done || stage === active ? "#000" : "var(--text-muted)",
        }}
      >
        {done ? "✓" : STAGE_ORDER.indexOf(stage) + 1}
      </div>
      <span className="text-xs text-center" style={{ color: stage === active ? "var(--text-bright)" : "var(--text-muted)" }}>
        {labels[stage]}
      </span>
    </div>
  );
}

export default function TrainingPage() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [currentStage, setCurrentStage] = useState<Stage>("idle");
  const [currentPct, setCurrentPct] = useState(0);
  const [currentMsg, setCurrentMsg] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<"pipeline" | "labels" | "colab">("pipeline");
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const loadStatus = async () => {
    try {
      const res = await patternsApi.getStatus();
      setStatus(res.data);
    } catch {}
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const startTraining = async () => {
    setIsRunning(true);
    setProgress([]);
    setCurrentStage("download");
    setCurrentPct(0);

    try {
      await patternsApi.startTraining();
    } catch {}

    const ws = new WebSocket(`ws://localhost:8000/api/v1/patterns/ws/train`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data) as ProgressEvent & { type?: string };

      if (data.type === "COMPLETE") {
        setIsRunning(false);
        loadStatus();
        return;
      }

      setCurrentStage(data.stage);
      setCurrentPct(data.pct);
      setCurrentMsg(data.message);
      setProgress((prev) => [data, ...prev].slice(0, 200));

      // Auto-scroll logs
      setTimeout(() => {
        logRef.current?.scrollTo({ top: 0 });
      }, 50);
    };

    ws.onclose = () => setIsRunning(false);
    ws.onerror = () => { setIsRunning(false); setCurrentStage("error"); };
  };

  const cancelTraining = async () => {
    wsRef.current?.close();
    try { await patternsApi.cancelTraining(); } catch {}
    setIsRunning(false);
  };

  const trainModelOnly = async () => {
    setIsRunning(true);
    try {
      const res = await patternsApi.trainModelOnly();
      alert(`✅ Model trained! CV Accuracy: ${(res.data.cv_accuracy * 100).toFixed(1)}%`);
      loadStatus();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const model = status?.model;
  const labels = status?.labels;
  const quota = status?.gemini_quota;

  return (
    <div className="flex flex-col gap-6 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black" style={{ color: "var(--text-bright)" }}>
            Phase 2 Training Pipeline
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Gemini Vision labeling → XGBoost classifier → Real-time detection
          </p>
        </div>
        <div className="flex gap-3">
          {labels && labels.total >= 50 && !model?.is_ready && (
            <button
              onClick={trainModelOnly}
              disabled={isRunning}
              className="btn-ghost px-4 py-2"
            >
              🧠 Train from Labels
            </button>
          )}
          <button
            onClick={isRunning ? cancelTraining : startTraining}
            className={`${isRunning ? "btn-ghost" : "btn-primary"} px-5 py-2`}
            style={isRunning ? { color: "var(--accent-red)", borderColor: "rgba(255,68,102,0.4)" } : {}}
          >
            {isRunning ? "⏹ Cancel" : "▶ Start Pipeline"}
          </button>
        </div>
      </div>

      {/* Model Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-label">Model Status</div>
          <div className="stat-value text-lg">
            <span style={{ color: model?.is_ready ? "var(--accent-green)" : "var(--accent-red)" }}>
              {model?.is_ready ? "✅ Ready" : "⚠ Not trained"}
            </span>
          </div>
          <div className="stat-change" style={{ color: "var(--text-muted)" }}>
            {model?.trained_at ? new Date(model.trained_at).toLocaleDateString("en-IN") : "Run pipeline first"}
          </div>
        </div>
        <div className="stat-card card-green">
          <div className="stat-label">CV Accuracy</div>
          <div className="stat-value" style={{ color: (model?.cv_accuracy ?? 0) >= 0.7 ? "var(--accent-green)" : "var(--accent-gold)" }}>
            {model?.cv_accuracy ? `${(model.cv_accuracy * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="stat-change">{model?.n_classes ?? 0} pattern classes</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Labeled Charts</div>
          <div className="stat-value" style={{ color: "var(--accent-blue)" }}>
            {labels?.total ?? 0}
          </div>
          <div className="stat-change" style={{ color: "var(--text-muted)" }}>
            {model?.n_samples ?? 0} training samples
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Gemini Quota</div>
          <div className="stat-value" style={{ color: quota?.is_exhausted ? "var(--accent-red)" : "var(--accent-green)" }}>
            {quota?.remaining ?? "—"} left
          </div>
          <div className="stat-change" style={{ color: "var(--text-muted)" }}>
            {quota?.used_today ?? 0}/{quota?.daily_limit ?? 1400} used today
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b" style={{ borderColor: "var(--border-primary)" }}>
        {(["pipeline", "labels", "colab"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === t
                ? "border-[var(--accent-blue)] text-white"
                : "border-transparent text-[var(--text-muted)] hover:text-white"
            }`}
          >
            {t === "pipeline" ? "🔄 Pipeline" : t === "labels" ? "🏷 Labels" : "☁ Colab CNN"}
          </button>
        ))}
      </div>

      {/* Pipeline Tab */}
      {activeTab === "pipeline" && (
        <div className="flex flex-col gap-5">
          {/* Stage Progress */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-6">
              {STAGE_ORDER.map((s, i) => (
                <>
                  <StageIndicator key={s} stage={s} active={currentStage} pct={currentPct} />
                  {i < STAGE_ORDER.length - 1 && (
                    <div className="h-px flex-1" style={{ background: "var(--border-primary)" }} />
                  )}
                </>
              ))}
            </div>

            {isRunning && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span style={{ color: "var(--text-bright)" }}>{STAGE_LABELS[currentStage]}</span>
                  <span className="font-mono" style={{ color: "var(--accent-blue)" }}>{currentPct}%</span>
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${currentPct}%`,
                      background: "linear-gradient(90deg, var(--accent-blue), var(--accent-green))",
                    }}
                  />
                </div>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{currentMsg}</p>
              </div>
            )}
          </div>

          {/* Live Logs */}
          {progress.length > 0 && (
            <div className="card p-4">
              <div className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-muted)" }}>
                Live Logs
              </div>
              <div
                ref={logRef}
                className="font-mono text-xs overflow-y-auto space-y-1"
                style={{ maxHeight: "240px", color: "var(--text-secondary)" }}
              >
                {progress.map((p, i) => (
                  <div key={i} className="flex gap-3 py-0.5">
                    <span style={{ color: p.stage === "error" ? "var(--accent-red)" : "var(--text-muted)", minWidth: 60 }}>
                      {p.pct > 0 ? `${p.pct}%` : "  —"}
                    </span>
                    <span style={{ color: p.stage === "done" ? "var(--accent-green)" : p.stage === "error" ? "var(--accent-red)" : "var(--text-secondary)" }}>
                      {p.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pattern class breakdown */}
          {labels && labels.by_pattern && Object.keys(labels.by_pattern).length > 0 && (
            <div className="card p-5">
              <div className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "var(--text-muted)" }}>
                Labels by Pattern
              </div>
              <div className="space-y-2">
                {Object.entries(labels.by_pattern)
                  .sort(([, a], [, b]) => b - a)
                  .map(([pattern, count]) => {
                    const total = labels.total || 1;
                    const pct = (count / total) * 100;
                    const isBullish = ["double_bottom", "hs_bottom", "bull_flag", "cup_handle", "ascending_triangle"].includes(pattern);
                    return (
                      <div key={pattern} className="flex items-center gap-3">
                        <span className="text-xs w-40 truncate" style={{ color: "var(--text-secondary)" }}>
                          {pattern.replace(/_/g, " ")}
                        </span>
                        <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${pct}%`,
                              background: isBullish ? "var(--accent-green)" : "var(--accent-red)",
                            }}
                          />
                        </div>
                        <span className="text-xs font-mono w-8 text-right" style={{ color: "var(--text-muted)" }}>
                          {count}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Labels Tab */}
      {activeTab === "labels" && (
        <div className="card p-5">
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {labels?.total ?? 0} chart windows labeled
            </p>
            <a
              href="http://localhost:8000/api/v1/patterns/labels/export"
              download="tradematrix_labels.jsonl"
              className="btn-ghost text-sm px-3 py-1.5"
            >
              ⬇ Export for Colab
            </a>
          </div>
          {labels?.by_source && (
            <div className="flex gap-4">
              {Object.entries(labels.by_source).map(([src, cnt]) => (
                <div key={src} className="badge-blue">
                  {src}: {cnt}
                </div>
              ))}
            </div>
          )}
          {!labels?.total && (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">🏷</div>
              <p style={{ color: "var(--text-muted)" }}>No labels yet. Run the pipeline to start labeling.</p>
            </div>
          )}
        </div>
      )}

      {/* Colab Tab */}
      {activeTab === "colab" && (
        <div className="flex flex-col gap-4">
          <div className="card p-6">
            <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-bright)" }}>
              ☁ Google Colab CNN Upgrade
            </h2>
            <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
              No GPU locally? Use Colab's free T4 GPU to train an{" "}
              <strong style={{ color: "var(--accent-blue)" }}>EfficientNet-B0 CNN</strong>{" "}
              — higher accuracy than XGBoost for complex patterns.
            </p>

            <div className="space-y-4">
              {[
                { step: "1", title: "Export Labels", desc: "Download your labeled dataset from the Labels tab", action: (
                  <a href="http://localhost:8000/api/v1/patterns/labels/export" download className="btn-ghost text-xs px-3 py-1">
                    ⬇ Export JSONL
                  </a>
                )},
                { step: "2", title: "Open Colab Notebook", desc: "Upload TradeMatrix_Phase2_CNN_Colab.ipynb to Google Colab (free T4 GPU)", action: null },
                { step: "3", title: "Train CNN", desc: "Upload labels.jsonl, run all cells. Takes ~20 min on T4 GPU.", action: null },
                { step: "4", title: "Import Model", desc: "Download colab_model.pkl → place in models/ → click Import", action: (
                  <button className="btn-primary text-xs px-3 py-1" onClick={async () => {
                    try {
                      const res = await patternsApi.importColabModel();
                      alert(`✅ ${res.data.message}`);
                      loadStatus();
                    } catch (e: any) {
                      alert(`Error: ${e.message}`);
                    }
                  }}>
                    📥 Import Model
                  </button>
                )},
              ].map((item) => (
                <div key={item.step} className="flex gap-4 items-start p-4 rounded-xl" style={{ background: "var(--bg-primary)" }}>
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-black flex-shrink-0"
                    style={{ background: "var(--accent-blue)", color: "#000" }}
                  >
                    {item.step}
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold text-sm" style={{ color: "var(--text-bright)" }}>{item.title}</div>
                    <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{item.desc}</div>
                  </div>
                  {item.action}
                </div>
              ))}
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-bold mb-3" style={{ color: "var(--text-bright)" }}>
              XGBoost vs CNN Comparison
            </h3>
            <table className="data-table w-full text-sm">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>XGBoost (local)</th>
                  <th>CNN EfficientNet (Colab)</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Speed", "< 1ms", "~50ms"],
                  ["GPU needed", "❌ CPU only", "✅ Free T4 GPU"],
                  ["Accuracy", "~72%", "~82%"],
                  ["Input", "23 features", "Chart image (224×224)"],
                  ["Training time", "~15 min (CPU)", "~20 min (T4 GPU)"],
                  ["Best for", "Real-time screening", "Higher confidence"],
                ].map(([feat, xgb, cnn]) => (
                  <tr key={feat}>
                    <td style={{ color: "var(--text-muted)" }}>{feat}</td>
                    <td style={{ color: "var(--text-secondary)" }}>{xgb}</td>
                    <td style={{ color: "var(--accent-blue)" }}>{cnn}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
