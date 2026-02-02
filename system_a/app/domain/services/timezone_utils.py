"""
Timezone utility functions for handling timezone-aware date boundaries.

This module provides utilities for working with timezone-aware timestamps and
date boundaries when querying TimescaleDB continuous aggregates. It's critical
for ensuring that daily/monthly queries align with the user's local calendar.

Key Concepts:
- A "local date" (e.g., 2024-01-15 in Asia/Karachi) spans from 00:00:00 to
  23:59:59 in that timezone
- When stored in UTC, this becomes a range that may span two UTC dates
- Example: 2024-01-15 PKT = 2024-01-14 19:00:00 UTC to 2024-01-15 18:59:59 UTC

Usage:
    # Get date range for querying hourly buckets
    start, end = get_local_date_range("2024-01-15", "Asia/Karachi")

    # Check if timestamp is in peak hours
    is_peak = is_peak_hour(timestamp, peak_windows, "Asia/Karachi")

    # Convert UTC hour bucket to local time
    local_dt = utc_to_local(utc_timestamp, "Asia/Karachi")
"""
from datetime import datetime, date, time, timedelta
from typing import Tuple, List, Optional
import pytz


class TimezoneUtils:
    """Utilities for timezone-aware date and time operations."""

    @staticmethod
    def get_local_date_range(
        local_date: date | str,
        timezone_str: str
    ) -> Tuple[datetime, datetime]:
        """
        Get UTC datetime range for a complete local calendar day.

        Args:
            local_date: The local calendar date (e.g., "2024-01-15" or date object)
            timezone_str: Timezone name (e.g., "Asia/Karachi")

        Returns:
            Tuple of (start_utc, end_utc) representing the full local day in UTC

        Example:
            >>> start, end = get_local_date_range("2024-01-15", "Asia/Karachi")
            >>> # For PKT (UTC+5):
            >>> # start = 2024-01-14 19:00:00 UTC (2024-01-15 00:00:00 PKT)
            >>> # end   = 2024-01-15 18:59:59.999999 UTC (2024-01-15 23:59:59.999999 PKT)
        """
        # Parse date if string
        if isinstance(local_date, str):
            local_date = date.fromisoformat(local_date)

        # Get timezone
        tz = pytz.timezone(timezone_str)

        # Create local datetime for start of day (00:00:00)
        local_start = datetime.combine(local_date, time.min)
        local_start = tz.localize(local_start)

        # Create local datetime for end of day (23:59:59.999999)
        local_end = datetime.combine(local_date, time.max)
        local_end = tz.localize(local_end)

        # Convert to UTC
        start_utc = local_start.astimezone(pytz.UTC)
        end_utc = local_end.astimezone(pytz.UTC)

        return start_utc, end_utc

    @staticmethod
    def get_local_month_range(
        year: int,
        month: int,
        timezone_str: str
    ) -> Tuple[datetime, datetime]:
        """
        Get UTC datetime range for a complete local calendar month.

        Args:
            year: Year (e.g., 2024)
            month: Month number (1-12)
            timezone_str: Timezone name (e.g., "Asia/Karachi")

        Returns:
            Tuple of (start_utc, end_utc) representing the full local month in UTC

        Example:
            >>> start, end = get_local_month_range(2024, 1, "Asia/Karachi")
            >>> # January 2024 in PKT
            >>> # start = 2023-12-31 19:00:00 UTC (2024-01-01 00:00:00 PKT)
            >>> # end   = 2024-01-31 18:59:59.999999 UTC (2024-01-31 23:59:59.999999 PKT)
        """
        # Get first day of month
        first_day = date(year, month, 1)

        # Get last day of month
        if month == 12:
            last_day = date(year, 12, 31)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        # Get timezone
        tz = pytz.timezone(timezone_str)

        # Create local datetime for start of month
        local_start = datetime.combine(first_day, time.min)
        local_start = tz.localize(local_start)

        # Create local datetime for end of month
        local_end = datetime.combine(last_day, time.max)
        local_end = tz.localize(local_end)

        # Convert to UTC
        start_utc = local_start.astimezone(pytz.UTC)
        end_utc = local_end.astimezone(pytz.UTC)

        return start_utc, end_utc

    @staticmethod
    def utc_to_local(utc_dt: datetime, timezone_str: str) -> datetime:
        """
        Convert UTC datetime to local timezone.

        Args:
            utc_dt: UTC datetime (timezone-aware or naive assumed UTC)
            timezone_str: Target timezone name (e.g., "Asia/Karachi")

        Returns:
            Datetime in the target timezone

        Example:
            >>> utc = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
            >>> local = utc_to_local(utc, "Asia/Karachi")
            >>> # local = 2024-01-15 19:00:00 PKT
        """
        # Ensure UTC datetime is timezone-aware
        if utc_dt.tzinfo is None:
            utc_dt = pytz.UTC.localize(utc_dt)

        # Convert to target timezone
        tz = pytz.timezone(timezone_str)
        return utc_dt.astimezone(tz)

    @staticmethod
    def local_to_utc(local_dt: datetime, timezone_str: str) -> datetime:
        """
        Convert local datetime to UTC.

        Args:
            local_dt: Local datetime (naive, assumed to be in timezone_str)
            timezone_str: Source timezone name (e.g., "Asia/Karachi")

        Returns:
            Datetime in UTC

        Example:
            >>> local = datetime(2024, 1, 15, 19, 0, 0)
            >>> utc = local_to_utc(local, "Asia/Karachi")
            >>> # utc = 2024-01-15 14:00:00 UTC
        """
        # Localize to source timezone
        tz = pytz.timezone(timezone_str)
        if local_dt.tzinfo is None:
            local_dt = tz.localize(local_dt)

        # Convert to UTC
        return local_dt.astimezone(pytz.UTC)

    @staticmethod
    def get_hour_in_timezone(dt: datetime, timezone_str: str) -> int:
        """
        Extract hour (0-23) from datetime in specified timezone.

        Args:
            dt: Datetime (timezone-aware or naive assumed UTC)
            timezone_str: Target timezone name (e.g., "Asia/Karachi")

        Returns:
            Hour in the target timezone (0-23)

        Example:
            >>> utc = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
            >>> hour = get_hour_in_timezone(utc, "Asia/Karachi")
            >>> # hour = 19 (14:00 UTC = 19:00 PKT)
        """
        local_dt = TimezoneUtils.utc_to_local(dt, timezone_str)
        return local_dt.hour

    @staticmethod
    def is_peak_hour(
        dt: datetime,
        peak_windows: List[Tuple[int, int]],
        timezone_str: str
    ) -> bool:
        """
        Check if datetime falls within peak hours in the specified timezone.

        Args:
            dt: Datetime to check (timezone-aware or naive assumed UTC)
            peak_windows: List of (start_hour, end_hour) tuples for peak periods
            timezone_str: Timezone for TOU classification

        Returns:
            True if datetime is in peak hours, False otherwise

        Example:
            >>> utc = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
            >>> peak_windows = [(17, 22)]  # 5 PM to 10 PM
            >>> is_peak = is_peak_hour(utc, peak_windows, "Asia/Karachi")
            >>> # is_peak = True (14:00 UTC = 19:00 PKT, which is in 17-22 range)
        """
        hour = TimezoneUtils.get_hour_in_timezone(dt, timezone_str)

        for start_hour, end_hour in peak_windows:
            # Handle windows that don't wrap around midnight
            if start_hour < end_hour:
                if start_hour <= hour < end_hour:
                    return True
            # Handle windows that wrap around midnight (e.g., 22:00 to 02:00)
            else:
                if hour >= start_hour or hour < end_hour:
                    return True

        return False

    @staticmethod
    def validate_timezone(timezone_str: str) -> bool:
        """
        Validate that timezone string is recognized by pytz.

        Args:
            timezone_str: Timezone name to validate

        Returns:
            True if valid, False otherwise

        Example:
            >>> validate_timezone("Asia/Karachi")
            True
            >>> validate_timezone("Invalid/Timezone")
            False
        """
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False

    @staticmethod
    def get_timezone_offset_hours(timezone_str: str, dt: Optional[datetime] = None) -> float:
        """
        Get UTC offset in hours for a timezone at a specific datetime.

        This accounts for DST - the offset may change depending on the date.

        Args:
            timezone_str: Timezone name (e.g., "Asia/Karachi")
            dt: Datetime for which to get offset (defaults to now)

        Returns:
            UTC offset in hours (can be fractional)

        Example:
            >>> offset = get_timezone_offset_hours("Asia/Karachi")
            >>> # offset = 5.0 (PKT is UTC+5)
        """
        tz = pytz.timezone(timezone_str)
        if dt is None:
            dt = datetime.now(pytz.UTC)
        elif dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        # Get offset for the specific datetime
        localized = dt.astimezone(tz)
        offset = localized.utcoffset()
        return offset.total_seconds() / 3600

    @staticmethod
    def get_date_in_timezone(dt: datetime, timezone_str: str) -> date:
        """
        Get the calendar date in a specific timezone.

        Args:
            dt: Datetime (timezone-aware or naive assumed UTC)
            timezone_str: Target timezone name

        Returns:
            Date in the target timezone

        Example:
            >>> utc = datetime(2024, 1, 15, 23, 30, 0, tzinfo=pytz.UTC)
            >>> local_date = get_date_in_timezone(utc, "Asia/Karachi")
            >>> # local_date = date(2024, 1, 16)  # Next day in PKT
        """
        local_dt = TimezoneUtils.utc_to_local(dt, timezone_str)
        return local_dt.date()


# Convenience functions that delegate to TimezoneUtils
def get_local_date_range(local_date: date | str, timezone_str: str) -> Tuple[datetime, datetime]:
    """Get UTC datetime range for a complete local calendar day."""
    return TimezoneUtils.get_local_date_range(local_date, timezone_str)


def get_local_month_range(year: int, month: int, timezone_str: str) -> Tuple[datetime, datetime]:
    """Get UTC datetime range for a complete local calendar month."""
    return TimezoneUtils.get_local_month_range(year, month, timezone_str)


def utc_to_local(utc_dt: datetime, timezone_str: str) -> datetime:
    """Convert UTC datetime to local timezone."""
    return TimezoneUtils.utc_to_local(utc_dt, timezone_str)


def local_to_utc(local_dt: datetime, timezone_str: str) -> datetime:
    """Convert local datetime to UTC."""
    return TimezoneUtils.local_to_utc(local_dt, timezone_str)


def get_hour_in_timezone(dt: datetime, timezone_str: str) -> int:
    """Extract hour (0-23) from datetime in specified timezone."""
    return TimezoneUtils.get_hour_in_timezone(dt, timezone_str)


def is_peak_hour(dt: datetime, peak_windows: List[Tuple[int, int]], timezone_str: str) -> bool:
    """Check if datetime falls within peak hours in the specified timezone."""
    return TimezoneUtils.is_peak_hour(dt, peak_windows, timezone_str)
