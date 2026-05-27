# TradeMatrix — Personal Algo-Trading Control Center

> **Phase 1: The Alpha Screener** — Complete implementation

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=nextdotjs)](https://nextjs.org)
[![SQLite](https://img.shields.io/badge/SQLite-Async-blue?logo=sqlite)](https://sqlite.org)

---

## 📋 Overview

TradeMatrix is a systematic algorithmic trading ecosystem for NSE/BSE Indian stocks. It combines:
- **Fundamental screening** (ROCE, D/E, Piotroski F-Score)
- **Technical analysis** (RSI, 200 EMA, ATR-based SL)
- **Paper trading** with full lifecycle management
- **Event Risk Filter** (blocks trades ±3 days around earnings)

---

## 🗺 Roadmap Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | The Core Alpha Screener | ✅ **Complete** |
| Phase 2 | Hybrid Pattern Recognition (ML) | 🔜 Planned |
| Phase 3 | Ecosystem & Paper Trading (Advanced) | 🔜 Planned |
| Phase 4 | Backtesting Engine | 🔜 Planned |
| Phase 5 | Live Execution | 🔜 Planned |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14 + TypeScript + Tailwind CSS |
| **Backend** | Python 3.11 + FastAPI (async) |
| **Database** | SQLite + SQLAlchemy 2.0 (async) |
| **Data** | yfinance (NSE stocks) |
| **Analysis** | pandas-ta (technical indicators) |
| **Scheduler** | APScheduler (daily 3:45 PM IST) |
| **Logging** | Loguru (structured, file rotation) |

---

## 🎯 Phase 1 Strategy — Alpha Screener

**Objective:** Find fundamentally strong companies in a short-term technical dip.

### Filter Rules

**A. Fundamental Filters:**
```
ROCE > 15%              # Capital efficiency
D/E < 1.0              # Low leverage (skip for banking)
Piotroski F-Score ≥ 7  # Financial quality score (0-9)
```

**B. Technical Filters:**
```
Price > 200 EMA        # Macro trend must be UP
RSI(14) < 30           # Short-term oversold
```

**C. Event Risk Filter:**
```
Not within ±3 days of Next Earnings Date
```

### Trade Parameters
```
Entry:      Next market open
Stop Loss:  max(5%, 2×ATR) — dynamic ATR-based
Target:     RSI > 70 OR +12% profit
Universe:   Nifty 500 (200 liquid stocks in Phase 1)
```

### Expert Improvements Over Original Plan
1. **ATR-based Dynamic SL** — adapts to stock volatility (better than fixed %)
2. **Piotroski F-Score** — 9-point financial quality filter
3. **Altman Z-Score** — bankruptcy risk screening
4. **Sector-aware rules** — Banking: NIM/NPA instead of D/E
5. **Composite Score** — Ranks all signals by weighted quality
6. **WebSocket progress** — Real-time screener progress in UI
7. **Async architecture** — Non-blocking concurrent data fetches
8. **Structured logging** — Loguru with file rotation

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone (already done)
```bash
git clone https://github.com/redopm/Trade_Matrix.git
cd Trade_Matrix
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Or use the startup script:**
```bash
start.bat
```

Backend will be available at:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`

---

## 📡 API Reference

### Screener
```
POST /api/v1/screener/run          # Start async screener run
GET  /api/v1/screener/run/{id}     # Get run status
GET  /api/v1/screener/results      # Get all signals (paginated)
GET  /api/v1/screener/results/passed  # Get only passing signals
WS   /api/v1/screener/ws/{id}     # Real-time progress
```

### Trades
```
POST /api/v1/trades/               # Create paper trade from signal
GET  /api/v1/trades/               # List all trades
GET  /api/v1/trades/open           # Get open trades
GET  /api/v1/trades/stats          # Portfolio statistics
PUT  /api/v1/trades/{id}/close     # Close trade manually
POST /api/v1/trades/update-all     # Update all P&L
```

### Stocks
```
GET /api/v1/stocks/search          # Search by symbol/name
GET /api/v1/stocks/{symbol}        # Full snapshot
GET /api/v1/stocks/{symbol}/chart  # OHLCV chart data
GET /api/v1/stocks/{symbol}/technicals  # Technical indicators
GET /api/v1/stocks/{symbol}/fundamentals  # Fundamental metrics
```

### Dashboard
```
GET /api/v1/dashboard/summary      # Portfolio + screener overview
GET /api/v1/dashboard/pnl-chart    # Daily P&L chart data
GET /api/v1/dashboard/heatmap      # Sector performance heatmap
```

---

## 📁 Project Structure

```
Trade_Matrix/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entrypoint
│   │   ├── config.py          # All settings (pydantic-settings)
│   │   ├── database.py        # Async SQLAlchemy setup
│   │   ├── models/
│   │   │   ├── stock.py       # StockUniverse ORM
│   │   │   ├── signal.py      # ScreenerSignal ORM
│   │   │   └── trade.py       # PaperTrade ORM
│   │   ├── routers/
│   │   │   ├── screener.py    # Screener API + WebSocket
│   │   │   ├── trades.py      # Paper trades API
│   │   │   ├── stocks.py      # Stock data API
│   │   │   └── dashboard.py   # Dashboard API
│   │   ├── services/
│   │   │   ├── data_fetcher.py    # yfinance async wrapper
│   │   │   ├── fundamental.py     # ROCE, D/E, Piotroski, Altman Z
│   │   │   ├── technical.py       # EMA, RSI, ATR, MACD, ADX...
│   │   │   ├── screener.py        # Alpha Screener engine
│   │   │   ├── paper_trading.py   # Trade lifecycle engine
│   │   │   └── scheduler.py       # APScheduler jobs
│   │   └── utils/
│   │       ├── logger.py          # Loguru structured logging
│   │       └── helpers.py         # Utilities
│   ├── requirements.txt
│   ├── .env.example
│   └── start.bat
├── frontend/
│   ├── app/
│   │   ├── page.tsx           # Dashboard
│   │   ├── screener/page.tsx  # Alpha Screener
│   │   ├── trades/page.tsx    # Paper Trades
│   │   └── stocks/page.tsx    # Stock Lookup
│   ├── components/
│   │   └── layout/Sidebar.tsx # Navigation sidebar
│   ├── lib/api.ts             # Typed API client
│   └── app/globals.css        # Dark trading UI theme
├── database/                  # Auto-created SQLite DB
├── logs/                      # Log files
├── README.md
└── STRATEGIES.md
```

---

## ⚙️ Configuration

All settings are in `backend/app/config.py` and can be overridden via `.env`:

```env
# Screener
MIN_ROCE=15.0
MAX_DEBT_TO_EQUITY=1.0
MIN_PIOTROSKI_SCORE=7
RSI_OVERSOLD=30.0
EMA_LONG_PERIOD=200

# Paper Trading
DEFAULT_CAPITAL=100000.0        # ₹1 Lakh
DEFAULT_POSITION_SIZE_PCT=0.10  # 10% per trade
FIXED_SL_PCT=0.05               # 5% hard SL
ATR_SL_MULTIPLIER=2.0           # 2×ATR dynamic SL
TARGET_PROFIT_PCT=0.12          # 12% target
EARNINGS_BLACKOUT_DAYS=3        # ±3 days event risk
```

---

## 📊 Composite Score Formula

Signals are ranked by a weighted composite score (0–100):

| Component | Weight | Logic |
|-----------|--------|-------|
| ROCE | 25 pts | `min(25, ROCE/40 × 25)` |
| D/E (inverse) | 15 pts | `(1 - D/E) × 15` |
| RSI (inverse) | 20 pts | `(30 - RSI)/30 × 20` (only if RSI ≤ 30) |
| Piotroski F | 20 pts | `F_Score/9 × 20` |
| EPS Growth | 10 pts | `min(10, EPS_Growth/30 × 10)` |
| Volume Ratio | 10 pts | `min(10, Vol_Ratio × 5)` |

---

## 🔄 Automated Schedule (IST)

| Time | Job |
|------|-----|
| **3:45 PM** | Daily Alpha Screener (Nifty 500) |
| **9:20 AM** | Update open trade P&L + check exits |

---

## ⚠️ Disclaimer

TradeMatrix is for **educational and paper trading purposes only**. This is NOT financial advice. Never use real money based solely on algorithmic signals. Always do your own research.

---

## 📈 Future Phases

**Phase 2:** Agentic AI labels historical chart patterns → trains local ML model → real-time pattern detection

**Phase 3:** Advanced backtesting, live paper trading, portfolio optimization

**Phase 4:** Backtesting with transaction costs, slippage simulation

**Phase 5:** Broker API integration (Zerodha/Angel One)

---

*Built with ❤️ by redopm*
