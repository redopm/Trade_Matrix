# 🏛️ TradeMatrix Protocol v2.1.2 Amendment Log (3 November 2026)

> ⚠️ **Authoritative Status:** In case of any conflict, divergence, or textual discrepancy between documents or code comments, this Amendment Log (`forward_testing_protocol_v2_1_2_amendment.md`) supersedes all prior amendment logs and is strictly **authoritative, definitive, and binding**.

**Reference Specification:** [docs/forward_testing_protocol_v2.md](file:///c:/project/Trade_matrix/docs/forward_testing_protocol_v2.md)  
**Previous Amendment:** [docs/forward_testing_protocol_v2_1_1_amendment.md](file:///c:/project/Trade_matrix/docs/forward_testing_protocol_v2_1_1_amendment.md)  
**Audit Record:** [FREEZE_HASHES.txt](file:///c:/project/Trade_matrix/FREEZE_HASHES.txt)  
**Status:** Pre-Registered & Locked  

---

## 1. Summary of Methodological Amendments

| Amendment ID | Topic | Prior Status (v2.1.1) | Amended Specification (v2.1.2) | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **AMD-212-01** | **Cohort 1 Quarantine** | Slated for Nov 2 launch | Tagged `CATCHUP_LATE` & quarantined | Frozen Nov 3 (post T=0); excluded from primary $H_0$ inference |
| **AMD-212-02** | **Primary Sample Size** | $N = 9$ cohorts | **$N = 8$ cohorts** (Dec 2026 – Jul 2027) | Preserves unpolluted primary sample space |
| **AMD-212-03** | **Minimum Detectable Edge** | MDE = 3.85% / 90 days | **MDE $\approx 4.2\%$ / 90 days** (~17.8% p.a.) | Recalibrated for $N = 8$, $\sigma = 5.0\%$, $1 - \beta = 0.80$ |
| **AMD-212-04** | **Ledger B Fill Rules** | Filled at market tick `current_price` | **Target @ Limit, SL @ Stop Price** | Eliminates return overstatement from intraday spikes / stale ticks |
| **AMD-212-05** | **Data Circuit-Breaker** | No anomaly filter | **>40% Drop Blocked & Tagged `DATA_SUSPECT`** | Prevents false stop-outs from foreign vendor collisions |
| **AMD-212-06** | **Audit Trail Integrity** | N/A | **`VOID_DATA_ERROR` Enum & Reinstatement** | Preserves original erroneous rows for immutable auditability |
| **AMD-212-07** | **Scoring Hash in Containers** | Required live `git` subprocess | **Baked Image Fingerprint** (`scoring_git_hash.txt`) | Allows headless production Docker containers without `.git` |

---

## 2. Detailed Technical Specifications

### 2.1 Cohort 1 Quarantine & Primary Cohorts Reduction ($N = 8$)
1. **Quarantine Status:** Cohort 1 (`COHORT_1_202611_20261103_LATE_DEFENSIVE`) was frozen on November 3, 2026 at 10:10 AM IST (one trading day following the scheduled November 2 market open). In accordance with Protocol v2.1.1 Rule 4, it is classified as `CATCHUP_LATE` and placed into secondary observation quarantine. It does **not** contribute to the primary statistical hypothesis test.
2. **Revised Primary Cohorts ($N = 8$):** The primary empirical validation cohorts will run monthly from **December 1, 2026 through July 1, 2027**:
   - Cohort 2: December 1, 2026
   - Cohort 3: January 1, 2027
   - Cohort 4: February 1, 2027
   - Cohort 5: March 1, 2027
   - Cohort 6: April 1, 2027
   - Cohort 7: May 3, 2027
   - Cohort 8: June 1, 2027
   - Cohort 9: July 1, 2027
3. **Statistical Power Recalibration:**
   - Assumed cross-sectional dispersion: $\sigma_{\Delta} \approx 5.0\%$ per 90 days.
   - Significance level: Two-tailed $\alpha = 0.05$ ($t_{\text{crit}} = 2.365$ for $df = 7$).
   - Target power: $1 - \beta = 0.80$ ($t_{\beta} = 0.896$).
   - Standard Error: $SE = \frac{5.0\%}{\sqrt{8}} \approx 1.768\%$.
   - **Minimum Detectable Edge (MDE):**
     $$\text{MDE} = \frac{(t_{\alpha/2, 7} + t_{\beta, 7}) \cdot \sigma_{\Delta}}{\sqrt{8}} = \frac{(2.365 + 0.896) \cdot 5.0\%}{2.828} \approx \mathbf{4.22\% \text{ per 90 days}} \quad (\sim 17.8\% \text{ annualized})$$

---

### 2.2 Ledger B Execution Rules (Limit Order Fills)
To prevent distorted performance metrics from anomalous market ticks, latency, or afternoon spikes:
1. **Target Price Fill:** When `current_price >= trade.target_price` (LONG) or `current_price <= trade.target_price` (SHORT), the trade exits strictly at **`trade.target_price`** (Limit Fill Rule).
2. **Stop Loss Fill:** When `current_price <= trade.stop_loss` (LONG) or `current_price >= trade.stop_loss` (SHORT), the trade exits strictly at **`trade.stop_loss`** (Stop Order Rule), unless the asset gapped through the stop at the market open, in which case the opening tick price is used.
3. **Circuit-Breaker Data Anomaly Guard:**
   - Any single-day tick showing a $>40\%$ price collapse on an asset with entry price $>₹100$ is flagged as a vendor data anomaly.
   - The engine tags the trade notes with `[DATA_SUSPECT]`, blocks automated stop loss execution, and logs a critical error for exchange verification.

---

### 2.3 Data Audit & Corrections Audit Trail

#### HAL (Trade #20 & #26)
- **Incident:** During the 15:35 IST update on 2026-11-03, un-suffixed symbol `"HAL"` queried Yahoo Finance, matching US stock **Halliburton Company** (NYSE: HAL) trading at **$34.61**, which triggered a false stop loss exit at -99.30%. Real NSE price for Hindustan Aeronautics Limited was **₹4,958.60** (+0.23% in profit).
- **Audit Correction:**
  - Trade #20: Status updated to **`VOID_DATA_ERROR`**; original row retained in database for immutable audit.
  - Trade #26: Reinstated HAL position as **`OPEN`** at entry ₹4,947.30, current price ₹4,958.60, SL ₹4,624.74, Target ₹5,200.39, unrealized PnL +₹56.50 (+0.23%).

#### BHARTIARTL (Trade #1)
- **Incident:** Legacy position reached intraday high of **₹2,081.10** on 2026-11-03, surpassing target T2 (**₹2,031.43**). The price feed was stale during market hours due to un-suffixed symbol query error (`$BHARTIARTL: No data found, symbol may be delisted`).
- **Audit Correction:**
  - Trade #1: Status updated to **`CLOSED_TARGET`** on date `2026-11-03`.
  - Exit fill price recorded at exact limit target price **`₹2,031.43`** (Realized PnL: **+₹13,025.65** / +13.20%).
  - Notes updated with audit rationale for limit fill and stale feed attribution.

---

### 2.4 Golden Regression & Scoring Hash Verification
1. **Historical vs Current Price Suffix Isolation:**
   - Historical OHLCV fetching (`fetch_price_history`) in [data_fetcher.py](file:///c:/project/Trade_matrix/backend/app/services/data_fetcher.py#L462) and [fyers_data_client.py](file:///c:/project/Trade_matrix/backend/app/services/fyers_data_client.py#L279) has always enforced `.NS` / `NSE:SYMBOL-EQ`.
   - The `.NS` patch in `_fetch_price_sync` strictly governs live ticker polling for paper trading and does **not** alter historical scoring data.
2. **Golden Regression Benchmark:**
   - Executed 10-symbol baseline regression test on T-1 date (2026-11-02):
     `RELIANCE (58.50), TCS (61.30), HDFCBANK (50.50), ICICIBANK (67.30), BHARTIARTL (63.10), INFY (62.20), ITC (56.80), SBIN (56.40), LT (66.10), HAL (65.70)`.
   - Verified 100% bit-for-bit identical score reproducibility.
3. **Baked Image Fingerprint:**
   - Headless Docker containers in production resolve scoring git hash from baked `models/scoring_git_hash.txt` (`28096b7`), eliminating dependency on host `.git` directories.

---

### 2.5 Single Production Source of Truth
- **Production Host:** GCP VM (`tradematrix-vm`, external IP `34.68.221.238`).
- **Authoritative Database:** `/home/opmaury001/app/backend/database/tradematrix.db`.
- **Authoritative Scheduler:** Containerized APScheduler running 24x7 on production VM.
