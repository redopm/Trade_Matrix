# 🏛️ TradeMatrix Institutional Quantitative Research: 1-Page Executive Summary
*Date: October 16, 2026, Friday | Pre-Registered Protocol: v2.1.1 | Compliance: Educational & Algorithmic Research Only*

---

### 1. 🎯 Core Research Question
> **Can active algorithmic timing (RSI swing dip-buying, technical patterns, or binary 200 EMA index timing) beat passive compounding (Nifty 50 TRI Buy & Hold) in Indian equities after accounting for real statutory delivery frictions and taxes?**

---

### 2. 🧪 Kya Test Hua (What Was Empirically Tested)
1. **Factor Ablations (2023–2026, 4 Stocks):** Tested isolated factors (candlestick patterns, RSI momentum, volume spikes, oversold pullbacks) across 67–118 trades with full Indian statutory delivery frictions (0.20% round-trip STT, ₹40 brokerage, 0.10% slippage, 18% GST).
2. **Historical Out-of-Sample Trial 8 (2016–2021, 46 Large-Cap Stocks):** Pre-registered in Git (`b7ef2b8`, audited on `cc79484`). Evaluated 362 executed trades (and 3,457 portfolio-capacity rejections) against pre-committed institutional hurdles, Control 1 (Ungated Pullback), and Control 2 (Trend-Gated Nifty 50).
3. **Long-Horizon Out-of-Sample Trial 9 (2007–2015, Nifty 50 TRI):** Pre-registered in Git (`3032624`). Evaluated 200 EMA trend-following vs Buy & Hold across 8.85 years (2,230 daily bars from official NSE archives) incorporating historical RBI 91-day T-bill yields, post-budget 2024 tax law (20.8% STCG, 13.0% LTCG, 31.2% debt slab), and historical 2007–15 tax law (Sec 10(38) 0% exempt LTCG).

---

### 3. ❌ Kya Fail Hua (What Empirically Failed in the Tested Formulations)
* **Active Swing Stock-Picking Engine (Trial 8):** **FAILED 5 OF 6 PRE-COMMITTED CRITERIA.**
  - Delivered negative expectancy ($EV = -₹24.9$ per trade), net loss of -₹9,018, Calmar ratio of 0.01, and annualized CAGR of **-0.31% (closed) / +0.44% (MTM)** vs Nifty Buy & Hold **+14.49%**.
* **Binary 200 EMA Index Trend-Following (Trial 9):** **FAILED 3 OF 4 PRE-COMMITTED CRITERIA.**
  - **Under 2024 Law:** Strategy generated **3.98% to 5.35% CAGR** vs Nifty TRI Buy & Hold **8.30% CAGR** (wealth lag of -₹2.19L to -₹3.06L).
    *(Note: 3.98% is the conservative base run with all trades taxed as STCG and zero loss carry-forward; 5.35% incorporates proper 13.0% LTCG on the 2 trades held > 365 days plus full loss carry-forward).*
  - **Under 2007–15 Law:** Strategy generated **4.50% to 5.71% CAGR** vs Nifty TRI Buy & Hold **9.19% CAGR** (wealth lag of -₹2.72L to -₹3.51L, where B&H was 100% tax-free under Sec 10(38)).
* **Root-Cause Breakdown of the Performance Lag (2007–2015 Diagnostic Decomposition):**
  1. **Whipsaw + Time-Out-of-Market Drag (2.75% p.a. / 63.7% of 2007–15 lag):** In sideways choppy markets (2011–2014), **32 of 44 round-trips lasted less than 30 days** (median holding: **8.0 calendar days**), repeatedly entering near local tops and exiting near local bottoms. (Note: 42 of 44 round-trips lasted $< 365$ days, determining their STCG tax status). This drag also includes cash drag (missing rapid rally rebounds like portions of 2009–10), ETF tracking error, and slippage.
  2. **Annual Tax Drag (1.57% p.a. / 36.3% of 2007–15 lag):** Frequent annual realizations permanently deplete capital from the compounding pool, whereas Buy & Hold allows 100% of the corpus to compound undisturbed.
* **Operational Action:** **The active short-term swing engine and automated market-timing execution models are PERMANENTLY RETIRED in these specific formulations.**

---

### 4. 🛡️ Kya Bacha (What Survived: Macro Regime Indicator)
* **The 200-Day EMA Filter:** Across the two historical eras tested (the 2008 GFC and 2020 COVID crashes), the 200-day EMA demonstrated downside crash containment:
  - **Cleanest Evidence (Control 2: Trend-Gated Nifty 50, 2016–2021):** Cut index Maximum Drawdown from **38.44% to 14.14%** (a 63.2% relative reduction) while retaining **13.42% CAGR** (vs Buy & Hold 14.49%, only ~1.1% return lag), achieving a Calmar ratio of **0.95 vs 0.38**.
  - **Crisis Defense:** Held 100% cash during the March 2020 COVID crash; in 2007–15, reduced crash drawdown from **59.53% to 39.05% pre-tax (40.28% post-tax)**.
* **The Essential Nuance ("Kam Dard, Kam Return"):**
  - In 2007–15 pre-tax terms, Calmar ratios are virtually identical (**0.16 Strategy vs 0.15 Buy & Hold**).
  - The 200 EMA gate is **NOT an alpha generator**. It is an **insurance trade-off** that purchases downside drawdown reduction at the cost of an annual performance drag that varied by era:
    - **2016–2021 (pre-tax, Control 2):** ~1.1% p.a. (13.42% vs 14.49%)
    - **2007–2015 (pre-tax, Trial 9):** 2.75% p.a. (6.44% vs 9.19%)
    - **2007–2015 (post-tax, Trial 9):** ~3.4% to 4.7% p.a. depending on tax model and carry-forward.
* **Software Implementation:** Retained strictly as an objective, **descriptive macro regime indicator** (`BULLISH REGIME` vs `DEFENSIVE REGIME` banner) with educational SEBI disclaimers. It emits zero trade tips or buy recommendations.

---

### 5. ❓ Kya Nahi Pata (What Remains Unvalidated & Forward Protocol v2.1)
* **Unvalidated Live Heuristics:**
  - **46-Pattern Deep Learning (CNN):** No long-term historical out-of-sample validation; standalone pattern triggers lost money in friction tests.
  - **F&O Derivatives Flow (OI build-up, PCR, Max Pain):** Proprietary historical tick data is unavailable; zero backtested validation.
  - **Fundamental Solvency (ROCE, D/E, Altman Z):** Point-in-time filing dates are unavailable; testing current figures on historical trades induces lookahead bias.
* **Pre-Registered Forward Sunset Protocol v2.1.1 (Dual-Ledger Empirical Trial):**
  - **Core Question:** *"Does Aladdin's multi-pillar composite score systematically select 90-day stock portfolios that outperform the exact universe equal-weight mean and 1,000-basket Monte Carlo random distributions from the identical Nifty 100 universe?"*
  - **Dual-Ledger Separation:**
    - **Ledger A (Primary Shadow Research):** Fixed 90-calendar-day holding return calculated offline from universe snapshots; fractional %-per-rupee equal weighting (10.0% each); zero stop loss or target truncation; corporate-action dividend-adjusted prices; Day $T$ Open entry, Day $T+90$ Close exit.
    - **Ledger B (Secondary Live Execution Desk):** Real-world paper execution with integer shares (~₹25k slots), dynamic ATR stops, 12% profit targets, and RSI exits. Ring-fenced under `FORWARD_TEST_CAPITAL_POOL = ₹10,00,000`.
  - **Unified Primary Metric ($\Delta_{\text{Cohort}}$):**
    $$\Delta_k = R_{\text{Tool Top 10, Net, } k} - \overline{R}_{\text{Universe Equal-Weight, Net, } k}$$
    Evaluated across completed cohorts with a cross-cohort standard error: $SE(\overline{\Delta}) = s_{\Delta} / \sqrt{K}$.
  - **Cohort Cadence & Calendar Horizon Limit ($K=9$):**
    - Automated monthly schedule (1st trading day of each month at 09:30 AM IST via NSE calendar).
    - Hard 12-month calendar deadline: **October 16, 2027**.
    - Only cohorts frozen up to mid-July 2027 complete 90 days before the deadline $\implies$ exactly **$K = 9$ fully completed cohorts** (November 2026 through July 2027).
    - Oct 16, 2026 manual run is designated **Cohort 0 (Pilot Verification)**, excluded from primary statistical inference. Cohort 1 begins **Monday, 02 November 2026** (NSE session open).
  - **Frozen Delivery Friction Schedule:** Based on discount broker equity delivery (₹0 brokerage, STT 0.20%, stamp duty, turnover fees, GST, DP charges ₹15.93, slippage 0.10%) $\implies$ frozen at **0.385% round-trip**.
  - **Statistical Power & Detectable Edge:** Excess return standard deviation is an **assumed planning estimate** ($\sigma_{\Delta} \approx 5.0\% \implies SE \approx 1.67\%$). With $t_{0.025, 8} = 2.306$, statistically detectable edge is $\approx +3.85\%$ per 90 days ($\approx +16.2\%$ annualized). An **"INCONCLUSIVE"** classification remains the expected baseline outcome.
  - **Pre-Committed Tri-State Decision Rule (Evaluated strictly after all $K=9$ cohorts complete):**
    - **Pass Rule (Validation Threshold):** $\text{CI}_{\text{lower}} > 0.0\%$ AND cross-cohort mean excess return $\overline{\Delta} \ge +1.0\%$ per 90 days (economic floor).
    - **Inconclusive Zone ($0.0\% < \overline{\Delta}$ but $\text{CI}_{\text{lower}} \le 0.0\%$ or $\overline{\Delta} < +1.0\%$):** Formally classified as **"INCONCLUSIVE"**; active descriptive desk is decommissioned without commercial claims.
    - **Sunset Rule (Permanent Decommissioning):** If $\overline{\Delta} \le 0.0\%$ after $K \ge 9$ completed cohorts, Aladdin is formally declared to possess zero predictive edge and the stock selection engine is permanently retired. (Premature sunset before $K=9$ is prohibited).
  - **Diagnostic Metrics & Control 2:** Control 1 (1,000 random baskets for percentile rank), Control 2 (1,000 sector-matched random baskets to isolate sector tilt vs stock selection), full 96-stock score distribution tracking, and between-cohort Spearman rank correlation ($\rho$).

---

### 6. ⚠️ Methodological Limitations & Caveats
1. **Survivorship Bias:** The 46-stock universe is based on recent large-cap constituents, creating an upward survivorship bias on historical stock backtests.
2. **Execution Timing Deviation:** Trial 9 was executed at Day $N$ Close (+0.05% slippage) instead of Day $N+1$ Open due to official NSE TRI archive data format.
3. **Cross-Study Non-Comparability:** The three studies (Ablations 2023–26, Trial 8 2016–21, Trial 9 2007–15) utilized differing tax regimes, cash yield assumptions, and data sources; results cannot be directly cross-compared.
4. **Past Results Non-Guarantee:** Crash defense observed in historical crises (2008 GFC, 2020 COVID) reflects past market dynamics and offers no guarantee against future drawdowns.

---

### 7. 📌 Bottom-Line Operational Rule
> **In the specific algorithmic formulations tested across 13 trials, passive index compounding remained superior to active market-timing and stock-picking after statutory delivery frictions and taxes. Tactical market-timing incurred substantial whipsaw and tax drag. TradeMatrix Aladdin operates exclusively as an honest, compliant research platform that objectively describes market regimes rather than speculating on trading tips.**
