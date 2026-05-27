"""
StockUniverse ORM Model
Stores the master list of NSE stocks with cached fundamental data.
"""
from typing import Optional
from sqlalchemy import String, Float, Integer, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockUniverse(Base):
    """
    Master list of stocks in the screener universe.
    Fundamental data is cached here and refreshed weekly.
    """
    __tablename__ = "stock_universe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Fundamental Data (cached) ─────────────────────────────────────────────
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Valuation
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peg_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Profitability
    roce: Mapped[Optional[float]] = mapped_column(Float, nullable=True)          # Return on Capital Employed %
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)           # Return on Equity %
    roa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)           # Return on Assets %
    operating_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_profit_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Financial Health
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quick_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Growth
    eps_growth_yoy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # YoY EPS growth %
    revenue_growth_yoy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Shareholding
    promoter_holding: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fii_holding: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dii_holding: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Quant Scores
    piotroski_f_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0–9
    altman_z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Sector-specific (Banking)
    nim: Mapped[Optional[float]] = mapped_column(Float, nullable=True)    # Net Interest Margin %
    npa_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # NPA %

    # Metadata
    data_source: Mapped[str] = mapped_column(String(50), default="yfinance", nullable=False)
    fundamentals_refreshed_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Raw JSON for additional fields
    raw_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_stock_sector", "sector"),
        Index("ix_stock_roce", "roce"),
        Index("ix_stock_de", "debt_to_equity"),
    )

    def __repr__(self) -> str:
        return f"<StockUniverse {self.symbol} | {self.company_name}>"

    @property
    def is_banking_sector(self) -> bool:
        """Returns True if stock belongs to banking/NBFC sector."""
        if not self.sector:
            return False
        banking_keywords = {"bank", "financial", "nbfc", "insurance", "finance"}
        return any(kw in self.sector.lower() for kw in banking_keywords)
