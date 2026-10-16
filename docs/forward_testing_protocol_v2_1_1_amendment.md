# 🏛️ TradeMatrix Protocol v2.1.1 Amendment Log (16 October 2026)

**Reference Specification:** [docs/forward_testing_protocol_v2.md](file:///c:/project/Trade_matrix/docs/forward_testing_protocol_v2.md)  
**Executive Summary:** [docs/one_page_research_summary.md](file:///c:/project/Trade_matrix/docs/one_page_research_summary.md)  
**Amended Commit SHA:** `a014fdd`  
**Status:** Pre-Registered & Locked  

---

## The 8 Peer-Review Amendments Implemented in v2.1.1

### 1. Number Consistency & Assumed SD Clarification
- **Overview Diagram:** Corrected from `3.3%/90d` to exact **`3.85%/90d (~16.2% p.a.)`** ($SE = 1.667\% \times t_{0.025,8} = 2.306$).
- **Assumed SD:** Explicitly clarified that $\sigma_{\Delta} \approx 5.0\%$ is an **assumed pre-study planning estimate** (derived from Indian large-cap cross-sectional dispersion), NOT calculated from Pilot Cohort 0.

### 2. Single Decoupled Pass Rule
- **Previous:** Dual-hurdle (`Mean > 3.85% AND CI_lower > 0`).
- **Amended (v2.1.1):** Decoupled to two sound conditions:
  1. **Statistical Significance:** $\text{CI}_{\text{lower}} > 0.0\%$ (strictly positive 95% confidence lower bound).
  2. **Economic Significance Floor:** $\overline{\Delta} \ge +1.0\%$ per 90 days.
  *(Prevents an arbitrary 3.85% mean hurdle from blocking genuine alpha if true dispersion $s_{\Delta}$ is smaller than assumed).*

### 3. Git Tree Cleanliness & Dynamic HEAD Lock
- `ForwardTestEngine.get_scoring_git_hash(enforce_clean=True)`:
  - Verifies `git status --porcelain`. If any uncommitted files exist, freeze is refused with `RuntimeError`.
  - Automatically reads dynamic HEAD commit SHA.
- Removed outdated mock commit `40404d2` from all documentation.

### 4. Scheduler Automation & Dynamic NSE Calendar
- **Cron Job:** APScheduler weekday job configured at **09:30 AM IST**.
- **Startup Catch-Up:** Automatic missed-run catch-up logic triggered on backend startup (`check_forward_test_catchup_on_startup`).
- **NSE Trading Calendar Utility:** [backend/app/utils/nse_calendar.py](file:///c:/project/Trade_matrix/backend/app/utils/nse_calendar.py) determines trading sessions dynamically:
  - 1 Nov 2026 is Sunday $\implies$ **Cohort 1 Freeze Date: Monday, 02 November 2026** (corrected from hardcoded 3 Nov).

### 5. Ledger A Pre-Registered Execution Timings
- **Scoring Data:** Sourced strictly from EOD data up to Day $T-1$ Close.
- **Entry Price:** Official Day $T$ Open (NSE 09:15–09:30 print) on freeze morning.
- **Exit Price:** Day $T+90$ Close (rolled forward to next active NSE session if holiday/weekend).
- **Dividends & Corporate Actions:** Adjusted price series applied.

### 6. Capital Pool Ring-Fencing
- Dedicated capital pool: `FORWARD_TEST_CAPITAL_POOL = ₹10,00,000.0` in [backend/app/config.py](file:///c:/project/Trade_matrix/backend/app/config.py).
- Legacy positions (₹2.72L in 5 trades) completely insulated in separate pool. Peak 3-cohort forward exposure is ₹7.5L, leaving ₹2.5L cash buffer.
- Ledger B rejections explicitly logged as `REJECTED_CAPITAL_EXHAUSTED`.
- Ledger A (Primary Shadow Research) is fractional %-per-rupee unconstrained research, completely immune to capital constraints.

### 7. Sector Exposure, Control 2 & Universe Net Delta
- **Sector Exposure Logged:** Cohort 0 top 10 logged with 70.0% defensive weight (IT, Pharma, Auto).
- **Full Universe Distribution Logged:** All 96 stock scores logged (`min: 44.5, max: 69.6, mean: 59.1, median: 59.4, std: 5.3`).
- **Control 2 Added:** 1,000 Sector-Matched Random Baskets (`run_sector_matched_baskets`) to decompose excess return into Stock Selection Skill vs Sector Allocation Beta.
- **Exact Universe Mean:** Primary $\Delta$ calculated directly against exact universe equal-weight net return $\overline{R}_{\text{Universe}}$ (zero Monte Carlo noise), using 1,000 MC baskets for empirical percentile rank and $p$-value.

### 8. Verification Outputs
All 5 test suites verified with exit code 0:
- `python -m py_compile` (All backend files clean)
- `python scratch/dry_run_forward_v2.py` (Friction, Spearman, Deterministic MC passed)
- `python scratch/test_scorecard.py` (Scorecard & Active Pilot Cohort 0 verified)
- `npx.cmd tsc --noEmit` (Zero TypeScript errors)
- Clean HEAD Git SHA verified: `a014fdd5b8`
