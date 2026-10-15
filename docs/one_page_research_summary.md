# 🏛️ TradeMatrix Institutional Quantitative Research: 1-Page Executive Summary
*Date: October 15, 2026 | Commit Version: research_v1-final | Compliance: Educational & Algorithmic Research Only*

---

### 1. 🎯 Core Research Question
> **Can active algorithmic timing (RSI swing dip-buying, technical patterns, or binary 200 EMA index timing) beat passive compounding (Nifty 50 TRI Buy & Hold) in Indian equities after accounting for real statutory delivery frictions and taxes?**

---

### 2. 🧪 Kya Test Hua (What Was Empirically Tested)
1. **Factor Ablations (2023–2026, 4 Stocks):** Tested isolated factors (candlestick patterns, RSI momentum, volume spikes, oversold pullbacks) across 67–118 trades with full Indian statutory delivery frictions (0.20% round-trip STT, ₹40 brokerage, 0.10% slippage, 18% GST).
2. **Historical Out-of-Sample Trial 8 (2016–2021, 46 Large-Cap Stocks):** Pre-registered in Git (`b7ef2b8`, audited on `cc79484`). Evaluated 362 executed trades (and 3,457 portfolio-capacity rejections) against pre-committed institutional hurdles, Control 1 (Ungated Pullback), and Control 2 (Trend-Gated Nifty 50).
3. **Long-Horizon Out-of-Sample Trial 9 (2007–2015, Nifty 50 TRI):** Pre-registered in Git (`3032624`). Evaluated 200 EMA trend-following vs Buy & Hold across 8.85 years (2,230 daily bars from official NSE archives) incorporating historical RBI 91-day T-bill yields, post-budget 2024 tax law (20.8% STCG, 13.0% LTCG, 31.2% debt slab), and historical 2007–15 tax law (Sec 10(38) 0% exempt LTCG).

---

### 3. ❌ Kya Fail Hua (What Empirically Failed & Why)
* **Active Swing Stock-Picking Engine (Trial 8):** **FAILED 5 OF 6 PRE-COMMITTED CRITERIA.**
  - Delivered negative expectancy ($EV = -₹24.9$ per trade), net loss of -₹9,018, Calmar ratio of 0.01, and annualized CAGR of **-0.31% (closed) / +0.44% (MTM)** vs Nifty Buy & Hold **+14.49%**.
* **Binary 200 EMA Index Trend-Following (Trial 9):** **FAILED 3 OF 4 PRE-COMMITTED CRITERIA.**
  - Under 2024 law: Strategy generated **3.98% to 5.35% CAGR** vs Nifty TRI Buy & Hold **8.30% CAGR** (wealth lag of -₹2.19L to -₹3.06L).
  - Under 2007–15 law: Strategy generated **4.50% to 5.71% CAGR** vs Nifty TRI Buy & Hold **9.19% CAGR** (wealth lag of -₹2.72L to -₹3.51L).
* **Root-Cause Breakdown of the Performance Lag:**
  1. **Gross Whipsaw Drag (2.75% p.a. / 63.7% of lag):** 42 of 44 switches were short whipsaws in sideways choppy markets (2011–2014; median holding period: 8.0 calendar days), repeatedly buying tops and selling bottoms.
  2. **Annual Tax Drag (1.57% p.a. / 36.3% of lag):** Frequent annual realizations permanently deplete capital from the compounding pool, whereas Buy & Hold allows 100% of the corpus to compound undisturbed.
* **Operational Action:** **The active short-term swing engine and automated market-timing execution models are PERMANENTLY RETIRED.**

---

### 4. 🛡️ Kya Bacha (What Survived: Macro Regime Indicator)
* **The 200-Day EMA Filter:** Across both historical eras, the 200-day EMA demonstrated dependable **downside crash containment**:
  - Reduced 2016–21 stock strategy Max Drawdown from **53.90% to 37.04%** (held 100% cash during the March 2020 COVID crash).
  - Reduced 2007–15 index crash Max Drawdown from **59.53% to 39.05% pre-tax (40.28% post-tax)**.
* **The Essential Nuance ("Kam Dard, Kam Return"):**
  - Pre-tax Calmar ratios are virtually identical (**0.16 Strategy vs 0.15 Buy & Hold**).
  - The 200 EMA gate is **NOT an alpha generator**. It is an **insurance trade-off** that purchases downside drawdown reduction at the cost of an annual performance drag of **~1.1% (pre-tax) to 4.0%–4.7% (post-tax)**.
* **Software Implementation:** Retained strictly as an objective, **descriptive macro regime indicator** (`BULLISH REGIME` vs `DEFENSIVE REGIME` banner) with educational SEBI disclaimers. It emits zero trade tips or buy recommendations.

---

### 5. ❓ Kya Nahi Pata (What Remains Unvalidated & Forward Sunset)
* **Unvalidated Live Heuristics:**
  - **46-Pattern Deep Learning (CNN):** No long-term historical out-of-sample validation; standalone pattern triggers lost money in friction tests.
  - **F&O Derivatives Flow (OI build-up, PCR, Max Pain):** Proprietary historical tick data is unavailable; zero backtested validation.
  - **Fundamental Solvency (ROCE, D/E, Altman Z):** Point-in-time filing dates are unavailable; testing current figures on historical trades induces lookahead bias.
* **Pre-Registered Forward Sunset Protocol:**
  - **Single Pre-Registered Question:** *"Do top-ranked descriptive watchlist stocks (Score $\ge 65$) outperform Nifty 50 TRI on a 90-calendar-day holding basis during bullish regimes?"*
  - **Sample Power:** Target sample size $N = 30$ completed prospective paper observations.
  - **Stopping Rule:** If average 90-day excess return over Nifty 50 TRI is $\le 0.0\%$, the descriptive scoring desk will be **permanently decommissioned** to prevent endless curve-fitting.

---

### 6. 📌 Bottom-Line Operational Rule
> **Passive compounding remains the dominant compounding vehicle in Indian equities. Tactical market-timing incurs significant friction and tax penalties. TradeMatrix Aladdin operates exclusively as an honest, compliant research platform that objectively describes market regimes rather than speculating on trading tips.**
