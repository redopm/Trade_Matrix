"use client";

import { useState, useEffect, useRef } from "react";
import { patternsApi } from "@/lib/api";
import { 
  Brain, 
  Download, 
  Tag, 
  Cpu, 
  CheckCircle2, 
  XCircle, 
  Play, 
  Square, 
  DownloadCloud, 
  Database,
  BarChart,
  HardDrive,
  UploadCloud,
  ChevronRight,
  Zap,
  Server
} from "lucide-react";

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

const STAGE_LABELS: Record<string, { text: string; icon: React.ReactNode }> = {
  idle: { text: "Ready", icon: <Brain size={16} /> },
  download: { text: "Downloading stock data", icon: <Download size={16} /> },
  labeling: { text: "Gemini Vision labeling", icon: <Tag size={16} /> },
  training: { text: "Training XGBoost model", icon: <Cpu size={16} /> },
  done: { text: "Complete", icon: <CheckCircle2 size={16} /> },
  error: { text: "Error", icon: <XCircle size={16} /> },
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
  const isActive = stage === active;
  
  return (
    <div className="flex flex-col items-center gap-3 flex-1 relative z-10">
      <div
        className={`w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold border-4 transition-all duration-500 shadow-sm ${
          done
            ? "bg-emerald-500 border-emerald-200 text-white"
            : isActive
            ? "bg-blue-600 border-blue-200 text-white"
            : "bg-white border-slate-200 text-slate-400"
        }`}
      >
        {done ? <CheckCircle2 size={20} /> : STAGE_ORDER.indexOf(stage) + 1}
      </div>
      <span className={`text-xs font-bold text-center uppercase tracking-wider ${isActive ? "text-blue-700" : done ? "text-emerald-700" : "text-slate-400"}`}>
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

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/patterns/ws/train`;
    const ws = new WebSocket(wsUrl);
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
      alert(`Model trained! CV Accuracy: ${(res.data.cv_accuracy * 100).toFixed(1)}%`);
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
    <div className="p-8 flex flex-col gap-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Phase 2 Training Pipeline
          </h1>
          <p className="text-sm mt-2 text-slate-500 font-medium">
            Gemini Vision labeling &rarr; XGBoost classifier &rarr; Real-time detection
          </p>
        </div>
        <div className="flex gap-4">
          {labels && labels.total >= 50 && !model?.is_ready && (
            <button
              onClick={trainModelOnly}
              disabled={isRunning}
              className="flex items-center gap-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 px-5 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-50"
            >
              <Cpu size={18} /> Train from Labels
            </button>
          )}
          <button
            onClick={isRunning ? cancelTraining : startTraining}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-bold shadow-sm transition-colors ${
              isRunning 
                ? "bg-red-50 text-red-600 border border-red-200 hover:bg-red-100" 
                : "bg-blue-600 hover:bg-blue-700 text-white"
            }`}
          >
            {isRunning ? <><Square size={16} /> Cancel</> : <><Play size={16} /> Start Pipeline</>}
          </button>
        </div>
      </div>

      {/* Model Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-5 text-blue-600">
            <Server size={64} />
          </div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 relative z-10">Model Status</div>
          <div className={`text-2xl font-black mb-1 relative z-10 ${model?.is_ready ? "text-emerald-600" : "text-amber-600"}`}>
            {model?.is_ready ? "Ready" : "Not trained"}
          </div>
          <div className="text-xs font-medium text-slate-400 relative z-10">
            {model?.trained_at ? new Date(model.trained_at).toLocaleDateString("en-IN") : "Run pipeline first"}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-emerald-200 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-5 text-emerald-600">
            <CheckCircle2 size={64} />
          </div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 relative z-10">CV Accuracy</div>
          <div className={`text-2xl font-black mb-1 relative z-10 ${(model?.cv_accuracy ?? 0) >= 0.7 ? "text-emerald-600" : "text-amber-600"}`}>
            {model?.cv_accuracy ? `${(model.cv_accuracy * 100).toFixed(1)}%` : "-"}
          </div>
          <div className="text-xs font-medium text-emerald-700 bg-emerald-50 inline-block px-2 py-0.5 rounded relative z-10">
            {model?.n_classes ?? 0} pattern classes
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Labeled Charts</div>
          <div className="text-2xl font-black mb-1 text-blue-600">
            {labels?.total ?? 0}
          </div>
          <div className="text-xs font-medium text-slate-400">
            {model?.n_samples ?? 0} training samples
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Gemini Quota</div>
          <div className={`text-2xl font-black mb-1 ${quota?.is_exhausted ? "text-red-600" : "text-emerald-600"}`}>
            {quota?.remaining ?? "-"} left
          </div>
          <div className="text-xs font-medium text-slate-400">
            {quota?.used_today ?? 0}/{quota?.daily_limit ?? 1400} used today
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        {(["pipeline", "labels", "colab"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-6 py-3 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === t
                ? "border-blue-600 text-blue-700 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-100"
            }`}
          >
            {t === "pipeline" && <Cpu size={18} />}
            {t === "labels" && <Tag size={18} />}
            {t === "colab" && <CloudCog size={18} />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Pipeline Tab */}
      {activeTab === "pipeline" && (
        <div className="flex flex-col gap-6">
          {/* Stage Progress */}
          <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="relative flex items-center justify-between mb-8 max-w-3xl mx-auto">
              <div className="absolute left-0 right-0 top-1/2 h-1 bg-slate-100 -translate-y-1/2 z-0 rounded-full" />
              {STAGE_ORDER.map((s, i) => (
                <StageIndicator key={s} stage={s} active={currentStage} pct={currentPct} />
              ))}
            </div>

            {isRunning ? (
              <div className="space-y-3 bg-slate-50 p-6 rounded-xl border border-slate-100 max-w-3xl mx-auto">
                <div className="flex items-center justify-between text-sm font-bold">
                  <div className="flex items-center gap-2 text-slate-800">
                    {STAGE_LABELS[currentStage]?.icon}
                    {STAGE_LABELS[currentStage]?.text || currentStage}
                  </div>
                  <span className="font-mono text-blue-600">{currentPct}%</span>
                </div>
                <div className="h-3 rounded-full overflow-hidden bg-slate-200">
                  <div
                    className="h-full rounded-full transition-all duration-500 bg-blue-500"
                    style={{ width: `${currentPct}%` }}
                  />
                </div>
                <p className="text-xs font-medium text-slate-500 mt-2">{currentMsg}</p>
              </div>
            ) : (
              <div className="text-center text-sm font-medium text-slate-500 max-w-3xl mx-auto">
                Pipeline is idle. Click "Start Pipeline" to begin data collection, Gemini labeling, and XGBoost training.
              </div>
            )}
          </div>

          {/* Live Logs */}
          {progress.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
              <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
                <Terminal size={16} /> Live Execution Logs
              </div>
              <div
                ref={logRef}
                className="font-mono text-xs overflow-y-auto space-y-1.5"
                style={{ maxHeight: "300px" }}
              >
                {progress.map((p, i) => (
                  <div key={i} className="flex gap-4 py-0.5">
                    <span className={`min-w-[60px] ${p.stage === "error" ? "text-red-400" : "text-slate-500"}`}>
                      {p.pct > 0 ? `${p.pct}%` : "  -"}
                    </span>
                    <span className={`${p.stage === "done" ? "text-emerald-400" : p.stage === "error" ? "text-red-400" : "text-slate-300"}`}>
                      {p.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pattern class breakdown */}
          {labels && labels.by_pattern && Object.keys(labels.by_pattern).length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
              <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
                <BarChart size={16} /> Labels by Pattern Class
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-4">
                {Object.entries(labels.by_pattern)
                  .sort(([, a], [, b]) => b - a)
                  .map(([pattern, count]) => {
                    const total = labels.total || 1;
                    const pct = (count / total) * 100;
                    const isBullish = ["double_bottom", "hs_bottom", "bull_flag", "cup_handle", "ascending_triangle"].includes(pattern);
                    return (
                      <div key={pattern} className="flex items-center gap-4">
                        <span className="text-sm font-bold text-slate-700 w-40 truncate">
                          {pattern.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                        </span>
                        <div className="flex-1 h-2.5 rounded-full overflow-hidden bg-slate-100">
                          <div
                            className={`h-full rounded-full ${isBullish ? "bg-emerald-500" : "bg-red-500"}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-sm font-mono font-bold text-slate-500 w-12 text-right">
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
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          <div className="flex justify-between items-center mb-8 border-b border-slate-100 pb-6">
            <div>
              <h3 className="text-xl font-bold text-slate-900">Training Dataset</h3>
              <p className="text-sm font-medium text-slate-500 mt-1">
                {labels?.total ?? 0} chart windows labeled by Gemini Pro Vision
              </p>
            </div>
            <a
              href="/api/v1/patterns/labels/export"
              download
              className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
            >
              <DownloadCloud size={18} /> Export JSONL
            </a>
          </div>
          
          {labels?.by_source && (
            <div className="mb-8">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Data Sources</h4>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(labels.by_source).map(([src, cnt]) => (
                  <div key={src} className="flex items-center gap-2 bg-blue-50 border border-blue-100 text-blue-700 px-3 py-1.5 rounded-lg text-sm font-bold">
                    <Database size={14} /> {src}: {cnt}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {!labels?.total && (
            <div className="text-center py-16 bg-slate-50 rounded-xl border border-slate-100">
              <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm text-slate-300">
                <Tag size={32} />
              </div>
              <p className="text-lg font-bold text-slate-900 mb-2">No labels yet</p>
              <p className="text-sm font-medium text-slate-500">Run the pipeline to start labeling charts using Gemini Vision.</p>
            </div>
          )}
        </div>
      )}

      {/* Colab Tab */}
      {activeTab === "colab" && (
        <div className="flex flex-col gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
                <CloudCog size={28} />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-900">
                  Google Colab CNN Upgrade
                </h2>
                <p className="text-sm font-medium text-slate-500 mt-2 max-w-2xl">
                  No GPU locally? Use Colab's free T4 GPU to train an <strong className="text-blue-600">EfficientNet-B0 CNN</strong> on your dataset. CNNs provide higher accuracy than XGBoost for complex visual chart patterns.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
              {[
                { step: "1", title: "Export Labels", desc: (
                    <>
                      <p className="text-sm text-slate-600 mt-2">Export your labeled dataset to JSONL format for training.</p>
                      <a href="/api/v1/patterns/labels/export" download className="flex w-fit items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold px-3 py-1.5 rounded transition-colors mt-2">
                        <Download size={14} /> Export JSONL
                      </a>
                    </>
                ), action: null },
                { step: "2", title: "Open Colab Notebook", desc: "Upload TradeMatrix_Phase2_CNN_Colab.ipynb to Google Colab and select the free T4 GPU runtime.", action: null },
                { step: "3", title: "Train CNN", desc: "Upload the labels.jsonl file to the Colab environment and run all cells. This takes ~20 mins on a T4 GPU.", action: null },
                { step: "4", title: "Import Model", desc: "Download colab_model.pkl from Colab, place it in the backend models/ directory, and click Import.", action: (
                  <button className="flex w-fit items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1.5 rounded transition-colors mt-2" onClick={async () => {
                    try {
                      const res = await patternsApi.importColabModel();
                      alert(`Success: ${res.data.message}`);
                      loadStatus();
                    } catch (e: any) {
                      alert(`Error: ${e.message}`);
                    }
                  }}>
                    <UploadCloud size={14} /> Import Model
                  </button>
                )},
              ].map((item) => (
                <div key={item.step} className="flex gap-4 items-start p-5 rounded-xl border border-slate-100 bg-slate-50 hover:bg-slate-100 transition-colors">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-black bg-blue-600 text-white flex-shrink-0 shadow-sm">
                    {item.step}
                  </div>
                  <div className="flex-1 flex flex-col">
                    <div className="font-bold text-sm text-slate-900">{item.title}</div>
                    <div className="text-xs font-medium text-slate-500 mt-1">{item.desc}</div>
                    {item.action && <div className="mt-auto pt-2">{item.action}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
              <Zap size={20} className="text-amber-500" /> XGBoost vs CNN Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left whitespace-nowrap">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400 rounded-tl-lg">Feature</th>
                    <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-400">XGBoost (Local)</th>
                    <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-blue-600 bg-blue-50 rounded-tr-lg">CNN EfficientNet (Colab)</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Inference Speed", "< 1ms", "~50ms"],
                    ["Hardware Needed", "CPU only", "Free T4 GPU"],
                    ["Expected Accuracy", "~72%", "~82%"],
                    ["Model Input", "23 extracted features", "Raw Chart Image (224x224)"],
                    ["Training Time", "~15 min (CPU)", "~20 min (T4 GPU)"],
                    ["Best Used For", "Real-time rapid screening", "High confidence signals"],
                  ].map(([feat, xgb, cnn], i) => (
                    <tr key={feat} className="border-b border-slate-50 last:border-0">
                      <td className="py-3 px-4 text-sm font-bold text-slate-600">{feat}</td>
                      <td className="py-3 px-4 text-sm font-medium text-slate-500">{xgb}</td>
                      <td className="py-3 px-4 text-sm font-bold text-blue-700 bg-blue-50/30">{cnn}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Missing icons to fix undefined
function CloudCog({ size }: { size?: number }) {
  return <Server size={size} />;
}

function Terminal({ size }: { size?: number }) {
  return <Cpu size={size} />;
}
