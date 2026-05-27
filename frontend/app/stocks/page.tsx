"use client";

import { useState } from "react";
import { stocksApi } from "@/lib/api";

function IndicatorRow({ label, value, good, unit = "" }: {
  label: string;
  value: number | null | undefined;
  good?: boolean;
  unit?: string;
}) {
  const color = good === undefined
    ? "var(--text-primary)"
    : good
    ? "var(--accent-green)"
    : "var(--accent-red)";

  return (
    <div className="flex justify-between items-center py-2 border-b"
      style={{ borderColor: "var(--border-primary)" }}>
      <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
        {label}
      </span>
      <span className="font-mono font-bold text-sm" style={{ color }}>
        {value != null ? `${value}${unit}` : "—"}
      </span>
    </div>
  );
}

export default function StocksPage() {
  const [query, setQuery] = useState("");
  const [stockData, setStockData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await stocksApi.getSnapshot(query.trim().toUpperCase());
      setStockData(res.data);
    } catch (e: any) {
      setError(e.message);
      setStockData(null);
    } finally {
      setLoading(false);
    }
  };

  const fund = stockData?.fundamentals || {};
  const tech = stockData?.technicals || {};

  return (
    <div className="flex flex-col gap-6 animate-slide-in">
      <div>
        <h1 className="text-3xl font-black" style={{ color: "var(--text-bright)" }}>
          Stock Lookup
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          Deep-dive analysis · Fundamentals + Technical indicators
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter NSE symbol (e.g. RELIANCE, TCS, INFY)"
          className="input-dark flex-1"
          style={{ fontSize: "1rem", padding: "12px 16px" }}
        />
        <button type="submit" className="btn-primary px-6 py-3" disabled={loading}>
          {loading ? "Loading..." : "🔍 Analyze"}
        </button>
      </form>

      {error && (
        <div className="p-4 rounded-xl text-sm"
          style={{ background: "rgba(255,68,102,0.1)", color: "var(--accent-red)", border: "1px solid rgba(255,68,102,0.3)" }}>
          {error}
        </div>
      )}

      {stockData && (
        <div className="animate-slide-in">
          {/* Header */}
          <div className="card p-6 mb-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-black" style={{ color: "var(--text-bright)" }}>
                  {fund.symbol?.replace(".NS", "")}
                </h2>
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {fund.company_name} · {fund.sector} · {fund.industry}
                </p>
                <div className="flex items-center gap-3 mt-3">
                  <span className="text-3xl font-black font-mono"
                    style={{ color: "var(--accent-green)" }}>
                    ₹{tech.current_price?.toFixed(2) ?? fund.current_price?.toFixed(2) ?? "—"}
                  </span>
                  {tech.rsi && (
                    <span className={`badge-${tech.rsi < 30 ? "green" : tech.rsi > 70 ? "red" : "blue"}`}>
                      RSI: {tech.rsi?.toFixed(1)}
                    </span>
                  )}
                  {fund.fundamentals_passed !== undefined && (
                    <span className={fund.fundamentals_passed ? "badge-green" : "badge-red"}>
                      {fund.fundamentals_passed ? "✓ Fundamental Pass" : "✗ Fundamental Fail"}
                    </span>
                  )}
                </div>
              </div>
              {fund.market_cap && (
                <div className="text-right">
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>Market Cap</div>
                  <div className="font-bold font-mono" style={{ color: "var(--accent-blue)" }}>
                    ₹{(fund.market_cap / 1e9).toFixed(0)}B
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Fundamentals */}
            <div className="card p-5">
              <div className="text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ color: "var(--text-muted)" }}>
                Fundamentals
              </div>
              <IndicatorRow label="ROCE" value={fund.roce} unit="%" good={fund.roce >= 15} />
              <IndicatorRow label="ROE" value={fund.roe} unit="%" good={fund.roe >= 15} />
              <IndicatorRow label="D/E Ratio" value={fund.debt_to_equity} good={fund.debt_to_equity <= 1} />
              <IndicatorRow label="P/E Ratio" value={fund.pe_ratio} />
              <IndicatorRow label="P/B Ratio" value={fund.pb_ratio} />
              <IndicatorRow label="Piotroski F" value={fund.piotroski_f_score} unit="/9" good={(fund.piotroski_f_score ?? 0) >= 7} />
              <IndicatorRow label="Altman Z" value={fund.altman_z_score} good={(fund.altman_z_score ?? 0) > 2.99} />
              <IndicatorRow label="EPS Growth" value={fund.eps_growth_yoy} unit="%" good={(fund.eps_growth_yoy ?? 0) >= 15} />
            </div>

            {/* Technical */}
            <div className="card p-5">
              <div className="text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ color: "var(--text-muted)" }}>
                Technical Indicators
              </div>
              <IndicatorRow label="RSI (14)" value={tech.rsi} good={tech.rsi < 30} />
              <IndicatorRow label="200 EMA" value={tech.ema_200?.toFixed(2)} />
              <IndicatorRow label="50 EMA" value={tech.ema_50?.toFixed(2)} />
              <IndicatorRow label="ATR (14)" value={tech.atr?.toFixed(2)} />
              <IndicatorRow label="ADX" value={tech.adx?.toFixed(1)} good={(tech.adx ?? 0) >= 25} />
              <IndicatorRow label="MACD" value={tech.macd?.toFixed(3)} good={(tech.macd ?? 0) > 0} />
              <IndicatorRow label="BB Width" value={tech.bb_width?.toFixed(3)} />
              <IndicatorRow label="Volume Ratio" value={tech.volume_ratio?.toFixed(2)} good={(tech.volume_ratio ?? 0) >= 1} />
            </div>

            {/* Trade Setup */}
            <div className="card p-5">
              <div className="text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ color: "var(--text-muted)" }}>
                Trade Setup
              </div>
              <div className="space-y-3">
                {[
                  { label: "52W High", value: tech.week_52_high?.toFixed(2), prefix: "₹", color: "var(--text-primary)" },
                  { label: "52W Low", value: tech.week_52_low?.toFixed(2), prefix: "₹", color: "var(--text-primary)" },
                  { label: "From 52W High", value: tech.pct_from_52w_high?.toFixed(1), suffix: "%", color: "var(--accent-red)" },
                  { label: "ATR Stop Loss", value: tech.atr_stop_loss?.toFixed(2), prefix: "₹", color: "var(--accent-red)" },
                  { label: "Fixed SL (5%)", value: tech.fixed_stop_loss?.toFixed(2), prefix: "₹", color: "var(--accent-red)" },
                  { label: "Target (12%)", value: tech.target_price?.toFixed(2), prefix: "₹", color: "var(--accent-green)" },
                  { label: "R:R Ratio", value: tech.risk_reward_ratio?.toFixed(2), color: "var(--accent-gold)" },
                ].map((item) => (
                  <div key={item.label} className="flex justify-between items-center py-1.5 border-b"
                    style={{ borderColor: "var(--border-primary)" }}>
                    <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {item.label}
                    </span>
                    <span className="font-mono font-bold text-sm" style={{ color: item.color }}>
                      {item.value != null ? `${item.prefix ?? ""}${item.value}${item.suffix ?? ""}` : "—"}
                    </span>
                  </div>
                ))}
              </div>

              {/* Screener Filters */}
              <div className="mt-4">
                <div className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>Screener Filters</div>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { label: "ROCE>15%", pass: tech.passed_roce ?? fund.passed_roce },
                    { label: "D/E<1.0", pass: fund.passed_debt_to_equity },
                    { label: ">200 EMA", pass: tech.passed_ema_200 },
                    { label: "RSI<30", pass: tech.passed_rsi_oversold },
                  ].map((f) => (
                    <div
                      key={f.label}
                      className={`indicator-pill ${f.pass ? "indicator-pass" : "indicator-fail"} justify-center`}
                    >
                      {f.pass ? "✓" : "✗"} {f.label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {!stockData && !loading && !error && (
        <div className="card p-16 text-center">
          <div className="text-6xl mb-4">🔍</div>
          <p className="text-xl font-bold" style={{ color: "var(--text-bright)" }}>
            Search any NSE stock
          </p>
          <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
            Get complete fundamental + technical analysis instantly
          </p>
          <div className="flex gap-2 justify-center mt-4 flex-wrap">
            {["RELIANCE", "TCS", "HDFCBANK", "INFOSYS", "ICICIBANK"].map((sym) => (
              <button
                key={sym}
                className="badge-blue cursor-pointer px-3 py-1"
                onClick={() => {
                  setQuery(sym);
                  stocksApi.getSnapshot(sym).then((r) => setStockData(r.data)).catch(setError);
                }}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
