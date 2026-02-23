"""
AI Chat Service.

Answers free-form user questions about their solar system using real telemetry.
When AI_API_KEY is configured, Claude (claude-haiku) produces context-aware answers.
Falls back to a deterministic rule-based summary otherwise.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...config import settings
from ...infrastructure.cache.telemetry_cache import TelemetryCacheReader
from ...infrastructure.external.system_b_client import SystemBClient

logger = logging.getLogger(__name__)

# Pakistan Standard Time
_PKT = timezone(timedelta(hours=5))

# Carbon intensity (kg CO2/kWh) — Pakistan grid
CO2_KG_PER_KWH = 0.7


class AIChatService:
    """
    Answers free-form questions about a solar site using real telemetry data.

    Data sources:
    - Real-time: Redis (TelemetryCacheReader)
    - Historical: System B energy chart (7-day)

    Claude is used when AI_API_KEY is set; rule-based summary otherwise.
    """

    def __init__(
        self,
        telemetry_cache: TelemetryCacheReader,
        system_b_client: SystemBClient,
    ):
        self._cache = telemetry_cache
        self._system_b = system_b_client
        self._claude = None
        self._init_claude()

    def _init_claude(self) -> None:
        api_key = settings.ai.api_key
        if not api_key:
            logger.debug("AI_API_KEY not set — chat will use rule-based fallback.")
            return
        try:
            import anthropic  # type: ignore
            self._claude = anthropic.AsyncAnthropic(api_key=api_key)
            logger.info("AIChatService: Claude client initialised (model=%s).", settings.ai.model)
        except ImportError:
            logger.warning("anthropic package not installed — run: pip install anthropic>=0.40.0")

    # =========================================================================
    # Public API
    # =========================================================================

    async def chat(
        self,
        message: str,
        site_id: UUID,
        device_serials: List[str],
        site_name: str,
        import_rate_pkr: float = 35.0,
    ) -> str:
        """
        Answer a free-form question about the solar site.

        Returns a plain-text reply (no markdown).
        """
        now_pkt = datetime.now(timezone.utc).astimezone(_PKT)
        stats = await self._gather_site_stats(device_serials)

        logger.info(
            "[chat] site=%s message=%r pv=%.0fW soc=%.0f%% energy=%.1fkWh",
            site_id, message[:80],
            stats["pv_power_w"], stats["avg_soc_pct"], stats["energy_today_kwh"],
        )

        if self._claude and settings.ai.enabled:
            try:
                reply = await self._ask_claude(message, stats, now_pkt, site_name, import_rate_pkr)
                logger.info("[chat] Claude replied for site=%s", site_id)
                return reply
            except Exception as exc:
                logger.warning("[chat] Claude failed for site=%s (%s) — using fallback.", site_id, exc)

        return self._rule_based_reply(message, stats, now_pkt, import_rate_pkr)

    # =========================================================================
    # Data gathering
    # =========================================================================

    async def _gather_site_stats(self, device_serials: List[str]) -> Dict[str, Any]:
        """Aggregate real-time stats from Redis across all site devices."""
        total_pv_w = 0.0
        total_load_w = 0.0
        total_grid_w = 0.0
        total_battery_w = 0.0
        total_energy_kwh = 0.0
        total_import_kwh = 0.0
        total_export_kwh = 0.0
        total_soc = 0.0
        soc_count = 0
        max_temp_c = 0.0
        devices_online = 0
        devices_total = len(device_serials)

        for serial in device_serials:
            telemetry = await self._cache.get_telemetry(serial)
            status = await self._cache.get_status(serial)

            if status == "online":
                devices_online += 1
            if not telemetry:
                continue

            power = telemetry.get("power", {})
            energy = telemetry.get("energy_today", {})
            battery = telemetry.get("battery", {})
            raw = telemetry.get("raw", {})
            temps = telemetry.get("temperatures", {})

            total_pv_w += float(power.get("pv_total_w", 0) or 0)
            total_load_w += float(power.get("load_w", 0) or 0)
            total_grid_w += float(power.get("grid_w", 0) or 0)
            total_battery_w += float(power.get("battery_w", 0) or 0)
            total_energy_kwh += float(energy.get("pv_kwh", 0) or 0)
            total_import_kwh += float(raw.get("grid_import_energy_today_kwh", 0) or 0)
            total_export_kwh += float(raw.get("grid_export_energy_today_kwh", 0) or 0)

            soc = float(battery.get("soc_pct", 0) or 0)
            if soc > 0:
                total_soc += soc
                soc_count += 1

            inv_temp = float(temps.get("inverter_c") or raw.get("inverter_temp_c") or 0)
            hs_temp = float(raw.get("heat_sink_temp_c") or 0)
            max_temp_c = max(max_temp_c, inv_temp, hs_temp)

        avg_soc = total_soc / soc_count if soc_count > 0 else 0.0
        self_consumed_kwh = max(0.0, total_energy_kwh - total_export_kwh)
        self_sufficiency_pct = (
            self_consumed_kwh / total_energy_kwh * 100
            if total_energy_kwh > 0 else 0.0
        )

        return {
            "pv_power_w": total_pv_w,
            "load_power_w": total_load_w,
            "grid_power_w": total_grid_w,
            "battery_power_w": total_battery_w,
            "energy_today_kwh": total_energy_kwh,
            "grid_import_today_kwh": total_import_kwh,
            "grid_export_today_kwh": total_export_kwh,
            "avg_soc_pct": avg_soc,
            "self_consumed_kwh": self_consumed_kwh,
            "self_sufficiency_pct": self_sufficiency_pct,
            "max_inverter_temp_c": max_temp_c,
            "co2_saved_kg": total_energy_kwh * CO2_KG_PER_KWH,
            "devices_online": devices_online,
            "devices_total": devices_total,
        }

    # =========================================================================
    # Claude
    # =========================================================================

    async def _ask_claude(
        self,
        message: str,
        stats: Dict[str, Any],
        now: datetime,
        site_name: str,
        import_rate_pkr: float,
    ) -> str:
        savings_pkr = round(stats["self_consumed_kwh"] * import_rate_pkr)
        grid_w = stats["grid_power_w"]
        grid_status = f"exporting {abs(grid_w):.0f} W to grid" if grid_w < 0 else f"importing {grid_w:.0f} W from grid"
        batt_w = stats["battery_power_w"]
        batt_status = f"charging at {abs(batt_w):.0f} W" if batt_w > 0 else f"discharging at {abs(batt_w):.0f} W"
        temp_c = stats["max_inverter_temp_c"]
        temp_note = ""
        if temp_c > 0:
            temp_note = f"\n- Inverter temperature: {temp_c:.0f}°C"
            if temp_c > 100:
                temp_note += " (may be a sensor scaling artifact — verify physically)"

        system_prompt = (
            "You are the Solar Hub assistant for a Pakistani solar installation. "
            "You have access to real-time data for the user's system. "
            "Answer the user's question in 2-4 sentences of plain text — no markdown, no bullet points, no bold. "
            "Be specific with numbers from the data provided. "
            "Use Pakistani context: PKR currency, DISCO net metering, load shedding."
        )

        user_prompt = (
            f"Site: {site_name}\n"
            f"Time: {now.strftime('%H:%M')} PKT\n\n"
            f"Real-time system data:\n"
            f"- Solar generation today: {stats['energy_today_kwh']:.1f} kWh\n"
            f"- Current PV power: {stats['pv_power_w']:.0f} W\n"
            f"- Current load: {stats['load_power_w']:.0f} W\n"
            f"- Grid: {grid_status}\n"
            f"- Battery: {stats['avg_soc_pct']:.0f}% SoC, {batt_status}\n"
            f"- Self-sufficiency today: {stats['self_sufficiency_pct']:.0f}%\n"
            f"- Money saved today: Rs. {savings_pkr:,} (at Rs. {import_rate_pkr}/kWh)\n"
            f"- CO2 avoided: {stats['co2_saved_kg']:.1f} kg\n"
            f"- Devices online: {stats['devices_online']} / {stats['devices_total']}"
            f"{temp_note}\n\n"
            f"User question: {message}"
        )

        response = await self._claude.messages.create(
            model=settings.ai.model,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text.strip()

    # =========================================================================
    # Rule-based fallback
    # =========================================================================

    def _rule_based_reply(
        self,
        message: str,
        stats: Dict[str, Any],
        now: datetime,
        import_rate_pkr: float,
    ) -> str:
        """Return a plain-text answer based on keyword matching and real stats."""
        msg = message.lower()
        soc = stats["avg_soc_pct"]
        pv = stats["pv_power_w"]
        grid = stats["grid_power_w"]
        energy = stats["energy_today_kwh"]
        savings = round(stats["self_consumed_kwh"] * import_rate_pkr)
        hour = now.hour

        if any(w in msg for w in ["battery", "charge", "soc", "backup", "health"]):
            if soc >= 80:
                return (
                    f"Your battery is in great shape at {soc:.0f}% SoC. "
                    f"It is currently {'charging' if stats['battery_power_w'] > 0 else 'providing backup power'}. "
                    f"You have plenty of reserve for evening load shedding."
                )
            elif soc >= 40:
                return (
                    f"Your battery is at {soc:.0f}% SoC — healthy operating range. "
                    f"It will continue to charge during peak solar hours."
                )
            else:
                return (
                    f"Your battery is low at {soc:.0f}% SoC. "
                    f"Try to reduce non-essential loads until it recharges during daylight."
                )

        if any(w in msg for w in ["generat", "produc", "solar", "kwh", "how much"]):
            return (
                f"Your system has generated {energy:.1f} kWh of solar energy today. "
                f"It is currently producing {pv:.0f} W. "
                f"{'Great conditions for solar right now!' if 9 <= hour <= 15 else 'Solar output will peak around midday.'}"
            )

        if any(w in msg for w in ["sav", "money", "cost", "bill", "rupee", "pkr", "rs"]):
            return (
                f"You have saved Rs. {savings:,} today by consuming solar instead of grid power. "
                f"Your self-sufficiency is {stats['self_sufficiency_pct']:.0f}% today, "
                f"meaning {stats['self_sufficiency_pct']:.0f}% of your energy needs are met by solar."
            )

        if any(w in msg for w in ["grid", "export", "import", "net meter"]):
            if grid < 0:
                return (
                    f"You are currently exporting {abs(grid):.0f} W to the grid — "
                    f"earning net metering credit from your DISCO. "
                    f"Total exported today: {stats['grid_export_today_kwh']:.1f} kWh."
                )
            else:
                return (
                    f"You are currently importing {grid:.0f} W from the grid. "
                    f"Total imported today: {stats['grid_import_today_kwh']:.1f} kWh."
                )

        if any(w in msg for w in ["temperatur", "hot", "overheat"]):
            temp = stats["max_inverter_temp_c"]
            if temp > 0:
                note = " Note: readings above 100°C may indicate a sensor issue — verify physically." if temp > 100 else ""
                return f"The inverter temperature is {temp:.0f}°C.{note}"
            return "Temperature data is not available right now."

        # Generic summary
        return (
            f"Your solar system is online and generating {pv:.0f} W right now. "
            f"Today's total generation is {energy:.1f} kWh, saving Rs. {savings:,}. "
            f"Battery is at {soc:.0f}% SoC and you are "
            f"{'exporting' if grid < 0 else 'importing'} {abs(grid):.0f} W {'to' if grid < 0 else 'from'} the grid."
        )
