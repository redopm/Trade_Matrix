# 🧪 TradeMatrix v3 Research Hypotheses Log

> **Protocol Integrity Notice:**  
> These hypotheses are documented strictly for post-trial research evaluation (after the Protocol v2.1.1 forward validation series completes in 2027).  
> **Under Protocol v2.1.1 rules, NO SCORING OR TRADING RULES MAY BE MODIFIED mid-flight.**  
> Pre-Registered Scoring Code Hash (`50f7c60`) and Model Weights Hash (`34f27003`) remain 100% frozen.

---

### Hypothesis 1: Macro Regime Gate Hard Enforcement (vs Observation Mode)
- **Concept:** Transition from passive observation tagging (`[Macro Warning: Nifty < 200 EMA]`) to active order suppression for High-Beta / Cyclical sectors during `DEFENSIVE` regimes.
- **Null Hypothesis ($H_0$):** Hard suppression of high-beta dip setups in defensive markets reduces total portfolio Sharpe ratio due to missing sharp mean-reversion bounces.
- **Alternative ($H_1$):** Restricting defensive cohort allocations exclusively to Low-Beta/Pharma/FMCG/IT reduces maximum drawdown without diminishing 90-day excess return $\Delta$.
- **Test Metric:** Cohort maximum drawdown (MDD) and post-recovery hit rate.

---

### Hypothesis 2: Multi-Timeframe Trend Confluence (Weekly EMA Filter)
- **Concept:** Require daily oversold signals (RSI < 30-40) to maintain Weekly 50 EMA or Weekly 200 EMA structural support.
- **Null Hypothesis ($H_0$):** Adding weekly moving average constraints introduces lag and misses the steepest V-bottom recovery trades.
- **Alternative ($H_1$):** Filters out multi-month structural downtrend "falling knives" (such as cyclical equipment manufacturers during industry downcycles).
- **Test Metric:** Win rate on trades held > 30 days and reduction in tail-loss events (> 8% loss).

---

### Hypothesis 3: Institutional Volume & Delivery Confirmation
- **Concept:** Filter buy signals to require entry day Volume > $1.3 \times$ 20-day SMA Volume AND NSE Delivery Percentage > 40%.
- **Null Hypothesis ($H_0$):** Delivery spikes are lagging indicators of institutional presence and reduce trade frequency without improving $\Delta$.
- **Alternative ($H_1$):** High delivery ratio filters out retail intraday churn and ensures institutional accumulation backing the dip.
- **Test Metric:** Spearman rank correlation $\rho$ between signal score and forward 30-day alpha.

---

### Hypothesis 4: Asymmetric Scale-Out (Partial Profit Booking at 1.5R / +5%)
- **Concept:** Automatically close 50% position quantity at Target 1 (+5.0% or $1.5 \times \text{ATR}$) and advance Stop-Loss of residual 50% to Breakeven (Cost).
- **Protocol Impact:** Safe for Ledger B execution optimization without altering Ledger A empirical scoring integrity.
- **Caveat:** Does not constitute "zero risk free ride" due to overnight gap-down slippage below breakeven stop and opportunity cost on multi-bagger runners.
- **Test Metric:** Realized portfolio Sharpe ratio and win-to-loss payoff ratio across 100+ executed trades.

---

### Hypothesis 5: Extended Corporate Event / Earnings Blackout Window
- **Concept:** Broaden the earnings blackout filter from $\pm 3$ trading days to $\pm 5$ or $\pm 7$ trading days around quarterly results announcements.
- **Null Hypothesis ($H_0$):** Earnings announcements provide volatility necessary for dip-buying mean reversion; wider windows reduce opportunity set.
- **Alternative ($H_1$):** Post-earnings gap-down tail risk accounts for disproportionate losses in algorithmic swing trades.
- **Test Metric:** Frequency and magnitude of gap-downs $> 3\%$ past statutory stop loss.

---

### Hypothesis 6: Duplicate Position Suppression & Runner Trailing (Anti-Averaging Up)
- **Concept:** If an existing open trade for a symbol is already active and the symbol is re-selected in subsequent cohort Top 10 rankings:
  1. Suppress new duplicate market orders to prevent high-price averaging up and concentration risk.
  2. Extend Target (T2 -> T3) and trail Stop-Loss above original entry to lock in gains ("Let Winners Run").
  3. Reallocate cohort capital to the next highest-ranking eligible symbol (Rank #11) to maintain diversification.
- **Null Hypothesis ($H_0$):** Suppressing re-buys of high-momentum winners reduces overall portfolio CAGR compared to pyramiding into runners.
- **Alternative ($H_1$):** Prevents portfolio average price distortion and late-cycle momentum traps while unlocking maximum runner upside risk-free.
- **Test Metric:** Portfolio diversification entropy, average winner return, and avoidance of breakeven round-trips.
