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

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(TradeStatus), default=TradeStatus.OPEN, nullable=False, index=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_trade_status_date", "status", "entry_date"),
        Index("ix_trade_symbol_status", "symbol", "status"),
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
