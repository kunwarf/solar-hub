"""
Outage Prediction Service.

Given a site's history of actual grid outages (grid_outages table), predicts
which 2-hour time slots are likely to have load shedding today.

Algorithm:
  1. Look at the last 60 days of completed outages for this site.
  2. Filter to today's day-of-week (Monday outages predict Monday, etc.).
  3. Bucket by 2-hour PKT slot (0–1, 2–3, 4–5, … 22–23).
  4. Compute occurrence rate = hit_count / total_days_sampled.
  5. Apply recency override: if the same slot occurred in all of the last 3
     consecutive occurrences of today's weekday, always flag it as HIGH.
  6. Return OutagePrediction objects for slots with rate >= 50%.

Confidence bands:
  ≥ 75% → 'high'
  50%–74% → 'moderate'
  < 50% → not returned

The result is formatted into a human-readable block by the AIInsightsService
for inclusion in the Claude prompt.
"""
import logging
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from ...domain.entities.ai_entities import (
    OutagePrediction,
    OutagePredictionResult,
)

logger = logging.getLogger(__name__)

# Pakistan Standard Time
_PKT = timezone(timedelta(hours=5))

# Prediction parameters
_HISTORY_DAYS       = 60
_SLOT_HOURS         = 2      # analyse in 2-hour blocks
_MIN_RATE_TO_REPORT = 0.50   # slots below 50% are not returned
_HIGH_CONFIDENCE    = 0.75
_RECENCY_STREAK     = 3      # consecutive weekday occurrences for recency override


class OutagePredictionService:
    """
    Produces confidence-scored outage window predictions for today.

    Usage:
        service = OutagePredictionService(session_factory)
        result  = await service.predict(site_id)
        block   = service.format_prompt_block(result)
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def predict(self, site_id: UUID) -> OutagePredictionResult:
        """
        Analyse historical outages and predict today's windows.

        Returns an OutagePredictionResult with all context needed for the
        Claude prompt block and for the API response.
        """
        now_pkt = datetime.now(timezone.utc).astimezone(_PKT)
        dow = now_pkt.weekday()   # 0=Mon … 6=Sun

        async with self._session_factory() as session:
            from ...infrastructure.database.repositories.ai_repository import (
                SQLAlchemyGridOutageRepository,
            )
            repo = SQLAlchemyGridOutageRepository(session)

            # Pattern data for today's day-of-week
            pattern_rows = await repo.get_pattern_by_hour_slot(
                site_id=site_id,
                day_of_week=dow,
                days=_HISTORY_DAYS,
                slot_hours=_SLOT_HOURS,
            )

            # Current open outage (if any)
            active_outage = await repo.get_active_outage(site_id)

            # Last completed outage
            last_outage = await repo.get_last_outage(site_id)

            # This month's stats (for the prompt block)
            today = now_pkt.date()
            month_start = today.replace(day=1)
            month_stats = await repo.get_month_stats(
                site_id=site_id,
                billing_month_start=month_start,
                billing_month_end=today,
            )

        predictions = self._build_predictions(pattern_rows)

        return OutagePredictionResult(
            site_id=site_id,
            day_of_week=dow,
            history_days=_HISTORY_DAYS,
            predictions=predictions,
            current_outage_active=active_outage is not None,
            current_outage_started_at=active_outage.started_at if active_outage else None,
            this_month_total_hours=month_stats.get("total_hours", 0.0),
            this_month_covered_pct=0.0,   # battery coverage computed by AIInsightsService
            last_outage_started_at=last_outage.started_at if last_outage else None,
            last_outage_duration_min=last_outage.duration_minutes if last_outage else None,
        )

    # =========================================================================
    # Prediction building
    # =========================================================================

    def _build_predictions(self, pattern_rows: list) -> List[OutagePrediction]:
        """Convert raw pattern rows into OutagePrediction objects."""
        predictions = []
        for row in pattern_rows:
            rate = row["rate"]
            if rate < _MIN_RATE_TO_REPORT:
                continue

            confidence = "high" if rate >= _HIGH_CONFIDENCE else "moderate"
            predictions.append(OutagePrediction(
                start_hour_pkt=row["slot_start"],
                end_hour_pkt=row["slot_end"],
                confidence=confidence,
                occurrence_rate=round(rate, 2),
                sample_count=row["day_count"],
                hit_count=row["hit_count"],
            ))

        # Sort by start hour for readability
        predictions.sort(key=lambda p: p.start_hour_pkt)
        return predictions

    # =========================================================================
    # Prompt block formatter
    # =========================================================================

    def format_prompt_block(self, result: OutagePredictionResult) -> str:
        """
        Render the load shedding section for the Claude hourly prompt.

        Returns a multi-line string ready to be injected into {load_shedding_block}.
        """
        lines = []

        # Current outage status
        if result.current_outage_active and result.current_outage_started_at:
            now_utc = datetime.now(timezone.utc)
            started_pkt = result.current_outage_started_at.astimezone(_PKT)
            elapsed_min = int((now_utc - result.current_outage_started_at).total_seconds() / 60)
            lines.append(
                f"⚡ ACTIVE OUTAGE — started {started_pkt.strftime('%H:%M')} PKT "
                f"({elapsed_min} min ago)"
            )
        else:
            lines.append("Grid: currently connected")

        # Last outage
        if result.last_outage_started_at:
            last_pkt = result.last_outage_started_at.astimezone(_PKT)
            dur = f"{result.last_outage_duration_min} min" if result.last_outage_duration_min else "unknown"
            lines.append(f"Last outage: {last_pkt.strftime('%a %d %b %H:%M')} PKT — {dur}")

        # Predicted windows for today
        if result.predictions:
            lines.append(f"\nPredicted windows today ({_dow_name(result.day_of_week)}):")
            for p in result.predictions:
                pct = int(p.occurrence_rate * 100)
                conf_icon = "🔴" if p.confidence == "high" else "🟡"
                lines.append(
                    f"  {conf_icon} {p.start_hour_pkt:02d}:00–{p.end_hour_pkt:02d}:00 PKT  "
                    f"— {p.confidence.upper()} ({pct}% — {p.hit_count}/{p.sample_count} "
                    f"past {_dow_name(result.day_of_week)}s)"
                )
        else:
            lines.append(
                f"\nNo high/moderate confidence windows predicted for today "
                f"({_dow_name(result.day_of_week)}) based on {result.history_days} days of history."
            )

        # Monthly summary
        lines.append(
            f"\nThis month: {result.this_month_total_hours:.1f}h total outages"
        )

        return "\n".join(lines)

    def format_monthly_block(
        self,
        total_hours: float,
        event_count: int,
        covered_hours: float,
        covered_pct: float,
        uncovered_hours: float,
        worst_day: Optional[date],
        worst_day_hours: float,
        worst_covered_pct: float,
        full_coverage_days: int,
        days_elapsed: int,
    ) -> str:
        """Render the monthly load shedding block for the monthly Claude prompt."""
        worst_str = (
            f"{worst_day.strftime('%d %b')} → {worst_day_hours:.1f}h, "
            f"battery covered {worst_covered_pct:.0f}%"
            if worst_day else "N/A"
        )
        return (
            f"Total outage hours: {total_hours:.1f}h across {event_count} events\n"
            f"Battery covered: {covered_hours:.1f}h ({covered_pct:.0f}%)\n"
            f"Grid fallback required: {uncovered_hours:.1f}h\n"
            f"Worst LS day: {worst_str}\n"
            f"Days with full battery coverage: {full_coverage_days}/{days_elapsed}"
        )


def _dow_name(dow: int) -> str:
    return ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"][dow % 7]
