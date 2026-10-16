"""
PaperTrade ORM Model
Tracks virtual/paper trades generated from screener signals.
Full lifecycle: OPEN → CLOSED (with reason).
"""
from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Float, Integer, Boolean, Text, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradeStatus(str, PyEnum):
    OPEN = "OPEN"
    CLOSED_TARGET = "CLOSED_TARGET"    # Exited at 12% profit target
    CLOSED_RSI = "CLOSED_RSI"          # Exited when RSI > 70
    CLOSED_SL = "CLOSED_SL"            # Stop loss hit
    CLOSED_MANUAL = "CLOSED_MANUAL"    # Manually closed
    CANCELLED = "CANCELLED"            # Never entered (e.g., gap up)


class TradeDirection(str, PyEnum):
    LONG = "LONG"
    SHORT = "SHORT"    # Reserved for future phases


class PaperTrade(Base):
    """
    Virtual paper trade record.
    Tracks entry, exit, P&L, and all trade metadata.
    """
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    direction: Mapped[str] = mapped_column(
        Enum(TradeDirection), default=TradeDirection.LONG, nullable=False
    )

    # ── Entry Details ─────────────────────────────────────────────────────────
    entry_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)   # YYYY-MM-DD
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price_gap_adj: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Actual fill price
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    invested_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Risk Parameters ───────────────────────────────────────────────────────
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)       # ATR-based SL
    stop_loss_fixed: Mapped[float] = mapped_column(Float, nullable=False) # Fixed 5% SL
    target_price: Mapped[float] = mapped_column(Float, nullable=False)    # 12% target
    atr_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Indicators at Entry ───────────────────────────────────────────────────
    rsi_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_200_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roce_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    piotroski_at_entry: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Current / Live Values ─────────────────────────────────────────────────
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)      # ₹
    unrealized_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # %
    highest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # All-time high since entry
    days_in_trade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Exit Details ──────────────────────────────────────────────────────────
    exit_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)        # ₹
    realized_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)    # %

    # ── Forward Validation Protocol v2.1 Metadata ────────────────────────────
    batch_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    experiment_arm: Mapped[Optional[str]] = mapped_column(String(30), default="TOOL_TOP10", nullable=True)
    regime_tag: Mapped[Optional[str]] = mapped_column(String(30), default="DEFENSIVE", nullable=True)
    nifty_entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nifty_exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    friction_cost: Mapped[Optional[float]] = mapped_column(Float, default=0.00385, nullable=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(TradeStatus), default=TradeStatus.OPEN, nullable=False, index=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_trade_status_date", "status", "entry_date"),
        Index("ix_trade_symbol_status", "symbol", "status"),
        Index("ix_trade_batch_arm", "batch_id", "experiment_arm"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperTrade #{self.id} {self.symbol} | "
            f"{self.status} | Entry ₹{self.entry_price:.2f}>"
        )

    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    @property
    def is_profitable(self) -> bool:
        pnl = self.realized_pnl or self.unrealized_pnl or 0
        return pnl > 0


class ForwardBatch(Base):
    """
    Cohort metadata record for empirical forward testing.
    Tracks primary unified metric (Tool vs 1,000 Random Baskets) and reproducibility parameters.
    """
    __tablename__ = "forward_batches"

    batch_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    cohort_type: Mapped[str] = mapped_column(String(20), default="PRIMARY", nullable=False) # 'PILOT' or 'PRIMARY'
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)        # 'ACTIVE' or 'COMPLETED'
    regime: Mapped[str] = mapped_column(String(20), default="DEFENSIVE", nullable=False)
    nifty_base_price: Mapped[float] = mapped_column(Float, nullable=False)
    scoring_git_hash: Mapped[str] = mapped_column(String(50), nullable=False)
    scoring_formula_version: Mapped[str] = mapped_column(String(50), nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_universe_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_stock_count: Mapped[int] = mapped_column(Integer, default=10)
    control_basket_count: Mapped[int] = mapped_column(Integer, default=1000)
    slot_capital_inr: Mapped[float] = mapped_column(Float, default=25000.0)
    total_allocated_inr: Mapped[float] = mapped_column(Float, default=250000.0)
    tool_avg_return_pct: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    control_mean_return_pct: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    delta_excess_return_pct: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    nifty_return_pct: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    spearman_rho: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    monte_carlo_percentile: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    completed_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)


class UniverseScoreSnapshot(Base):
    """
    Full universe score snapshot frozen on Cohort T=0.
    Enables offline rank correlation and 1,000 Monte Carlo bootstrap simulations.
    """
    __tablename__ = "universe_score_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_top10: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    day90_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    day90_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    day90_net_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
