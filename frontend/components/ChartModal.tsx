"use client";

import { useEffect, useState } from "react";

export function ChartModal({
  symbol,
  chartPath,
  onClose,
}: {
  symbol: string;
  chartPath: string;
  onClose: () => void;
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  useEffect(() => {
    // If we already have the local file path from the backend, we can construct the API url to fetch it.
    // The backend provides /api/v1/patterns/chart/{symbol}
    setImageUrl(`http://localhost:8000/api/v1/patterns/chart/${symbol.replace(".NS", "")}?t=${Date.now()}`);
  }, [symbol]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      style={{ background: "rgba(0,0,0,0.8)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl rounded-2xl overflow-hidden shadow-2xl animate-scale-in"
        style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-primary)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border-primary)]">
          <h2 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-bright)" }}>
            {symbol} — Pattern Analysis
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            style={{ color: "var(--text-muted)" }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-1 min-h-[400px] flex items-center justify-center" style={{ background: "#111" }}>
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={`Chart for ${symbol}`}
              className="w-full h-auto object-contain max-h-[75vh] rounded-lg"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.src = "";
                target.alt = "Failed to load chart image. Make sure backend is running.";
              }}
            />
          ) : (
            <div className="animate-pulse flex items-center justify-center space-x-2 text-[var(--text-muted)]">
              <div className="w-4 h-4 rounded-full bg-[var(--text-secondary)] animate-bounce" />
              <div className="w-4 h-4 rounded-full bg-[var(--text-secondary)] animate-bounce" style={{ animationDelay: "0.2s" }} />
              <div className="w-4 h-4 rounded-full bg-[var(--text-secondary)] animate-bounce" style={{ animationDelay: "0.4s" }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
