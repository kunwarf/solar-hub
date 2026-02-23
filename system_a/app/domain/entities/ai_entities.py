"""
Domain entities for the AI Intelligence layer.

GridOutage               – a detected grid outage event
AIInsightsLog            – a persisted AI insight generation result
AIPromptTemplate         – an admin-editable Claude prompt template
AIPromptTemplateVersion  – one version snapshot of a template
OutagePrediction         – a predicted load-shedding window (transient, not persisted)
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# GridOutage
# ---------------------------------------------------------------------------

@dataclass
class GridOutage:
    """
    A detected grid outage for a site.

    Created by OutageDetectionService when it sees grid_power_w transition
    from positive/negative → 0 in telemetry.  The row is *updated* (ended_at
    + duration_minutes filled in) when the grid comes back.
    """
    site_id: UUID
    started_at: datetime
    day_of_week: int            # 0=Mon … 6=Sun  (PKT)
    week_of_year: int
    month_pkt: int              # 1–12
    started_hour_pkt: int       # 0–23

    id: UUID = field(default_factory=uuid4)
    ended_at: Optional[datetime] = None
    ended_hour_pkt: Optional[int] = None
    duration_minutes: Optional[int] = None
    detected_by_serial: Optional[str] = None
    was_predicted: bool = False
    created_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """True while the outage has no end time (still ongoing)."""
        return self.ended_at is None

    def close(self, ended_at: datetime) -> None:
        """Mark the outage as finished and compute duration."""
        self.ended_at = ended_at
        # PKT = UTC+5
        from datetime import timezone, timedelta
        _PKT = timezone(timedelta(hours=5))
        ended_pkt = ended_at.astimezone(_PKT)
        self.ended_hour_pkt = ended_pkt.hour
        delta = ended_at - self.started_at
        self.duration_minutes = int(delta.total_seconds() / 60)


# ---------------------------------------------------------------------------
# AIInsightsLog
# ---------------------------------------------------------------------------

@dataclass
class AIInsightsLog:
    """
    Persisted record of one AI insight generation.

    Used for:
    - Historical browsing of AI output
    - Feeding prior anomalies as context to monthly/yearly Claude calls
    - Auditing what data was sent and what was returned
    """
    site_id: UUID
    tier: str                   # 'hourly' | 'monthly' | 'yearly'
    model: str                  # claude model id or 'rule-based'
    period_start: datetime
    input_stats: Dict[str, Any]

    id: UUID = field(default_factory=uuid4)
    period_end: Optional[datetime] = None
    billing_month: Optional[date] = None

    daily_insights: List[Dict[str, Any]] = field(default_factory=list)
    anomaly_alerts: List[Dict[str, Any]] = field(default_factory=list)
    monthly_analysis: Optional[Dict[str, Any]] = None   # monthly tier only
    yearly_analysis: Optional[Dict[str, Any]] = None    # yearly  tier only

    cache_key: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# AIPromptTemplate
# ---------------------------------------------------------------------------

@dataclass
class AIPromptTemplate:
    """
    An admin-editable prompt template for a Claude call.

    Key naming convention:  '<tier>_<type>'
      e.g. 'hourly_system', 'hourly_user',
           'monthly_system', 'monthly_user',
           'yearly_system',  'yearly_user'

    The `template` field uses Python str.format_map() placeholders.
    The `variables` field is a list of dicts describing each placeholder
    so the admin UI can display a reference panel.
    """
    key: str
    tier: str           # hourly | monthly | yearly
    prompt_type: str    # system | user
    name: str
    template: str
    variables: List[Dict[str, Any]]

    id: UUID = field(default_factory=uuid4)
    description: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    version: int = 1
    is_active: bool = True
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def render(self, variables: Dict[str, Any]) -> str:
        """
        Render the template by substituting variables.

        Unknown placeholders are left as-is (safe substitution) so a
        partially configured template does not crash the service.
        """
        return _SafeFormatMap(self.template).format(**variables)

    def bump_version(self, updated_by: Optional[UUID] = None) -> None:
        """Increment version number and update audit fields."""
        self.version += 1
        self.updated_by = updated_by
        self.updated_at = datetime.utcnow()


class _SafeFormatMap(str):
    """
    str subclass whose .format() leaves unknown {keys} intact instead of raising KeyError.
    """
    def __new__(cls, s: str) -> "_SafeFormatMap":
        return super().__new__(cls, s)

    def format(self, **kwargs: Any) -> str:
        class _Default(dict):
            def __missing__(self, key: str) -> str:
                return "{" + key + "}"
        return self.__str__().format_map(_Default(kwargs))


# ---------------------------------------------------------------------------
# AIPromptTemplateVersion
# ---------------------------------------------------------------------------

@dataclass
class AIPromptTemplateVersion:
    """
    Immutable snapshot of a prompt template at a specific version.

    Written whenever an admin saves a template edit.
    """
    template_id: UUID
    version: int
    template: str
    variables: List[Dict[str, Any]]

    id: UUID = field(default_factory=uuid4)
    changed_by: Optional[UUID] = None
    change_note: Optional[str] = None
    changed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# OutagePrediction  (transient — not persisted)
# ---------------------------------------------------------------------------

@dataclass
class OutagePrediction:
    """
    A predicted load-shedding window for today, derived from outage history.

    Confidence levels:
      'high'    → occurrence rate > 75%
      'moderate' → 50%–75%
    """
    start_hour_pkt: int     # 0–23
    end_hour_pkt: int       # 0–23
    confidence: str         # 'high' | 'moderate'
    occurrence_rate: float  # 0.0–1.0
    sample_count: int       # total observations for this slot
    hit_count: int          # times the slot had an outage


@dataclass
class OutagePredictionResult:
    """Full prediction result for a site + day."""
    site_id: UUID
    day_of_week: int
    history_days: int           # how many days of history were analysed
    predictions: List[OutagePrediction]
    current_outage_active: bool
    current_outage_started_at: Optional[datetime]
    this_month_total_hours: float
    this_month_covered_pct: float   # % of outage hours the battery covered
    last_outage_started_at: Optional[datetime]
    last_outage_duration_min: Optional[int]
