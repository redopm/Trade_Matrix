"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getMarketStatus, MarketStatus } from "@/lib/marketStatus";
import { brokerApi } from "@/lib/api";
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
  ChevronRight,
  ChevronDown,
  Zap,
  Menu,
  X
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

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "Core Trading Desk",
    items: [
      { href: "/", label: "Dashboard", icon: <LayoutDashboard size={18} />, description: "Market Mood & Overview" },
      { href: "/screener", label: "Market Screener", icon: <Activity size={18} />, description: "Scan 500 Stocks & Setups", badge: "Live" },
      { href: "/aladdin", label: "Aladdin AI", icon: <BrainCircuit size={18} />, description: "5-Pillar DNA & ML Brain", badge: "27% CAGR" },
      { href: "/trades", label: "Trading Desk", icon: <Briefcase size={18} />, description: "Active Positions & Auto-SL" },
    ]
  },
  {
    title: "Derivatives & Quant",
    items: [
      { 
        href: "/fno", 
        label: "F&O Dashboard", 
        icon: <Activity size={18} />, 
        description: "Options Chain & Greeks", 
        subItems: [
          { href: "/fno", label: "Option Chain", icon: <Activity size={15} /> },
          { href: "/fno/strategy-builder", label: "Strategy Builder", icon: <FlaskConical size={15} /> },
          { href: "/fno/oi-analysis", label: "Open Interest", icon: <BarChart2 size={15} /> },
          { href: "/fno/pcr-analysis", label: "PCR & Volatility", icon: <TrendingDown size={15} /> },
          { href: "/fno/option-analysis", label: "Option Analysis", icon: <FileSearch size={15} /> },
          { href: "/fno/fii-dii", label: "FII / DII Data", icon: <Building2 size={15} /> },
        ]
      },
      { href: "/backtest", label: "Backtest Proof", icon: <BarChart2 size={18} />, description: "5.7Y Performance Audit" },
    ]
  },
  {
    title: "Advanced Labs",
    items: [
      { href: "/research", label: "Deep Research", icon: <Zap size={18} />, description: "Institutional Scanner" },
      { href: "/patterns", label: "Pattern Scanner", icon: <Eye size={18} />, description: "Chart Patterns" },
      { href: "/training", label: "ML Training", icon: <FlaskConical size={18} />, description: "Model Pipeline (Offline)" },
      { href: "/stocks", label: "Stock Lookup", icon: <Search size={18} />, description: "Symbol Snapshot" },
    ]
  },
  {
    title: "System",
    items: [
      { href: "/settings", label: "Settings", icon: <Settings size={18} />, description: "Fyers API & Risk Config" },
    ]
  }
];

const allNavItems = navSections.flatMap(s => s.items);

export function Sidebar() {
  const pathname = usePathname();
  const [marketStatus, setMarketStatus] = useState<MarketStatus>({ isOpen: false, message: "Loading..." });
  const [brokerStatus, setBrokerStatus] = useState<{ connected: boolean; name?: string }>({ connected: false });
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileExpandedItem, setMobileExpandedItem] = useState<string | null>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    setMarketStatus(getMarketStatus());
    const interval = setInterval(() => setMarketStatus(getMarketStatus()), 60000);

    const checkBroker = () => {
      brokerApi.getStatus()
        .then(res => {
          setBrokerStatus({
            connected: res.data.status === "connected",
            name: res.data.name
          });
        })
        .catch(() => setBrokerStatus({ connected: false }));
    };
    checkBroker();
    const brokerInterval = setInterval(checkBroker, 10000);
    window.addEventListener("broker-status-updated", checkBroker);

    return () => {
      clearInterval(interval);
      clearInterval(brokerInterval);
      window.removeEventListener("broker-status-updated", checkBroker);
    };
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [mobileOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleMouseEnter = useCallback((href: string) => {
    const el = itemRefs.current[href];
    if (el) {
      const rect = el.getBoundingClientRect();
      const estimatedHeight = 260;
      let top = rect.top;
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

  const activeItem = allNavItems.find(i => i.href === hoveredItem);

  // Common Header Content
  const renderSidebarHeader = (isMobile = false) => (
    <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-50/50 flex-shrink-0 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center text-lg sm:text-xl font-bold bg-blue-600 text-white shadow-sm flex-shrink-0">
          T
        </div>
        <div>
          <div className="font-bold text-slate-900 tracking-wide text-sm sm:text-base">TRADEMATRIX</div>
          <div className="text-[11px] text-slate-500 font-medium">Phase 1+2 &bull; Alpha + Patterns</div>
        </div>
      </div>
      {isMobile && (
        <button
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-lg transition-colors"
        >
          <X size={20} />
        </button>
      )}
    </div>
  );

  // Status Badges
  const renderStatusBadges = () => (
    <div className="px-3.5 pt-3 pb-1 flex-shrink-0 space-y-2">
      {/* Market Status Badge */}
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border shadow-xs transition-colors ${
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

      {/* Fyers Broker Status Badge */}
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs shadow-xs transition-colors ${
        brokerStatus.connected 
          ? "border-emerald-200 bg-emerald-50/70" 
          : "border-rose-200 bg-rose-50/50"
      }`}>
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
          brokerStatus.connected ? "bg-emerald-500 animate-pulse" : "bg-rose-400"
        }`} />
        <span className={`text-xs font-semibold ${
          brokerStatus.connected ? "text-emerald-800" : "text-rose-700"
        }`}>Fyers API</span>
        <span className={`ml-auto text-[11px] font-bold truncate max-w-[110px] ${
          brokerStatus.connected ? "text-emerald-700" : "text-rose-500"
        }`} title={brokerStatus.name || (brokerStatus.connected ? "Connected" : "Disconnected")}>
          {brokerStatus.connected ? (brokerStatus.name || "Live") : "Disconnected"}
        </span>
      </div>
    </div>
  );

  return (
    <>
      {/* 1. Mobile Fixed Top Header Bar (< lg) */}
      <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-white/95 backdrop-blur-md border-b border-slate-200 z-40 flex items-center justify-between px-3.5 shadow-xs">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
            className="p-2 -ml-1 text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors focus:outline-none"
          >
            <Menu size={22} />
          </button>
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center font-bold bg-blue-600 text-white shadow-xs text-base">
              T
            </div>
            <span className="font-extrabold text-slate-900 tracking-wide text-sm">TRADEMATRIX</span>
          </Link>
        </div>

        {/* Quick status chips on mobile header */}
        <div className="flex items-center gap-1.5">
          {/* NSE Market Status Chip */}
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-bold ${
            marketStatus.isOpen 
              ? "border-emerald-200 bg-emerald-50 text-emerald-700" 
              : "border-slate-200 bg-slate-50 text-slate-600"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${marketStatus.isOpen ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`} />
            <span>NSE</span>
          </div>

          {/* Fyers Status Chip */}
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-bold ${
            brokerStatus.connected 
              ? "border-emerald-200 bg-emerald-50 text-emerald-800" 
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${brokerStatus.connected ? "bg-emerald-500 animate-pulse" : "bg-rose-400"}`} />
            <span>{brokerStatus.connected ? "Fyers Live" : "Fyers Off"}</span>
          </div>
        </div>
      </header>

      {/* 2. Mobile Backdrop Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 lg:hidden transition-opacity duration-200"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* 3. Mobile Slide-Over Drawer (< lg) */}
      <aside
        className={`fixed top-0 left-0 bottom-0 w-72 max-w-[85vw] bg-white z-50 flex flex-col shadow-2xl lg:hidden transform transition-transform duration-300 ease-in-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {renderSidebarHeader(true)}
        {renderStatusBadges()}

        {/* Mobile Navigation */}
        <nav className="flex-1 px-3 py-2 space-y-3 overflow-y-auto">
          {navSections.map((section, sIdx) => (
            <div key={section.title} className={sIdx > 0 ? "pt-2 border-t border-slate-100" : ""}>
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-3 pb-1.5">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname.startsWith(item.href);
                  const hasSubItems = item.subItems && item.subItems.length > 0;
                  const isMobileSubOpen = mobileExpandedItem === item.href;

                  return (
                    <div key={item.href} className="space-y-0.5">
                      <div className="flex items-center">
                        <Link 
                          href={item.href} 
                          onClick={() => setMobileOpen(false)}
                          className="flex-1 block"
                        >
                          <div className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-all ${
                            isActive 
                              ? "bg-blue-50 text-blue-700 shadow-xs border border-blue-100" 
                              : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                          }`}>
                            <div className={`mt-0.5 flex-shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`}>
                              {item.icon}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-1">
                                <span className={`text-sm ${isActive ? "font-bold text-blue-900" : "font-medium"}`}>
                                  {item.label}
                                </span>
                                {item.badge && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                                    item.badge === "Live"
                                      ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                                      : item.badge === "27% CAGR"
                                      ? "bg-amber-100 text-amber-800 border border-amber-200"
                                      : "bg-blue-100 text-blue-700"
                                  }`}>
                                    {item.badge}
                                  </span>
                                )}
                              </div>
                              {item.description && (
                                <div className={`text-[11px] mt-0.5 truncate ${isActive ? "text-blue-600/80 font-medium" : "text-slate-400"}`}>
                                  {item.description}
                                </div>
                              )}
                            </div>
                          </div>
                        </Link>
                        {hasSubItems && (
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              setMobileExpandedItem(isMobileSubOpen ? null : item.href);
                            }}
                            aria-label="Toggle sub-items"
                            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg ml-1"
                          >
                            <ChevronDown size={16} className={`transition-transform duration-200 ${isMobileSubOpen ? "rotate-180" : ""}`} />
                          </button>
                        )}
                      </div>

                      {/* Mobile Accordion Sub-items */}
                      {hasSubItems && isMobileSubOpen && (
                        <div className="ml-7 pl-3 border-l-2 border-blue-200 space-y-1 py-1">
                          {item.subItems?.map(sub => {
                            const subActive = pathname === sub.href;
                            return (
                              <Link
                                key={sub.href}
                                href={sub.href}
                                onClick={() => setMobileOpen(false)}
                                className={`flex items-center gap-2.5 px-2.5 py-1.5 text-xs rounded-md transition-colors ${
                                  subActive
                                    ? "bg-blue-50 text-blue-700 font-bold"
                                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                }`}
                              >
                                <span className={subActive ? "text-blue-600" : "text-slate-400"}>{sub.icon}</span>
                                <span>{sub.label}</span>
                              </Link>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      {/* 4. Desktop Sidebar (lg:flex) */}
      <aside className="hidden lg:flex w-64 bg-white border-r border-slate-200 h-screen fixed top-0 left-0 z-30 flex-col shadow-xs overflow-hidden">
        {renderSidebarHeader(false)}
        {renderStatusBadges()}

        {/* Desktop Navigation */}
        <nav className="flex-1 px-3 py-2 space-y-3 overflow-y-auto">
          {navSections.map((section, sIdx) => (
            <div key={section.title} className={sIdx > 0 ? "pt-2 border-t border-slate-100" : ""}>
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-3 pb-1.5">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) => {
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
                        <div className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-all ${
                          isActive 
                            ? "bg-blue-50 text-blue-700 shadow-xs border border-blue-100" 
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}>
                          <div className={`mt-0.5 flex-shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`}>
                            {item.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              <span className={`text-sm ${isActive ? "font-bold text-blue-900" : "font-medium"}`}>
                                {item.label}
                              </span>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                {item.badge && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                                    item.badge === "Live"
                                      ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                                      : item.badge === "27% CAGR"
                                      ? "bg-amber-100 text-amber-800 border border-amber-200"
                                      : "bg-blue-100 text-blue-700"
                                  }`}>
                                    {item.badge}
                                  </span>
                                )}
                                {hasSubItems && (
                                  <ChevronRight size={13} className={`text-slate-400 transition-transform ${isHovered ? "rotate-90" : ""}`} />
                                )}
                              </div>
                            </div>
                            {item.description && (
                              <div className={`text-[11px] mt-0.5 truncate ${isActive ? "text-blue-600/80 font-medium" : "text-slate-400"}`}>
                                {item.description}
                              </div>
                            )}
                          </div>
                        </div>
                      </Link>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      {/* 5. Desktop Fixed-position dropdown (only on lg screens) */}
      {hoveredItem && activeItem?.subItems && dropdownPos && (
        <div
          className="hidden lg:block fixed z-[9999] w-52 bg-white border border-slate-200 rounded-lg shadow-2xl py-1.5"
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
