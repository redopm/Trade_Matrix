"use client";

import { useEffect, useState } from "react";
import { settingsApi } from "@/lib/api";

export default function SettingsPage() {
  const [enabled, setEnabled] = useState(false);
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await settingsApi.getTelegram();
        setEnabled(res.data.enabled);
        setBotToken(res.data.bot_token);
        setChatId(res.data.chat_id);
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
    </div>
  );
}
