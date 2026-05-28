"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Activity, 
  Eye, 
  BrainCircuit, 
  Briefcase, 
  Search, 
  Settings,
  CheckCircle2,
  XCircle,
  AlertCircle
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  description?: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard size={18} />, description: "Overview & Stats" },
  { href: "/screener", label: "Screener", icon: <Activity size={18} />, description: "Alpha Screener" },
  { href: "/patterns", label: "Patterns", icon: <Eye size={18} />, description: "Pattern Recognition", badge: "Phase 2" },
  { href: "/training", label: "Training", icon: <BrainCircuit size={18} />, description: "ML Pipeline" },
  { href: "/trades", label: "Trades", icon: <Briefcase size={18} />, description: "Paper Trades" },
  { href: "/stocks", label: "Stocks", icon: <Search size={18} />, description: "Stock Lookup" },
  { href: "/settings", label: "Settings", icon: <Settings size={18} />, description: "Live Alerts & Prefs", badge: "Phase 3" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-white border-r border-slate-200 h-screen fixed top-0 left-0 overflow-y-auto z-50 flex flex-col shadow-sm">
      {/* Logo */}
      <div className="p-5 border-b border-slate-200 bg-slate-50/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-xl font-bold bg-blue-600 text-white shadow-sm">
            T
          </div>
          <div>
            <div className="font-bold text-slate-900 tracking-wide">
              TRADEMATRIX
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Phase 1+2 &bull; Alpha + Patterns
            </div>
          </div>
        </div>
      </div>

      {/* Market Status Badge */}
      <div className="px-4 py-4">
        <div className="flex items-center gap-2 px-3 py-2 rounded-md border border-emerald-200 bg-emerald-50 shadow-sm">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-semibold text-emerald-700">NSE Market</span>
          <span className="ml-auto text-xs font-medium text-emerald-600">Live</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-1">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-400 px-3 pb-2 pt-1">
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
                className={`flex items-start gap-3 px-3 py-2.5 rounded-md transition-all ${
                  isActive 
                    ? "bg-blue-50 text-blue-700 shadow-sm border border-blue-100" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <div className={`mt-0.5 ${isActive ? "text-blue-600" : "text-slate-400"}`}>
                  {item.icon}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm ${isActive ? "font-semibold" : "font-medium"}`}>
                      {item.label}
                    </span>
                    {item.badge && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold bg-blue-100 text-blue-700">
                        {item.badge}
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <div className={`text-xs mt-0.5 ${isActive ? "text-blue-600/80" : "text-slate-400"}`}>
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
      <div className="m-4 p-4 rounded-lg bg-slate-50 border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Activity size={14} className="text-slate-400" />
          <div className="font-bold text-xs uppercase tracking-wider text-slate-500">
            Alpha Screener Rules
          </div>
        </div>
        <div className="space-y-2 text-xs font-medium text-slate-600">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-500" />
            <span>ROCE &gt; 15%</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-500" />
            <span>D/E &lt; 1.0</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-blue-500" />
            <span>Price &gt; 200 EMA</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-blue-500" />
            <span>RSI(14) &lt; 30</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle size={14} className="text-amber-500" />
            <span>SL: 2&times;ATR</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle size={14} className="text-amber-500" />
            <span>Target: 12%</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
