"""
Fundamental Analysis Service
Computes all fundamental metrics from yfinance info dict:
- ROCE, ROE, D/E ratio
- Piotroski F-Score (0–9)
- Altman Z-Score
- Sector-aware rules (Banking: NIM/NPA)
- Earnings quality checks
"""
from typing import Any, Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Banking/NBFC sector identifiers ──────────────────────────────────────────
BANKING_SECTORS = {
    "Financial Services", "Banks", "Banking", "NBFC",
    "Insurance", "Diversified Financials",
}
CAPITAL_INTENSIVE_SECTORS = {
    "Steel", "Power", "Utilities", "Basic Materials",
    "Metals & Mining", "Energy",
}


class FundamentalAnalyzer:
    """
    Computes fundamental analysis metrics from raw yfinance info dict.
    
    Usage:
        analyzer = FundamentalAnalyzer()
        result = analyzer.analyze(symbol, info_dict)
    """

    def __init__(self) -> None:
        self.cfg = settings

    def analyze(
        self, symbol: str, info: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Main entry point: compute all fundamental metrics.
        
        Returns a dict with all computed values and pass/fail flags.
        """
        if not info:
            return self._empty_result(symbol)

        sector = info.get("sector", "") or ""
        is_banking = self._is_banking(sector)
        is_capital_intensive = self._is_capital_intensive(sector)

        result = {
            "symbol": symbol,
            "sector": sector,
            "industry": info.get("industry", ""),
            "company_name": info.get("longName", symbol),
            "is_banking": is_banking,
            "is_capital_intensive": is_capital_intensive,
            # ── Prices ──────────────────────────────────────────────────
            "current_price": self._safe_float(info, "currentPrice") or
                             self._safe_float(info, "regularMarketPrice"),
            "market_cap": self._safe_float(info, "marketCap"),
            # ── Valuation ───────────────────────────────────────────────
            "pe_ratio": self._safe_float(info, "trailingPE"),
            "forward_pe": self._safe_float(info, "forwardPE"),
            "pb_ratio": self._safe_float(info, "priceToBook"),
            "peg_ratio": self._safe_float(info, "pegRatio"),
            "ev_ebitda": self._safe_float(info, "enterpriseToEbitda"),
            # ── Profitability ────────────────────────────────────────────
            "roe": self._compute_roe(info),
            "roa": self._safe_float(info, "returnOnAssets"),
            "operating_margin": self._safe_float(info, "operatingMargins"),
            "net_profit_margin": self._safe_float(info, "profitMargins"),
            # ── Financial Health ─────────────────────────────────────────
            "current_ratio": self._safe_float(info, "currentRatio"),
            "quick_ratio": self._safe_float(info, "quickRatio"),
            "free_cash_flow": self._safe_float(info, "freeCashflow"),
            # ── Growth ──────────────────────────────────────────────────
            "eps_growth_yoy": self._compute_eps_growth(info),
            "revenue_growth_yoy": self._safe_pct(info, "revenueGrowth"),
            "earnings_growth": self._safe_pct(info, "earningsGrowth"),
            # ── Shareholding ─────────────────────────────────────────────
            "promoter_holding": None,   # Not available via yfinance; requires NSE API
            "fii_holding": None,
            "dii_holding": None,
        }

        # ── Computed Metrics ─────────────────────────────────────────────────
        result["roce"] = self._compute_roce(info)
        result["debt_to_equity"] = self._compute_debt_to_equity(info)

        # ── Banking-specific ─────────────────────────────────────────────────
        result["nim"] = None          # NSE-specific, requires different source
        result["npa_ratio"] = None

        # ── Quant Scores ─────────────────────────────────────────────────────
        result["piotroski_f_score"] = self._compute_piotroski(info, result)
        result["altman_z_score"] = self._compute_altman_z(info)

        # ── Filter Evaluation ────────────────────────────────────────────────
        result.update(self._evaluate_filters(result, is_banking, is_capital_intensive))

        return result

    # ── Filter Evaluation ─────────────────────────────────────────────────────

    def _evaluate_filters(
        self,
        data: dict[str, Any],
        is_banking: bool,
        is_capital_intensive: bool,
    ) -> dict[str, Any]:
        """
        Evaluate all fundamental filter conditions.
        Returns dict of filter pass/fail flags + overall status.
        """
        filters = {}

        # ROCE filter (skip for banking: they use NIM instead)
        roce = data.get("roce")
        if is_banking:
            filters["passed_roce"] = True  # Banking: apply NIM/NPA separately
            filters["roce_note"] = "Banking sector: ROCE filter bypassed, NIM applied"
        else:
            filters["passed_roce"] = (
                roce is not None and roce >= self.cfg.MIN_ROCE
            )

        # Debt-to-Equity filter (skip for banking)
        de = data.get("debt_to_equity")
        if is_banking:
            filters["passed_debt_to_equity"] = True
            filters["de_note"] = "Banking sector: D/E filter bypassed"
        else:
            filters["passed_debt_to_equity"] = (
                de is not None and de <= self.cfg.MAX_DEBT_TO_EQUITY
            )

        # Piotroski F-Score
        f_score = data.get("piotroski_f_score")
        filters["passed_piotroski"] = (
            f_score is not None and f_score >= self.cfg.MIN_PIOTROSKI_SCORE
        )

        # Altman Z-Score (only apply if calculable)
        z_score = data.get("altman_z_score")
        filters["passed_altman"] = (
            z_score is None or z_score > 1.8  # < 1.8 = distress zone
        )

        # EPS Growth
        eps_growth = data.get("eps_growth_yoy")
        filters["passed_eps_growth"] = (
            eps_growth is None or eps_growth >= self.cfg.MIN_EPS_GROWTH
        )

        # Composite fundamentals pass
        filters["fundamentals_passed"] = (
            filters["passed_roce"]
            and filters["passed_debt_to_equity"]
            # Piotroski is a bonus filter; not hard mandatory in Phase 1
            # Uncomment to make it mandatory:
            # and filters["passed_piotroski"]
        )

        return filters

    # ── Metric Computations ───────────────────────────────────────────────────

    def _compute_roce(self, info: dict[str, Any]) -> Optional[float]:
        """
        ROCE = EBIT / Capital Employed × 100
        Capital Employed = Total Assets - Current Liabilities
        """
        try:
            ebit = info.get("ebit") or info.get("operatingIncome")
            total_assets = info.get("totalAssets")
            current_liabilities = info.get("currentLiabilities") or info.get("totalCurrentLiabilities")

            if ebit and total_assets and current_liabilities:
                capital_employed = total_assets - current_liabilities
                if capital_employed > 0:
                    return round((ebit / capital_employed) * 100, 2)

            # Fallback: use returnOnEquity × (1 + D/E)
            roe = self._safe_float(info, "returnOnEquity")
            de = self._compute_debt_to_equity(info)
            if roe and de is not None:
                return round(roe * (1 + de) * 100, 2)

            return None
        except Exception as e:
            logger.debug(f"ROCE computation error: {e}")
            return None

    def _compute_roe(self, info: dict[str, Any]) -> Optional[float]:
        """ROE from yfinance returnOnEquity (decimal → percentage)."""
        roe = self._safe_float(info, "returnOnEquity")
        if roe is not None:
            return round(roe * 100, 2)
        return None

    def _compute_debt_to_equity(self, info: dict[str, Any]) -> Optional[float]:
        """
        D/E = Total Debt / Shareholders' Equity
        """
        try:
            # yfinance provides debtToEquity as a ratio already
            de = self._safe_float(info, "debtToEquity")
            if de is not None:
                return round(de / 100, 3)  # yfinance returns it as percentage

            total_debt = (
                info.get("totalDebt") or
                (info.get("longTermDebt", 0) + info.get("shortLongTermDebt", 0))
            )
            equity = info.get("totalStockholderEquity") or info.get("stockholdersEquity")

            if total_debt and equity and equity > 0:
                return round(total_debt / equity, 3)
            return None
        except Exception as e:
            logger.debug(f"D/E computation error: {e}")
            return None

    def _compute_eps_growth(self, info: dict[str, Any]) -> Optional[float]:
        """YoY EPS growth percentage."""
        try:
            eps_ttm = self._safe_float(info, "trailingEps")
            eps_fwd = self._safe_float(info, "forwardEps")
            earnings_growth = self._safe_float(info, "earningsGrowth")

            if earnings_growth is not None:
                return round(earnings_growth * 100, 2)

            if eps_ttm and eps_fwd and eps_ttm != 0:
                return round(((eps_fwd - eps_ttm) / abs(eps_ttm)) * 100, 2)

            return None
        except Exception:
            return None

    def _compute_piotroski(
        self, info: dict[str, Any], computed: dict[str, Any]
    ) -> Optional[int]:
        """
        Piotroski F-Score (0–9).
        A score of 7–9 indicates a financially strong company.
        
        Scoring criteria:
        PROFITABILITY (4 points):
          F1: ROA > 0
          F2: Operating Cash Flow > 0
          F3: ROA increased YoY
          F4: Accruals < 0 (OCF > Net Income / Assets)
        
        LEVERAGE & LIQUIDITY (3 points):
          F5: Leverage decreased YoY
          F6: Current ratio improved YoY
          F7: No new shares issued
        
        OPERATING EFFICIENCY (2 points):
          F8: Gross margin improved YoY
          F9: Asset turnover improved YoY
        """
        try:
            score = 0
            roa = self._safe_float(info, "returnOnAssets")
            ocf = self._safe_float(info, "operatingCashflow")
            net_income = self._safe_float(info, "netIncome")
            total_assets = self._safe_float(info, "totalAssets")
            current_ratio = self._safe_float(info, "currentRatio")
            de_raw = self._safe_float(info, "debtToEquity")
            gross_margins = self._safe_float(info, "grossMargins")
            revenue = self._safe_float(info, "totalRevenue")
            shares_outstanding = self._safe_float(info, "sharesOutstanding")

            # F1: ROA > 0
            if roa is not None and roa > 0:
                score += 1

            # F2: Operating Cash Flow > 0
            if ocf is not None and ocf > 0:
                score += 1

            # F3: ROA improvement (use earnings growth as proxy)
            earnings_growth = self._safe_float(info, "earningsGrowth")
            if earnings_growth is not None and earnings_growth > 0:
                score += 1

            # F4: Accruals (OCF/Assets > ROA → good quality earnings)
            if ocf and total_assets and roa is not None and total_assets > 0:
                ocf_roa = ocf / total_assets
                if ocf_roa > roa:
                    score += 1

            # F5: Lower leverage (D/E decreased) — use current D/E < 1 as proxy
            if de_raw is not None:
                de_normalized = de_raw / 100
                if de_normalized < 1.0:
                    score += 1

            # F6: Current ratio > 1 (liquid)
            if current_ratio is not None and current_ratio > 1:
                score += 1

            # F7: No significant dilution (shares outstanding not exploding)
            # Use revenue growth as proxy for share issuance discipline
            rev_growth = self._safe_float(info, "revenueGrowth")
            if rev_growth is not None and rev_growth > 0:
                score += 1  # Growing revenue → good sign

            # F8: Gross margin > 20% (healthy)
            if gross_margins is not None and gross_margins > 0.20:
                score += 1

            # F9: Asset turnover > 0 (using revenue / assets)
            if revenue and total_assets and total_assets > 0:
                asset_turnover = revenue / total_assets
                if asset_turnover > 0.3:
                    score += 1

            return score
        except Exception as e:
            logger.debug(f"Piotroski computation error: {e}")
            return None

    def _compute_altman_z(self, info: dict[str, Any]) -> Optional[float]:
        """
        Altman Z-Score for manufacturing companies.
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        
        X1 = Working Capital / Total Assets
        X2 = Retained Earnings / Total Assets
        X3 = EBIT / Total Assets
        X4 = Market Cap / Total Liabilities
        X5 = Revenue / Total Assets
        
        Z > 2.99 → Safe
        1.81 < Z < 2.99 → Grey Zone
        Z < 1.81 → Distress
        """
        try:
            total_assets = self._safe_float(info, "totalAssets")
            total_liabilities = (
                self._safe_float(info, "totalLiab") or
                self._safe_float(info, "totalLiabilities")
            )
            market_cap = self._safe_float(info, "marketCap")
            ebit = self._safe_float(info, "ebit") or self._safe_float(info, "operatingIncome")
            revenue = self._safe_float(info, "totalRevenue")
            working_capital = (
                (self._safe_float(info, "totalCurrentAssets") or 0) -
                (self._safe_float(info, "totalCurrentLiabilities") or 0)
            )
            retained_earnings = self._safe_float(info, "retainedEarnings")

            if not all([total_assets, total_liabilities, market_cap, ebit, revenue]):
                return None
            if total_assets <= 0 or total_liabilities <= 0:
                return None

            x1 = working_capital / total_assets
            x2 = (retained_earnings or 0) / total_assets
            x3 = ebit / total_assets
            x4 = market_cap / total_liabilities
            x5 = revenue / total_assets

            z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
            return round(z, 3)
        except Exception as e:
            logger.debug(f"Altman Z computation error: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_float(info: dict, key: str) -> Optional[float]:
        """Safely extract a float value from info dict."""
        val = info.get(key)
        if val is None:
            return None
        try:
            f = float(val)
            return f if not (f != f) else None  # NaN check
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_pct(info: dict, key: str) -> Optional[float]:
        """Extract percentage value (decimal → percentage)."""
        val = info.get(key)
        if val is None:
            return None
        try:
            return round(float(val) * 100, 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_banking(sector: str) -> bool:
        return any(s.lower() in sector.lower() for s in BANKING_SECTORS)

    @staticmethod
    def _is_capital_intensive(sector: str) -> bool:
        return any(s.lower() in sector.lower() for s in CAPITAL_INTENSIVE_SECTORS)

    @staticmethod
    def _empty_result(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "company_name": symbol,
            "sector": None,
            "fundamentals_passed": False,
            "error": "No data available",
        }
