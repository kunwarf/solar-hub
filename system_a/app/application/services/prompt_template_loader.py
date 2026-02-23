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
            from ...infrastructure.cache.redis_cache import RedisManager
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
            from ...infrastructure.cache.redis_cache import RedisManager
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
            from ...infrastructure.cache.redis_cache import RedisManager
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
    # Variables supplied by AIInsightsService._claude_hourly():
    #   time_pkt, energy_today_kwh, peak_power_kw, load_power_w, grid_power_w,
    #   battery_power_w, avg_soc_pct, self_consumed_kwh, grid_import_today_kwh,
    #   grid_export_today_kwh, self_sufficiency_pct, co2_saved_kg, savings_pkr,
    #   import_rate_pkr, devices_online, devices_total, inverter_temp_line,
    #   battery_charge_today_kwh, battery_discharge_today_kwh,
    #   battery_hourly_charge_kwh, battery_hourly_discharge_kwh,
    #   system_alerts_block, load_shedding_block, warn_temp_c

    "hourly_system": (
        "You are an expert solar energy analyst for Pakistani residential and "
        "commercial solar installations. You generate concise, actionable insights "
        "for system owners.\n\n"
        "Write in clear English. Keep messages under 200 characters.\n"
        "Use Pakistani context: PKR currency, DISCO net metering, load shedding "
        "(bijli gul), Karachi/Lahore climate.\n"
        "Consider battery state-of-charge when recommending EV charging windows.\n"
        "If load shedding is predicted, recommend optimal battery charge level "
        "before the outage window."
    ),

    "hourly_user": (
        "Analyse the following real-time solar site data and generate insights.\n\n"
        "## Current Site Data ({time_pkt} PKT)\n"
        "- Solar generation today: {energy_today_kwh} kWh  |  Peak: {peak_power_kw} kW\n"
        "- Current load: {load_power_w} W\n"
        "- Current grid power: {grid_power_w} W  (positive=import, negative=export)\n"
        "- Current battery power: {battery_power_w} W  "
        "(positive=charging, negative=discharging)\n"
        "- Battery SoC: {avg_soc_pct}%\n"
        "- Self-consumed solar today: {self_consumed_kwh} kWh\n"
        "- Grid import today: {grid_import_today_kwh} kWh  |  "
        "Export: {grid_export_today_kwh} kWh\n"
        "- Self-sufficiency: {self_sufficiency_pct}%\n"
        "- CO\u2082 avoided: {co2_saved_kg} kg  |  "
        "Money saved: Rs. {savings_pkr} (@ Rs. {import_rate_pkr}/kWh)\n"
        "- Battery charged today: {battery_charge_today_kwh} kWh  |  "
        "Discharged: {battery_discharge_today_kwh} kWh\n"
        "- Devices online: {devices_online}/{devices_total}\n"
        "- {inverter_temp_line}\n\n"
        "## System Alerts\n"
        "{system_alerts_block}\n\n"
        "## Load Shedding Status & Prediction\n"
        "{load_shedding_block}\n\n"
        "## Solar Window (Pakistan)\n"
        "- Good solar generation: now until {solar_peak_end_pkt} "
        "({ev_hours_remaining}h remaining)\n"
        "- Current solar surplus available for EV: {solar_surplus_kw} kW\n\n"
        "## Instructions\n"
        "- Generate 2\u20134 daily_insights: generation performance, savings, "
        "self-sufficiency, load-shedding readiness, and one time-of-day tip.\n"
        "- EV charging window (include if battery > 70% SoC and solar surplus > 0.5 kW): "
        "state the specific window, e.g. 'now until {solar_peak_end_pkt} "
        "({ev_hours_remaining}h, {solar_surplus_kw} kW surplus). "
        "Enough for ~X kWh before solar ends.' Calculate X from surplus × hours.\n"
        "- Generate anomaly_alerts ONLY for real problems (low generation during "
        "daylight, very low battery, devices offline, high temperature, "
        "predicted outage with low battery).\n"
        "- If inverter temperature \u2265 {warn_temp_c}\u00b0C, include an overheating alert.\n"
        "- If an outage is predicted in the next 2\u20134 hours and SoC < 60%, "
        "warn the user to let the battery charge.\n"
        "- Be specific with numbers. Avoid filler text.\n"
        "- Call the `return_insights` tool with your response."
    ),

    # =============================================================== MONTHLY
    # Variables supplied by AIInsightsService._claude_monthly():
    #   billing_month, days_elapsed, total_pv_kwh, total_load_kwh,
    #   total_import_kwh, total_export_kwh, self_sufficiency_pct, savings_pkr,
    #   import_rate_pkr, outage_hours, outage_events, chart_snippet

    "monthly_system": (
        "You are an expert solar energy analyst preparing a monthly performance "
        "report for a Pakistani solar installation.\n\n"
        "Write in clear English. Use Pakistani context (PKR, DISCO, load shedding, "
        "seasonal patterns).\n"
        "Be analytical and specific. Reference actual numbers from the data provided.\n"
        "Focus on actionable improvements for the next billing month."
    ),

    "monthly_user": (
        "Generate a CONCISE monthly analysis for {billing_month} ({days_elapsed} days).\n"
        "Be brief: summary ≤ 2 sentences, highlights exactly 3 bullets (≤15 words each), "
        "recommendations exactly 2 bullets (≤15 words each).\n\n"
        "## Monthly Energy Summary\n"
        "- Solar: {total_pv_kwh} kWh  |  Load: {total_load_kwh} kWh\n"
        "- Grid import: {total_import_kwh} kWh  |  Export: {total_export_kwh} kWh\n"
        "- Self-sufficiency: {self_sufficiency_pct}%  |  Saved: Rs. {savings_pkr} "
        "(@ Rs. {import_rate_pkr}/kWh)\n\n"
        "## Load Shedding\n"
        "- {outage_hours}h across {outage_events} events\n\n"
        "## Daily Breakdown (last 10 days)\n"
        "{chart_snippet}\n\n"
        "Call the `return_monthly_analysis` tool with your analysis."
    ),

    # ================================================================ YEARLY
    # Variables supplied by AIInsightsService._claude_yearly():
    #   year, month_label, total_pv_kwh, total_load_kwh, total_import_kwh,
    #   total_export_kwh, self_sufficiency_pct, savings_pkr, co2_saved_kg,
    #   import_rate_pkr, chart_snippet

    "yearly_system": (
        "You are an expert solar energy analyst preparing a year-to-date "
        "performance review for a Pakistani solar installation.\n\n"
        "Write in clear English. Use Pakistani context (PKR, DISCO net metering, "
        "seasonal monsoon/winter patterns).\n"
        "Be strategic. Identify long-term trends, ROI progress, and seasonal patterns.\n"
        "Compare months and identify the best/worst performing periods."
    ),

    "yearly_user": (
        "Generate a CONCISE year-to-date analysis as of {month_label}.\n"
        "Be brief: summary ≤ 2 sentences, best/worst month ≤ 15 words each, "
        "trends exactly 3 bullets (≤15 words each), recommendations exactly 2 bullets (≤15 words each).\n\n"
        "## Year-to-Date ({year})\n"
        "- Solar: {total_pv_kwh} kWh  |  Load: {total_load_kwh} kWh\n"
        "- Grid import: {total_import_kwh} kWh  |  Export: {total_export_kwh} kWh\n"
        "- Self-sufficiency: {self_sufficiency_pct}%  |  Saved: Rs. {savings_pkr} "
        "(@ Rs. {import_rate_pkr}/kWh)  |  CO\u2082: {co2_saved_kg} kg\n\n"
        "## Recent Monthly Breakdown\n"
        "{chart_snippet}\n\n"
        "Call the `return_yearly_analysis` tool with your analysis."
    ),
}
