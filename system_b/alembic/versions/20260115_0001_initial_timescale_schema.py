"""Initial TimescaleDB schema for System B.

Revision ID: 0001
Revises:
Create Date: 2026-01-15

Creates all tables for telemetry storage in TimescaleDB:
- device_registry: Device management
- telemetry_raw: Raw telemetry hypertable
- device_events: Device events hypertable
- device_commands: Command queue
- metric_definitions: Standard metrics
- ingestion_batches: Batch tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Enable uuid-ossp extension
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    # Create device_registry table
    op.create_table(
        "device_registry",
        sa.Column("device_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=False, unique=True),
        sa.Column("auth_token_hash", sa.String(255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(20), nullable=False, default="disconnected"),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconnect_count", sa.Integer, default=0),
        sa.Column("protocol", sa.String(50), nullable=True),
        sa.Column("connection_config", JSONB, nullable=True),
        sa.Column("polling_interval_seconds", sa.Integer, default=60),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_device_registry_status", "device_registry", ["connection_status"])
    op.create_index("idx_device_registry_next_poll", "device_registry", ["next_poll_at"])

    # Create telemetry_raw table
    op.create_table(
        "telemetry_raw",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("metric_value_str", sa.String(255), nullable=True),
        sa.Column("quality", sa.String(20), nullable=False, server_default="good"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("raw_value", sa.LargeBinary, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("time", "device_id", "metric_name"),
    )

    # Convert telemetry_raw to hypertable
    op.execute("""
        SELECT create_hypertable(
            'telemetry_raw',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes on telemetry_raw
    op.create_index("idx_telemetry_raw_device_time", "telemetry_raw", ["device_id", "time"])
    op.create_index("idx_telemetry_raw_site_time", "telemetry_raw", ["site_id", "time"])
    op.create_index("idx_telemetry_raw_metric", "telemetry_raw", ["metric_name", "time"])
    op.create_index("idx_telemetry_raw_device_metric", "telemetry_raw", ["device_id", "metric_name", "time"])

    # Create device_events table
    op.create_table(
        "device_events",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_code", sa.String(50), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("time", "device_id", "event_type"),
    )

    # Convert device_events to hypertable
    op.execute("""
        SELECT create_hypertable(
            'device_events',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes on device_events
    op.create_index("idx_device_events_device", "device_events", ["device_id", "time"])
    op.create_index("idx_device_events_site", "device_events", ["site_id", "time"])
    op.create_index("idx_device_events_type", "device_events", ["event_type", "time"])

    # Create device_commands table
    op.create_table(
        "device_commands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("site_id", UUID(as_uuid=True), nullable=False),
        sa.Column("command_type", sa.String(100), nullable=False),
        sa.Column("command_params", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer, server_default=sa.text("3")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.Integer, server_default=sa.text("5")),
    )
    op.create_index(
        "idx_device_commands_pending",
        "device_commands",
        ["device_id", "priority", "created_at"],
    )

    # Create metric_definitions table
    op.create_table(
        "metric_definitions",
        sa.Column("metric_name", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("device_types", ARRAY(sa.String(50)), nullable=False),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("aggregation_method", sa.String(20), server_default="avg"),
        sa.Column("is_cumulative", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Create ingestion_batches table
    op.create_table(
        "ingestion_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=True),
        sa.Column("device_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("record_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("records_inserted", sa.Integer, server_default=sa.text("0")),
        sa.Column("records_failed", sa.Integer, server_default=sa.text("0")),
        sa.Column("errors", JSONB, nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
    )
    op.create_index(
        "idx_ingestion_batches_status",
        "ingestion_batches",
        ["status", "started_at"],
    )

    # Insert default metric definitions
    op.execute("""
        INSERT INTO metric_definitions (metric_name, display_name, unit, data_type, device_types, aggregation_method, is_cumulative)
        VALUES
            ('power_ac', 'AC Power', 'W', 'float', ARRAY['inverter'], 'avg', false),
            ('power_dc', 'DC Power', 'W', 'float', ARRAY['inverter'], 'avg', false),
            ('voltage_ac', 'AC Voltage', 'V', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('voltage_dc', 'DC Voltage', 'V', 'float', ARRAY['inverter'], 'avg', false),
            ('current_ac', 'AC Current', 'A', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('current_dc', 'DC Current', 'A', 'float', ARRAY['inverter'], 'avg', false),
            ('frequency', 'Grid Frequency', 'Hz', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('power_factor', 'Power Factor', '', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('energy_total', 'Total Energy', 'kWh', 'float', ARRAY['inverter', 'meter'], 'last', true),
            ('energy_today', 'Today Energy', 'kWh', 'float', ARRAY['inverter'], 'last', false),
            ('battery_soc', 'Battery SOC', '%', 'float', ARRAY['inverter', 'battery'], 'avg', false),
            ('battery_power', 'Battery Power', 'W', 'float', ARRAY['inverter', 'battery'], 'avg', false),
            ('battery_voltage', 'Battery Voltage', 'V', 'float', ARRAY['inverter', 'battery'], 'avg', false),
            ('battery_current', 'Battery Current', 'A', 'float', ARRAY['inverter', 'battery'], 'avg', false),
            ('battery_temperature', 'Battery Temperature', '°C', 'float', ARRAY['inverter', 'battery'], 'avg', false),
            ('grid_power', 'Grid Power', 'W', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('load_power', 'Load Power', 'W', 'float', ARRAY['inverter', 'meter'], 'avg', false),
            ('pv_power', 'PV Power', 'W', 'float', ARRAY['inverter'], 'avg', false),
            ('temperature', 'Temperature', '°C', 'float', ARRAY['inverter', 'weather_station'], 'avg', false),
            ('irradiance', 'Irradiance', 'W/m²', 'float', ARRAY['weather_station', 'sensor'], 'avg', false)
        ON CONFLICT (metric_name) DO NOTHING
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("ingestion_batches")
    op.drop_table("metric_definitions")
    op.drop_table("device_commands")
    op.drop_table("device_events")
    op.drop_table("telemetry_raw")
    op.drop_table("device_registry")
