"""add AI insights tables

Revision ID: 20260223_ai01
Revises: a1b2c3d4e5f6
Create Date: 2026-02-23 00:01:00.000000+00:00

Adds four tables that form the AI Intelligence layer:

  grid_outages              – detected grid outage events (per-site, auto-detected
                              from telemetry). Used for load-shedding pattern analysis
                              and daily predictions.

  ai_insights_log           – persists every Claude-generated (or rule-based) insight
                              result, keyed by site + tier + period. Enables:
                                • historical browsing of AI output
                                • feeding prior anomalies as context to monthly/yearly calls
                                • auditing what Claude was told and what it replied

  ai_prompt_templates       – admin-editable prompt templates for each Claude call
                              tier (hourly / monthly / yearly) and type (system / user).
                              The service loads these at runtime (Redis cache, 5-min TTL)
                              and falls back to hardcoded defaults if DB is unavailable.

  ai_prompt_template_versions – full audit trail of every edit to a prompt template,
                              allowing admins to diff and revert changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "20260223_ai01"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1.  grid_outages
    #
    #     One row per detected grid outage event for a site.
    #     started_at / ended_at are stored in UTC; the PKT-derived
    #     convenience columns (day_of_week, started_hour_pkt, etc.) are
    #     pre-computed on insert to make the pattern-analysis query fast.
    # -----------------------------------------------------------------------
    op.create_table(
        "grid_outages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        # FK to sites
        sa.Column("site_id", UUID(as_uuid=True),
                  sa.ForeignKey("sites.id", ondelete="CASCADE"),
                  nullable=False),

        # Timing (UTC)
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),   # filled on end

        # PKT convenience columns for fast pattern queries
        # (PKT = UTC+5, no DST)
        sa.Column("day_of_week",      sa.SmallInteger, nullable=False),   # 0=Mon..6=Sun
        sa.Column("week_of_year",     sa.SmallInteger, nullable=False),
        sa.Column("month_pkt",        sa.SmallInteger, nullable=False),   # 1-12
        sa.Column("started_hour_pkt", sa.SmallInteger, nullable=False),   # 0-23
        sa.Column("ended_hour_pkt",   sa.SmallInteger, nullable=True),

        # Source / quality flags
        sa.Column("detected_by_serial", sa.String(100), nullable=True),
        sa.Column("was_predicted",      sa.Boolean, nullable=False,
                  server_default=sa.text("false")),

        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_outages_site_time",
                    "grid_outages", ["site_id", "started_at"],
                    postgresql_using="btree")
    op.create_index("idx_outages_site_pattern",
                    "grid_outages", ["site_id", "day_of_week", "started_hour_pkt"],
                    postgresql_using="btree")
    # BRIN is efficient for append-only, monotonically increasing timestamps
    op.create_index("idx_outages_started_brin",
                    "grid_outages", ["started_at"],
                    postgresql_using="brin")

    # -----------------------------------------------------------------------
    # 2.  ai_insights_log
    #
    #     Persists every AI insight generation result (Claude or rule-based).
    #     Tier values: 'hourly' | 'monthly' | 'yearly'
    #     The input_stats column stores the exact data block sent to Claude
    #     so we can reproduce or debug results.
    # -----------------------------------------------------------------------
    op.create_table(
        "ai_insights_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        sa.Column("site_id", UUID(as_uuid=True),
                  sa.ForeignKey("sites.id", ondelete="CASCADE"),
                  nullable=False),

        # Classification
        sa.Column("tier",  sa.String(20), nullable=False),   # hourly|monthly|yearly
        sa.Column("model", sa.String(100), nullable=False),  # claude model id or 'rule-based'

        # Time period this result covers
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end",   sa.DateTime(timezone=True), nullable=True),

        # For monthly / yearly: first day of the billing month (in PKT)
        sa.Column("billing_month", sa.Date, nullable=True),

        # Claude output – parsed and stored as JSONB
        sa.Column("daily_insights",  JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("anomaly_alerts",  JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("monthly_analysis", JSONB, nullable=True),  # monthly tier only
        sa.Column("yearly_analysis",  JSONB, nullable=True),  # yearly  tier only

        # Exact data snapshot sent to Claude (for debugging + future context)
        sa.Column("input_stats", JSONB, nullable=False),

        # Redis cache key used for this result
        sa.Column("cache_key", sa.String(200), nullable=True),

        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ai_log_site_tier_time",
                    "ai_insights_log", ["site_id", "tier", "generated_at"],
                    postgresql_using="btree")
    op.create_index("idx_ai_log_site_billing",
                    "ai_insights_log", ["site_id", "billing_month"],
                    postgresql_using="btree")
    op.create_index("idx_ai_log_generated_brin",
                    "ai_insights_log", ["generated_at"],
                    postgresql_using="brin")

    # -----------------------------------------------------------------------
    # 3.  ai_prompt_templates
    #
    #     Admin-editable prompts for each call tier and type.
    #     Key naming convention:  '<tier>_<type>'
    #       e.g. 'hourly_system', 'hourly_user',
    #            'monthly_system', 'monthly_user',
    #            'yearly_system',  'yearly_user'
    #
    #     Templates use Python str.format_map() placeholders: {variable_name}
    #     The variables column is a JSON array describing each placeholder
    #     so the admin UI can show a reference panel.
    # -----------------------------------------------------------------------
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        # Unique business key – the service looks up by this
        sa.Column("key", sa.String(100), nullable=False, unique=True),

        # Classification
        sa.Column("tier",        sa.String(20), nullable=False),  # hourly|monthly|yearly
        sa.Column("prompt_type", sa.String(20), nullable=False),  # system|user

        # Human-readable
        sa.Column("name",        sa.String(200), nullable=False),
        sa.Column("description", sa.Text,        nullable=True),

        # The template text with {variable} placeholders
        sa.Column("template", sa.Text, nullable=False),

        # Variable manifest for admin UI reference panel
        # JSON array: [{"name":"pv_power_w","type":"number","description":"..."}]
        sa.Column("variables", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),

        # Target model (informational)
        sa.Column("model",      sa.String(100), nullable=True),
        sa.Column("max_tokens", sa.Integer,     nullable=True),

        # Versioning
        sa.Column("version",   sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),

        # Audit
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_prompt_templates_key",
                    "ai_prompt_templates", ["key"],
                    postgresql_using="btree")
    op.create_index("idx_prompt_templates_tier",
                    "ai_prompt_templates", ["tier", "prompt_type"],
                    postgresql_using="btree")

    # -----------------------------------------------------------------------
    # 4.  ai_prompt_template_versions
    #
    #     Immutable audit trail – one row per admin save on any template.
    #     Allows diffing and reverting to any prior version.
    # -----------------------------------------------------------------------
    op.create_table(
        "ai_prompt_template_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("ai_prompt_templates.id", ondelete="CASCADE"),
                  nullable=False),

        # Snapshot of the template text and variables at this version
        sa.Column("version",   sa.Integer, nullable=False),
        sa.Column("template",  sa.Text,    nullable=False),
        sa.Column("variables", JSONB,      nullable=False),

        # Who changed it and why
        sa.Column("changed_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("change_note", sa.Text, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("idx_prompt_versions_template",
                    "ai_prompt_template_versions", ["template_id", "version"],
                    postgresql_using="btree")

    # -----------------------------------------------------------------------
    # 5.  Seed the six default prompt templates
    #
    #     These are the finalized prompts from the requirements design session.
    #     Admins can edit them via /admin/ai-prompts without any code change.
    #     The service always falls back to hardcoded defaults if the table
    #     is empty or unreachable.
    # -----------------------------------------------------------------------
    _seed_prompt_templates()


def _seed_prompt_templates() -> None:
    """Insert the six default prompt templates."""

    connection = op.get_bind()

    templates = _get_default_templates()
    for t in templates:
        connection.execute(sa.text("""
            INSERT INTO ai_prompt_templates
                (id, key, tier, prompt_type, name, description, template,
                 variables, model, max_tokens, version, is_active, created_at)
            VALUES
                (gen_random_uuid(), :key, :tier, :prompt_type, :name,
                 :description, :template, CAST(:variables AS jsonb),
                 :model, :max_tokens, 1, true, NOW())
            ON CONFLICT (key) DO NOTHING
        """), t)


def _get_default_templates() -> list:
    import json
    return [
        # ------------------------------------------------------------------ #
        # HOURLY — SYSTEM                                                      #
        # ------------------------------------------------------------------ #
        dict(
            key="hourly_system",
            tier="hourly",
            prompt_type="system",
            name="Hourly Insights — System Prompt",
            description=(
                "Sets Claude's role and output constraints for real-time "
                "hourly snapshot analysis. Instructs it to be concise, "
                "data-specific, and Pakistan-context aware."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "system_type", "type": "string",
                 "default": "residential and commercial",
                 "description": "Type of solar installation"},
                {"name": "max_chars", "type": "number", "default": "200",
                 "description": "Maximum characters per insight message field"},
                {"name": "city", "type": "string", "default": "Karachi/Lahore",
                 "description": "City for climate and load-shedding context"},
                {"name": "current_datetime", "type": "string",
                 "description": "Auto-filled: current PKT datetime string"},
            ]),
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
        ),

        # ------------------------------------------------------------------ #
        # HOURLY — USER                                                        #
        # ------------------------------------------------------------------ #
        dict(
            key="hourly_user",
            tier="hourly",
            prompt_type="user",
            name="Hourly Insights — Data Prompt",
            description=(
                "The full real-time telemetry block sent to Claude on every "
                "hourly call. Includes power snapshot, today's energy, battery "
                "kWh charged/discharged, system alerts, load-shedding prediction, "
                "and EV charging context."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "pv_power_w", "type": "number", "description": "Current PV power (W)"},
                {"name": "load_power_w", "type": "number", "description": "Current load (W)"},
                {"name": "solar_surplus_w", "type": "number",
                 "description": "PV - load surplus (W), positive = excess solar"},
                {"name": "grid_power_w", "type": "number",
                 "description": "Grid power (W), positive=import, negative=export"},
                {"name": "battery_power_w", "type": "number",
                 "description": "Battery power (W), positive=charging"},
                {"name": "battery_soc_pct", "type": "number",
                 "description": "Battery state of charge (%)"},
                {"name": "energy_today_kwh", "type": "number",
                 "description": "Solar energy generated today (kWh)"},
                {"name": "peak_power_kw", "type": "number",
                 "description": "Peak PV power today (kW)"},
                {"name": "grid_import_today_kwh", "type": "number",
                 "description": "Grid energy imported today (kWh)"},
                {"name": "grid_export_today_kwh", "type": "number",
                 "description": "Grid energy exported today (kWh)"},
                {"name": "battery_charge_today_kwh", "type": "number",
                 "description": "Battery energy charged today (kWh)"},
                {"name": "battery_discharge_today_kwh", "type": "number",
                 "description": "Battery energy discharged today (kWh)"},
                {"name": "self_consumed_kwh", "type": "number",
                 "description": "Solar self-consumed today (kWh)"},
                {"name": "self_sufficiency_pct", "type": "number",
                 "description": "Self-sufficiency percentage today"},
                {"name": "savings_pkr", "type": "number",
                 "description": "Money saved today (PKR)"},
                {"name": "import_rate_pkr", "type": "number",
                 "description": "Grid import rate (PKR/kWh)"},
                {"name": "co2_saved_kg", "type": "number",
                 "description": "CO2 avoided today (kg)"},
                {"name": "devices_online", "type": "number",
                 "description": "Number of devices online"},
                {"name": "devices_total", "type": "number",
                 "description": "Total number of devices"},
                {"name": "inverter_temp_c", "type": "number",
                 "description": "Max inverter temperature (°C)"},
                {"name": "system_alerts_block", "type": "string",
                 "description": "Auto-rendered: active faults and warnings from device status"},
                {"name": "ls_history_days", "type": "number",
                 "description": "Days of outage history used for prediction (e.g. 60)"},
                {"name": "load_shedding_block", "type": "string",
                 "description": "Auto-rendered: predicted LS windows with confidence scores"},
                {"name": "solar_hours_remaining", "type": "number",
                 "description": "Estimated hours until sunset"},
                {"name": "battery_headroom_kwh", "type": "number",
                 "description": "kWh available above the 20% battery reserve"},
                {"name": "current_time", "type": "string",
                 "description": "Auto-filled: current time string HH:MM PKT"},
                {"name": "recent_anomalies_block", "type": "string",
                 "description": "Auto-rendered: last 24h anomaly log from ai_insights_log"},
            ]),
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
        ),

        # ------------------------------------------------------------------ #
        # MONTHLY — SYSTEM                                                     #
        # ------------------------------------------------------------------ #
        dict(
            key="monthly_system",
            tier="monthly",
            prompt_type="system",
            name="Monthly Analysis — System Prompt",
            description=(
                "Sets Claude's role for the once-per-day billing-month analysis. "
                "Instructs it to act as a solar financial analyst with deep "
                "Pakistan grid and billing context."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "city", "type": "string", "default": "Karachi/Lahore",
                 "description": "City for climate context"},
                {"name": "current_date", "type": "string",
                 "description": "Auto-filled: current date YYYY-MM-DD PKT"},
            ]),
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
        ),

        # ------------------------------------------------------------------ #
        # MONTHLY — USER                                                       #
        # ------------------------------------------------------------------ #
        dict(
            key="monthly_user",
            tier="monthly",
            prompt_type="user",
            name="Monthly Analysis — Data Prompt",
            description=(
                "Billing-month data block: daily PV/load/import/export/battery "
                "breakdown, MTD totals, load-shedding stats, recurring anomalies "
                "from the AI log, and five structured questions."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "billing_month_start", "type": "string",
                 "description": "First day of billing month (e.g. '1 Feb 2026')"},
                {"name": "billing_month_today", "type": "string",
                 "description": "Today's date within the billing month"},
                {"name": "days_elapsed", "type": "number",
                 "description": "Days elapsed in billing month"},
                {"name": "days_in_month", "type": "number",
                 "description": "Total days in billing month"},
                {"name": "days_remaining", "type": "number",
                 "description": "Days remaining in billing month"},
                {"name": "import_rate_pkr", "type": "number",
                 "description": "Grid import rate (PKR/kWh)"},
                {"name": "daily_breakdown_table", "type": "string",
                 "description": "Auto-rendered: pipe-separated table of daily data"},
                {"name": "mtd_pv_kwh", "type": "number",
                 "description": "Total PV generated MTD (kWh)"},
                {"name": "mtd_load_kwh", "type": "number",
                 "description": "Total load MTD (kWh)"},
                {"name": "mtd_import_kwh", "type": "number",
                 "description": "Total grid import MTD (kWh)"},
                {"name": "mtd_export_kwh", "type": "number",
                 "description": "Total grid export MTD (kWh)"},
                {"name": "mtd_batt_charge_kwh", "type": "number",
                 "description": "Total battery charged MTD (kWh)"},
                {"name": "mtd_batt_discharge_kwh", "type": "number",
                 "description": "Total battery discharged MTD (kWh)"},
                {"name": "batt_efficiency_pct", "type": "number",
                 "description": "Battery round-trip efficiency % (discharge/charge × 100)"},
                {"name": "self_sufficiency_pct", "type": "number",
                 "description": "Self-sufficiency % for the month"},
                {"name": "savings_pkr", "type": "number",
                 "description": "Money saved MTD (PKR)"},
                {"name": "co2_kg", "type": "number",
                 "description": "CO2 avoided MTD (kg)"},
                {"name": "best_day_date", "type": "string",
                 "description": "Date of highest generation day"},
                {"name": "best_day_kwh", "type": "number",
                 "description": "kWh on best generation day"},
                {"name": "worst_day_date", "type": "string",
                 "description": "Date of lowest generation day"},
                {"name": "worst_day_kwh", "type": "number",
                 "description": "kWh on worst generation day"},
                {"name": "daily_avg_kwh", "type": "number",
                 "description": "Average daily generation so far (kWh)"},
                {"name": "ls_total_hours", "type": "number",
                 "description": "Total load shedding hours this billing month"},
                {"name": "ls_event_count", "type": "number",
                 "description": "Number of outage events this billing month"},
                {"name": "ls_covered_hours", "type": "number",
                 "description": "Hours battery covered outages"},
                {"name": "ls_covered_pct", "type": "number",
                 "description": "Percentage of outage hours covered by battery"},
                {"name": "ls_uncovered_hours", "type": "number",
                 "description": "Outage hours not covered by battery"},
                {"name": "ls_worst_day", "type": "string",
                 "description": "Date of worst load-shedding day"},
                {"name": "ls_worst_hours", "type": "number",
                 "description": "Hours of outage on worst LS day"},
                {"name": "ls_worst_covered_pct", "type": "number",
                 "description": "Battery coverage % on worst LS day"},
                {"name": "ls_full_coverage_days", "type": "number",
                 "description": "Days with 100% battery coverage of outages"},
                {"name": "recent_anomaly_log", "type": "string",
                 "description": "Auto-rendered: anomaly titles from last 30 ai_insights_log rows"},
                {"name": "system_alerts_month", "type": "string",
                 "description": "Auto-rendered: device fault/warning events this month"},
            ]),
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
        ),

        # ------------------------------------------------------------------ #
        # YEARLY — SYSTEM                                                      #
        # ------------------------------------------------------------------ #
        dict(
            key="yearly_system",
            tier="yearly",
            prompt_type="system",
            name="Yearly Analysis — System Prompt",
            description=(
                "Sets Claude's role for the once-per-month year-to-date strategic "
                "review. Instructs it to focus on seasonal patterns, ROI, "
                "and long-term recommendations."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "city", "type": "string", "default": "Karachi/Lahore",
                 "description": "City for climate and seasonal context"},
                {"name": "current_date", "type": "string",
                 "description": "Auto-filled: current date YYYY-MM-DD PKT"},
            ]),
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
        ),

        # ------------------------------------------------------------------ #
        # YEARLY — USER                                                        #
        # ------------------------------------------------------------------ #
        dict(
            key="yearly_user",
            tier="yearly",
            prompt_type="user",
            name="Yearly Analysis — Data Prompt",
            description=(
                "Year-to-date data block: monthly breakdown of PV/load/import/export/"
                "battery/LS/savings, YTD totals, recurring anomalies from the "
                "monthly AI log, and six strategic questions."
            ),
            template=(
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
            variables=json.dumps([
                {"name": "ytd_period_label", "type": "string",
                 "description": "e.g. 'Jan 2026 – Feb 2026'"},
                {"name": "months_available", "type": "number",
                 "description": "Number of billing months with data"},
                {"name": "monthly_breakdown_table", "type": "string",
                 "description": "Auto-rendered: pipe-separated table of monthly data"},
                {"name": "ytd_pv_kwh", "type": "number",
                 "description": "Total PV generated year-to-date (kWh)"},
                {"name": "ytd_load_kwh", "type": "number",
                 "description": "Total load year-to-date (kWh)"},
                {"name": "ytd_import_kwh", "type": "number",
                 "description": "Total grid import year-to-date (kWh)"},
                {"name": "ytd_export_kwh", "type": "number",
                 "description": "Total grid export year-to-date (kWh)"},
                {"name": "ytd_savings_pkr", "type": "number",
                 "description": "Total money saved year-to-date (PKR)"},
                {"name": "ytd_co2_kg", "type": "number",
                 "description": "Total CO2 avoided year-to-date (kg)"},
                {"name": "ytd_self_sufficiency_pct", "type": "number",
                 "description": "Average self-sufficiency % year-to-date"},
                {"name": "best_month_label", "type": "string",
                 "description": "Name of best generation month"},
                {"name": "best_month_kwh", "type": "number",
                 "description": "kWh in best month"},
                {"name": "worst_month_label", "type": "string",
                 "description": "Name of worst generation month"},
                {"name": "worst_month_kwh", "type": "number",
                 "description": "kWh in worst month"},
                {"name": "avg_monthly_kwh", "type": "number",
                 "description": "Average monthly generation (kWh)"},
                {"name": "ytd_ls_hours", "type": "number",
                 "description": "Total load shedding hours year-to-date"},
                {"name": "ytd_ls_coverage_pct", "type": "number",
                 "description": "Battery coverage % of outages year-to-date"},
                {"name": "ls_worst_month_label", "type": "string",
                 "description": "Month with most load shedding"},
                {"name": "ls_worst_month_hours", "type": "number",
                 "description": "Outage hours in worst month"},
                {"name": "monthly_ai_summaries", "type": "string",
                 "description": "Auto-rendered: monthly_analysis.mtd_summary from DB log"},
                {"name": "recurring_anomalies", "type": "string",
                 "description": "Auto-rendered: anomalies appearing 3+ times in hourly logs"},
                {"name": "ytd_avg_batt_efficiency_pct", "type": "number",
                 "description": "Average battery round-trip efficiency year-to-date (%)"},
            ]),
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
        ),
    ]


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("ai_prompt_template_versions")
    op.drop_table("ai_prompt_templates")
    op.drop_table("ai_insights_log")
    op.drop_table("grid_outages")

    # NOTE: PostgreSQL does not allow removing enum values once added,
    # so no enum cleanup is needed here (no new enums were created).
