"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getMarketStatus, MarketStatus } from "@/lib/marketStatus";
import { 
  LayoutDashboard, 
  Activity, 
  Eye, 
  BrainCircuit, 
  Briefcase, 
  Search, 
  Settings,
  FlaskConical,
  BarChart2,
  TrendingDown,
  FileSearch,
  Building2,
  ChevronRight
} from "lucide-react";

interface SubItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  description?: string;
  badge?: string;
  subItems?: SubItem[];
}

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard size={18} />, description: "Overview & Stats" },
  { href: "/screener", label: "Screener", icon: <Activity size={18} />, description: "Alpha Screener" },
  { href: "/patterns", label: "Patterns", icon: <Eye size={18} />, description: "Pattern Recognition", badge: "Phase 2" },
  { href: "/training", label: "Training", icon: <BrainCircuit size={18} />, description: "ML Pipeline" },
  { href: "/trades", label: "Trades", icon: <Briefcase size={18} />, description: "Paper Trades" },
  { 
    href: "/fno", 
    label: "F&O Dashboard", 
    icon: <Activity size={18} />, 
    description: "Options Engine", 
    badge: "Phase 4",
    subItems: [
      { href: "/fno", label: "Option Chain", icon: <Activity size={15} /> },
      { href: "/fno/strategy-builder", label: "Strategy Builder", icon: <FlaskConical size={15} /> },
      { href: "/fno/oi-analysis", label: "Open Interest", icon: <BarChart2 size={15} /> },
      { href: "/fno/pcr-analysis", label: "PCR & Volatility", icon: <TrendingDown size={15} /> },
      { href: "/fno/option-analysis", label: "Option Analysis", icon: <FileSearch size={15} /> },
      { href: "/fno/fii-dii", label: "FII / DII Data", icon: <Building2 size={15} /> },
    ]
  },
  { href: "/stocks", label: "Stocks", icon: <Search size={18} />, description: "Stock Lookup" },
  { href: "/settings", label: "Settings", icon: <Settings size={18} />, description: "Alerts & Prefs", badge: "Phase 3" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [marketStatus, setMarketStatus] = useState<MarketStatus>({ isOpen: false, message: "Loading..." });
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    setMarketStatus(getMarketStatus());
    const interval = setInterval(() => setMarketStatus(getMarketStatus()), 60000);
    return () => clearInterval(interval);
  }, []);

  const handleMouseEnter = useCallback((href: string) => {
    const el = itemRefs.current[href];
    if (el) {
      const rect = el.getBoundingClientRect();
      // Calculate approximate height of dropdown (header + 6 items * 36px) = ~250px
      const estimatedHeight = 260;
      let top = rect.top;
      // If the dropdown would go off the bottom of the screen, shift it up
      if (top + estimatedHeight > window.innerHeight) {
        top = Math.max(10, window.innerHeight - estimatedHeight - 10);
      }
      setDropdownPos({ top, left: rect.right + 4 });
    }
    setHoveredItem(href);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setHoveredItem(null);
    setDropdownPos(null);
  }, []);

  const activeItem = navItems.find(i => i.href === hoveredItem);

  return (
    <>
      <aside className="w-64 bg-white border-r border-slate-200 h-screen fixed top-0 left-0 z-50 flex flex-col shadow-sm overflow-hidden">
        {/* Logo */}
        <div className="p-5 border-b border-slate-200 bg-slate-50/50 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center text-xl font-bold bg-blue-600 text-white shadow-sm">
              T
            </div>
            <div>
              <div className="font-bold text-slate-900 tracking-wide">TRADEMATRIX</div>
              <div className="text-xs text-slate-500 font-medium">Phase 1+2 &bull; Alpha + Patterns</div>
            </div>
          </div>
        </div>

        {/* Market Status Badge */}
        <div className="px-4 py-3 flex-shrink-0">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md border shadow-sm transition-colors ${
            marketStatus.isOpen 
              ? "border-emerald-200 bg-emerald-50" 
              : "border-slate-200 bg-slate-50"
          }`}>
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
              marketStatus.isOpen ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
            }`} />
            <span className={`text-xs font-semibold ${
              marketStatus.isOpen ? "text-emerald-700" : "text-slate-600"
            }`}>NSE Market</span>
            <span className={`ml-auto text-xs font-bold ${
              marketStatus.isOpen ? "text-emerald-600" : "text-slate-500"
            }`}>{marketStatus.message}</span>
          </div>
        </div>

        {/* Navigation — scrollable */}
        <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 px-3 pb-2 pt-1">
            Navigation
          </div>
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const hasSubItems = item.subItems && item.subItems.length > 0;
            const isHovered = hoveredItem === item.href;

            return (
              <div 
                key={item.href}
                ref={el => { itemRefs.current[item.href] = el; }}
                onMouseEnter={() => handleMouseEnter(item.href)}
                onMouseLeave={handleMouseLeave}
              >
                <Link href={item.href} className="block">
                  <div className={`flex items-start gap-3 px-3 py-2.5 rounded-md transition-all ${
                    isActive 
                      ? "bg-blue-50 text-blue-700 shadow-sm border border-blue-100" 
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}>
                    <div className={`mt-0.5 flex-shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`}>
                      {item.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className={`text-sm ${isActive ? "font-semibold" : "font-medium"}`}>
                          {item.label}
                        </span>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {item.badge && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold bg-blue-100 text-blue-700">
                              {item.badge}
                            </span>
                          )}
                          {hasSubItems && (
                            <ChevronRight size={13} className={`text-slate-400 transition-transform ${isHovered ? "rotate-90" : ""}`} />
                          )}
                        </div>
                      </div>
                      {item.description && (
                        <div className={`text-xs mt-0.5 ${isActive ? "text-blue-600/80" : "text-slate-400"}`}>
                          {item.description}
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              </div>
            );
          })}
        </nav>
      </aside>

      {/* Fixed-position dropdown — rendered OUTSIDE sidebar so it never gets clipped */}
      {hoveredItem && activeItem?.subItems && dropdownPos && (
        <div
          className="fixed z-[9999] w-52 bg-white border border-slate-200 rounded-lg shadow-2xl py-1.5"
          style={{ top: dropdownPos.top, left: dropdownPos.left }}
          onMouseEnter={() => handleMouseEnter(hoveredItem)}
          onMouseLeave={handleMouseLeave}
        >
          <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-100 mb-1">
            F&O Sections
          </div>
          {activeItem.subItems.map(subItem => {
            const subActive = pathname === subItem.href;
            return (
              <Link 
                key={subItem.href} 
                href={subItem.href}
                className={`flex items-center gap-3 px-3 py-2 text-sm font-medium transition-colors ${
                  subActive 
                    ? "bg-blue-50 text-blue-700" 
                    : "text-slate-700 hover:bg-slate-50 hover:text-blue-600"
                }`}
              >
                <div className={subActive ? "text-blue-500" : "text-slate-400"}>
                  {subItem.icon}
                </div>
                {subItem.label}
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
