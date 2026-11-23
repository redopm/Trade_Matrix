"use client";

import React, { useEffect, useState } from "react";
import { fnoApi } from "@/lib/api";
import { Building2, TrendingUp, TrendingDown, ShieldCheck, Activity, AlertCircle } from "lucide-react";
import { FnoHeaderNav } from "@/components/FnoHeaderNav";

export default function FiiDiiData() {
  const [flow, setFlow] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFlow = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fnoApi.getInstitutionalFlow();
      setFlow(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to fetch live institutional derivatives flow");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadFlow();
  }, []);

  const bias = flow?.institutional_bias || "NEUTRAL";
  const putShare = Number(flow?.put_writing_share_pct ?? 50);
  const callShare = Number(flow?.call_writing_share_pct ?? 50);
  const indices = flow?.indices || [];

  return (
    <div className="flex-1 min-h-screen bg-slate-50/50 pb-12">
      <FnoHeaderNav
        activeTab="fii"
        title="Institutional Smart Money & F&O Positioning"
        subtitle="Real-time NIFTY & BANKNIFTY Institutional Call/Put Writing Dominance"
        onRefresh={loadFlow}
        isRefreshing={loading}
        rightExtra={
          <div
            className={`px-3.5 py-2 rounded-lg border font-bold text-xs sm:text-sm ${
              bias === "BULLISH"
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : bias === "BEARISH"
                ? "text-red-700 bg-red-50 border-red-200"
                : "text-slate-700 bg-slate-100 border-slate-200"
            }`}
          >
            Smart Money Bias: {bias.replace("_", " ")}
          </div>
        }
      />

      {loading ? (
        <div className="p-12 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-indigo-600 animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 p-6 rounded-xl flex items-start gap-4">
            <AlertCircle className="text-red-600 mt-1" />
            <div>
              <h3 className="font-bold text-red-900">Unable to load Live Institutional Flow</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
          {/* LIVE AGGREGATE SUMMARY */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Building2 size={20} className="text-indigo-600" /> Live Index Writer Positioning (NIFTY + BANKNIFTY)
                </h2>
                <p className="text-sm text-slate-600 mt-1">{flow?.interpretation}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs font-bold uppercase text-slate-400">Aggregate Index PCR</div>
                <div className="text-3xl font-black text-indigo-700">
                  {Number(flow?.aggregate_pcr || 1.0).toFixed(2)}
                </div>
              </div>
            </div>

            {/* CALL VS PUT WRITER SHARE BAR */}
            <div className="relative h-9 bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
              <div
                className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 flex items-center px-4 text-white text-xs sm:text-sm font-bold"
                style={{ width: `${putShare}%` }}
              >
                Put Support Writers {putShare}%
              </div>
              <div
                className="h-full bg-gradient-to-l from-red-600 to-red-400 flex items-center justify-end px-4 text-white text-xs sm:text-sm font-bold"
                style={{ width: `${callShare}%` }}
              >
                Call Resistance Writers {callShare}%
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-5">
              <div className="bg-emerald-50/70 p-4 rounded-xl border border-emerald-100">
                <div className="text-xs font-bold text-emerald-700 uppercase">Total Index Put OI</div>
                <div className="text-xl font-black text-emerald-800 mt-1 flex items-center gap-1.5">
                  <TrendingUp size={18} /> {(Number(flow?.total_index_put_oi || 0) / 10000000).toFixed(2)} Cr
                </div>
              </div>
              <div className="bg-red-50/70 p-4 rounded-xl border border-red-100">
                <div className="text-xs font-bold text-red-700 uppercase">Total Index Call OI</div>
                <div className="text-xl font-black text-red-800 mt-1 flex items-center gap-1.5">
                  <TrendingDown size={18} /> {(Number(flow?.total_index_call_oi || 0) / 10000000).toFixed(2)} Cr
                </div>
              </div>
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div className="text-xs font-bold text-slate-600 uppercase">Net Intraday OI Shift</div>
                <div
                  className={`text-xl font-black mt-1 ${
                    Number(flow?.net_intraday_oi_flow || 0) >= 0 ? "text-emerald-700" : "text-red-600"
                  }`}
                >
                  {Number(flow?.net_intraday_oi_flow || 0) >= 0 ? "+" : ""}
                  {(Number(flow?.net_intraday_oi_flow || 0) / 100000).toFixed(2)}L (Put - Call)
                </div>
              </div>
            </div>
          </div>

          {/* PER-INDEX LIVE INSTITUTIONAL BREAKDOWN */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {indices.map((idx: any) => (
              <div key={idx.symbol} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-slate-900 flex items-center gap-2">
                      <Activity size={16} className="text-indigo-600" /> {idx.symbol} Derivatives Desk
                    </h3>
                    <div className="text-xs text-slate-500 mt-0.5">
                      Spot: ₹{Number(idx.spot_price || 0).toLocaleString("en-IN")} (
                      <span className={idx.spot_change_pct >= 0 ? "text-emerald-600 font-semibold" : "text-red-600 font-semibold"}>
                        {idx.spot_change_pct >= 0 ? "+" : ""}
                        {Number(idx.spot_change_pct || 0).toFixed(2)}%
                      </span>
                      )
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                      idx.directional_bias === "BULLISH"
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : idx.directional_bias === "BEARISH"
                        ? "bg-red-50 text-red-700 border-red-200"
                        : "bg-slate-100 text-slate-700 border-slate-200"
                    }`}
                  >
                    Aladdin: {idx.conviction_score}% ({idx.directional_bias})
                  </span>
                </div>

                <div className="p-5 grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">OI PCR / Vol PCR</div>
                    <div className="font-bold text-slate-800 mt-0.5">
                      {idx.pcr} / {idx.vol_pcr}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">ATM IV / Skew</div>
                    <div className="font-bold text-slate-800 mt-0.5">
                      {idx.avg_atm_iv}% ({idx.iv_skew >= 0 ? "+" : ""}
                      {idx.iv_skew}%)
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">Max Pain Magnet</div>
                    <div className="font-bold text-indigo-700 mt-0.5">{idx.max_pain}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">Put Floor Wall</div>
                    <div className="font-bold text-emerald-600 mt-0.5">{idx.put_wall}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">Call Ceiling Wall</div>
                    <div className="font-bold text-red-600 mt-0.5">{idx.call_wall}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-semibold">Intraday OI Shift</div>
                    <div
                      className={`font-bold mt-0.5 ${
                        idx.put_chng_oi - idx.call_chng_oi >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}
                    >
                      {((idx.put_chng_oi - idx.call_chng_oi) / 100000).toFixed(1)}L
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-indigo-50/70 border border-indigo-200 p-4 rounded-xl flex items-start gap-3">
            <ShieldCheck className="text-indigo-600 mt-0.5 shrink-0" size={20} />
            <div className="text-sm text-indigo-900">
              <span className="font-bold">Live Exchange Footprint (Zero Delay):</span> FII/DII exchange cash reports publish after market close, whereas live Index Option Writers (Big Money sellers defending Call & Put Walls) reveal institutional bias in real time via live Open Interest & IV Skew above.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
