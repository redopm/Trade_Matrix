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

### 3. Scoring-Specific Clean Tree Check & Dedicated Hash
- **Previous Risk:** A dirty check on the whole repository (`git status --porcelain`) would cause any stray note, scratch script, or untracked test file to reject Cohort 1 on Nov 2 with `RuntimeError`.
- **Amended (v2.1.1):**
  - Dirty check is **strictly restricted to scoring-critical files**:
    - `backend/app/services/aladdin_brain.py`
    - `backend/app/services/forward_test.py`
    - `backend/app/services/data_fetcher.py`
  - Unrelated edits in `scratch/`, `docs/`, or `frontend/` will **NEVER block cohort freeze**.
  - `scoring_git_hash` specifically tracks the commit history of the scoring logic (`git log -1 --format=%h -- [scoring_files]`), while repo HEAD is logged separately for general audit.
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

### 6. Ledger A Pre-Registered Execution Timings
- **Scoring Data:** Sourced strictly from EOD data up to Day $T-1$ Close. Zero lookahead into Day $T$ pricing.
- **Entry Price:** Official Day $T$ Open (NSE 09:15–09:30 print) on freeze morning.
- **Exit Price:** Day $T+90$ Close (rolled forward to next active NSE session if holiday/weekend).
- **Dividends & Corporate Actions:** Corporate-action dividend-adjusted prices sourced.

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
