/**
 * TradeMatrix API Client
 * Typed axios client for all backend endpoints
 */
import axios from "axios";

const isBrowser = typeof window !== "undefined";

// Use BACKEND_URL if provided, else use docker service name in production, or localhost in development
const serverBaseUrl = process.env.BACKEND_URL || 
  (process.env.NODE_ENV === "production" ? "http://backend:8000" : "http://127.0.0.1:8000");

const defaultBaseUrl = isBrowser ? "/api/v1" : `${serverBaseUrl}/api/v1`;
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || defaultBaseUrl;

const defaultWsUrl = isBrowser 
  ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1` 
  : `${serverBaseUrl.replace("http", "ws").replace("https", "wss")}/api/v1`;
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || defaultWsUrl;

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 300000,  // 5 minutes — massive operations like detectAll take ~2 minutes
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for logging
api.interceptors.request.use((config) => {
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const data = error.response?.data;
    let message: string;

    if (Array.isArray(data?.detail)) {
      // FastAPI 422 validation errors — format each field error
      message = data.detail
        .map((e: any) => {
          const field = e.loc?.slice(1).join(".") ?? "field";
          return `${field}: ${e.msg}`;
        })
        .join(" | ");
    } else {
      message =
        data?.detail ||
        data?.message ||
        error.message ||
        "An error occurred";
    }

    const status = error.response?.status ?? "network";
    const endpoint = error.config?.url ? ` on [${error.config?.method?.toUpperCase()} ${error.config.url}]` : "";
    if (status === "network") {
      console.warn(`[API Connection Waiting]${endpoint}: Backend momentarily offline or restarting`);
    } else if (typeof status === "number" && status >= 400 && status < 500) {
      console.warn(`[API Client Error] [${status}]${endpoint}: ${message}`);
    } else {
      console.error(`API Error [${status}]${endpoint}: ${message}`);
    }
    return Promise.reject(new Error(message));
  }
);

// ── Dashboard ────────────────────────────────────────────────────────────────
// Updated error handling to prevent UI crashes
export const fetchOptionChain = async (symbol: string, atm_strike?: number) => {
  const t = new Date().getTime();
  let url = `${BASE_URL}/fno/chain/${symbol}?t=${t}`;
  if (atm_strike) url += `&atm_strike=${atm_strike}`;
  try {
    const response = await fetch(url, { cache: 'no-store', headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' } });
    if (!response.ok) {
      return { error: `Failed to fetch option chain (HTTP ${response.status})` };
    }
    return await response.json();
  } catch (error: any) {
    return { error: `Network error: ${error.message}` };
  }
};

export const predictKronos = async (symbol: string, pred_len: number = 5) => {
  try {
    const response = await api.post("/fno/predict", { symbol, pred_len, range_from: "2024-01-01" });
    return response.data;
  } catch (error: any) {
    return { error: error.message };
  }
};

export const dashboardApi = {
  getSummary: () => api.get("/dashboard/summary"),
  getPnlChart: (days: number = 30) => api.get(`/dashboard/pnl-chart?days=${days}`),
  getHeatmap: () => api.get("/dashboard/heatmap"),
  getRecentSignals: (limit: number = 10) =>
    api.get(`/dashboard/recent-signals?limit=${limit}`),
  getAiPicks: (forceRefresh: boolean = false) =>
    api.get(`/dashboard/ai-picks?force_refresh=${forceRefresh}`),
};

// ── Settings ────────────────────────────────────────────────────────────────────
export const settingsApi = {
  getTelegram: () => api.get("/settings/telegram"),
  updateTelegram: (data: { enabled: boolean; bot_token: string; chat_id: string }) =>
    api.post("/settings/telegram", data),
  testTelegram: (data: { enabled: boolean; bot_token: string; chat_id: string }) =>
    api.post("/settings/telegram/test", data),
  getScreener: () => api.get("/settings/screener"),
  updateScreener: (data: any) => api.post("/settings/screener", data),
};

// ── Broker ──────────────────────────────────────────────────────────────────────
export const brokerApi = {
  getStatus: () => api.get("/broker/status"),
  getAuthUrl: () => api.get("/broker/auth-url"),
  setAuthCode: (auth_code: string) => api.post("/broker/auth", { auth_code }),
};

// ── Backtesting ─────────────────────────────────────────────────────────────────
export const backtestApi = {
  getStrategies: () => api.get("/backtest/strategies"),
  runBacktest: (data: {
    symbol: string;
    strategy: string;
    period?: string;
    initial_capital?: number;
    risk_per_trade_pct?: number;
    atr_multiplier?: number;
    rr_ratio?: number;
    slippage_pct?: number;
  }) => api.post("/backtest/run", data),
  quickBacktest: (symbol: string, strategy: string = "ALPHA_PULLBACK", period: string = "3y") =>
    api.get(`/backtest/quick/${symbol}?strategy=${strategy}&period=${period}`),
  getUniverses: () => api.get("/backtest/universes"),
  runPortfolioBacktest: (data: {
    universe: string;
    period?: string;
    initial_capital?: number;
    top_n?: number;
    rebalance_freq?: number;
    slippage_pct?: number;
    custom_symbols?: string[];
    use_macro_regime?: boolean;
    max_per_sector?: number;
  }) => api.post("/backtest/portfolio", data),
};

// ── Screener ──────────────────────────────────────────────────────────────────
export const screenerApi = {
  startRun: (opts?: { symbols?: string[]; description?: string }) =>
    api.post("/screener/run", opts ?? {}),
  getRunStatus: (runId: string) => api.get(`/screener/run/${runId}`),
  getAllRuns: () => api.get("/screener/runs"),
  getResults: (params?: {
    passed_only?: boolean;
    sector?: string;
    min_score?: number;
    page?: number;
    page_size?: number;
    sort_by?: string;
    direction?: string;
    date_from?: string;
    date_to?: string;
  }) => api.get("/screener/results", { params }),
  getPassedSignals: (limit?: number) =>
    api.get(`/screener/results/passed${limit ? `?limit=${limit}` : ""}`),
  getSignal: (id: number) => api.get(`/screener/signals/${id}`),
  getMarketRegime: () => api.get("/screener/market-regime"),
  getUniverse: () => api.get("/screener/universe", { timeout: 90000 }),
  getSectorBreakdown: () => api.get("/screener/universe/sectors", { timeout: 90000 }),
};

// ── Trades ────────────────────────────────────────────────────────────────────
export const tradesApi = {
  createTrade: (signalId: number, capital?: number, notes?: string) =>
    api.post("/trades/", { signal_id: signalId, capital, notes }),
  createCustomTrade: (data: any) => api.post("/trades/custom", data),
  listTrades: (params?: { status?: string; symbol?: string; page?: number; page_size?: number }) =>
    api.get("/trades/", { params }),
  getOpenTrades: () => api.get("/trades/open"),
  getStats: () => api.get("/trades/stats"),
  getTrade: (id: number) => api.get(`/trades/${id}`),
  closeTrade: (id: number, exitPrice?: number, notes?: string) =>
    api.put(`/trades/${id}/close`, { exit_price: exitPrice, notes }),
  deleteTrade: (id: number) => api.delete(`/trades/${id}`),
  deleteAllClosed: () => api.delete("/trades/closed/all"),
  updateAll: (sync = true) => api.post(`/trades/update-all?sync=${sync}`),
};

// ── Stocks ────────────────────────────────────────────────────────────────────
export const stocksApi = {
  search: (q: string) => api.get(`/stocks/search?q=${encodeURIComponent(q)}`),
  getUniverse: () => api.get("/stocks/universe"),
  getSnapshot: (symbol: string) => api.get(`/stocks/${symbol}`),
  getChart: (symbol: string, days?: number, period?: string) =>
    api.get(`/stocks/${symbol}/chart`, { params: { days, period } }),
  getTechnicals: (symbol: string) => api.get(`/stocks/${symbol}/technicals`),
  getFundamentals: (symbol: string) => api.get(`/stocks/${symbol}/fundamentals`),
};

// ── Patterns (Phase 2) ────────────────────────────────────────────────────────
export const patternsApi = {
  // Model status
  getStatus: () => api.get("/patterns/status"),
  getQuota: () => api.get("/patterns/quota"),
  getPerformance: () => api.get("/patterns/performance"),

  // Training
  startTraining: (useFullNifty200 = true) =>
    api.post("/patterns/train", null, { params: { use_full_nifty200: useFullNifty200 } }),
  trainModelOnly: () => api.post("/patterns/train/model-only"),
  cancelTraining: () => api.post("/patterns/train/cancel"),
  importColabModel: () => api.post("/patterns/model/import"),

  // Detection
  detect: (symbol: string, phase1Passed = false, generateChart = true) =>
    api.get(`/patterns/detect/${symbol}`, {
      params: { phase1_passed: phase1Passed, generate_chart: generateChart },
    }),
  detectAll: (limit = 50) => api.get("/patterns/detect-all", { params: { limit } }),

  // Chart image
  getChartUrl: (symbol: string, date?: string) =>
    `${BASE_URL}/patterns/chart/${symbol}${date ? `?date=${date}` : ""}`,

  // Labels
  getLabelStats: () => api.get("/patterns/labels/stats"),
  getLabels: (params?: { pattern?: string; source?: string; limit?: number; offset?: number }) =>
    api.get("/patterns/labels", { params }),
  exportLabels: () => `${BASE_URL}/patterns/labels/export`,
};

// ── Research Engine (Phase 1 Rebuilt) ─────────────────────────────────────────
export const researchApi = {
  startRun: (mode: string = "SWING", universe: string = "NIFTY500", symbols?: string[]) =>
    api.post("/research/run", { mode, universe, symbols }),
  getRunStatus: (runId: string) => api.get(`/research/run/${runId}`),
  getRunSignals: (runId: string, minScore: number = 0, limit: number = 100) =>
    api.get(`/research/signals/${runId}?min_score=${minScore}&limit=${limit}`),
  listRuns: () => api.get("/research/runs"),
  analyzeStock: (symbol: string, mode: string = "SWING") =>
    api.post(`/research/analyze/${symbol}?mode=${mode}`),
};

// ── Aladdin Brain (Universal Stock Intelligence) ───────────────────────────
export const aladdinApi = {
  diagnose: (symbol: string, forceRefresh: boolean = false) =>
    api.get(`/aladdin/diagnose/${encodeURIComponent(symbol)}`, {
      params: { force_refresh: forceRefresh }
    }),
  getPopular: () => api.get("/aladdin/popular"),
  deploy: (data: {
    symbol: string;
    company_name: string;
    sector?: string;
    entry_price: number;
    stop_loss: number;
    target_price: number;
    quantity: number;
    capital?: number;
    notes?: string;
  }) => api.post("/aladdin/deploy", data),
  getBacktestReport: () => api.get("/aladdin/backtest"),
  getStressTestReport: () => api.get("/aladdin/stress-test"),
};
// Backward compatibility alias
export const oracleApi = aladdinApi;

// ── WebSocket ─────────────────────────────────────────────────────────────────
export const createScreenerWebSocket = (
  runId: string,
  onMessage: (data: ScreenerRunStatus) => void,
  onClose?: () => void
): WebSocket => {
  const ws = new WebSocket(`${WS_URL}/screener/ws/${runId}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("WS parse error:", e);
    }
  };
  ws.onclose = () => onClose?.();
  ws.onerror = (e) => console.error("WebSocket error:", e);
  return ws;
};

// ── Types ─────────────────────────────────────────────────────────────────────
export interface ScreenerRunStatus {
  run_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "NOT_FOUND";
  started_at: string;
  finished_at?: string;
  total_symbols: number;
  processed: number;
  progress_pct: number;
  passed: number;
  failed_data: number;
  failed_fundamental: number;
  failed_technical: number;
  failed_event_risk: number;
  current_symbol: string;
  signals_count: number;
  market_regime?: string;
  regime_confidence?: number;
}

export interface Signal {
  id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  signal_date: string;
  signal_price: number;
  rsi_14?: number;
  ema_200?: number;
  roce?: number;
  debt_to_equity?: number;
  piotroski_f_score?: number;
  suggested_entry?: number;
  suggested_sl?: number;
  suggested_target?: number;
  risk_reward_ratio?: number;
  passed_all: boolean;
  passed_roce: boolean;
  passed_debt_to_equity: boolean;
  passed_ema_200: boolean;
  passed_rsi: boolean;
  passed_piotroski: boolean;
  passed_earnings_blackout: boolean;
  composite_score?: number;
  market_cap?: number;
  atr_14?: number;
  adx?: number;
  
  // Phase 3: Market Regime & Direction
  direction?: string;
  market_regime?: string;
  regime_confidence?: number;

  // Phase 2: Pattern Recognition
  pattern_name?: string;
  pattern_confidence?: number;
  chart_image_path?: string;
  
  // Phase 4: Fibonacci Retracement
  fib_confluence?: boolean;
  fib_nearest_level?: string;
  fib_nearest_price?: number;
  
  is_traded: boolean;
  screener_run_id?: string;
}

export interface Trade {
  id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  direction: string;
  entry_date: string;
  entry_price: number;
  quantity: number;
  invested_amount: number;
  stop_loss: number;
  stop_loss_fixed: number;
  target_price: number;
  atr_at_entry?: number;
  risk_reward_ratio?: number;
  rsi_at_entry?: number;
  roce_at_entry?: number;
  piotroski_at_entry?: number;
  current_price?: number;
  current_rsi?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  highest_price?: number;
  days_in_trade?: number;
  exit_date?: string;
  exit_price?: number;
  exit_reason?: string;
  realized_pnl?: number;
  realized_pnl_pct?: number;
  status: string;
  notes?: string;
}

export interface PortfolioStats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  expectancy: number;
  profit_factor?: number;
  total_invested: number;
  capital?: number;
  available_cash?: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  total_return_pct: number;
  exit_reasons: {
    sl_hits: number;
    targets: number;
    rsi_exits: number;
    manual: number;
  };
}

export interface ChartCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema_50?: number;
  ema_200?: number;
  rsi?: number;
}
