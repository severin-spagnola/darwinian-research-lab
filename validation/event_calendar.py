# validation/event_calendar.py
"""
Market event calendar for regime tagging.
Identifies FOMC meetings, major earnings, and significant market events.
"""

from datetime import datetime
from typing import Set

# Major market events 2023-2024 (FOMC, significant announcements, volatility events)
MARKET_EVENTS = {
    # 2023 FOMC meetings
    "2023-02-01": "FOMC Meeting",
    "2023-03-22": "FOMC Meeting",
    "2023-05-03": "FOMC Meeting",
    "2023-06-14": "FOMC Meeting",
    "2023-07-26": "FOMC Meeting",
    "2023-09-20": "FOMC Meeting",
    "2023-11-01": "FOMC Meeting",
    "2023-12-13": "FOMC Meeting",

    # 2024 FOMC meetings
    "2024-01-31": "FOMC Meeting",
    "2024-03-20": "FOMC Meeting",
    "2024-05-01": "FOMC Meeting",
    "2024-06-12": "FOMC Meeting",
    "2024-07-31": "FOMC Meeting",
    "2024-09-18": "FOMC Meeting",
    "2024-11-07": "FOMC Meeting",
    "2024-12-18": "FOMC Meeting",

    # Other significant events
    "2023-03-10": "Silicon Valley Bank Collapse",
    "2023-05-25": "Debt Ceiling Crisis",
    "2023-08-25": "Jackson Hole Symposium",
    "2024-01-10": "CPI Surprise",
    "2024-08-23": "Jackson Hole Symposium",
}

# Major tech earnings dates (approximate - typically after-hours)
EARNINGS_EVENTS = {
    # TSLA earnings (quarterly)
    "2023-01-25": "TSLA Earnings",
    "2023-04-19": "TSLA Earnings",
    "2023-07-19": "TSLA Earnings",
    "2023-10-18": "TSLA Earnings",
    "2024-01-24": "TSLA Earnings",
    "2024-04-23": "TSLA Earnings",
    "2024-07-23": "TSLA Earnings",

    # NVDA earnings (quarterly)
    "2023-02-22": "NVDA Earnings",
    "2023-05-24": "NVDA Earnings",
    "2023-08-23": "NVDA Earnings",
    "2023-11-21": "NVDA Earnings",
    "2024-02-21": "NVDA Earnings",
    "2024-05-22": "NVDA Earnings",
    "2024-08-28": "NVDA Earnings",

    # AAPL earnings (quarterly)
    "2023-02-02": "AAPL Earnings",
    "2023-05-04": "AAPL Earnings",
    "2023-08-03": "AAPL Earnings",
    "2023-11-02": "AAPL Earnings",
    "2024-02-01": "AAPL Earnings",
    "2024-05-02": "AAPL Earnings",
    "2024-08-01": "AAPL Earnings",
}

# Combine all events
ALL_EVENTS = {**MARKET_EVENTS, **EARNINGS_EVENTS}


def is_event_day(date: datetime) -> bool:
    """Check if a given date is a known market event day."""
    date_str = date.strftime("%Y-%m-%d")
    return date_str in ALL_EVENTS


def get_event_description(date: datetime) -> str:
    """Get the description of an event on a given date."""
    date_str = date.strftime("%Y-%m-%d")
    return ALL_EVENTS.get(date_str, "")


def get_event_dates(start_date: datetime, end_date: datetime) -> Set[str]:
    """Get all event dates within a date range."""
    event_dates = set()
    for date_str in ALL_EVENTS.keys():
        event_date = datetime.strptime(date_str, "%Y-%m-%d")
        if start_date <= event_date <= end_date:
            event_dates.add(date_str)
    return event_dates


def add_event_tag(existing_tags: list, date: datetime) -> list:
    """
    Add 'event_day' tag to existing regime tags if date is an event day.

    Args:
        existing_tags: List of existing regime tags (e.g., ['trending', 'high_volatility'])
        date: Date to check

    Returns:
        Updated tag list with 'event_day' added if applicable
    """
    tags = existing_tags.copy()
    if is_event_day(date):
        tags.append("event_day")
    return tags
