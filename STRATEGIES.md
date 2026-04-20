### 2. The Trading Logic (``)

```markdown
# Trading Strategies & Logic Playbook

This document contains the plain-English rules for every algorithm running inside TradeMatrix. If the code deviates from these rules, the code is wrong.

---

## Strategy 1: The Alpha Screener (Phase 1)
**Objective:** Identify fundamentally strong companies that are currently experiencing a short-term technical pullback (Buy the dip in a strong asset).

### Parameters
* **Universe:** Nifty 500 (or Top 200 Liquid Stocks)
* **Timeframe:** Daily (End of Day Data)
* **Position Type:** Swing Trading / Short-to-Medium Term

### Filter Rules (Entry Conditions)
**A. Fundamental Filters:**
1. `ROCE > 15%` (Capital is being used efficiently).
2. `Debt-to-Equity < 1.0` (Low bankruptcy/leverage risk).

**B. Technical Filters:**
1. `Current Price > 200 DMA` (The long-term macro trend must be UP).
2. `RSI (14) < 30` (The stock is currently oversold or in a short-term correction).

### Paper Trading / Execution Logic
* **Entry:** Buy at the market open on the day *after* the signal is generated.
* **Stop Loss (SL):** 5% below the entry price (Strict cut-off).
* **Target / Exit:** - *Condition 1:* RSI (14) crosses above 70 (Overbought).
  - *Condition 2:* Fixed trailing target of 12% profit.
