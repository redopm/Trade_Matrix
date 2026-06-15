"use client";

import { useEffect, useState } from "react";
import { settingsApi, brokerApi } from "@/lib/api";

export default function SettingsPage() {
  const [enabled, setEnabled] = useState(false);
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");

  // Screener Rules State
  const [screenerRules, setScreenerRules] = useState({
    min_roce: 15.0,
    max_debt_to_equity: 1.0,
    rsi_oversold: 30.0,
    target_profit_pct: 0.12,
    atr_sl_multiplier: 2.0,
    short_max_roce: 10.0,
    short_min_debt_to_equity: 1.5,
    rsi_overbought: 65.0,
    short_target_pct: 0.12,
    default_capital: 100000.0
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  
  // Broker State
  const [brokerStatus, setBrokerStatus] = useState("disconnected");
  const [brokerName, setBrokerName] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [connecting, setConnecting] = useState(false);
  
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [telRes, scrRes, brokerRes] = await Promise.all([
          settingsApi.getTelegram(),
          settingsApi.getScreener(),
          brokerApi.getStatus().catch(() => ({ data: { status: "disconnected" } }))
        ]);
        setEnabled(telRes.data.enabled);
        setBotToken(telRes.data.bot_token);
        setChatId(telRes.data.chat_id);
        
        setBrokerStatus(brokerRes.data.status);
        if (brokerRes.data.name) setBrokerName(brokerRes.data.name);
        
        setScreenerRules({
          min_roce: scrRes.data.min_roce,
          max_debt_to_equity: scrRes.data.max_debt_to_equity,
          rsi_oversold: scrRes.data.rsi_oversold,
          target_profit_pct: scrRes.data.target_profit_pct,
          atr_sl_multiplier: scrRes.data.atr_sl_multiplier,
          short_max_roce: scrRes.data.short_max_roce,
          short_min_debt_to_equity: scrRes.data.short_min_debt_to_equity,
          rsi_overbought: scrRes.data.rsi_overbought,
          short_target_pct: scrRes.data.short_target_pct,
          default_capital: scrRes.data.default_capital || 100000.0
        });
      } catch (e: any) {
        setMessage({ type: "error", text: "Failed to load settings. Is the backend running?" });
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await settingsApi.updateTelegram({ enabled, bot_token: botToken, chat_id: chatId });
      setMessage({ type: "success", text: "Settings saved successfully! (Note: Restart the backend for .env changes to fully apply in all components)." });
    } catch (e: any) {
      setMessage({ type: "error", text: `Failed to save: ${e.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveScreener = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await settingsApi.updateScreener(screenerRules);
      setMessage({ type: "success", text: "Screener rules saved successfully!" });
    } catch (e: any) {
      setMessage({ type: "error", text: `Failed to save: ${e.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setMessage(null);
    try {
      await settingsApi.testTelegram({ enabled, bot_token: botToken, chat_id: chatId });
      setMessage({ type: "success", text: "Test alert sent! Check your Telegram app." });
    } catch (e: any) {
      setMessage({ type: "error", text: `Test failed: ${e.message}` });
    } finally {
      setTesting(false);
    }
  };

  const handleGenerateLink = async () => {
    setMessage(null);
    try {
      const res = await brokerApi.getAuthUrl();
      if (res.data.auth_url) {
        window.open(res.data.auth_url, "_blank");
      }
    } catch (e: any) {
      setMessage({ type: "error", text: `Failed to generate auth link: ${e.message}` });
    }
  };

  const handleConnectBroker = async () => {
    if (!authCode) {
      setMessage({ type: "error", text: "Please enter the auth code first." });
      return;
    }
    setConnecting(true);
    setMessage(null);
    try {
      await brokerApi.setAuthCode(authCode);
      const res = await brokerApi.getStatus();
      setBrokerStatus(res.data.status);
      setBrokerName(res.data.name || "");
      setMessage({ type: "success", text: "Fyers connected successfully!" });
      setAuthCode("");
    } catch (e: any) {
      setMessage({ type: "error", text: `Failed to connect: ${e.message}` });
    } finally {
      setConnecting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-slide-in max-w-3xl">
        <div className="skeleton h-10 w-64 rounded-xl" />
        <div className="skeleton h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 animate-slide-in max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight" style={{ color: "var(--text-bright)" }}>
          Settings
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          Configure live alerts and system preferences.
        </p>
      </div>

      {message && (
        <div
          className="p-4 rounded-xl text-sm font-medium animate-fade-in"
          style={{
            background: message.type === "success" ? "rgba(0, 245, 160, 0.1)" : "rgba(255, 68, 102, 0.1)",
            border: `1px solid ${message.type === "success" ? "rgba(0, 245, 160, 0.3)" : "rgba(255, 68, 102, 0.3)"}`,
            color: message.type === "success" ? "var(--accent-green)" : "var(--accent-red)",
          }}
        >
          {message.text}
        </div>
      )}

      {/* Broker Setup Card */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6 border-b pb-4 border-[var(--border-primary)]">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2" style={{ color: "var(--text-bright)" }}>
              Fyers Data Connection
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Connect to Fyers API to fetch high-quality institutional historical data.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              {brokerStatus === "connected" && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              )}
              <span className={`relative inline-flex rounded-full h-3 w-3 ${brokerStatus === 'connected' ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
            </span>
            <span className="text-sm font-semibold capitalize" style={{ color: brokerStatus === "connected" ? "var(--accent-green)" : "var(--accent-red)" }}>
              {brokerStatus} {brokerName && `(${brokerName})`}
            </span>
          </div>
        </div>

        <div className="space-y-5">
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-bold mb-2" style={{ color: "var(--text-secondary)" }}>
                OAuth Authorization Code
              </label>
              <input
                type="text"
                className="w-full bg-[var(--bg-tertiary)] border border-[var(--border-primary)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--accent-blue)] transition-colors text-[var(--text-bright)]"
                placeholder="Paste the 'auth_code' from the redirected URL..."
                value={authCode}
                onChange={(e) => setAuthCode(e.target.value)}
              />
            </div>
            <button
              className="btn-primary py-3 px-6 font-bold whitespace-nowrap h-[46px]"
              onClick={handleConnectBroker}
              disabled={connecting || !authCode}
            >
              {connecting ? "Connecting..." : "Connect Fyers"}
            </button>
          </div>
          
          <div className="bg-[var(--bg-tertiary)] p-4 rounded-xl border border-[var(--border-primary)]">
            <h4 className="text-sm font-bold mb-2 text-[var(--text-bright)]">How to connect:</h4>
            <ol className="text-xs space-y-2 text-[var(--text-muted)] list-decimal pl-4">
              <li>Click the button below to open the Fyers Login page.</li>
              <li>Login with your Client ID, PIN, and TOTP.</li>
              <li>The page will redirect to an empty page (`http://127.0.0.1:8000/?auth_code=...`)</li>
              <li>Copy the long code after `auth_code=` in the address bar.</li>
              <li>Paste the code above and click Connect.</li>
            </ol>
            <button
              className="mt-4 w-full py-2 bg-blue-600/10 text-blue-500 border border-blue-500/30 rounded-lg hover:bg-blue-600/20 transition-colors font-semibold text-sm"
              onClick={handleGenerateLink}
            >
              Generate Fyers Login Link
            </button>
          </div>
        </div>
      </div>

      {/* Telegram Config Card */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6 border-b pb-4 border-[var(--border-primary)]">
          <div>
            <h2 className="text-lg font-bold" style={{ color: "var(--text-bright)" }}>
              Telegram Live Alerts
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Receive instant push notifications when the screener finds a High Conviction pattern signal.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold" style={{ color: enabled ? "var(--accent-green)" : "var(--text-muted)" }}>
              {enabled ? "Enabled" : "Disabled"}
            </span>
            <button 
              className={`w-12 h-6 rounded-full relative transition-colors ${enabled ? 'bg-[var(--accent-green)]' : 'bg-[var(--bg-tertiary)]'}`}
              onClick={() => setEnabled(!enabled)}
            >
              <div 
                className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${enabled ? 'translate-x-6' : 'translate-x-0'}`} 
              />
            </button>
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-bold mb-2" style={{ color: "var(--text-secondary)" }}>
              Bot Token
            </label>
            <input
              type="password"
              className="w-full bg-[var(--bg-tertiary)] border border-[var(--border-primary)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--accent-blue)] transition-colors text-[var(--text-bright)]"
              placeholder="e.g. 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              disabled={!enabled}
            />
            <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
              Create a bot via <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-[var(--accent-blue)] hover:underline">@BotFather</a> on Telegram to get your token.
            </p>
          </div>

          <div>
            <label className="block text-sm font-bold mb-2" style={{ color: "var(--text-secondary)" }}>
              Chat ID
            </label>
            <input
              type="text"
              className="w-full bg-[var(--bg-tertiary)] border border-[var(--border-primary)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--accent-blue)] transition-colors text-[var(--text-bright)]"
              placeholder="e.g. 123456789"
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
              disabled={!enabled}
            />
            <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
              Send a message to your bot, then visit <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> to find your Chat ID.
            </p>
          </div>

          <div className="flex gap-4 pt-4">
            <button
              className="btn-primary flex-1 py-3 font-bold"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
            <button
              className="flex-1 py-3 font-bold rounded-lg transition-colors border border-[var(--border-primary)] hover:bg-[var(--bg-tertiary)]"
              style={{ color: "var(--text-bright)" }}
              onClick={handleTest}
              disabled={testing || !botToken || !chatId}
            >
              {testing ? "Sending..." : "Send Test Alert"}
            </button>
          </div>
        </div>
      </div>

      {/* Screener Rules Card */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6 border-b pb-4 border-[var(--border-primary)]">
          <div>
            <h2 className="text-lg font-bold" style={{ color: "var(--text-bright)" }}>
              Alpha Screener Rules
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Customize the technical and fundamental thresholds used by the AI to filter stocks.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* LONG Strategy Rules */}
          <div className="space-y-4 p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-tertiary)]">
            <h3 className="font-bold text-emerald-600 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span> LONG Strategy
            </h3>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Minimum ROCE (%)</label>
              <input type="number" step="0.1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.min_roce}
                onChange={(e) => setScreenerRules({...screenerRules, min_roce: parseFloat(e.target.value)})}
              />
            </div>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Max Debt/Equity Ratio</label>
              <input type="number" step="0.1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.max_debt_to_equity}
                onChange={(e) => setScreenerRules({...screenerRules, max_debt_to_equity: parseFloat(e.target.value)})}
              />
            </div>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">RSI Oversold (Entry) Threshold</label>
              <input type="number" step="1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.rsi_oversold}
                onChange={(e) => setScreenerRules({...screenerRules, rsi_oversold: parseFloat(e.target.value)})}
              />
            </div>
          </div>

          {/* SHORT Strategy Rules */}
          <div className="space-y-4 p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-tertiary)]">
            <h3 className="font-bold text-red-600 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span> SHORT Strategy
            </h3>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Maximum ROCE (%)</label>
              <input type="number" step="0.1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.short_max_roce}
                onChange={(e) => setScreenerRules({...screenerRules, short_max_roce: parseFloat(e.target.value)})}
              />
              <p className="text-[10px] text-[var(--text-muted)] mt-1">Shorting weak businesses.</p>
            </div>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Min Debt/Equity Ratio</label>
              <input type="number" step="0.1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.short_min_debt_to_equity}
                onChange={(e) => setScreenerRules({...screenerRules, short_min_debt_to_equity: parseFloat(e.target.value)})}
              />
            </div>
            
            <div>
              <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">RSI Overbought (Entry) Threshold</label>
              <input type="number" step="1" 
                className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                value={screenerRules.rsi_overbought}
                onChange={(e) => setScreenerRules({...screenerRules, rsi_overbought: parseFloat(e.target.value)})}
              />
            </div>
          </div>

          {/* Trade Parameters */}
          <div className="space-y-4 p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-tertiary)] md:col-span-2">
            <h3 className="font-bold text-blue-600 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span> Trade Execution Rules
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Paper Trading Capital (₹)</label>
                <input type="number" step="1000" 
                  className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                  value={screenerRules.default_capital}
                  onChange={(e) => setScreenerRules({...screenerRules, default_capital: parseFloat(e.target.value)})}
                />
              </div>
              <div>
                <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">Stop Loss (ATR Multiplier)</label>
                <input type="number" step="0.1" 
                  className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                  value={screenerRules.atr_sl_multiplier}
                  onChange={(e) => setScreenerRules({...screenerRules, atr_sl_multiplier: parseFloat(e.target.value)})}
                />
              </div>
              <div>
                <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">LONG Target Profit (%)</label>
                <input type="number" step="0.01" 
                  className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                  value={screenerRules.target_profit_pct}
                  onChange={(e) => setScreenerRules({...screenerRules, target_profit_pct: parseFloat(e.target.value)})}
                />
              </div>
              <div>
                <label className="block text-xs font-bold mb-1 text-[var(--text-secondary)]">SHORT Target Profit (%)</label>
                <input type="number" step="0.01" 
                  className="w-full bg-white border border-[var(--border-primary)] rounded-md p-2 text-sm"
                  value={screenerRules.short_target_pct}
                  onChange={(e) => setScreenerRules({...screenerRules, short_target_pct: parseFloat(e.target.value)})}
                />
              </div>
            </div>
          </div>
        </div>

        <button
          className="btn-primary w-full py-3 font-bold"
          onClick={handleSaveScreener}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Screener Rules"}
        </button>
      </div>
    </div>
  );
}
