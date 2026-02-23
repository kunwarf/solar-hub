"""
Prompt Template Loader.

Loads Claude prompt templates from:
  1. Redis cache (TTL = 5 minutes) — fastest, handles burst traffic
  2. PostgreSQL (ai_prompt_templates table) — source of truth, admin-editable
  3. Hardcoded defaults (this module) — failsafe when DB is unavailable

Admin edits via /admin/ai-prompts reflect within 5 minutes (next cache miss).
No service restart required.

Usage:
    loader = PromptTemplateLoader(session_factory)
    system_prompt = await loader.render("hourly_system", variables={...})
    user_prompt   = await loader.render("hourly_user",   variables={...})
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_REDIS_TTL_SECONDS = 300   # 5-minute cache
_REDIS_KEY_PREFIX  = "prompt_tmpl:"


class PromptTemplateLoader:
    """
    Loads and renders prompt templates with Redis + DB + hardcoded fallback.

    The render() method:
    - Fetches the template string (Redis → DB → hardcoded default)
    - Substitutes {variable} placeholders using _SafeFormatMap
      (unknown placeholders are left as-is, never raise KeyError)
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # =========================================================================
    # Public API
    # =========================================================================

    async def render(self, key: str, variables: Dict[str, Any]) -> str:
        """
        Load template `key` and render it with `variables`.

        Returns the fully rendered string.
        """
        template = await self._load(key)
        return _safe_format(template, variables)

    async def get_raw(self, key: str) -> str:
        """Return the raw (un-rendered) template string for a key."""
        return await self._load(key)

    async def invalidate(self, key: str) -> None:
        """Evict a template from Redis so the next request re-fetches from DB."""
        try:
            from ...infrastructure.cache.redis_manager import RedisManager
            redis = await RedisManager.get_client()
            await redis.delete(f"{_REDIS_KEY_PREFIX}{key}")
            logger.info("Prompt template cache invalidated for key=%s", key)
        except Exception as exc:
            logger.warning("Could not invalidate prompt cache for key=%s: %s", key, exc)

    # =========================================================================
    # Loading chain: Redis → DB → hardcoded
    # =========================================================================

    async def _load(self, key: str) -> str:
        # 1. Try Redis
        cached = await self._from_redis(key)
        if cached is not None:
            return cached

        # 2. Try DB
        db_template = await self._from_db(key)
        if db_template is not None:
            await self._store_redis(key, db_template)
            return db_template

        # 3. Hardcoded default
        default = _HARDCODED_DEFAULTS.get(key)
        if default:
            logger.debug("Using hardcoded default for prompt key=%s", key)
            return default

        logger.warning("No prompt template found for key=%s — returning empty string", key)
        return ""

    async def _from_redis(self, key: str) -> Optional[str]:
        try:
            from ...infrastructure.cache.redis_manager import RedisManager
            redis = await RedisManager.get_client()
            value = await redis.get(f"{_REDIS_KEY_PREFIX}{key}")
            if value:
                return value if isinstance(value, str) else value.decode()
        except Exception as exc:
            logger.debug("Redis unavailable for prompt key=%s: %s", key, exc)
        return None

    async def _from_db(self, key: str) -> Optional[str]:
        try:
            async with self._session_factory() as session:
                from ...infrastructure.database.repositories.ai_repository import (
                    SQLAlchemyAIPromptTemplateRepository,
                )
                repo = SQLAlchemyAIPromptTemplateRepository(session)
                template_obj = await repo.get_active_by_key(key)
                if template_obj:
                    return template_obj.template
        except Exception as exc:
            logger.warning("DB unavailable for prompt key=%s: %s", key, exc)
        return None

    async def _store_redis(self, key: str, template: str) -> None:
        try:
            from ...infrastructure.cache.redis_manager import RedisManager
            redis = await RedisManager.get_client()
            await redis.setex(f"{_REDIS_KEY_PREFIX}{key}", _REDIS_TTL_SECONDS, template)
        except Exception as exc:
            logger.debug("Could not cache prompt key=%s in Redis: %s", key, exc)


# ---------------------------------------------------------------------------
# Safe format helper
# ---------------------------------------------------------------------------

def _safe_format(template: str, variables: Dict[str, Any]) -> str:
    """
    Substitute {variable} placeholders in template.

    Unknown keys are left as-is ({unknown}) instead of raising KeyError.
    All values are converted to strings before substitution.
    """
    class _Default(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    str_vars = {k: str(v) if v is not None else "" for k, v in variables.items()}
    try:
        return template.format_map(_Default(str_vars))
    except Exception as exc:
        logger.warning("Template rendering error: %s", exc)
        return template


# ---------------------------------------------------------------------------
# Hardcoded defaults
# These are the canonical prompts from the requirements design session.
# They are used as a fallback when the DB is unavailable.
# Admins should edit the DB versions via /admin/ai-prompts.
# ---------------------------------------------------------------------------

_HARDCODED_DEFAULTS: Dict[str, str] = {

    # ================================================================ HOURLY

    "hourly_system": (
        "You are an expert solar energy analyst for Pakistani {system_type} solar "
        "installations. You generate concise, actionable insights for system owners.\n"
        "Rules:\n"
        "- Write in plain English. No markdown, no bullet points inside message fields.\n"
        "- Keep each insight message under {max_chars} characters.\n"
        "- Use Pakistani context: PKR currency, DISCO net metering, load shedding.\n"
        "- Climate context: {city}.\n"
        "- Be specific with numbers — never give generic advice when real data is available.\n"
        "- Call the `return_insights` tool with your structured response.\n"
        "- Current date/time: {current_datetime} PKT."
    ),

    "hourly_user": (
        "Analyse this real-time solar site snapshot and generate insights.\n\n"

        "━━ REAL-TIME POWER ━━\n"
        "PV generation now: {pv_power_w} W\n"
        "Load now: {load_power_w} W\n"
        "Solar surplus (PV − load): {solar_surplus_w} W  "
        "(positive = excess solar available)\n"
        "Grid: {grid_power_w} W  (positive = importing, negative = exporting)\n"
        "Battery: {battery_power_w} W  (positive = charging, negative = discharging)\n"
        "Battery SoC: {battery_soc_pct}%\n\n"

        "━━ TODAY'S ENERGY ━━\n"
        "Solar generated today: {energy_today_kwh} kWh\n"
        "Peak solar power today: {peak_power_kw} kW\n"
        "Grid imported today: {grid_import_today_kwh} kWh\n"
        "Grid exported today: {grid_export_today_kwh} kWh\n"
        "Battery charged today: {battery_charge_today_kwh} kWh\n"
        "Battery discharged today: {battery_discharge_today_kwh} kWh\n"
        "Self-consumed solar today: {self_consumed_kwh} kWh\n"
        "Self-sufficiency today: {self_sufficiency_pct}%\n"
        "Money saved today: Rs. {savings_pkr} (at Rs. {import_rate_pkr}/kWh)\n"
        "CO₂ avoided today: {co2_saved_kg} kg\n\n"

        "━━ SYSTEM STATUS ━━\n"
        "Devices online: {devices_online} / {devices_total}\n"
        "Inverter temperature: {inverter_temp_c}°C\n"
        "{system_alerts_block}\n\n"

        "━━ LOAD SHEDDING INTELLIGENCE ━━\n"
        "(Based on {ls_history_days} days of actual grid outage data for this site)\n"
        "{load_shedding_block}\n\n"

        "━━ EV CHARGING CONTEXT ━━\n"
        "Solar surplus available now: {solar_surplus_w} W\n"
        "Estimated solar window remaining today: {solar_hours_remaining} hours\n"
        "Battery headroom above 20% reserve: {battery_headroom_kwh} kWh\n\n"

        "━━ QUESTIONS TO ANSWER ━━\n"
        "1. Is the system performing as expected for {current_time} PKT? "
        "Comment on generation vs time-of-day norms.\n"
        "2. Battery optimisation: given the load-shedding windows predicted above, "
        "is the battery charging/discharging at the right rate? "
        "Will it be sufficiently charged before the next outage?\n"
        "3. EV charging recommendation: based on current solar surplus, "
        "battery headroom, and predicted outage windows — should the user "
        "charge their EV now, wait, or skip today? Give a specific time window.\n"
        "4. Flag any anomalies: low generation during daylight, battery below 15%, "
        "devices offline, high inverter temperature. "
        "Only raise an alert for real problems.\n"
        "5. One time-appropriate actionable tip "
        "(solar peak hours → run heavy loads; evening → conserve battery; "
        "night → grid situation).\n\n"
        "{recent_anomalies_block}"
    ),

    # =============================================================== MONTHLY

    "monthly_system": (
        "You are a solar energy financial analyst reviewing billing-month "
        "performance for a Pakistani solar customer.\n"
        "Rules:\n"
        "- Write in clear, professional English. Be specific with numbers.\n"
        "- Currency: Pakistani Rupee (Rs. or PKR).\n"
        "- Reference DISCO net metering for export credit calculations.\n"
        "- Pakistan load shedding context: evening peaks, stage-based schedules.\n"
        "- Climate: {city}.\n"
        "- Call the `return_monthly_analysis` tool with your structured response.\n"
        "- Current date: {current_date} PKT."
    ),

    "monthly_user": (
        "Analyse this billing month's solar performance and answer the "
        "five questions below.\n\n"

        "━━ BILLING MONTH ━━\n"
        "Period: {billing_month_start} – {billing_month_today} "
        "({days_elapsed} of {days_in_month} days elapsed, "
        "{days_remaining} days remaining)\n"
        "Import rate: Rs. {import_rate_pkr}/kWh\n\n"

        "━━ DAILY BREAKDOWN ━━\n"
        "Date       | PV kWh | Load kWh | Import kWh | Export kWh | "
        "Bat Charge kWh | Bat Discharge kWh | LS Hours | LS Covered %\n"
        "{daily_breakdown_table}\n\n"

        "━━ MONTH-TO-DATE TOTALS ━━\n"
        "Total generated: {mtd_pv_kwh} kWh\n"
        "Total load:      {mtd_load_kwh} kWh\n"
        "Grid import:     {mtd_import_kwh} kWh\n"
        "Grid export:     {mtd_export_kwh} kWh\n"
        "Battery charged:    {mtd_batt_charge_kwh} kWh\n"
        "Battery discharged: {mtd_batt_discharge_kwh} kWh\n"
        "Battery avg round-trip efficiency: {batt_efficiency_pct}%\n"
        "Self-sufficiency: {self_sufficiency_pct}%\n"
        "Money saved MTD:  Rs. {savings_pkr}\n"
        "CO₂ avoided MTD:  {co2_kg} kg\n"
        "Best day:  {best_day_date} → {best_day_kwh} kWh\n"
        "Worst day: {worst_day_date} → {worst_day_kwh} kWh\n"
        "Daily average so far: {daily_avg_kwh} kWh\n\n"

        "━━ LOAD SHEDDING THIS BILLING MONTH ━━\n"
        "Total outage hours: {ls_total_hours}h across {ls_event_count} events\n"
        "Battery covered: {ls_covered_hours}h ({ls_covered_pct}%)\n"
        "Grid fallback required: {ls_uncovered_hours}h\n"
        "Worst LS day: {ls_worst_day} → {ls_worst_hours}h, "
        "battery covered {ls_worst_covered_pct}%\n"
        "Days with full battery coverage: {ls_full_coverage_days}/{days_elapsed}\n\n"

        "━━ RECURRING ANOMALIES FROM AI LOG (last 30 daily results) ━━\n"
        "{recent_anomaly_log}\n\n"

        "━━ SYSTEM ALERTS THIS MONTH ━━\n"
        "{system_alerts_month}\n\n"

        "━━ QUESTIONS ━━\n"
        "1. MTD SUMMARY: How is this billing month going overall? "
        "Key numbers and whether performance is above/below expectations.\n"
        "2. MONTH-END PROJECTION: Extrapolate from daily average × remaining "
        "{days_remaining} days. Project total generation and total savings for "
        "the full billing month.\n"
        "3. BILLING ESTIMATE: How much will the electricity bill be reduced this "
        "month? Factor in import savings and DISCO net metering export credit.\n"
        "4. BATTERY RESILIENCE: Was the battery sufficient to cover load shedding? "
        "What reserve SoC would have achieved full coverage? "
        "Is the battery efficiency ({batt_efficiency_pct}%) normal or concerning?\n"
        "5. RECOMMENDATIONS: 2–3 specific actions for the remaining "
        "{days_remaining} days to maximise savings. "
        "Consider: EV charging windows, heavy-load scheduling, "
        "battery reserve settings, and load-shedding preparation.\n\n"
        "Call the `return_monthly_analysis` tool with your response."
    ),

    # ================================================================ YEARLY

    "yearly_system": (
        "You are a senior solar energy consultant conducting an annual "
        "performance review for a Pakistani solar installation.\n"
        "Rules:\n"
        "- Write in clear, professional English.\n"
        "- Currency: Pakistani Rupee (Rs. / PKR).\n"
        "- Pakistan seasonality: summer (Apr–Sep) produces 40–60% more solar "
        "than winter (Oct–Mar) due to longer days and higher irradiance.\n"
        "- Reference DISCO net metering and load-shedding context.\n"
        "- Call the `return_yearly_analysis` tool with your structured response.\n"
        "- Tone: positive and motivating, while being honest about areas for improvement.\n"
        "- City: {city}.\n"
        "- Report date: {current_date} PKT."
    ),

    "yearly_user": (
        "Conduct a year-to-date strategic review for this solar site "
        "and answer the six questions below.\n\n"

        "━━ PERIOD ━━\n"
        "{ytd_period_label}  ({months_available} billing months of data)\n\n"

        "━━ MONTHLY BREAKDOWN ━━\n"
        "Month    | Generated kWh | Load kWh | Import kWh | Export kWh | "
        "Bat Charge kWh | Bat Efficiency % | LS Hours | LS Coverage % | Saved Rs.\n"
        "{monthly_breakdown_table}\n\n"

        "━━ YEAR-TO-DATE TOTALS ━━\n"
        "Total generated: {ytd_pv_kwh} kWh\n"
        "Total load:      {ytd_load_kwh} kWh\n"
        "Grid import:     {ytd_import_kwh} kWh\n"
        "Grid export:     {ytd_export_kwh} kWh\n"
        "Total savings:   Rs. {ytd_savings_pkr}\n"
        "CO₂ avoided:     {ytd_co2_kg} kg\n"
        "Avg self-sufficiency: {ytd_self_sufficiency_pct}%\n"
        "Best month:  {best_month_label} → {best_month_kwh} kWh\n"
        "Worst month: {worst_month_label} → {worst_month_kwh} kWh\n"
        "Average monthly generation: {avg_monthly_kwh} kWh\n\n"

        "━━ LOAD SHEDDING YEAR-TO-DATE ━━\n"
        "Total outage hours: {ytd_ls_hours}h\n"
        "Battery coverage:   {ytd_ls_coverage_pct}%\n"
        "Most affected month: {ls_worst_month_label} "
        "({ls_worst_month_hours}h outage)\n\n"

        "━━ MONTHLY AI SUMMARIES (context from previous monthly analyses) ━━\n"
        "{monthly_ai_summaries}\n\n"

        "━━ RECURRING ANOMALIES (appearing 3+ times in AI log this year) ━━\n"
        "{recurring_anomalies}\n\n"

        "━━ QUESTIONS ━━\n"
        "1. YTD SUMMARY: Summarise total generation, savings, and CO₂ avoided. "
        "Is performance good for this system size and location?\n"
        "2. SEASONAL ANALYSIS: Compare summer vs winter performance. "
        "Were the summer months significantly better? "
        "What does this mean for expected performance going forward?\n"
        "3. TREND ANALYSIS: Is the system performing consistently month-over-month, "
        "or is there a degradation or improvement trend? "
        "Is battery efficiency ({ytd_avg_batt_efficiency_pct}% avg) stable?\n"
        "4. LOAD SHEDDING RESILIENCE: How well did the battery handle "
        "Pakistan's load shedding over the year? "
        "Are there months where coverage was inadequate?\n"
        "5. NEXT MONTH FORECAST: Based on the same calendar month in prior years "
        "(or seasonal patterns if first year), what generation and savings "
        "can the user expect next month?\n"
        "6. STRATEGIC RECOMMENDATIONS: 2–3 high-impact actions for the next "
        "12 months. Consider: panel cleaning schedule, battery reserve optimisation, "
        "EV charging strategy, potential system expansion, tariff optimisation.\n\n"
        "Call the `return_yearly_analysis` tool with your response."
    ),
}
