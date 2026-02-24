"""
AI Insights Service — Three-Tier Architecture.

Tier 1 – Hourly (default: claude-haiku-4-5-20251001, admin-configurable):
    Triggered on login / page reload, then re-fetched every clock hour.
    Cache TTL: 60 minutes.  Redis key: insights:hourly:{site_id}
    Data: live telemetry + battery kWh today + system alerts + LS prediction.
    Produces: daily_insights + anomaly_alerts.

Tier 2 – Monthly (default: claude-sonnet-4-6, admin-configurable):
    Called once per calendar day.
    Cache TTL: 24 hours.  Redis key: insights:monthly:{site_id}:{billing_date}
    Data: 30-day System B energy chart + billing data + outage history.
    Produces: monthly_analysis block.

Tier 3 – Yearly (default: claude-sonnet-4-6, admin-configurable):
    Called once per billing month (on first load after billing month rolls over).
    Cache TTL: 30 days.  Redis key: insights:yearly:{site_id}:{year}:{month}
    Data: 365-day System B energy chart + year-to-date billing + outage YTD.
    Produces: yearly_analysis block.

Every Claude call result is persisted to the ai_insights_log table for
historical trend analysis and to seed future Claude prompts with context.

Prompt templates are loaded from DB (Redis-cached 5 min) with a hardcoded
fallback, so admins can edit them at /admin/ai-prompts without a deploy.

Rule-based fallback is used when Claude is unavailable or disabled.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ...config import settings
from ...infrastructure.cache.telemetry_cache import TelemetryCacheReader
from ...infrastructure.external.system_b_client import SystemBClient, SystemBClientError

logger = logging.getLogger(__name__)

# Pakistan Standard Time
_PKT = timezone(timedelta(hours=5))

# Redis cache TTLs
_TTL_HOURLY_S         = 3600   # 1 hour  (devices online)
_TTL_HOURLY_OFFLINE_S = 300    # 5 min   (any device offline — refreshes fast on reconnect)
_TTL_MONTHLY_S        = 86400  # 24 hours
_TTL_YEARLY_S         = 2592000  # 30 days

# Default models per tier — overridden at runtime via PromptTemplateLoader
_TIER_MODEL_DEFAULTS: Dict[str, str] = {
    "hourly":  "claude-haiku-4-5-20251001",
    "monthly": "claude-sonnet-4-6",
    "yearly":  "claude-sonnet-4-6",
}

# Pakistan seasonal solar generation window (start_hour, end_hour) in PKT
# Used to calculate EV charging window and hours remaining
_PAKISTAN_SOLAR_WINDOW: Dict[int, tuple] = {
    1: (8, 17),  2: (8, 17),  # Jan-Feb: 8am–5pm
    3: (7, 18),  4: (7, 18),  # Mar-Apr: 7am–6pm
    5: (6, 19),  6: (6, 19),  # May-Jun: 6am–7pm
    7: (6, 19),  8: (6, 18),  # Jul-Aug: 6am–7/6pm (monsoon clouds but long days)
    9: (7, 18),  10: (7, 17), # Sep-Oct: 7am–6/5pm
    11: (8, 17), 12: (8, 17), # Nov-Dec: 8am–5pm
}

# Thresholds
INVERTER_TEMP_WARN_C = 75.0
INVERTER_TEMP_HIGH_C = 90.0
CO2_KG_PER_KWH       = 0.7
DEFAULT_PKR_RATE      = 35.0

WEEKLY_TIPS = [
    "Run dishwasher and laundry during peak solar hours (11 AM – 3 PM) to maximize savings.",
    "Pre-cool your home before 4 PM to reduce AC load during expensive evening rates.",
    "Check panel cleanliness monthly — dust reduces efficiency by up to 15% in Pakistan's dry climate.",
    "Set battery minimum reserve to 20% to extend battery lifespan significantly.",
    "Your DISCO net metering export rate earns you credit — export excess during peak solar hours.",
    "Use a timer on your water heater to heat water during midday solar surplus.",
    "Ceiling fans use 10× less power than AC — combine both on mild days to cut cooling costs.",
]


# =============================================================================
# Response types (unchanged from previous version — frontend compatibility)
# =============================================================================

@dataclass
class InsightData:
    """A single insight item."""
    id: str
    type: str
    category: str
    title: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WeeklyDigestData:
    """Weekly energy digest for the AIInsightsWidget."""
    total_generated_kwh: float
    total_saved_pkr: float
    self_sufficiency_pct: float
    prev_week_generated_kwh: float
    prev_week_saved_pkr: float
    prev_week_self_sufficiency_pct: float
    generated_change_pct: float
    saved_change_pct: float
    self_sufficiency_change_pct: float
    tip_of_the_week: str


@dataclass
class InsightsResponse:
    """Full insights payload returned to the API endpoint."""
    daily_insights: List[InsightData]
    anomaly_alerts: List[InsightData]
    weekly_digest: Optional[WeeklyDigestData]
    generated_at: datetime
    monthly_analysis: Optional[Dict] = None   # structured dict from Claude tool
    yearly_analysis:  Optional[Dict] = None   # structured dict from Claude tool
    source: str = "rule_based"   # "claude" | "cache" | "rule_based"


# =============================================================================
# Claude tool schemas
# =============================================================================

_HOURLY_TOOL = {
    "name": "return_insights",
    "description": (
        "Return structured hourly insights and anomaly alerts for the solar site. "
        "Always call this tool."
    ),
    "input_schema": {
        "type": "object",
        "required": ["daily_insights", "anomaly_alerts"],
        "properties": {
            "daily_insights": {
                "type": "array",
                "description": "2–4 daily insights covering generation, savings, load shedding, EV, and self-sufficiency.",
                "items": {
                    "type": "object",
                    "required": ["id", "type", "category", "title", "message"],
                    "properties": {
                        "id":       {"type": "string"},
                        "type":     {"type": "string", "enum": ["positive", "neutral", "warning", "tip"]},
                        "category": {"type": "string", "enum": ["production", "savings", "consumption", "anomaly", "recommendation", "load_shedding", "ev_charging"]},
                        "title":    {"type": "string", "maxLength": 60},
                        "message":  {"type": "string", "maxLength": 200},
                        "metadata": {"type": "object"},
                    },
                },
            },
            "anomaly_alerts": {
                "type": "array",
                "description": "0–3 anomaly alerts. Only real problems, not routine observations.",
                "items": {
                    "type": "object",
                    "required": ["id", "type", "category", "title", "message"],
                    "properties": {
                        "id":       {"type": "string"},
                        "type":     {"type": "string", "enum": ["positive", "neutral", "warning", "tip"]},
                        "category": {"type": "string", "enum": ["production", "savings", "consumption", "anomaly", "recommendation", "load_shedding", "ev_charging"]},
                        "title":    {"type": "string", "maxLength": 60},
                        "message":  {"type": "string", "maxLength": 200},
                        "metadata": {"type": "object"},
                    },
                },
            },
        },
    },
}

_MONTHLY_TOOL = {
    "name": "return_monthly_analysis",
    "description": "Return a concise structured monthly energy analysis. Always call this tool.",
    "input_schema": {
        "type": "object",
        "required": ["summary", "highlights", "recommendations"],
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-sentence executive summary of this billing month. Max 50 words.",
                "maxLength": 300,
            },
            "highlights": {
                "type": "array",
                "description": "Exactly 3 highlights (wins or issues). Each ≤ 15 words. No filler.",
                "items": {"type": "string", "maxLength": 100},
                "maxItems": 3,
            },
            "recommendations": {
                "type": "array",
                "description": "Exactly 2 actionable recommendations for next month. Each ≤ 15 words.",
                "items": {"type": "string", "maxLength": 100},
                "maxItems": 2,
            },
            "load_shedding_insight": {
                "type": "string",
                "description": "1 sentence on battery coverage of load shedding this month. Max 20 words.",
                "maxLength": 150,
            },
        },
    },
}

_YEARLY_TOOL = {
    "name": "return_yearly_analysis",
    "description": "Return a concise year-to-date energy analysis. Always call this tool.",
    "input_schema": {
        "type": "object",
        "required": ["summary", "best_month", "worst_month", "trends", "recommendations"],
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-sentence year-to-date executive summary. Max 50 words.",
                "maxLength": 300,
            },
            "best_month":  {
                "type": "string",
                "description": "Best performing month and why. Max 15 words.",
                "maxLength": 100,
            },
            "worst_month": {
                "type": "string",
                "description": "Worst performing month and why. Max 15 words.",
                "maxLength": 100,
            },
            "trends": {
                "type": "array",
                "description": "Exactly 3 year-to-date trends. Each ≤ 15 words.",
                "items": {"type": "string", "maxLength": 100},
                "maxItems": 3,
            },
            "recommendations": {
                "type": "array",
                "description": "Exactly 2 strategic recommendations for the coming year. Each ≤ 15 words.",
                "items": {"type": "string", "maxLength": 100},
                "maxItems": 2,
            },
            "roi_insight": {
                "type": "string",
                "description": "ROI payback estimate in 1 sentence. Max 20 words.",
                "maxLength": 150,
            },
        },
    },
}


# =============================================================================
# Main service
# =============================================================================

class AIInsightsService:
    """
    Three-tier AI insights service.

    Each tier independently checks Redis for a cached response and only calls
    Claude when the cache is empty.  Results are persisted to ai_insights_log.

    Constructor arguments:
        telemetry_cache:  TelemetryCacheReader
        system_b_client:  SystemBClient
        session_factory:  async_sessionmaker[AsyncSession]  (for DB writes)
    """

    def __init__(
        self,
        telemetry_cache: TelemetryCacheReader,
        system_b_client: SystemBClient,
        session_factory=None,
    ):
        self._cache = telemetry_cache
        self._system_b = system_b_client
        self._session_factory = session_factory
        self._claude: Any = None
        self._prompt_loader = None
        self._init_claude()

    def _init_claude(self) -> None:
        api_key = settings.ai.api_key
        if not api_key:
            logger.debug("AI_API_KEY not set — using rule-based insights.")
            return
        try:
            import anthropic
            self._claude = anthropic.AsyncAnthropic(api_key=api_key)
            logger.info("Claude AI client initialised.")
        except ImportError:
            logger.warning("anthropic package not installed. Run: pip install anthropic>=0.40.0")

    def _solar_window(self, now_pkt: datetime) -> tuple:
        """Return (start_hour, end_hour) for the good solar generation window in PKT."""
        return _PAKISTAN_SOLAR_WINDOW.get(now_pkt.month, (7, 18))

    def _get_prompt_loader(self):
        if self._prompt_loader is None:
            from .prompt_template_loader import PromptTemplateLoader
            if self._session_factory:
                self._prompt_loader = PromptTemplateLoader(self._session_factory)
        return self._prompt_loader

    async def _resolve_model(self, tier: str) -> str:
        """Resolve the Claude model for a tier via loader, falling back to defaults."""
        loader = self._get_prompt_loader()
        if loader:
            try:
                return await loader.get_model_for_tier(tier)
            except Exception as exc:
                logger.debug("[insights] Could not resolve model for tier=%s: %s", tier, exc)
        return _TIER_MODEL_DEFAULTS.get(tier, "claude-sonnet-4-6")

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_insights(
        self,
        site_id: UUID,
        device_serials: List[str],
        import_rate_pkr: float = DEFAULT_PKR_RATE,
        billing_month_start: Optional[date] = None,
    ) -> InsightsResponse:
        """
        Generate / retrieve insights for a site (all three tiers).

        The hourly tier is always refreshed on-demand (cache checked internally).
        Monthly and yearly tiers are also cache-checked here; they are included
        in the response when available.
        """
        now     = datetime.now(timezone.utc)
        now_pkt = now.astimezone(_PKT)

        logger.info(
            "[insights] site=%s devices=%s rate=%.1f",
            site_id, device_serials, import_rate_pkr,
        )

        # --- Tier 1: Hourly (always runs, cached) ---
        hourly = await self._get_hourly(
            site_id, device_serials, import_rate_pkr, now_pkt,
        )

        # --- Tier 2: Monthly (run once per day, cached 24h) ---
        monthly_text = await self._get_monthly_cached(
            site_id, import_rate_pkr, billing_month_start, now_pkt,
        )

        # --- Tier 3: Yearly (run once per billing month, cached 30d) ---
        yearly_text = await self._get_yearly_cached(
            site_id, import_rate_pkr, now_pkt,
        )

        # Weekly digest (arithmetic, no LLM)
        weekly_digest = await self._generate_weekly_digest(site_id, import_rate_pkr)

        return InsightsResponse(
            daily_insights=hourly["daily_insights"],
            anomaly_alerts=hourly["anomaly_alerts"],
            weekly_digest=weekly_digest,
            generated_at=now,
            monthly_analysis=monthly_text,
            yearly_analysis=yearly_text,
            source=hourly["source"],
        )

    # =========================================================================
    # Tier 1 – Hourly
    # =========================================================================

    async def _get_hourly(
        self,
        site_id: UUID,
        device_serials: List[str],
        import_rate_pkr: float,
        now_pkt: datetime,
    ) -> Dict[str, Any]:
        cache_key = f"insights:hourly:{site_id}"

        # Check Redis cache first
        cached = await self._redis_get(cache_key)
        if cached:
            logger.info("[insights] Hourly cache HIT for site=%s", site_id)
            now_dt = datetime.now(timezone.utc)
            return {
                "daily_insights": self._parse_insight_list(cached.get("daily_insights", []), now_dt),
                "anomaly_alerts": self._parse_insight_list(cached.get("anomaly_alerts", []), now_dt),
                "source": "cache",
            }

        # Gather data
        site_stats = await self._gather_site_stats(device_serials)
        alerts_block = await self._gather_alerts_block(device_serials)
        ls_block = await self._gather_load_shedding_block(site_id)
        battery_kwh = self._extract_battery_kwh(site_stats)

        # Resolve model for this tier
        hourly_model = await self._resolve_model("hourly")

        # Try Claude
        if self._claude and settings.ai.enabled:
            try:
                daily, anomalies = await self._claude_hourly(
                    site_stats, import_rate_pkr, now_pkt,
                    alerts_block, ls_block, battery_kwh,
                    model=hourly_model,
                )
                source = "claude"
            except Exception as exc:
                logger.warning("[insights] Hourly Claude failed (%s) — rule-based fallback", exc)
                daily    = self._rule_daily(site_stats, import_rate_pkr, now_pkt)
                anomalies = self._rule_anomalies(site_stats, now_pkt)
                source = "rule_based"
        else:
            daily    = self._rule_daily(site_stats, import_rate_pkr, now_pkt)
            anomalies = self._rule_anomalies(site_stats, now_pkt)
            source = "rule_based"

        result = {
            "daily_insights": daily,
            "anomaly_alerts": anomalies,
            "source": source,
        }

        # Cache and persist
        # Use a short TTL when devices are offline so stale "inverter offline"
        # insights expire quickly once the device reconnects.
        devices_online = site_stats.get("devices_online", 0)
        devices_total = site_stats.get("devices_total", 1)
        hourly_ttl = _TTL_HOURLY_S if devices_online >= devices_total else _TTL_HOURLY_OFFLINE_S
        serializable = {
            "daily_insights": [self._insight_to_dict(i) for i in daily],
            "anomaly_alerts": [self._insight_to_dict(i) for i in anomalies],
        }
        await self._redis_set(cache_key, serializable, hourly_ttl)
        await self._persist_insights_log(
            site_id=site_id,
            tier="hourly",
            model=hourly_model if source == "claude" else "rule_based",
            period=now_pkt.strftime("%Y-%m-%dT%H:00"),
            billing_month=None,
            daily_insights=[self._insight_to_dict(i) for i in daily],
            anomaly_alerts=[self._insight_to_dict(i) for i in anomalies],
            input_stats={
                **{k: v for k, v in site_stats.items() if not isinstance(v, list)},
                "battery_kwh": battery_kwh,
            },
        )

        return result

    async def _claude_hourly(
        self,
        stats: Dict[str, Any],
        import_rate_pkr: float,
        now: datetime,
        alerts_block: str,
        ls_block: str,
        battery_kwh: Dict[str, float],
        model: str = "claude-haiku-4-5-20251001",
    ) -> tuple:
        loader = self._get_prompt_loader()
        now_pkt_str = now.strftime("%H:%M %a %d %b")
        savings_pkr = round(stats["self_consumed_kwh"] * import_rate_pkr)
        max_temp = stats.get("max_inverter_temp_c", 0.0)
        temp_line = (
            f"Inverter temperature: {max_temp:.0f}°C"
            + (" ⚠ CRITICAL" if max_temp >= INVERTER_TEMP_HIGH_C else
               " ⚠ Elevated" if max_temp >= INVERTER_TEMP_WARN_C else "")
        ) if max_temp > 0 else "Inverter temperature: not available"

        solar_start_h, solar_end_h = self._solar_window(now)
        solar_surplus_kw = max(0.0, (stats.get("pv_power_w", 0) - stats.get("load_power_w", 0)) / 1000)
        ev_hours_remaining = max(0, solar_end_h - now.hour)

        variables = {
            "time_pkt":             now_pkt_str,
            "energy_today_kwh":     f"{stats['energy_today_kwh']:.2f}",
            "peak_power_kw":        f"{stats['peak_power_kw']:.2f}",
            "load_power_w":         f"{stats['load_power_w']:.0f}",
            "grid_power_w":         f"{stats['grid_power_w']:.0f}",
            "battery_power_w":      f"{stats['battery_power_w']:.0f}",
            "avg_soc_pct":          f"{stats['avg_soc_pct']:.1f}",
            "self_consumed_kwh":    f"{stats['self_consumed_kwh']:.2f}",
            "grid_import_today_kwh":f"{stats['grid_import_today_kwh']:.2f}",
            "grid_export_today_kwh":f"{stats['grid_export_today_kwh']:.2f}",
            "self_sufficiency_pct": f"{stats['self_sufficiency_pct']:.1f}",
            "co2_saved_kg":         f"{stats['co2_saved_kg']:.2f}",
            "savings_pkr":          f"{savings_pkr:,}",
            "import_rate_pkr":      f"{import_rate_pkr:.1f}",
            "devices_online":       str(stats['devices_online']),
            "devices_total":        str(stats['devices_total']),
            "inverter_temp_line":   temp_line,
            "battery_charge_today_kwh":    f"{battery_kwh.get('charge', 0.0):.2f}",
            "battery_discharge_today_kwh": f"{battery_kwh.get('discharge', 0.0):.2f}",
            "battery_hourly_charge_kwh":   f"{battery_kwh.get('hour_charge', 0.0):.3f}",
            "battery_hourly_discharge_kwh":f"{battery_kwh.get('hour_discharge', 0.0):.3f}",
            "system_alerts_block":  alerts_block or "No active system alerts.",
            "load_shedding_block":  ls_block or "No load shedding data available.",
            "warn_temp_c":          str(int(INVERTER_TEMP_WARN_C)),
            # EV charging window
            "solar_peak_end_pkt":   f"{solar_end_h}:00",
            "ev_hours_remaining":   str(ev_hours_remaining),
            "solar_surplus_kw":     f"{solar_surplus_kw:.1f}",
        }

        if loader:
            system_prompt = await loader.render("hourly_system", variables)
            user_prompt   = await loader.render("hourly_user",   variables)
        else:
            system_prompt = _HARDCODED_HOURLY_SYSTEM.format_map(_Default(variables))
            user_prompt   = _HARDCODED_HOURLY_USER.format_map(_Default(variables))

        response = await self._claude.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            tools=[_HOURLY_TOOL],
            tool_choice={"type": "tool", "name": "return_insights"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        block = next((b for b in response.content if b.type == "tool_use"), None)
        if not block:
            raise ValueError("Claude did not call return_insights.")

        raw = block.input
        now_dt = datetime.now(timezone.utc)
        daily    = self._parse_insight_list(raw.get("daily_insights", []), now_dt)
        anomalies = self._parse_insight_list(raw.get("anomaly_alerts",  []), now_dt)
        return daily, anomalies

    # =========================================================================
    # Tier 2 – Monthly
    # =========================================================================

    async def _get_monthly_cached(
        self,
        site_id: UUID,
        import_rate_pkr: float,
        billing_month_start: Optional[date],
        now_pkt: datetime,
    ) -> Optional[str]:
        today = now_pkt.date()
        bm = billing_month_start or today.replace(day=1)
        cache_key = f"insights:monthly:{site_id}:{bm.isoformat()}"

        cached = await self._redis_get(cache_key)
        if cached:
            logger.info("[insights] Monthly cache HIT for site=%s", site_id)
            return cached.get("monthly_analysis")

        if not (self._claude and settings.ai.enabled):
            return None

        monthly_model = await self._resolve_model("monthly")
        try:
            text = await self._claude_monthly(
                site_id, import_rate_pkr, bm, today, now_pkt,
                model=monthly_model,
            )
        except Exception as exc:
            logger.warning("[insights] Monthly Claude failed: %s", exc)
            return None

        await self._redis_set(cache_key, {"monthly_analysis": text}, _TTL_MONTHLY_S)
        await self._persist_insights_log(
            site_id=site_id,
            tier="monthly",
            model=monthly_model,
            period=bm.isoformat(),
            billing_month=bm,
            monthly_analysis=text,
        )
        return text

    async def _claude_monthly(
        self,
        site_id: UUID,
        import_rate_pkr: float,
        billing_month_start: date,
        today: date,
        now_pkt: datetime,
        model: str = "claude-sonnet-4-6",
    ) -> str:
        # Fetch 30-day energy chart from System B
        try:
            monthly_data = await self._system_b.get_site_energy_chart(
                site_id=site_id, period="month",
            )
            data_points = monthly_data.get("data", [])
        except SystemBClientError:
            data_points = []

        # Aggregate monthly stats
        total_pv    = sum(float(p.get("pv_kwh",          0) or 0) for p in data_points)
        total_load  = sum(float(p.get("load_kwh",         0) or 0) for p in data_points)
        total_import= sum(float(p.get("grid_import_kwh",  0) or 0) for p in data_points)
        total_export= sum(float(p.get("grid_export_kwh",  0) or 0) for p in data_points)
        self_consumed = max(0.0, total_load - total_import)
        self_suf_pct  = (self_consumed / total_load * 100) if total_load > 0 else 0.0
        savings_pkr   = round(self_consumed * import_rate_pkr)
        days_elapsed  = (today - billing_month_start).days + 1

        # Outage statistics from DB
        ls_stats = await self._fetch_monthly_outage_stats(site_id, billing_month_start, today)
        outage_hours = ls_stats.get("total_hours", 0.0)
        outage_events = ls_stats.get("event_count", 0)

        # Build chart snippet (max 10 rows to keep prompt lean)
        # System B returns 'timestamp' (ISO string) not 'date'
        chart_rows = "\n".join(
            f"  {str(p.get('timestamp','?'))[:10]} | pv={float(p.get('pv_kwh',0) or 0):.1f}kWh "
            f"load={float(p.get('load_kwh',0) or 0):.1f}kWh "
            f"import={float(p.get('grid_import_kwh',0) or 0):.1f}kWh"
            for p in data_points[-10:]
        ) or "  (no daily breakdown available)"

        loader = self._get_prompt_loader()
        variables = {
            "billing_month":      billing_month_start.strftime("%B %Y"),
            "days_elapsed":       str(days_elapsed),
            "total_pv_kwh":       f"{total_pv:.1f}",
            "total_load_kwh":     f"{total_load:.1f}",
            "total_import_kwh":   f"{total_import:.1f}",
            "total_export_kwh":   f"{total_export:.1f}",
            "self_sufficiency_pct": f"{self_suf_pct:.1f}",
            "savings_pkr":        f"{savings_pkr:,}",
            "import_rate_pkr":    f"{import_rate_pkr:.1f}",
            "outage_hours":       f"{outage_hours:.1f}",
            "outage_events":      str(outage_events),
            "chart_snippet":      chart_rows,
        }

        if loader:
            system_prompt = await loader.render("monthly_system", variables)
            user_prompt   = await loader.render("monthly_user",   variables)
        else:
            system_prompt = _HARDCODED_MONTHLY_SYSTEM.format_map(_Default(variables))
            user_prompt   = _HARDCODED_MONTHLY_USER.format_map(_Default(variables))

        response = await self._claude.messages.create(
            model=model,
            max_tokens=1500,
            system=system_prompt,
            tools=[_MONTHLY_TOOL],
            tool_choice={"type": "tool", "name": "return_monthly_analysis"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        block = next((b for b in response.content if b.type == "tool_use"), None)
        if not block:
            raise ValueError("Claude did not call return_monthly_analysis.")

        raw = block.input
        return {
            "summary":              raw.get("summary", ""),
            "highlights":           raw.get("highlights", []),
            "recommendations":      raw.get("recommendations", []),
            "load_shedding_insight":raw.get("load_shedding_insight", ""),
        }

    # =========================================================================
    # Tier 3 – Yearly
    # =========================================================================

    async def _get_yearly_cached(
        self,
        site_id: UUID,
        import_rate_pkr: float,
        now_pkt: datetime,
    ) -> Optional[str]:
        year  = now_pkt.year
        month = now_pkt.month
        cache_key = f"insights:yearly:{site_id}:{year}:{month:02d}"

        cached = await self._redis_get(cache_key)
        if cached:
            logger.info("[insights] Yearly cache HIT for site=%s", site_id)
            return cached.get("yearly_analysis")

        if not (self._claude and settings.ai.enabled):
            return None

        yearly_model = await self._resolve_model("yearly")
        try:
            text = await self._claude_yearly(site_id, import_rate_pkr, now_pkt, model=yearly_model)
        except Exception as exc:
            logger.warning("[insights] Yearly Claude failed: %s", exc)
            return None

        await self._redis_set(cache_key, {"yearly_analysis": text}, _TTL_YEARLY_S)
        await self._persist_insights_log(
            site_id=site_id,
            tier="yearly",
            model=yearly_model,
            period=f"{year}-{month:02d}",
            billing_month=now_pkt.date().replace(day=1),
            yearly_analysis=text,
        )
        return text

    async def _claude_yearly(
        self,
        site_id: UUID,
        import_rate_pkr: float,
        now_pkt: datetime,
        model: str = "claude-sonnet-4-6",
    ) -> str:
        try:
            yearly_data = await self._system_b.get_site_energy_chart(
                site_id=site_id, period="month",
            )
            data_points = yearly_data.get("data", [])
        except Exception:
            data_points = []

        total_pv    = sum(float(p.get("pv_kwh",         0) or 0) for p in data_points)
        total_load  = sum(float(p.get("load_kwh",        0) or 0) for p in data_points)
        total_import= sum(float(p.get("grid_import_kwh", 0) or 0) for p in data_points)
        total_export= sum(float(p.get("grid_export_kwh", 0) or 0) for p in data_points)
        self_consumed = max(0.0, total_load - total_import)
        self_suf_pct  = (self_consumed / total_load * 100) if total_load > 0 else 0.0
        savings_pkr   = round(self_consumed * import_rate_pkr)
        co2_saved     = total_pv * CO2_KG_PER_KWH

        # Monthly breakdown for chart snippet (last 12 months)
        # System B returns 'timestamp' (ISO string) not 'date'
        chart_rows = "\n".join(
            f"  {str(p.get('timestamp','?'))[:10]} | pv={float(p.get('pv_kwh',0) or 0):.0f}kWh "
            f"load={float(p.get('load_kwh',0) or 0):.0f}kWh "
            f"import={float(p.get('grid_import_kwh',0) or 0):.0f}kWh"
            for p in data_points
        ) or "  (no monthly breakdown available)"

        loader = self._get_prompt_loader()
        variables = {
            "year":               str(now_pkt.year),
            "month_label":        now_pkt.strftime("%B %Y"),
            "total_pv_kwh":       f"{total_pv:.0f}",
            "total_load_kwh":     f"{total_load:.0f}",
            "total_import_kwh":   f"{total_import:.0f}",
            "total_export_kwh":   f"{total_export:.0f}",
            "self_sufficiency_pct": f"{self_suf_pct:.1f}",
            "savings_pkr":        f"{savings_pkr:,}",
            "co2_saved_kg":       f"{co2_saved:.0f}",
            "import_rate_pkr":    f"{import_rate_pkr:.1f}",
            "chart_snippet":      chart_rows,
        }

        if loader:
            system_prompt = await loader.render("yearly_system", variables)
            user_prompt   = await loader.render("yearly_user",   variables)
        else:
            system_prompt = _HARDCODED_YEARLY_SYSTEM.format_map(_Default(variables))
            user_prompt   = _HARDCODED_YEARLY_USER.format_map(_Default(variables))

        response = await self._claude.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            tools=[_YEARLY_TOOL],
            tool_choice={"type": "tool", "name": "return_yearly_analysis"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        block = next((b for b in response.content if b.type == "tool_use"), None)
        if not block:
            raise ValueError("Claude did not call return_yearly_analysis.")

        raw = block.input
        return {
            "summary":        raw.get("summary", ""),
            "best_month":     raw.get("best_month", ""),
            "worst_month":    raw.get("worst_month", ""),
            "trends":         raw.get("trends", []),
            "recommendations":raw.get("recommendations", []),
            "roi_insight":    raw.get("roi_insight", ""),
        }

    # =========================================================================
    # Data Helpers
    # =========================================================================

    async def _gather_site_stats(self, device_serials: List[str]) -> Dict[str, Any]:
        """Aggregate real-time stats from Redis across all site devices."""
        total_pv_w = total_load_w = total_grid_w = total_battery_w = 0.0
        total_energy_today = total_import = total_export = 0.0
        total_batt_charge = total_batt_discharge = 0.0
        total_soc = 0.0
        soc_count = 0
        peak_kw = max_temp = 0.0
        devices_online = 0
        devices_total = len(device_serials)

        for serial in device_serials:
            telemetry = await self._cache.get_telemetry(serial)
            status    = await self._cache.get_status(serial)
            if status == "online":
                devices_online += 1
            if not telemetry:
                continue

            power   = telemetry.get("power", {})
            energy  = telemetry.get("energy_today", {})
            battery = telemetry.get("battery", {})
            raw     = telemetry.get("raw", {})
            temps   = telemetry.get("temperatures", {})

            inv_temp  = float(temps.get("inverter_c") or raw.get("inverter_temp_c") or 0)
            sink_temp = float(raw.get("heat_sink_temp_c") or 0)
            max_temp  = max(max_temp, inv_temp, sink_temp)

            pv_w   = float(power.get("pv_total_w", 0) or 0)
            load_w = float(power.get("load_w",     0) or 0)
            grid_w = float(power.get("grid_w",     0) or 0)
            batt_w = float(power.get("battery_w",  0) or 0)
            energy_today = float(energy.get("pv_kwh", 0) or 0)
            grid_import  = float(raw.get("grid_import_energy_today_kwh", 0) or 0)
            grid_export  = float(raw.get("grid_export_energy_today_kwh", 0) or 0)
            batt_charge  = float(raw.get("battery_charge_today_kwh",     0) or 0)
            batt_disch   = float(raw.get("battery_discharge_today_kwh",  0) or 0)
            soc          = float(battery.get("soc_pct", 0) or 0)

            total_pv_w      += pv_w
            total_load_w    += load_w
            total_grid_w    += grid_w
            total_battery_w += batt_w
            total_energy_today += energy_today
            total_import    += grid_import
            total_export    += grid_export
            total_batt_charge   += batt_charge
            total_batt_discharge += batt_disch
            if pv_w > 0:
                peak_kw = max(peak_kw, pv_w / 1000.0)
            if soc > 0:
                total_soc += soc
                soc_count += 1

        avg_soc = total_soc / soc_count if soc_count > 0 else 0.0
        self_consumed = max(0.0, total_energy_today - total_export)
        self_suf = (self_consumed / total_energy_today * 100) if total_energy_today > 0 else 0.0

        return {
            "pv_power_w":              total_pv_w,
            "load_power_w":            total_load_w,
            "grid_power_w":            total_grid_w,
            "battery_power_w":         total_battery_w,
            "energy_today_kwh":        total_energy_today,
            "grid_import_today_kwh":   total_import,
            "grid_export_today_kwh":   total_export,
            "battery_charge_today_kwh":   total_batt_charge,
            "battery_discharge_today_kwh":total_batt_discharge,
            "avg_soc_pct":             avg_soc,
            "peak_power_kw":           peak_kw,
            "max_inverter_temp_c":     max_temp,
            "self_sufficiency_pct":    self_suf,
            "self_consumed_kwh":       self_consumed,
            "devices_online":          devices_online,
            "devices_total":           devices_total,
            "co2_saved_kg":            total_energy_today * CO2_KG_PER_KWH,
        }

    def _extract_battery_kwh(self, stats: Dict[str, Any]) -> Dict[str, float]:
        return {
            "charge":            stats.get("battery_charge_today_kwh",   0.0),
            "discharge":         stats.get("battery_discharge_today_kwh",0.0),
            "hour_charge":       0.0,   # instantaneous hourly not tracked separately
            "hour_discharge":    0.0,
        }

    async def _gather_alerts_block(self, device_serials: List[str]) -> str:
        """Build a text block of active system alerts from Redis device status."""
        lines = []
        try:
            from ...infrastructure.cache.redis_cache import RedisManager
            redis = await RedisManager.get_client()
            for serial in device_serials:
                raw = await redis.get(f"device:{serial}:alerts")
                if raw:
                    data = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
                    for alert in (data.get("alerts") or []):
                        lines.append(
                            f"[{serial}] {alert.get('severity','INFO').upper()}: {alert.get('message','')}"
                        )
        except Exception as exc:
            logger.debug("[insights] Could not fetch alerts from Redis: %s", exc)
        return "\n".join(lines) if lines else ""

    async def _gather_load_shedding_block(self, site_id: UUID) -> str:
        """Build the LS prediction block using OutagePredictionService."""
        if not self._session_factory:
            return ""
        try:
            from .outage_prediction_service import OutagePredictionService
            svc = OutagePredictionService(self._session_factory)
            result = await svc.predict(site_id)
            return svc.format_prompt_block(result)
        except Exception as exc:
            logger.debug("[insights] LS block failed: %s", exc)
            return ""

    async def _fetch_monthly_outage_stats(
        self,
        site_id: UUID,
        month_start: date,
        month_end: date,
    ) -> Dict[str, Any]:
        if not self._session_factory:
            return {}
        try:
            async with self._session_factory() as session:
                from ...infrastructure.database.repositories.ai_repository import (
                    SQLAlchemyGridOutageRepository,
                )
                repo = SQLAlchemyGridOutageRepository(session)
                return await repo.get_month_stats(
                    site_id=site_id,
                    billing_month_start=month_start,
                    billing_month_end=month_end,
                )
        except Exception as exc:
            logger.debug("[insights] Monthly outage stats failed: %s", exc)
            return {}

    # =========================================================================
    # Redis cache helpers
    # =========================================================================

    async def _redis_get(self, key: str) -> Optional[Dict]:
        try:
            from ...infrastructure.cache.redis_cache import RedisManager
            redis = await RedisManager.get_client()
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("[insights] Redis GET failed for %s: %s", key, exc)
        return None

    async def _redis_set(self, key: str, value: Dict, ttl_s: int) -> None:
        try:
            from ...infrastructure.cache.redis_cache import RedisManager
            redis = await RedisManager.get_client()
            await redis.setex(key, ttl_s, json.dumps(value, default=str))
            logger.debug("[insights] Redis SET ok key=%s ttl=%ds", key, ttl_s)
        except Exception as exc:
            logger.warning("[insights] Redis SET failed for %s: %s", key, exc)

    # =========================================================================
    # DB persistence
    # =========================================================================

    async def _persist_insights_log(
        self,
        site_id: UUID,
        tier: str,
        model: str,
        period: str,
        billing_month: Optional[date],
        daily_insights: Optional[List[Dict]] = None,
        anomaly_alerts: Optional[List[Dict]] = None,
        monthly_analysis: Optional[Dict] = None,
        yearly_analysis:  Optional[Dict] = None,
        input_stats: Optional[Dict] = None,
    ) -> None:
        if not self._session_factory:
            return
        try:
            from ...domain.entities.ai_entities import AIInsightsLog
            from ...infrastructure.database.repositories.ai_repository import (
                SQLAlchemyAIInsightsLogRepository,
            )
            # Convert period string ("2026-02-23T15:00", "2026-02-01", "2026-02") to datetime
            try:
                period_start = datetime.fromisoformat(period)
                if period_start.tzinfo is None:
                    period_start = period_start.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                # Handle compact "YYYY-MM" format used by yearly tier
                try:
                    parts = period.split("-")
                    period_start = datetime(int(parts[0]), int(parts[1]), 1, tzinfo=timezone.utc)
                except Exception:
                    period_start = datetime.now(timezone.utc)
            log = AIInsightsLog(
                id=uuid4(),
                site_id=site_id,
                tier=tier,
                model=model,
                period_start=period_start,
                billing_month=billing_month,
                daily_insights=daily_insights or [],
                anomaly_alerts=anomaly_alerts or [],
                monthly_analysis=monthly_analysis,
                yearly_analysis=yearly_analysis,
                input_stats=input_stats or {},
            )
            async with self._session_factory() as session:
                repo = SQLAlchemyAIInsightsLogRepository(session)
                await repo.add(log)
                await session.commit()
        except Exception as exc:
            logger.warning("[insights] Failed to persist insights log: %s", exc)

    # =========================================================================
    # Weekly digest (arithmetic, no LLM)
    # =========================================================================

    async def _generate_weekly_digest(
        self,
        site_id: UUID,
        import_rate_pkr: float,
    ) -> Optional[WeeklyDigestData]:
        try:
            data = await self._system_b.get_site_energy_chart(
                site_id=site_id, period="week",
            )
            points = data.get("data", [])
            if not points:
                return None

            total_pv    = sum(float(p.get("pv_kwh",         0) or 0) for p in points)
            total_load  = sum(float(p.get("load_kwh",        0) or 0) for p in points)
            total_import= sum(float(p.get("grid_import_kwh", 0) or 0) for p in points)
            self_cons   = max(0.0, total_load - total_import)
            self_suf    = (self_cons / total_load * 100) if total_load > 0 else (
                100.0 if total_pv > 0 else 0.0
            )
            saved_pkr   = round(self_cons * import_rate_pkr)
            tip = WEEKLY_TIPS[date.today().weekday() % len(WEEKLY_TIPS)]

            return WeeklyDigestData(
                total_generated_kwh=round(total_pv, 1),
                total_saved_pkr=float(saved_pkr),
                self_sufficiency_pct=round(self_suf, 1),
                prev_week_generated_kwh=0.0,
                prev_week_saved_pkr=0.0,
                prev_week_self_sufficiency_pct=0.0,
                generated_change_pct=0.0,
                saved_change_pct=0.0,
                self_sufficiency_change_pct=0.0,
                tip_of_the_week=tip,
            )
        except Exception as exc:
            logger.warning("[insights] Weekly digest failed for site %s: %s", site_id, exc)
            return None

    # =========================================================================
    # Rule-based fallback generators
    # =========================================================================

    def _rule_daily(
        self,
        stats: Dict[str, Any],
        import_rate_pkr: float,
        now: datetime,
    ) -> List[InsightData]:
        insights: List[InsightData] = []
        hour = now.hour
        energy_today = stats["energy_today_kwh"]
        self_consumed = stats["self_consumed_kwh"]
        self_suf = stats["self_sufficiency_pct"]
        co2_saved = stats["co2_saved_kg"]
        peak_kw = stats["peak_power_kw"]

        if energy_today > 0:
            insights.append(InsightData(
                id="prod-daily", type="positive" if energy_today >= 5 else "neutral",
                category="production", title="Today's Solar Generation",
                message=(
                    f"Generated {energy_today:.1f} kWh today"
                    + (f", avoiding {co2_saved:.1f} kg CO₂" if co2_saved > 0.1 else "")
                ),
                timestamp=now,
                metadata={"energy_today_kwh": round(energy_today, 1)},
            ))

        savings_pkr = round(self_consumed * import_rate_pkr)
        if savings_pkr > 0:
            insights.append(InsightData(
                id="save-daily", type="positive", category="savings",
                title="Money Saved Today",
                message=f"Saved Rs. {savings_pkr:,} using {self_consumed:.1f} kWh of solar instead of grid power.",
                timestamp=now,
                metadata={"savings_pkr": savings_pkr},
            ))

        if self_suf >= 80:
            insights.append(InsightData(
                id="suf-high", type="positive", category="production",
                title="High Solar Independence",
                message=f"{self_suf:.0f}% of your energy came from solar today — nearly grid-independent!",
                timestamp=now,
            ))
        elif self_suf >= 50:
            insights.append(InsightData(
                id="suf-mid", type="neutral", category="production",
                title="Solar Coverage",
                message=f"Solar covered {self_suf:.0f}% of your energy needs today.",
                timestamp=now,
            ))

        if 9 <= hour <= 15:
            insights.append(InsightData(
                id="tip-solar-hours", type="tip", category="recommendation",
                title="Peak Solar Hours",
                message="Best time for high-load appliances — AC, washer, dishwasher. Solar is at peak.",
                timestamp=now,
            ))
        elif 16 <= hour <= 20:
            insights.append(InsightData(
                id="tip-evening", type="tip", category="recommendation",
                title="Evening Load Tip",
                message="Solar reducing. Use battery for evening loads to avoid grid import costs.",
                timestamp=now,
            ))
        else:
            tip = WEEKLY_TIPS[date.today().weekday() % len(WEEKLY_TIPS)]
            insights.append(InsightData(
                id="tip-weekly", type="tip", category="recommendation",
                title="Energy Saving Tip", message=tip, timestamp=now,
            ))

        return insights

    def _rule_anomalies(
        self,
        stats: Dict[str, Any],
        now: datetime,
    ) -> List[InsightData]:
        alerts: List[InsightData] = []
        hour = now.hour
        max_temp       = stats.get("max_inverter_temp_c", 0.0)
        avg_soc        = stats["avg_soc_pct"]
        energy_today   = stats["energy_today_kwh"]
        peak_kw        = stats["peak_power_kw"]
        devices_online = stats["devices_online"]
        devices_total  = stats["devices_total"]

        if max_temp >= INVERTER_TEMP_HIGH_C:
            note = " (may also be a sensor scaling artifact)" if max_temp > 100 else ""
            alerts.append(InsightData(
                id="anomaly-overtemp", type="warning", category="anomaly",
                title="High Inverter Temperature",
                message=f"Inverter at {max_temp:.0f}°C — above safe range. Check ventilation.{note}",
                timestamp=now, metadata={"max_inverter_temp_c": round(max_temp, 1)},
            ))
        elif max_temp >= INVERTER_TEMP_WARN_C:
            alerts.append(InsightData(
                id="anomaly-hightemp", type="warning", category="anomaly",
                title="Elevated Inverter Temperature",
                message=f"Inverter at {max_temp:.0f}°C. Ensure adequate ventilation.",
                timestamp=now, metadata={"max_inverter_temp_c": round(max_temp, 1)},
            ))

        if 9 <= hour <= 16 and devices_online > 0 and energy_today < 0.5 and peak_kw < 0.3:
            alerts.append(InsightData(
                id="anomaly-low-gen", type="warning", category="anomaly",
                title="Unusually Low Solar Generation",
                message="Very low generation for this time of day. Check panels or inverter if sky is clear.",
                timestamp=now,
            ))

        if 0 < avg_soc < 15:
            alerts.append(InsightData(
                id="anomaly-batt-crit", type="warning", category="anomaly",
                title="Battery Critically Low",
                message=f"Battery at {avg_soc:.0f}%. Reduce non-essential loads.",
                timestamp=now, metadata={"soc_pct": round(avg_soc, 1)},
            ))
        elif 0 < avg_soc < 25:
            alerts.append(InsightData(
                id="anomaly-batt-low", type="warning", category="anomaly",
                title="Battery Level Low",
                message=f"Battery at {avg_soc:.0f}%. Will recharge during next solar window.",
                timestamp=now, metadata={"soc_pct": round(avg_soc, 1)},
            ))

        if devices_total > 0 and devices_online == 0:
            alerts.append(InsightData(
                id="anomaly-all-offline", type="warning", category="anomaly",
                title="All Devices Offline",
                message="No devices reporting data. Check internet or data logger status.",
                timestamp=now,
            ))
        elif devices_total > 1 and devices_online < devices_total:
            n = devices_total - devices_online
            alerts.append(InsightData(
                id="anomaly-some-offline", type="warning", category="anomaly",
                title=f"{n} Device(s) Offline",
                message=f"{n} of {devices_total} devices not reporting. Check connectivity.",
                timestamp=now,
            ))

        return alerts

    # =========================================================================
    # Serialization helpers
    # =========================================================================

    def _insight_to_dict(self, insight: InsightData) -> Dict[str, Any]:
        return {
            "id":       insight.id,
            "type":     insight.type,
            "category": insight.category,
            "title":    insight.title,
            "message":  insight.message,
            "timestamp":insight.timestamp.isoformat(),
            "metadata": insight.metadata,
        }

    def _parse_insight_list(
        self, items: List[Dict[str, Any]], now: datetime
    ) -> List[InsightData]:
        result = []
        for item in items:
            try:
                result.append(InsightData(
                    id=item["id"], type=item["type"],
                    category=item["category"], title=item["title"],
                    message=item["message"], timestamp=now,
                    metadata=item.get("metadata", {}),
                ))
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed insight from Claude: %s — %s", item, exc)
        return result


# =============================================================================
# _Default dict for safe format_map (missing keys → left as {key})
# =============================================================================

class _Default(dict):
    def __missing__(self, key):
        return "{" + key + "}"


# =============================================================================
# Hardcoded prompt templates (exact copies of what is seeded in the migration)
# =============================================================================

_HARDCODED_HOURLY_SYSTEM = """You are an expert solar energy analyst for Pakistani residential and commercial solar installations. You generate concise, actionable insights for system owners.

Write in clear English. Keep messages under 200 characters.
Use Pakistani context: PKR currency, DISCO net metering, load shedding (bijli gul), Karachi/Lahore climate.
Consider battery state-of-charge when recommending EV charging windows.
If load shedding is predicted, recommend optimal battery charge level before the outage window."""

_HARDCODED_HOURLY_USER = """Analyse the following real-time solar site data and generate insights.

## Current Site Data ({time_pkt} PKT)
- Solar generation today: {energy_today_kwh} kWh  |  Peak: {peak_power_kw} kW
- Current load: {load_power_w} W
- Current grid power: {grid_power_w} W  (positive=import, negative=export)
- Current battery power: {battery_power_w} W  (positive=charging, negative=discharging)
- Battery SoC: {avg_soc_pct}%
- Self-consumed solar today: {self_consumed_kwh} kWh
- Grid import today: {grid_import_today_kwh} kWh  |  Export: {grid_export_today_kwh} kWh
- Self-sufficiency: {self_sufficiency_pct}%
- CO₂ avoided: {co2_saved_kg} kg  |  Money saved: Rs. {savings_pkr} (@ Rs. {import_rate_pkr}/kWh)
- Battery charged today: {battery_charge_today_kwh} kWh  |  Discharged: {battery_discharge_today_kwh} kWh
- Devices online: {devices_online}/{devices_total}
- {inverter_temp_line}

## System Alerts
{system_alerts_block}

## Load Shedding Status & Prediction
{load_shedding_block}

## Instructions
- Generate 2–4 daily_insights: generation performance, savings, self-sufficiency, load-shedding readiness, EV charging window (if battery > 70% SoC and solar surplus exists), and one time-of-day tip.
- Generate anomaly_alerts ONLY for real problems (low generation during daylight, very low battery, devices offline, high temperature, predicted outage with low battery).
- If inverter temperature ≥ {warn_temp_c}°C, include an overheating anomaly alert.
- If an outage is predicted in the next 2–4 hours and SoC < 60%, warn the user to let the battery charge.
- Be specific with numbers. Avoid filler text.
- Call the `return_insights` tool with your response."""

_HARDCODED_MONTHLY_SYSTEM = """You are an expert solar energy analyst preparing a monthly performance report for a Pakistani solar installation.

Write in clear English. Use Pakistani context (PKR, DISCO, load shedding, seasonal patterns).
Be analytical and specific. Reference actual numbers from the data provided.
Focus on actionable improvements for the next billing month."""

_HARDCODED_MONTHLY_USER = """Generate a monthly performance analysis for {billing_month} ({days_elapsed} days elapsed).

## Monthly Energy Summary
- Solar generation: {total_pv_kwh} kWh
- Total consumption: {total_load_kwh} kWh
- Grid import: {total_import_kwh} kWh  |  Export: {total_export_kwh} kWh
- Self-sufficiency: {self_sufficiency_pct}%
- Money saved: Rs. {savings_pkr} (@ Rs. {import_rate_pkr}/kWh)

## Load Shedding This Month
- Total outage hours: {outage_hours}h across {outage_events} events

## Daily Breakdown (last 10 days)
{chart_snippet}

Call the `return_monthly_analysis` tool with your analysis."""

_HARDCODED_YEARLY_SYSTEM = """You are an expert solar energy analyst preparing a year-to-date performance review for a Pakistani solar installation.

Write in clear English. Use Pakistani context (PKR, DISCO net metering, seasonal monsoon/winter patterns).
Be strategic. Identify long-term trends, ROI progress, and seasonal patterns.
Compare months and identify the best/worst performing periods."""

_HARDCODED_YEARLY_USER = """Generate a year-to-date analysis as of {month_label}.

## Year-to-Date Energy Summary ({year})
- Total solar generation: {total_pv_kwh} kWh
- Total consumption: {total_load_kwh} kWh
- Grid import: {total_import_kwh} kWh  |  Export: {total_export_kwh} kWh
- Self-sufficiency: {self_sufficiency_pct}%
- Total savings: Rs. {savings_pkr} (@ Rs. {import_rate_pkr}/kWh)
- CO₂ avoided: {co2_saved_kg} kg

## Monthly Breakdown
{chart_snippet}

Call the `return_yearly_analysis` tool with your analysis."""
