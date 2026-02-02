"""
Unit tests for timezone utility functions.

Tests cover:
- Date range conversions (local to UTC)
- Month range conversions
- UTC to local conversions
- Hour extraction in different timezones
- Peak hour detection
- DST handling
- Edge cases (midnight boundaries, month boundaries)
"""
import pytest
from datetime import datetime, date, time, timedelta
import pytz

from app.domain.services.timezone_utils import (
    TimezoneUtils,
    get_local_date_range,
    get_local_month_range,
    utc_to_local,
    local_to_utc,
    get_hour_in_timezone,
    is_peak_hour,
)


class TestGetLocalDateRange:
    """Test get_local_date_range function."""

    def test_basic_date_range_pkt(self):
        """Test basic date range for Pakistan timezone."""
        # PKT is UTC+5
        start_utc, end_utc = get_local_date_range("2024-01-15", "Asia/Karachi")

        # 2024-01-15 00:00:00 PKT = 2024-01-14 19:00:00 UTC
        expected_start = datetime(2024, 1, 14, 19, 0, 0, tzinfo=pytz.UTC)
        # 2024-01-15 23:59:59.999999 PKT = 2024-01-15 18:59:59.999999 UTC
        expected_end = datetime(2024, 1, 15, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_date_range_with_date_object(self):
        """Test date range with date object instead of string."""
        local_date = date(2024, 1, 15)
        start_utc, end_utc = get_local_date_range(local_date, "Asia/Karachi")

        expected_start = datetime(2024, 1, 14, 19, 0, 0, tzinfo=pytz.UTC)
        assert start_utc == expected_start

    def test_date_range_utc_timezone(self):
        """Test date range for UTC timezone (should have no offset)."""
        start_utc, end_utc = get_local_date_range("2024-01-15", "UTC")

        expected_start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2024, 1, 15, 23, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_date_range_negative_offset(self):
        """Test date range for timezone with negative offset (EST)."""
        # EST is UTC-5
        start_utc, end_utc = get_local_date_range("2024-01-15", "America/New_York")

        # 2024-01-15 00:00:00 EST = 2024-01-15 05:00:00 UTC
        expected_start = datetime(2024, 1, 15, 5, 0, 0, tzinfo=pytz.UTC)
        # 2024-01-15 23:59:59.999999 EST = 2024-01-16 04:59:59.999999 UTC
        expected_end = datetime(2024, 1, 16, 4, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_date_range_spans_utc_days(self):
        """Verify that local date range can span two UTC dates."""
        start_utc, end_utc = get_local_date_range("2024-01-15", "Asia/Karachi")

        # Start should be on Jan 14 UTC, end should be on Jan 15 UTC
        assert start_utc.date() == date(2024, 1, 14)
        assert end_utc.date() == date(2024, 1, 15)


class TestGetLocalMonthRange:
    """Test get_local_month_range function."""

    def test_basic_month_range_pkt(self):
        """Test basic month range for Pakistan timezone."""
        start_utc, end_utc = get_local_month_range(2024, 1, "Asia/Karachi")

        # 2024-01-01 00:00:00 PKT = 2023-12-31 19:00:00 UTC
        expected_start = datetime(2023, 12, 31, 19, 0, 0, tzinfo=pytz.UTC)
        # 2024-01-31 23:59:59.999999 PKT = 2024-01-31 18:59:59.999999 UTC
        expected_end = datetime(2024, 1, 31, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_month_range_december(self):
        """Test month range for December (edge case)."""
        start_utc, end_utc = get_local_month_range(2024, 12, "Asia/Karachi")

        # 2024-12-01 00:00:00 PKT
        expected_start = datetime(2024, 11, 30, 19, 0, 0, tzinfo=pytz.UTC)
        # 2024-12-31 23:59:59.999999 PKT
        expected_end = datetime(2024, 12, 31, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_month_range_february_non_leap(self):
        """Test month range for February in non-leap year."""
        start_utc, end_utc = get_local_month_range(2023, 2, "Asia/Karachi")

        # February 2023 has 28 days
        expected_start = datetime(2023, 1, 31, 19, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2023, 2, 28, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_month_range_february_leap(self):
        """Test month range for February in leap year."""
        start_utc, end_utc = get_local_month_range(2024, 2, "Asia/Karachi")

        # February 2024 has 29 days (leap year)
        expected_start = datetime(2024, 1, 31, 19, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2024, 2, 29, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end


class TestUTCToLocal:
    """Test utc_to_local function."""

    def test_basic_utc_to_local_pkt(self):
        """Test basic UTC to local conversion for PKT."""
        utc_dt = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        local_dt = utc_to_local(utc_dt, "Asia/Karachi")

        # 14:00 UTC = 19:00 PKT (UTC+5)
        assert local_dt.hour == 19
        assert local_dt.day == 15

    def test_utc_to_local_crosses_day_boundary(self):
        """Test UTC to local conversion that crosses day boundary."""
        utc_dt = datetime(2024, 1, 15, 23, 30, 0, tzinfo=pytz.UTC)
        local_dt = utc_to_local(utc_dt, "Asia/Karachi")

        # 23:30 UTC = 04:30 PKT next day
        assert local_dt.hour == 4
        assert local_dt.minute == 30
        assert local_dt.day == 16  # Next day

    def test_utc_to_local_naive_datetime(self):
        """Test UTC to local with naive datetime (assumes UTC)."""
        utc_dt = datetime(2024, 1, 15, 14, 0, 0)  # Naive
        local_dt = utc_to_local(utc_dt, "Asia/Karachi")

        assert local_dt.hour == 19


class TestLocalToUTC:
    """Test local_to_utc function."""

    def test_basic_local_to_utc_pkt(self):
        """Test basic local to UTC conversion for PKT."""
        local_dt = datetime(2024, 1, 15, 19, 0, 0)  # Naive, PKT
        utc_dt = local_to_utc(local_dt, "Asia/Karachi")

        # 19:00 PKT = 14:00 UTC
        assert utc_dt.hour == 14
        assert utc_dt.day == 15
        assert utc_dt.tzinfo == pytz.UTC

    def test_local_to_utc_crosses_day_boundary_backwards(self):
        """Test local to UTC conversion that crosses day boundary backwards."""
        local_dt = datetime(2024, 1, 15, 2, 0, 0)  # 02:00 PKT
        utc_dt = local_to_utc(local_dt, "Asia/Karachi")

        # 02:00 PKT = 21:00 UTC previous day
        assert utc_dt.hour == 21
        assert utc_dt.day == 14  # Previous day


class TestGetHourInTimezone:
    """Test get_hour_in_timezone function."""

    def test_basic_hour_extraction(self):
        """Test basic hour extraction in PKT."""
        utc_dt = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        hour = get_hour_in_timezone(utc_dt, "Asia/Karachi")

        # 14:00 UTC = 19:00 PKT
        assert hour == 19

    def test_hour_extraction_multiple_timezones(self):
        """Test hour extraction for same UTC time in different timezones."""
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)

        pkt_hour = get_hour_in_timezone(utc_dt, "Asia/Karachi")  # UTC+5
        est_hour = get_hour_in_timezone(utc_dt, "America/New_York")  # UTC-5
        utc_hour = get_hour_in_timezone(utc_dt, "UTC")  # UTC+0

        assert pkt_hour == 17  # 12:00 + 5 = 17:00
        assert est_hour == 7   # 12:00 - 5 = 07:00
        assert utc_hour == 12

    def test_hour_extraction_naive_datetime(self):
        """Test hour extraction with naive datetime (assumes UTC)."""
        utc_dt = datetime(2024, 1, 15, 14, 0, 0)  # Naive
        hour = get_hour_in_timezone(utc_dt, "Asia/Karachi")

        assert hour == 19


class TestIsPeakHour:
    """Test is_peak_hour function."""

    def test_within_single_peak_window(self):
        """Test datetime within a single peak window."""
        # 19:00 PKT (14:00 UTC)
        utc_dt = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        peak_windows = [(17, 22)]  # 5 PM to 10 PM

        assert is_peak_hour(utc_dt, peak_windows, "Asia/Karachi") is True

    def test_outside_peak_window(self):
        """Test datetime outside peak window."""
        # 13:00 PKT (08:00 UTC)
        utc_dt = datetime(2024, 1, 15, 8, 0, 0, tzinfo=pytz.UTC)
        peak_windows = [(17, 22)]

        assert is_peak_hour(utc_dt, peak_windows, "Asia/Karachi") is False

    def test_at_peak_window_start(self):
        """Test datetime exactly at peak window start (inclusive)."""
        # 17:00 PKT (12:00 UTC)
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        peak_windows = [(17, 22)]

        assert is_peak_hour(utc_dt, peak_windows, "Asia/Karachi") is True

    def test_at_peak_window_end(self):
        """Test datetime exactly at peak window end (exclusive)."""
        # 22:00 PKT (17:00 UTC)
        utc_dt = datetime(2024, 1, 15, 17, 0, 0, tzinfo=pytz.UTC)
        peak_windows = [(17, 22)]

        # End hour is exclusive
        assert is_peak_hour(utc_dt, peak_windows, "Asia/Karachi") is False

    def test_multiple_peak_windows(self):
        """Test with multiple peak windows."""
        peak_windows = [(6, 9), (17, 22)]  # Morning and evening peaks

        # 07:00 PKT (02:00 UTC) - morning peak
        utc_dt_morning = datetime(2024, 1, 15, 2, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_morning, peak_windows, "Asia/Karachi") is True

        # 19:00 PKT (14:00 UTC) - evening peak
        utc_dt_evening = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_evening, peak_windows, "Asia/Karachi") is True

        # 12:00 PKT (07:00 UTC) - off-peak
        utc_dt_offpeak = datetime(2024, 1, 15, 7, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_offpeak, peak_windows, "Asia/Karachi") is False

    def test_peak_window_wrapping_midnight(self):
        """Test peak window that wraps around midnight."""
        # Window from 22:00 to 02:00 (spans midnight)
        peak_windows = [(22, 2)]

        # 23:00 PKT (18:00 UTC) - in peak
        utc_dt_before_midnight = datetime(2024, 1, 15, 18, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_before_midnight, peak_windows, "Asia/Karachi") is True

        # 01:00 PKT (20:00 UTC previous day) - in peak
        utc_dt_after_midnight = datetime(2024, 1, 14, 20, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_after_midnight, peak_windows, "Asia/Karachi") is True

        # 12:00 PKT (07:00 UTC) - off-peak
        utc_dt_offpeak = datetime(2024, 1, 15, 7, 0, 0, tzinfo=pytz.UTC)
        assert is_peak_hour(utc_dt_offpeak, peak_windows, "Asia/Karachi") is False


class TestTimezoneValidation:
    """Test timezone validation functions."""

    def test_validate_valid_timezone(self):
        """Test validation of valid timezone."""
        assert TimezoneUtils.validate_timezone("Asia/Karachi") is True
        assert TimezoneUtils.validate_timezone("America/New_York") is True
        assert TimezoneUtils.validate_timezone("UTC") is True

    def test_validate_invalid_timezone(self):
        """Test validation of invalid timezone."""
        assert TimezoneUtils.validate_timezone("Invalid/Timezone") is False
        assert TimezoneUtils.validate_timezone("Not_A_Timezone") is False


class TestTimezoneOffset:
    """Test timezone offset calculation."""

    def test_offset_pkt(self):
        """Test offset for Pakistan timezone."""
        offset = TimezoneUtils.get_timezone_offset_hours("Asia/Karachi")
        assert offset == 5.0  # PKT is UTC+5

    def test_offset_est(self):
        """Test offset for Eastern timezone."""
        # Note: Offset depends on DST, so we test with specific date
        dt = datetime(2024, 1, 15, tzinfo=pytz.UTC)  # January (EST, not EDT)
        offset = TimezoneUtils.get_timezone_offset_hours("America/New_York", dt)
        assert offset == -5.0  # EST is UTC-5

    def test_offset_utc(self):
        """Test offset for UTC."""
        offset = TimezoneUtils.get_timezone_offset_hours("UTC")
        assert offset == 0.0


class TestGetDateInTimezone:
    """Test get_date_in_timezone function."""

    def test_date_same_day(self):
        """Test date extraction when local date matches UTC date."""
        utc_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        local_date = TimezoneUtils.get_date_in_timezone(utc_dt, "Asia/Karachi")

        # 12:00 UTC = 17:00 PKT, same day
        assert local_date == date(2024, 1, 15)

    def test_date_next_day(self):
        """Test date extraction when local date is next day."""
        utc_dt = datetime(2024, 1, 15, 23, 0, 0, tzinfo=pytz.UTC)
        local_date = TimezoneUtils.get_date_in_timezone(utc_dt, "Asia/Karachi")

        # 23:00 UTC = 04:00 PKT next day
        assert local_date == date(2024, 1, 16)

    def test_date_previous_day(self):
        """Test date extraction when local date is previous day."""
        utc_dt = datetime(2024, 1, 15, 2, 0, 0, tzinfo=pytz.UTC)
        local_date = TimezoneUtils.get_date_in_timezone(utc_dt, "America/New_York")

        # 02:00 UTC = 21:00 EST previous day (in January)
        assert local_date == date(2024, 1, 14)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_month_boundary(self):
        """Test date range at month boundary."""
        # Last day of January
        start_utc, end_utc = get_local_date_range("2024-01-31", "Asia/Karachi")

        expected_start = datetime(2024, 1, 30, 19, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2024, 1, 31, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_year_boundary(self):
        """Test date range at year boundary."""
        # Last day of year
        start_utc, end_utc = get_local_date_range("2024-12-31", "Asia/Karachi")

        expected_start = datetime(2024, 12, 30, 19, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2024, 12, 31, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_leap_year_feb_29(self):
        """Test date range for Feb 29 in leap year."""
        start_utc, end_utc = get_local_date_range("2024-02-29", "Asia/Karachi")

        expected_start = datetime(2024, 2, 28, 19, 0, 0, tzinfo=pytz.UTC)
        expected_end = datetime(2024, 2, 29, 18, 59, 59, 999999, tzinfo=pytz.UTC)

        assert start_utc == expected_start
        assert end_utc == expected_end

    def test_timezone_with_half_hour_offset(self):
        """Test timezone with half-hour offset (e.g., India)."""
        # IST is UTC+5:30
        offset = TimezoneUtils.get_timezone_offset_hours("Asia/Kolkata")
        assert offset == 5.5

    def test_timezone_with_quarter_hour_offset(self):
        """Test timezone with quarter-hour offset (e.g., Nepal)."""
        # NPT is UTC+5:45
        offset = TimezoneUtils.get_timezone_offset_hours("Asia/Kathmandu")
        assert offset == 5.75


class TestDSTHandling:
    """Test Daylight Saving Time handling."""

    def test_dst_transition_spring(self):
        """Test DST transition in spring (clock forward)."""
        # In 2024, EDT begins March 10 at 2:00 AM
        before_dst = datetime(2024, 3, 9, 12, 0, 0, tzinfo=pytz.UTC)
        after_dst = datetime(2024, 3, 11, 12, 0, 0, tzinfo=pytz.UTC)

        offset_before = TimezoneUtils.get_timezone_offset_hours("America/New_York", before_dst)
        offset_after = TimezoneUtils.get_timezone_offset_hours("America/New_York", after_dst)

        # Before: EST (UTC-5), After: EDT (UTC-4)
        assert offset_before == -5.0
        assert offset_after == -4.0

    def test_dst_transition_fall(self):
        """Test DST transition in fall (clock backward)."""
        # In 2024, EDT ends November 3 at 2:00 AM
        during_dst = datetime(2024, 11, 2, 12, 0, 0, tzinfo=pytz.UTC)
        after_dst = datetime(2024, 11, 4, 12, 0, 0, tzinfo=pytz.UTC)

        offset_during = TimezoneUtils.get_timezone_offset_hours("America/New_York", during_dst)
        offset_after = TimezoneUtils.get_timezone_offset_hours("America/New_York", after_dst)

        # During: EDT (UTC-4), After: EST (UTC-5)
        assert offset_during == -4.0
        assert offset_after == -5.0

    def test_dst_date_range(self):
        """Test date range calculation during DST transition."""
        # Test a date during DST in New York
        start_utc, end_utc = get_local_date_range("2024-07-15", "America/New_York")

        # During EDT (UTC-4):
        # 2024-07-15 00:00:00 EDT = 2024-07-15 04:00:00 UTC
        expected_start = datetime(2024, 7, 15, 4, 0, 0, tzinfo=pytz.UTC)

        assert start_utc == expected_start
