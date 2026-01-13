"""
Time range and date range value objects.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..exceptions import ValidationException


class TimeGranularity(str, Enum):
    """Time granularity for aggregations."""
    MINUTE = "minute"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass(frozen=True)
class TimeRange:
    """
    Time range value object.

    Represents a period of time with start and end timestamps.
    """
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """Validate time range."""
        # Ensure timezone-aware datetimes
        if self.start.tzinfo is None:
            object.__setattr__(self, 'start', self.start.replace(tzinfo=timezone.utc))
        if self.end.tzinfo is None:
            object.__setattr__(self, 'end', self.end.replace(tzinfo=timezone.utc))

        if self.start > self.end:
            raise ValidationException(
                message="Invalid time range",
                errors={'time_range': ['Start time must be before or equal to end time']}
            )

    @property
    def duration(self) -> timedelta:
        """Return duration of the time range."""
        return self.end - self.start

    @property
    def duration_hours(self) -> float:
        """Return duration in hours."""
        return self.duration.total_seconds() / 3600

    @property
    def duration_days(self) -> float:
        """Return duration in days."""
        return self.duration.total_seconds() / 86400

    def contains(self, timestamp: datetime) -> bool:
        """Check if timestamp falls within this range."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return self.start <= timestamp <= self.end

    def overlaps(self, other: 'TimeRange') -> bool:
        """Check if this range overlaps with another."""
        return self.start <= other.end and self.end >= other.start

    def intersection(self, other: 'TimeRange') -> Optional['TimeRange']:
        """Return intersection with another range, or None if no overlap."""
        if not self.overlaps(other):
            return None
        return TimeRange(
            start=max(self.start, other.start),
            end=min(self.end, other.end)
        )

    def union(self, other: 'TimeRange') -> 'TimeRange':
        """Return union with another range (covers both ranges)."""
        return TimeRange(
            start=min(self.start, other.start),
            end=max(self.end, other.end)
        )

    def split_by_granularity(self, granularity: TimeGranularity) -> List['TimeRange']:
        """
        Split this range into smaller ranges based on granularity.

        Useful for aggregation queries.
        """
        intervals: List[TimeRange] = []
        current = self.start

        delta_map = {
            TimeGranularity.MINUTE: timedelta(minutes=1),
            TimeGranularity.FIVE_MINUTES: timedelta(minutes=5),
            TimeGranularity.FIFTEEN_MINUTES: timedelta(minutes=15),
            TimeGranularity.HOURLY: timedelta(hours=1),
            TimeGranularity.DAILY: timedelta(days=1),
            TimeGranularity.WEEKLY: timedelta(weeks=1),
        }

        if granularity in delta_map:
            delta = delta_map[granularity]
            while current < self.end:
                next_time = min(current + delta, self.end)
                intervals.append(TimeRange(start=current, end=next_time))
                current = next_time
        elif granularity == TimeGranularity.MONTHLY:
            while current < self.end:
                # Move to first day of next month
                if current.month == 12:
                    next_time = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    next_time = current.replace(month=current.month + 1, day=1)
                next_time = min(next_time, self.end)
                intervals.append(TimeRange(start=current, end=next_time))
                current = next_time
        elif granularity == TimeGranularity.YEARLY:
            while current < self.end:
                next_time = current.replace(year=current.year + 1, month=1, day=1)
                next_time = min(next_time, self.end)
                intervals.append(TimeRange(start=current, end=next_time))
                current = next_time

        return intervals

    def extend(self, before: Optional[timedelta] = None, after: Optional[timedelta] = None) -> 'TimeRange':
        """Return a new range extended by the given amounts."""
        new_start = self.start - before if before else self.start
        new_end = self.end + after if after else self.end
        return TimeRange(start=new_start, end=new_end)

    def __str__(self) -> str:
        return f"{self.start.isoformat()} to {self.end.isoformat()}"

    def __repr__(self) -> str:
        return f"TimeRange({self.start.isoformat()}, {self.end.isoformat()})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'duration_hours': self.duration_hours
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeRange':
        """Create from dictionary."""
        start = data.get('start')
        end = data.get('end')

        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        return cls(start=start, end=end)

    @classmethod
    def last_hours(cls, hours: int) -> 'TimeRange':
        """Create range for last N hours."""
        now = datetime.now(timezone.utc)
        return cls(start=now - timedelta(hours=hours), end=now)

    @classmethod
    def last_days(cls, days: int) -> 'TimeRange':
        """Create range for last N days."""
        now = datetime.now(timezone.utc)
        return cls(start=now - timedelta(days=days), end=now)

    @classmethod
    def today(cls, tz: Optional[timezone] = None) -> 'TimeRange':
        """Create range for today."""
        tz = tz or timezone.utc
        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return cls(start=start, end=end)

    @classmethod
    def this_month(cls, tz: Optional[timezone] = None) -> 'TimeRange':
        """Create range for current month."""
        tz = tz or timezone.utc
        now = datetime.now(tz)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            end = now.replace(month=now.month + 1, day=1)
        end = end - timedelta(microseconds=1)
        return cls(start=start, end=end)


@dataclass(frozen=True)
class DateRange:
    """
    Date range value object.

    Similar to TimeRange but operates on dates (no time component).
    """
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        """Validate date range."""
        if self.start_date > self.end_date:
            raise ValidationException(
                message="Invalid date range",
                errors={'date_range': ['Start date must be before or equal to end date']}
            )

    @property
    def days(self) -> int:
        """Return number of days in range (inclusive)."""
        return (self.end_date - self.start_date).days + 1

    def contains(self, d: date) -> bool:
        """Check if date falls within this range."""
        return self.start_date <= d <= self.end_date

    def overlaps(self, other: 'DateRange') -> bool:
        """Check if this range overlaps with another."""
        return self.start_date <= other.end_date and self.end_date >= other.start_date

    def iterate_days(self) -> Iterator[date]:
        """Iterate over all days in the range."""
        current = self.start_date
        while current <= self.end_date:
            yield current
            current += timedelta(days=1)

    def to_time_range(self, tz: Optional[timezone] = None) -> TimeRange:
        """Convert to TimeRange (full days)."""
        tz = tz or timezone.utc
        start = datetime.combine(self.start_date, time.min, tzinfo=tz)
        end = datetime.combine(self.end_date, time.max, tzinfo=tz)
        return TimeRange(start=start, end=end)

    def __str__(self) -> str:
        return f"{self.start_date.isoformat()} to {self.end_date.isoformat()}"

    def __repr__(self) -> str:
        return f"DateRange({self.start_date}, {self.end_date})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'days': self.days
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DateRange':
        """Create from dictionary."""
        start = data.get('start_date')
        end = data.get('end_date')

        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)

        return cls(start_date=start, end_date=end)

    @classmethod
    def last_days(cls, days: int) -> 'DateRange':
        """Create range for last N days."""
        today = date.today()
        return cls(start_date=today - timedelta(days=days - 1), end_date=today)

    @classmethod
    def this_month(cls) -> 'DateRange':
        """Create range for current month."""
        today = date.today()
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return cls(start_date=start, end_date=end)

    @classmethod
    def for_month(cls, year: int, month: int) -> 'DateRange':
        """Create range for a specific month."""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return cls(start_date=start, end_date=end)
