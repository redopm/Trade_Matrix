"""
Paper Trading Engine
Handles the full lifecycle of paper trades:
  - Trade entry (from screener signals)
  - Daily P&L updates
  - Exit logic: RSI > 70, 12% target, ATR-based SL
  - Position sizing
  - Portfolio statistics
"""
from datetime import date, datetime, timedelta
from typing import Optional, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.trade import PaperTrade, TradeStatus, TradeDirection
from app.models.signal import ScreenerSignal
from app.services.data_fetcher import DataFetcher
from app.services.technical import TechnicalAnalyzer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PaperTradingEngine:
    """
    Paper trading engine that simulates trade execution and tracking.
    
    Features:
    - Position sizing based on configured capital %
    - ATR-based dynamic stop loss (better than fixed %)
    - Dual exit conditions: RSI overbought + fixed target
    - Daily P&L updates for all open trades
    - Portfolio-level statistics
    """

    def __init__(self) -> None:
        self.fetcher = DataFetcher()
        self.technical = TechnicalAnalyzer()
        self.cfg = settings

    async def enter_trade(
        self,
        db: AsyncSession,
        signal: ScreenerSignal,
        capital: float = None,
        notes: str = None,
    ) -> PaperTrade:
        """
        Create a new paper trade from a screener signal.
        
        Entry price = signal_price (next day market open simulation)
        Position size = configured_capital × position_size_pct
        """
        capital = capital or self.cfg.DEFAULT_CAPITAL
        position_value = capital * self.cfg.DEFAULT_POSITION_SIZE_PCT

        entry_price = signal.signal_price
        quantity = max(1, int(position_value / entry_price))
        invested_amount = quantity * entry_price

        # Determine SL — use ATR-based if available, fall back to fixed
        atr_sl = signal.suggested_sl
        fixed_sl = entry_price * (1 - self.cfg.FIXED_SL_PCT)
        effective_sl = max(atr_sl, fixed_sl) if atr_sl else fixed_sl

        target = entry_price * (1 + self.cfg.TARGET_PROFIT_PCT)

        risk = entry_price - effective_sl
        reward = target - entry_price
        rr_ratio = round(reward / risk, 2) if risk > 0 else None

        trade = PaperTrade(
            signal_id=signal.id,
            symbol=signal.symbol,
            company_name=signal.company_name,
            sector=signal.sector,
            direction=TradeDirection.LONG,
            entry_date=date.today().strftime("%Y-%m-%d"),
            entry_price=entry_price,
            quantity=quantity,
            invested_amount=invested_amount,
            stop_loss=round(effective_sl, 2),
            stop_loss_fixed=round(fixed_sl, 2),
            target_price=round(target, 2),
            atr_at_entry=signal.atr_14,
            risk_reward_ratio=rr_ratio,
            rsi_at_entry=signal.rsi_14,
            ema_200_at_entry=signal.ema_200,
            roce_at_entry=signal.roce,
            piotroski_at_entry=signal.piotroski_f_score,
            current_price=entry_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            highest_price=entry_price,
            days_in_trade=0,
            status=TradeStatus.OPEN,
            notes=notes,
        )

        db.add(trade)
        await db.flush()

        # Mark signal as traded
        signal.is_traded = True
        signal.trade_id = trade.id

        await db.commit()

        logger.info(
            f"Trade ENTERED: {trade.symbol} | "
            f"Qty: {quantity} @ ₹{entry_price:.2f} | "
            f"SL: ₹{effective_sl:.2f} | Target: ₹{target:.2f} | "
            f"R:R = {rr_ratio}"
        )
        return trade

    async def update_open_trades(self, db: AsyncSession) -> dict[str, Any]:
        """
        Update all open trades with current prices and check exit conditions.
        Called daily at market open (or on-demand).
        
        Returns summary of updates performed.
        """
        stmt = select(PaperTrade).where(PaperTrade.status == TradeStatus.OPEN)
        result = await db.execute(stmt)
        open_trades = result.scalars().all()

        summary = {
            "updated": 0,
            "sl_hits": 0,
            "target_hits": 0,
            "rsi_exits": 0,
            "errors": 0,
        }

        for trade in open_trades:
            try:
                await self._update_single_trade(db, trade, summary)
            except Exception as e:
                logger.error(f"Failed to update trade {trade.id} ({trade.symbol}): {e}")
                summary["errors"] += 1

        await db.commit()
        logger.info(f"Trade update complete: {summary}")
        return summary

    async def _update_single_trade(
        self,
        db: AsyncSession,
        trade: PaperTrade,
        summary: dict,
    ) -> None:
        """Update a single trade with current market data and check exits."""
        symbol = trade.symbol

        # Fetch current price and technical data
        current_price = await self.fetcher.fetch_current_price(symbol)
        if current_price is None or current_price <= 0:
            logger.warning(f"Could not fetch price for {symbol}")
            return

        # Update price tracking
        trade.current_price = current_price
        trade.highest_price = max(trade.highest_price or 0, current_price)

        # Calculate P&L
        pnl = (current_price - trade.entry_price) * trade.quantity
        pnl_pct = ((current_price / trade.entry_price) - 1) * 100
        trade.unrealized_pnl = round(pnl, 2)
        trade.unrealized_pnl_pct = round(pnl_pct, 2)

        # Days in trade
        try:
            entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%d").date()
            trade.days_in_trade = (date.today() - entry_dt).days
        except Exception:
            pass

        # ── Exit Condition 1: Stop Loss Hit ───────────────────────────────────
        if current_price <= trade.stop_loss:
            await self._close_trade(
                db, trade, current_price, TradeStatus.CLOSED_SL, "Stop loss hit"
            )
            summary["sl_hits"] += 1
            logger.info(f"SL HIT: {symbol} @ ₹{current_price:.2f} (SL: ₹{trade.stop_loss:.2f})")
            return

        # ── Exit Condition 2: Target Price Hit ────────────────────────────────
        if current_price >= trade.target_price:
            await self._close_trade(
                db, trade, current_price, TradeStatus.CLOSED_TARGET, "Target reached (12%)"
            )
            summary["target_hits"] += 1
            logger.info(f"TARGET HIT: {symbol} @ ₹{current_price:.2f}")
            return

        # ── Exit Condition 3: RSI > 70 (Overbought) ──────────────────────────
        # Fetch price history to compute RSI
        df = await self.fetcher.fetch_price_history(symbol, period="3mo")
        if df is not None and not df.empty:
            tech = self.technical.analyze(symbol, df)
            current_rsi = tech.get("rsi")
            trade.current_rsi = current_rsi

            if current_rsi and current_rsi >= self.cfg.TARGET_RSI_OVERBOUGHT:
                await self._close_trade(
                    db, trade, current_price, TradeStatus.CLOSED_RSI,
                    f"RSI overbought ({current_rsi:.1f} > {self.cfg.TARGET_RSI_OVERBOUGHT})"
                )
                summary["rsi_exits"] += 1
                logger.info(f"RSI EXIT: {symbol} RSI={current_rsi:.1f} @ ₹{current_price:.2f}")
                return

        summary["updated"] += 1

    async def _close_trade(
        self,
        db: AsyncSession,
        trade: PaperTrade,
        exit_price: float,
        status: TradeStatus,
        reason: str,
    ) -> None:
        """Close a trade and compute realized P&L."""
        trade.exit_date = date.today().strftime("%Y-%m-%d")
        trade.exit_price = round(exit_price, 2)
        trade.exit_reason = reason
        trade.status = status

        realized_pnl = (exit_price - trade.entry_price) * trade.quantity
        realized_pnl_pct = ((exit_price / trade.entry_price) - 1) * 100

        trade.realized_pnl = round(realized_pnl, 2)
        trade.realized_pnl_pct = round(realized_pnl_pct, 2)
        trade.unrealized_pnl = None
        trade.unrealized_pnl_pct = None

    async def get_portfolio_stats(self, db: AsyncSession) -> dict[str, Any]:
        """
        Compute portfolio-level statistics across all paper trades.
        """
        stmt = select(PaperTrade)
        result = await db.execute(stmt)
        all_trades = result.scalars().all()

        if not all_trades:
            return self._empty_stats()

        open_trades = [t for t in all_trades if t.is_open]
        closed_trades = [t for t in all_trades if not t.is_open]
        winning_trades = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
        losing_trades = [t for t in closed_trades if (t.realized_pnl or 0) <= 0]

        total_invested = sum(t.invested_amount for t in open_trades)
        unrealized_pnl = sum(t.unrealized_pnl or 0 for t in open_trades)
        realized_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
        total_pnl = realized_pnl + unrealized_pnl

        win_rate = (
            round(len(winning_trades) / len(closed_trades) * 100, 1)
            if closed_trades
            else 0.0
        )

        avg_win = (
            round(
                sum(t.realized_pnl_pct or 0 for t in winning_trades)
                / len(winning_trades),
                2,
            )
            if winning_trades
            else 0.0
        )
        avg_loss = (
            round(
                sum(t.realized_pnl_pct or 0 for t in losing_trades)
                / len(losing_trades),
                2,
            )
            if losing_trades
            else 0.0
        )

        expectancy = (
            round((win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 2)
            if closed_trades
            else 0.0
        )

        # Profit Factor
        gross_profit = sum(t.realized_pnl or 0 for t in winning_trades)
        gross_loss = abs(sum(t.realized_pnl or 0 for t in losing_trades))
        profit_factor = (
            round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        )

        return {
            "total_trades": len(all_trades),
            "open_trades": len(open_trades),
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "total_invested": round(total_invested, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(
                (total_pnl / self.cfg.DEFAULT_CAPITAL) * 100, 2
            ) if self.cfg.DEFAULT_CAPITAL > 0 else 0.0,
            "exit_reasons": {
                "sl_hits": sum(1 for t in closed_trades if t.status == TradeStatus.CLOSED_SL),
                "targets": sum(1 for t in closed_trades if t.status == TradeStatus.CLOSED_TARGET),
                "rsi_exits": sum(1 for t in closed_trades if t.status == TradeStatus.CLOSED_RSI),
                "manual": sum(1 for t in closed_trades if t.status == TradeStatus.CLOSED_MANUAL),
            },
        }

    @staticmethod
    def _empty_stats() -> dict[str, Any]:
        return {
            "total_trades": 0,
            "open_trades": 0,
            "closed_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "total_return_pct": 0.0,
        }

    async def close_trade_manual(
        self,
        db: AsyncSession,
        trade_id: int,
        exit_price: Optional[float] = None,
        notes: str = None,
    ) -> Optional[PaperTrade]:
        """Manually close a trade at current price."""
        stmt = select(PaperTrade).where(
            and_(PaperTrade.id == trade_id, PaperTrade.status == TradeStatus.OPEN)
        )
        result = await db.execute(stmt)
        trade = result.scalar_one_or_none()

        if not trade:
            return None

        if not exit_price:
            exit_price = await self.fetcher.fetch_current_price(trade.symbol)
        if not exit_price:
            exit_price = trade.current_price or trade.entry_price

        await self._close_trade(
            db, trade, exit_price, TradeStatus.CLOSED_MANUAL,
            f"Manually closed. Notes: {notes or 'N/A'}"
        )
        if notes:
            trade.notes = notes

        await db.commit()
        logger.info(f"Trade {trade_id} ({trade.symbol}) manually closed @ ₹{exit_price:.2f}")
        return trade
