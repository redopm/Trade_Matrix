import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "TradeMatrix — Algo Trading Control Center",
  description:
    "Systematic algorithmic trading dashboard for NSE stocks. Phase 1: Alpha Screener with fundamental + technical filters.",
  keywords: "algo trading, NSE, screener, paper trading, ROCE, RSI, EMA",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body suppressHydrationWarning className="bg-slate-50 text-slate-900 min-h-screen antialiased">
        <div className="flex flex-col lg:flex-row min-h-screen bg-slate-50">
          <Sidebar />
          <main className="flex-1 lg:ml-64 pt-14 lg:pt-0 min-w-0 w-full overflow-x-hidden">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
