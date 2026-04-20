# Trade_Matrix
# TradeMatrix: Personal Algo-Trading Control Center

## Overview
TradeMatrix is a systematic algorithmic trading ecosystem designed to filter, backtest, and execute trades without manual emotional interference. It combines fundamental screening, technical analysis, and locally-trained ML models for pattern recognition.

## 🛠 Tech Stack
* **Frontend:** Next.js / React (Tailwind CSS for UI)
* **Backend:** Python (FastAPI for serving data, Pandas/TA-Lib for logic)
* **Database:** SQLite (for local paper trading and order tracking)
* **Data Sources:** Yahoo Finance (yfinance) / NSE Python APIs

## 🗺 The 5-Phase Roadmap
1. **Phase 1: The Core Screener** - Filtering stocks using a blend of Fundamentals (ROCE, Debt) and Technicals (RSI, DMA).
2. **Phase 2: Hybrid Pattern Recognition** - Using Agentic AI to label historical chart data, then training a lightweight local ML model for real-time pattern detection.
3. **Phase 3: Ecosystem & Paper Trading** - Built-in continuous backtesting and live paper trading tracking (P&L, targets, stop-losses).
4. **Phase 4: F&O Integration** - Options data integration (OI, Option Chain) for risk calculation and hedging strategies.
5. **Phase 5: Sentiment & Execution** - Real-time news/sentiment filtering and final broker API integration for auto-execution.

## 🚀 Local Setup Instructions

1. **Clone the repository & create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
2. Install dependencies:
   pip install -r requirements.txt
3. Environment Variables: (Warning: Create a .env file in the root directory. Never commit this file.)
  # API Keys
  DATA_API_KEY=your_api_key_here
  BROKER_API_KEY=your_broker_key_here
  
  # Database
  DB_PATH=sqlite:///tradematrix_local.db
