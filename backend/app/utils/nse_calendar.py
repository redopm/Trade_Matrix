"""
NSE Trading Calendar & Market Session Utilities (Protocol v2.1.1)
Accurate first-trading-day detection and Day-90 maturity date rolling.
"""
from datetime import date, timedelta
from typing import Set, Tuple, List

# NSE Equity Trading Holidays
# 2026: Official Exchange Master Schedule
# 2027: PROVISIONAL (Standard Exchange Projections; subject to final annual circular issued by NSE in Nov/Dec 2026)
NSE_EQUITY_HOLIDAYS_OFFICIAL_2026: Set[str] = {
    "2026-01-26",  # Republic Day
    "2026-02-17",  # Mahashivratri
    "2026-03-03",  # Holi
    "2026-03-27",  # Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. B.R. Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id / Eid-ul-Adha
    "2026-06-26",  # Muharram
    "2026-08-15",  # Independence Day (Saturday)
    "2026-09-04",  # Milad-un-Nabi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-09",  # Diwali Balipratipada
    "2026-11-24",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
}

NSE_EQUITY_HOLIDAYS_PROVISIONAL_2027: Set[str] = {
    "2027-01-26",  # Republic Day (Provisional)
    "2027-03-08",  # Mahashivratri (Provisional)
    "2027-03-22",  # Holi (Provisional)
    "2027-03-26",  # Good Friday (Provisional)
    "2027-04-14",  # Dr. Ambedkar Jayanti (Provisional)
    "2027-05-01",  # Maharashtra Day (Saturday, Provisional)
    "2027-05-17",  # Bakri Id (Provisional)
    "2027-06-16",  # Muharram (Provisional)
    "2027-08-15",  # Independence Day (Sunday, Provisional)
    "2027-10-02",  # Gandhi Jayanti (Saturday, Provisional)
    "2027-10-11",  # Dussehra (Provisional)
    "2027-10-29",  # Diwali Balipratipada (Provisional)
    "2027-11-14",  # Guru Nanak Jayanti (Sunday, Provisional)
    "2027-12-25",  # Christmas (Saturday, Provisional)
}

NSE_EQUITY_HOLIDAYS: Set[str] = NSE_EQUITY_HOLIDAYS_OFFICIAL_2026.union(NSE_EQUITY_HOLIDAYS_PROVISIONAL_2027)


class NSETradingCalendar:
    """Trading calendar calculations strictly aligned with NSE holiday rules."""

    @staticmethod
    def is_trading_day(d: date) -> bool:
        """Returns True if date is Monday-Friday and not an official NSE holiday."""
        if d.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        return d.isoformat() not in NSE_EQUITY_HOLIDAYS

    @classmethod
    def get_first_trading_day_of_month(cls, year: int, month: int) -> date:
        """
        Determines the exact first active NSE trading session of a given month.
        Example:
        - 2026-11: 1 Nov is Sunday -> 2 Nov is Monday (Trading Day)
        - 2027-05: 1 May is Sat (Maharashtra Day), 2 May is Sun -> 3 May is Monday
        """
        curr = date(year, month, 1)
        while not cls.is_trading_day(curr):
            curr += timedelta(days=1)
        return curr

    @classmethod
    def get_day_90_exit_date(cls, entry_date: date) -> date:
        """
        Calculates the official Day-90 exit date.
        If Day-90 falls on a Saturday, Sunday, or exchange holiday, rolls forward
        to the next active trading session.
        """
        target = entry_date + timedelta(days=90)
        while not cls.is_trading_day(target):
            target += timedelta(days=1)
        return target

    @classmethod
    def get_all_protocol_cohort_dates(cls) -> List[Tuple[int, date, date]]:
        """
        Returns all 9 pre-registered primary cohort dates (Cohort 1 through Cohort 9)
        from Nov 2026 through Jul 2027, along with their respective Day-90 exit dates.
        """
        cohort_months = [
            (1, 2026, 11),
            (2, 2026, 12),
            (3, 2027, 1),
            (4, 2027, 2),
            (5, 2027, 3),
            (6, 2027, 4),
            (7, 2027, 5),
            (8, 2027, 6),
            (9, 2027, 7),
        ]
        res = []
        for c_num, y, m in cohort_months:
            entry_d = cls.get_first_trading_day_of_month(y, m)
            exit_d = cls.get_day_90_exit_date(entry_d)
            res.append((c_num, entry_d, exit_d))
        return res
