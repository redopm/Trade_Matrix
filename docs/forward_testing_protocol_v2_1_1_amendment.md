# 🏛️ TradeMatrix Protocol v2.1.1 Amendment Log (16 October 2026)

> ⚠️ **Authoritative Status:** In case of any conflict, divergence, or textual discrepancy between documents or code comments, this Amendment Log (`forward_testing_protocol_v2_1_1_amendment.md`) is strictly **authoritative, definitive, and binding**.

**Reference Specification:** [docs/forward_testing_protocol_v2.md](file:///c:/project/Trade_matrix/docs/forward_testing_protocol_v2.md)  
**Executive Summary:** [docs/one_page_research_summary.md](file:///c:/project/Trade_matrix/docs/one_page_research_summary.md)  
**Audit Record:** [FREEZE_HASHES.txt](file:///c:/project/Trade_matrix/FREEZE_HASHES.txt)  
**Status:** Pre-Registered & Locked  

---

## 1. Core Methodological Amendments (Detailed Specifications)

### 1. Number Consistency & Assumed SD Clarification
- **Overview Diagram:** Corrected from `3.3%/90d` to exact **`3.85%/90d (~16.2% p.a.)`** ($SE = 1.667\% \times t_{0.025,8} = 2.306$).
- **Assumed SD:** Explicitly clarified that $\sigma_{\Delta} \approx 5.0\%$ is an **assumed pre-study planning estimate** (derived from Indian large-cap cross-sectional dispersion), NOT calculated from Pilot Cohort 0.

### 2. Single Decoupled Pass Rule
- **Previous:** Dual-hurdle (`Mean > 3.85% AND CI_lower > 0`).
- **Amended (v2.1.1):** Decoupled to two sound conditions:
  1. **Statistical Significance:** $\text{CI}_{\text{lower}} > 0.0\%$ (strictly positive 95% confidence lower bound).
  2. **Economic Significance Floor:** $\overline{\Delta} \ge +1.0\%$ per 90 days.
  *(Prevents an arbitrary 3.85% mean hurdle from blocking genuine alpha if true dispersion $s_{\Delta}$ is smaller than assumed).*
- **Inconclusive Zone Definition:** Formally defined as **$0.0\% < \overline{\Delta} < +1.0\%$ OR $\text{CI}_{\text{lower}} \le 0.0\%$**.

### 3. Scoring-Specific Clean Tree Check & Full Fingerprint
- **Previous Risk:** A dirty check on the whole repository (`git status --porcelain`) would cause any stray note, scratch script, or untracked test file to reject Cohort 1 on Nov 2 with `RuntimeError`.
- **Amended (v2.1.1):**
  - Dirty check is **strictly restricted to scoring-critical code files**:
    - `backend/app/services/aladdin_brain.py`
    - `backend/app/services/technical.py`
    - `backend/app/services/fundamental.py`
    - `backend/app/services/fibonacci.py`
    - `backend/app/services/market_regime.py`
    - `backend/app/services/data_fetcher.py`
  - In addition, ML model weights are tracked via SHA256 content hash:
    - `backend/models/aladdin_classifier.pkl`
    - `backend/models/aladdin_regressor.pkl`
    - `backend/models/aladdin_feature_names.json`
    - `backend/models/expert_model_weights.pth`
  - `forward_test.py` harness is excluded so display/logging tweaks do not alter the scoring algorithm fingerprint.
  - Unrelated edits in `scratch/`, `docs/`, or `frontend/` will **NEVER block cohort freeze**.
- Removed outdated mock commit `40404d2` from all documentation.

### 4. Scheduler Automation & Catch-Up Quarantine Rule
- **Cron Job:** APScheduler weekday job configured at **09:30 AM IST**.
- **Startup Catch-Up:** Automatic missed-run catch-up logic triggered on backend startup (`check_forward_test_catchup_on_startup`).
- **Timing Drift & Lookahead Quarantine (`CATCHUP_LATE`):**
  - If a freeze runs on-schedule on the first trading day: Tagged `PRIMARY` (included in primary statistical inference).
  - If a freeze is delayed because the server/laptop was offline on the first trading day: Tagged **`CATCHUP_LATE`** and **strictly quarantined from primary statistical inference** to prevent lookahead bias and entry price distortion.

### 5. NSE Trading Calendar & 2027 Provisional Annotation
- **NSE Trading Calendar Utility:** [backend/app/utils/nse_calendar.py](file:///c:/project/Trade_matrix/backend/app/utils/nse_calendar.py) determines trading sessions dynamically:
  - 1 Nov 2026 is Sunday $\implies$ **Cohort 1 Freeze Date: Monday, 02 November 2026** (corrected from hardcoded 3 Nov).
- **2026 Holidays:** Verified against official NSE Master Holiday Circular.
- **2027 Holidays:** Explicitly annotated in code and docs as **PROVISIONAL** (standard exchange projections; subject to final annual circular issued by NSE in Nov/Dec 2026).

### 6. Ledger A Pre-Registered Execution Timings & Strict T-1 Truncation
- **Scoring Data:** Sourced strictly from EOD data up to Day $T-1$ Close. Enforced via `as_of_date` parameter in `AladdinBrainEngine.diagnose_stock(sym, as_of_date=now.date())` which explicitly strips any partial day-of-freeze candle.
- **Entry Price:** Official Day $T$ Open (NSE 09:15–09:30 print) on freeze morning.
- **Exit Price:** Day $T+90$ Close (rolled forward to next active NSE session if holiday/weekend).
- **Dividends & Corporate Actions:** Adjusted price series applied.

### 7. Capital Pool Ring-Fencing
- Dedicated capital pool: `FORWARD_TEST_CAPITAL_POOL = ₹10,00,000.0` in [backend/app/config.py](file:///c:/project/Trade_matrix/backend/app/config.py).
- Legacy positions (₹2.72L in 5 trades) completely insulated in separate pool. Peak 3-cohort forward exposure is ₹7.5L, leaving ₹2.5L cash buffer.
- Ledger B rejections explicitly logged as `REJECTED_CAPITAL_EXHAUSTED`.
- Ledger A (Primary Shadow Research) is fractional %-per-rupee unconstrained research, completely immune to capital constraints.

### 8. Sector Exposure, Control 2 & Universe Net Delta
- **Sector Exposure Logged:** Cohort 0 top 10 logged with 70.0% defensive weight (IT, Pharma, Auto).
- **Full Universe Distribution Logged:** All 96 stock scores logged (`min: 44.5, max: 69.6, mean: 59.1, median: 59.4, std: 5.3`).
- **Control 2 Added:** 1,000 Sector-Matched Random Baskets (`run_sector_matched_baskets`) to decompose excess return into Stock Selection Skill vs Sector Allocation Beta.
- **Exact Universe Mean:** Primary $\Delta$ calculated directly against exact universe equal-weight net return $\overline{R}_{\text{Universe}}$ (zero Monte Carlo noise), using 1,000 MC baskets for empirical percentile rank and $p$-value.

### 9. Overlapping Cohort Autocorrelation Limitation & "PASS (suggestive)" Label
- Monthly cohorts with 90-day holding horizons overlap for 60 and 30 days respectively, inducing cross-cohort return autocorrelation.
- The standard error formula ($SE = s_{\Delta} / \sqrt{K}$) assumes independent draws, so the resulting Confidence Interval is narrower than true cross-correlation would yield.
- Therefore, if the empirical hurdle is cleared, the status is pre-committed strictly as **`PASS (suggestive): Algorithmic Edge Suggested Under Overlapping Cohort Assumptions`**, and capital allocation must remain conservative without risking large real institutional money.

---

## 2. Test Verification & Code Quality Status

1. **Python Compilation (`py_compile`):**
   ```powershell
   python -m py_compile backend/app/main.py backend/app/services/forward_test.py backend/app/routers/forward_test.py backend/app/services/scheduler.py backend/app/utils/nse_calendar.py backend/app/models/trade.py backend/app/config.py
   # Result: Exit Code 0 (Clean, 0 errors)
   ```

2. **Offline Simulation & Friction Dry-Run:**
   ```powershell
   python scratch/dry_run_forward_v2.py
   # Result: Exit Code 0 (Friction, Spearman rho, and Deterministic 1,000 MC simulation verified)
   ```

3. **Protocol Scorecard Verification:**
   ```powershell
   python scratch/test_scorecard.py
   # Result: Exit Code 0 (Scorecard correctly reports Active Pilot Cohort 0 and In-Progress trial)
   ```

4. **Frontend TypeScript Typecheck:**
   ```powershell
   npx.cmd tsc --noEmit
   # Result: Exit Code 0 (Zero TypeScript compilation errors)
   ```

5. **Frontend ESLint Audit (`npx.cmd eslint app/ lib/`):**
   - **Status:** Completed.
   - **Output:** 194 issues reported (126 errors, 68 warnings).
   - **Root Cause Audit:** 100% of reported issues are pre-existing `@typescript-eslint/no-explicit-any` usages in legacy UI files (e.g. `api.ts`, `training/page.tsx`, `settings/page.tsx`).
   - **Zero Lint Regressions:** The modifications made for Protocol v2.1.1 (`page.tsx` and `api.ts` cohort methods) introduced **zero** lint errors.

---

## 3. Operational Readiness & Pre-November 2 Execution Checklist

Before Cohort 1 executes on **Monday, 02 November 2026 at 09:30 AM IST**, 4 operational safeguards are permanently enforced and tested:

### Check 1: Comprehensive Scoring Files & Model Weights Fingerprint
- **Audit Findings:** The initial hash monitored only 3 files (`aladdin_brain.py`, `forward_test.py`, `data_fetcher.py`).
- **Resolution:**
  - Expanded code cleanliness checking to all 6 modules that determine composite scores:
    1. `backend/app/services/aladdin_brain.py` (composite formula & weights)
    2. `backend/app/services/technical.py` (technical indicators)
    3. `backend/app/services/fundamental.py` (Piotroski & Alt-Z scoring)
    4. `backend/app/services/fibonacci.py` (harmonic & golden ratio confluence)
    5. `backend/app/services/market_regime.py` (VIX & sector defensive rotation)
    6. `backend/app/services/data_fetcher.py` (market data feed normalization)
  - Explicitly excluded `forward_test.py` harness so display formatting or reporting tweaks cannot corrupt the algorithm fingerprint.
  - Added SHA256 content hashing for binary ML models:
    - `backend/models/aladdin_classifier.pkl`
    - `backend/models/aladdin_regressor.pkl`
    - `backend/models/aladdin_feature_names.json`
    - `backend/models/expert_model_weights.pth`
  - Combined scoring fingerprint: `<git_commit_sha>+<weights_sha256>`. Any uncommitted change in the 6 scoring files halts freeze with `RuntimeError`.

### Check 2: Strict T-1 EOD Data Truncation (Zero Partial Bar Leakage)
- **Audit Findings:** Running freeze at 09:30 AM morning or after market close risks including an incomplete or lookahead daily candle.
- **Resolution:**
  - Added `as_of_date: Optional[date] = None` to `AladdinBrainEngine.diagnose_stock`.
  - When `as_of_date` is provided, all dataframe bars where `df.index.date >= as_of_date` are strictly dropped:
    ```python
    if as_of_date is not None:
        df = df[df.index.date < as_of_date].copy()
    ```
  - Indicators (RSI, EMAs, ATR, SuperTrend, Volume) and composite score are calculated strictly from completed EOD bars up to Day $T-1$ Close.
  - Entry price is sourced from Day $T$ live quote / Open at 09:30 AM.

### Check 3: Fyers Token Expiration, Machine Availability & Alerts
- **Token Lifecycle:**
  - Fyers access tokens expire daily.
  - `DataFetcher` has a tested automatic fallback: if Fyers token is absent or expired, `yfinance` seamlessly provides daily EOD historical bars and quotes.
  - The scoring pipeline will NOT crash if Fyers token is expired on Nov 2 morning.
- **Machine Availability & Quarantine:**
  - If the machine is powered off or backend is offline at 09:30 AM on Nov 2:
    - Upon machine restart, `check_and_freeze_monthly_cohort_if_due` automatically detects the missed session.
    - Because the date is after Day $T$ 09:30 AM, it automatically tags the batch as `CATCHUP_LATE`.
    - `CATCHUP_LATE` cohorts are permanently quarantined from the Primary Trial ($K=9$), preserving empirical integrity.
- **Execution Environment Recommendation:**
  - For zero downtime, run the backend on an always-on VM or GCP instance.
  - If running locally, power on laptop by 09:15 AM on Monday, 02 Nov 2026.

### Check 4: End-to-End Scheduled Pipeline Dry-Run
- **Simulation:** Cloned `database/tradematrix.db` to `tradematrix_e2e_test.db` and simulated execution of `check_and_freeze_monthly_cohort_if_due(session, target_date=date(2026, 11, 2))`.
- **Results:**
  - Triggered cohort freeze on Monday, 02 Nov 2026 (first trading day of month).
  - Calculated 5-pillar diagnostics with $T-1$ truncation across entire universe.
  - Saved 96 universe score snapshots in Ledger A and 10 paper trades in Ledger B.
  - Idempotency test confirmed: second invocation returned `None` with zero duplicate rows.

### Honest Statistical Limitation: "PASS (suggestive)"
- **Overlapping Cohort Autocorrelation:** The standard error $s_{\Delta} / \sqrt{9}$ assumes independent trials. However, adjacent 90-day cohorts overlap for 60 and 30 days respectively, inducing cross-cohort return correlation and understating true uncertainty.
- **Binding Verdict:** If the primary evaluation clears all hurdle criteria ($CI_{\text{lower}} > 0.0\%$ and $\overline{\Delta} \ge +1.0\%$), the verdict is strictly pre-registered as:
  **`PASS (suggestive): Algorithmic Edge Suggested Under Overlapping Cohort Assumptions`**.
  This label reminds all stakeholders that paper forward edge is suggestive and does not warrant unhedged institutional capital allocation.

---

## 4. Operational Calendar & Next Action Items

| Date & Time | Milestone / Action | Primary Objective |
| :--- | :--- | :--- |
| **02 Nov 2026, 09:45 AM IST** | **Cohort 1 Verification** | Confirm Cohort 1 was generated with `PRIMARY` tag (not `CATCHUP_LATE`), 96 scrips scored in Ledger A, and 10 trades deployed in Ledger B. |
| **Nov 2026 – Oct 2027** | **Monthly 15-Minute Audit** | Once a month, review dashboard for 15 minutes to confirm active batch generation. Zero code or doc edits. |
| **~14 Jan 2027** | **Cohort 0 Pipeline Dry-Run** | Cohort 0 (Pilot) completes 90-day holding horizon. Execute shadow return, Monte Carlo percentile rank, and Spearman correlation pipeline to validate evaluation math before Cohort 1 matures (~01 Feb 2027). |
| **October 2027** | **Final Trial Scorecard** | Compute definitive primary trial metrics across 9 primary cohorts ($K=9$). |

