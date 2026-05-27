"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  description?: string;
}

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "⬡", description: "Overview & Stats" },
  { href: "/screener", label: "Screener", icon: "⚡", description: "Alpha Screener" },
  { href: "/trades", label: "Trades", icon: "📊", description: "Paper Trades" },
  { href: "/stocks", label: "Stocks", icon: "🔍", description: "Stock Lookup" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar flex flex-col">
      {/* Logo */}
      <div className="p-5 border-b" style={{ borderColor: "var(--border-primary)" }}>
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-xl font-black"
            style={{ background: "var(--gradient-green)", color: "#080c14" }}
          >
            T
          </div>
          <div>
            <div
              className="font-black text-sm tracking-wider"
              style={{ color: "var(--text-bright)", letterSpacing: "0.15em" }}
            >
              TRADEMATRIX
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              Phase 1 · Alpha Screener
            </div>
          </div>
        </div>
      </div>

      {/* Market Status Badge */}
      <div className="px-4 py-3">
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
          style={{
            background: "rgba(0, 245, 160, 0.06)",
            border: "1px solid rgba(0, 245, 160, 0.15)",
          }}
        >
          <div className="live-indicator" />
          <span style={{ color: "var(--accent-green)" }}>NSE Market</span>
          <span className="ml-auto" style={{ color: "var(--text-muted)" }}>
            Live
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-2">
        <div className="text-xs font-semibold uppercase tracking-widest px-3 py-2 mb-1"
          style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          Navigation
        </div>
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} className="block">
              <div
                className={`sidebar-item ${isActive ? "active" : ""}`}
                style={{
                  borderColor: isActive
                    ? "rgba(0, 245, 160, 0.15)"
                    : "transparent",
                }}
              >
                <span className="text-lg">{item.icon}</span>
                <div>
                  <div className="text-sm font-medium">{item.label}</div>
                  {item.description && (
                    <div
                      className="text-xs"
                      style={{
                        color: isActive
                          ? "rgba(0, 245, 160, 0.7)"
                          : "var(--text-muted)",
                      }}
                    >
                      {item.description}
                    </div>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Strategy Quick-Ref */}
      <div
        className="mx-3 mb-4 p-3 rounded-xl text-xs"
        style={{
          background: "rgba(255, 255, 255, 0.02)",
          border: "1px solid var(--border-primary)",
        }}
      >
        <div
          className="font-bold mb-2 text-xs uppercase tracking-wider"
          style={{ color: "var(--text-muted)" }}
        >
          Alpha Screener Rules
        </div>
        <div className="space-y-1" style={{ color: "var(--text-secondary)" }}>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-green)" }}>✓</span>
            <span>ROCE &gt; 15%</span>
          </div>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-green)" }}>✓</span>
            <span>D/E &lt; 1.0</span>
          </div>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-blue)" }}>✓</span>
            <span>Price &gt; 200 EMA</span>
          </div>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-blue)" }}>✓</span>
            <span>RSI(14) &lt; 30</span>
          </div>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-gold)" }}>✓</span>
            <span>SL: 2×ATR</span>
          </div>
          <div className="flex items-center gap-1">
            <span style={{ color: "var(--accent-gold)" }}>✓</span>
            <span>Target: 12%</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
