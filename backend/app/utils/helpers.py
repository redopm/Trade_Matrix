"""
Common utility functions for TradeMatrix backend.
"""
from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated API response."""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate(
    items: list,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Paginate a list of items."""
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def format_inr(amount: float) -> str:
    """Format a number as Indian Rupees."""
    if amount is None:
        return "N/A"
    if abs(amount) >= 1e7:
        return f"₹{amount / 1e7:.2f} Cr"
    if abs(amount) >= 1e5:
        return f"₹{amount / 1e5:.2f} L"
    return f"₹{amount:,.2f}"


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safe division returning None instead of ZeroDivisionError."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def pct_change(old: Optional[float], new: Optional[float]) -> Optional[float]:
    """Calculate percentage change."""
    if old is None or new is None or old == 0:
        return None
    return round(((new - old) / abs(old)) * 100, 2)
