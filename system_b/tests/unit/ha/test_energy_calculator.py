"""
Unit tests for BatteryEnergyCalculator and InverterEnergyCalculator.

All Redis and DB calls are mocked — no external dependencies.
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from system_b.device_server.ha.energy_calculator import (
    BatteryEnergyCalculator,
    InverterEnergyCalculator,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def redis():
    r = AsyncMock()
    r.incrbyfloat = AsyncMock(return_value=None)
    r.expire = AsyncMock(return_value=True)
    r.get = AsyncMock(return_value=None)
    r.mget = AsyncMock(return_value=[None] * 6)
    r.setex = AsyncMock(return_value=True)
    r.pipeline = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(execute=AsyncMock())),
        __aexit__=AsyncMock(return_value=False),
        setex=AsyncMock(),
        execute=AsyncMock(),
    ))
    return r


SERIAL = "SH01GWAT9Q7YDV90"
TODAY = date.today().isoformat()


# ===========================================================================
# BatteryEnergyCalculator
# ===========================================================================

class TestBatteryAccumulateToday:
    """Tests for Redis accumulation of today's battery energy."""

    @pytest.mark.asyncio
    async def test_charging_increments_charge_key(self, redis):
        calc = BatteryEnergyCalculator(redis)
        # First get → charge key (has data); second get → discharge key (empty)
        redis.get = AsyncMock(side_effect=[b"0.5", None])

        charge, discharge = await calc._accumulate_today(SERIAL, power_w=100.0, interval_sec=3600)

        # 100W × 3600s / 3_600_000 = 0.1 kWh increment
        redis.incrbyfloat.assert_called_once()
        call_key = redis.incrbyfloat.call_args[0][0]
        assert "charge" in call_key
        assert discharge == 0.0  # discharge key has no data

    @pytest.mark.asyncio
    async def test_discharging_increments_discharge_key(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"0.3")

        charge, discharge = await calc._accumulate_today(SERIAL, power_w=-200.0, interval_sec=1800)

        redis.incrbyfloat.assert_called_once()
        call_key = redis.incrbyfloat.call_args[0][0]
        assert "discharge" in call_key

    @pytest.mark.asyncio
    async def test_zero_interval_no_increment(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=None)

        await calc._accumulate_today(SERIAL, power_w=500.0, interval_sec=0.0)

        redis.incrbyfloat.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_power_no_increment(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=None)

        charge, discharge = await calc._accumulate_today(SERIAL, power_w=None, interval_sec=30.0)

        redis.incrbyfloat.assert_not_called()
        assert charge == 0.0
        assert discharge == 0.0

    @pytest.mark.asyncio
    async def test_returns_rounded_values(self, redis):
        calc = BatteryEnergyCalculator(redis)
        # First get → charge key; second get → discharge key (empty)
        redis.get = AsyncMock(side_effect=[b"1.23456789", None])

        charge, discharge = await calc._accumulate_today(SERIAL, power_w=None, interval_sec=0)

        assert charge == 1.235  # rounded to 3 dp
        assert discharge == 0.0


class TestBatteryGetTotal:
    """Tests for lifetime total energy retrieval."""

    @pytest.mark.asyncio
    async def test_returns_cached_redis_values(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(side_effect=[b"50.5", b"30.2"])

        charge, discharge = await calc._get_total(SERIAL)

        assert charge == 50.5
        assert discharge == 30.2

    @pytest.mark.asyncio
    async def test_returns_none_none_when_no_db_url(self, redis):
        calc = BatteryEnergyCalculator(redis, db_url=None)
        redis.get = AsyncMock(return_value=None)

        charge, discharge = await calc._get_total(SERIAL)

        assert charge is None
        assert discharge is None


class TestBatteryGetEnergy:
    """Tests for the public get_energy() interface."""

    @pytest.mark.asyncio
    async def test_returns_four_tuple(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"1.0")

        result = await calc.get_energy(SERIAL, power_w=100.0, interval_sec=30.0)

        assert len(result) == 4
        charge_today, discharge_today, charge_total, discharge_total = result
        assert charge_today is not None

    @pytest.mark.asyncio
    async def test_charging_power_fills_charge_today(self, redis):
        calc = BatteryEnergyCalculator(redis)
        redis.get = AsyncMock(side_effect=[b"0.9", None, None, None])

        charge_today, discharge_today, _, _ = await calc.get_energy(
            SERIAL, power_w=300.0, interval_sec=60.0
        )

        assert charge_today == 0.9
        assert discharge_today == 0.0


# ===========================================================================
# InverterEnergyCalculator
# ===========================================================================

class TestInverterComponentKeys:
    """Tests for the static key-mapping helpers."""

    def test_today_key_mappings(self):
        mapping = {
            "pv":                "pv_energy_today_kwh",
            "battery_charge":    "battery_charge_today_kwh",
            "battery_discharge": "battery_discharge_today_kwh",
            "grid_import":       "grid_import_today_kwh",
            "grid_export":       "grid_export_today_kwh",
            "load":              "load_energy_today_kwh",
        }
        for component, expected_key in mapping.items():
            assert InverterEnergyCalculator._component_to_state_key(component) == expected_key

    def test_total_key_mappings(self):
        mapping = {
            "pv":                "pv_energy_total_kwh",
            "battery_charge":    "battery_charge_total_kwh",
            "battery_discharge": "battery_discharge_total_kwh",
            "grid_import":       "grid_import_total_kwh",
            "grid_export":       "grid_export_total_kwh",
            "load":              "load_energy_total_kwh",
        }
        for component, expected_key in mapping.items():
            assert InverterEnergyCalculator._component_to_total_state_key(component) == expected_key

    def test_today_and_total_keys_are_different(self):
        for component in ("pv", "battery_charge", "grid_import"):
            today = InverterEnergyCalculator._component_to_state_key(component)
            total = InverterEnergyCalculator._component_to_total_state_key(component)
            assert today != total
            assert "today" in today
            assert "total" in total


class TestInverterAccumulateToday:
    """Tests for today's energy accumulation from real-time power."""

    @pytest.mark.asyncio
    async def test_pv_power_increments_pv_key(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"5.0")

        result = await calc._accumulate_today(
            SERIAL, pv_w=1000.0, bat_w=None, grid_w=None, load_w=None, interval_sec=60.0
        )

        redis.incrbyfloat.assert_called()
        pv_key_call = redis.incrbyfloat.call_args_list[0][0][0]
        assert "pv" in pv_key_call
        assert result["pv_energy_today_kwh"] == 5.0

    @pytest.mark.asyncio
    async def test_positive_battery_power_is_charge(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"2.0")

        result = await calc._accumulate_today(
            SERIAL, pv_w=None, bat_w=500.0, grid_w=None, load_w=None, interval_sec=60.0
        )

        keys_incremented = [c[0][0] for c in redis.incrbyfloat.call_args_list]
        assert any("battery_charge" in k for k in keys_incremented)
        assert not any("battery_discharge" in k for k in keys_incremented)

    @pytest.mark.asyncio
    async def test_negative_battery_power_is_discharge(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"1.5")

        result = await calc._accumulate_today(
            SERIAL, pv_w=None, bat_w=-300.0, grid_w=None, load_w=None, interval_sec=60.0
        )

        keys_incremented = [c[0][0] for c in redis.incrbyfloat.call_args_list]
        assert any("battery_discharge" in k for k in keys_incremented)
        assert not any("battery_charge" in k for k in keys_incremented)

    @pytest.mark.asyncio
    async def test_positive_grid_power_is_import(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"0.8")

        result = await calc._accumulate_today(
            SERIAL, pv_w=None, bat_w=None, grid_w=400.0, load_w=None, interval_sec=60.0
        )

        keys_incremented = [c[0][0] for c in redis.incrbyfloat.call_args_list]
        assert any("grid_import" in k for k in keys_incremented)
        assert not any("grid_export" in k for k in keys_incremented)

    @pytest.mark.asyncio
    async def test_negative_grid_power_is_export(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"0.3")

        result = await calc._accumulate_today(
            SERIAL, pv_w=None, bat_w=None, grid_w=-150.0, load_w=None, interval_sec=60.0
        )

        keys_incremented = [c[0][0] for c in redis.incrbyfloat.call_args_list]
        assert any("grid_export" in k for k in keys_incremented)
        assert not any("grid_import" in k for k in keys_incremented)

    @pytest.mark.asyncio
    async def test_result_has_all_six_components(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"1.0")

        result = await calc._accumulate_today(
            SERIAL, pv_w=500.0, bat_w=100.0, grid_w=-50.0, load_w=450.0, interval_sec=30.0
        )

        assert "pv_energy_today_kwh" in result
        assert "battery_charge_today_kwh" in result
        assert "battery_discharge_today_kwh" in result
        assert "grid_import_today_kwh" in result
        assert "grid_export_today_kwh" in result
        assert "load_energy_today_kwh" in result


class TestInverterFillMissingEnergy:
    """Tests for fill_missing_energy — only fills None fields."""

    @pytest.mark.asyncio
    async def test_fills_none_pv_today_from_accumulator(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"3.5")
        redis.mget = AsyncMock(return_value=[b"10.0"] * 6)

        state = {
            "pv_power_w": 1000.0,
            "battery_power_w": None,
            "grid_power_w": None,
            "load_power_w": None,
            "pv_energy_today_kwh": None,  # should be filled
            "battery_charge_today_kwh": None,
            "battery_discharge_today_kwh": None,
            "grid_import_today_kwh": None,
            "grid_export_today_kwh": None,
            "load_energy_today_kwh": None,
            "pv_energy_total_kwh": None,
            "battery_charge_total_kwh": None,
            "battery_discharge_total_kwh": None,
            "grid_import_total_kwh": None,
            "grid_export_total_kwh": None,
            "load_energy_total_kwh": None,
        }

        await calc.fill_missing_energy(SERIAL, state, interval_sec=30.0)

        assert state["pv_energy_today_kwh"] is not None

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_hardware_values(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"99.0")
        redis.mget = AsyncMock(return_value=[b"50.0"] * 6)

        state = {
            "pv_power_w": 1000.0,
            "battery_power_w": None,
            "grid_power_w": None,
            "load_power_w": None,
            "pv_energy_today_kwh": 12.5,        # hardware value — must NOT be overwritten
            "battery_charge_today_kwh": None,
            "battery_discharge_today_kwh": None,
            "grid_import_today_kwh": None,
            "grid_export_today_kwh": None,
            "load_energy_today_kwh": None,
            "pv_energy_total_kwh": 5000.0,      # hardware value — must NOT be overwritten
            "battery_charge_total_kwh": None,
            "battery_discharge_total_kwh": None,
            "grid_import_total_kwh": None,
            "grid_export_total_kwh": None,
            "load_energy_total_kwh": None,
        }

        await calc.fill_missing_energy(SERIAL, state, interval_sec=30.0)

        assert state["pv_energy_today_kwh"] == 12.5
        assert state["pv_energy_total_kwh"] == 5000.0

    @pytest.mark.asyncio
    async def test_skips_total_db_query_when_all_present(self, redis):
        calc = InverterEnergyCalculator(redis)
        redis.get = AsyncMock(return_value=b"1.0")

        # All total fields already have values
        state = {
            "pv_power_w": 500.0,
            "battery_power_w": None,
            "grid_power_w": None,
            "load_power_w": None,
            "pv_energy_today_kwh": None,
            "battery_charge_today_kwh": None,
            "battery_discharge_today_kwh": None,
            "grid_import_today_kwh": None,
            "grid_export_today_kwh": None,
            "load_energy_today_kwh": None,
            "pv_energy_total_kwh": 1000.0,
            "battery_charge_total_kwh": 500.0,
            "battery_discharge_total_kwh": 450.0,
            "grid_import_total_kwh": 200.0,
            "grid_export_total_kwh": 300.0,
            "load_energy_total_kwh": 900.0,
        }

        await calc.fill_missing_energy(SERIAL, state, interval_sec=30.0)

        # mget should not have been called (no totals to fetch)
        redis.mget.assert_not_called()


class TestInverterGetTotals:
    """Tests for _get_totals Redis cache and DB fallback."""

    @pytest.mark.asyncio
    async def test_returns_cached_values_from_redis(self, redis):
        calc = InverterEnergyCalculator(redis)
        cached = [b"100.0", b"50.0", b"45.0", b"20.0", b"30.0", b"90.0"]
        redis.mget = AsyncMock(return_value=cached)

        result = await calc._get_totals(SERIAL)

        assert result["pv_energy_total_kwh"] == 100.0
        assert result["battery_charge_total_kwh"] == 50.0
        assert result["battery_discharge_total_kwh"] == 45.0
        assert result["grid_import_total_kwh"] == 20.0
        assert result["grid_export_total_kwh"] == 30.0
        assert result["load_energy_total_kwh"] == 90.0

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_db_url_and_no_cache(self, redis):
        calc = InverterEnergyCalculator(redis, db_url=None)
        redis.mget = AsyncMock(return_value=[None] * 6)

        result = await calc._get_totals(SERIAL)

        assert result == {}

    @pytest.mark.asyncio
    async def test_partial_cache_miss_triggers_db(self, redis):
        """If any cached key is missing, should attempt DB query."""
        calc = InverterEnergyCalculator(redis, db_url=None)
        # Only 5 of 6 keys are cached — one None triggers DB path
        redis.mget = AsyncMock(return_value=[b"1.0", b"2.0", b"3.0", b"4.0", None, b"6.0"])

        result = await calc._get_totals(SERIAL)

        # No DB URL → returns empty dict
        assert result == {}


class TestInverterNoHistoryPoisoning:
    """
    Regression: when device_telemetry has no rows for the serial, the DB
    integration query still returns a single COALESCE'd row of zeros.  The
    previous _get_totals cached those 0.0 values in Redis for 1 h and
    returned them, causing HA to display "0.00 kWh" on every lifetime
    sensor.  The fix must:

      * Return an empty dict from _query_db_totals when row_count == 0.
      * Cause _get_totals to skip the Redis cache write in that case.
      * Cause _get_totals to return {} so fill_missing_energy leaves the
        state field as None (HA shows Unknown, not a bogus 0.00).
    """

    @pytest.mark.asyncio
    async def test_get_totals_returns_empty_when_query_returned_no_rows(self, redis):
        calc = InverterEnergyCalculator(redis, db_url="postgres://x")
        redis.mget = AsyncMock(return_value=[None] * 6)
        calc._query_db_totals = AsyncMock(return_value={})

        result = await calc._get_totals(SERIAL)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_totals_does_not_cache_zeros_when_no_rows(self, redis):
        calc = InverterEnergyCalculator(redis, db_url="postgres://x")
        redis.mget = AsyncMock(return_value=[None] * 6)
        calc._query_db_totals = AsyncMock(return_value={})

        pipe = redis.pipeline.return_value
        await calc._get_totals(SERIAL)

        # No setex on the pipeline — we must not poison Redis with 0.0s
        pipe.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_totals_caches_and_returns_when_query_has_rows(self, redis):
        calc = InverterEnergyCalculator(redis, db_url="postgres://x")
        redis.mget = AsyncMock(return_value=[None] * 6)
        real_totals = {
            "pv_energy_total_kwh":         1234.5,
            "battery_charge_total_kwh":    100.0,
            "battery_discharge_total_kwh": 90.0,
            "grid_import_total_kwh":       50.0,
            "grid_export_total_kwh":       800.0,
            "load_energy_total_kwh":       1500.0,
        }
        calc._query_db_totals = AsyncMock(return_value=real_totals)

        result = await calc._get_totals(SERIAL)

        assert result == real_totals
        pipe = redis.pipeline.return_value
        # One setex per component
        assert pipe.setex.call_count == 6


class TestBatteryNoHistoryPoisoning:
    """
    Same regression for BatteryEnergyCalculator._get_total: when the DB
    query returned no rows, the old code cached 0.0/0.0 with 1 h TTL and
    returned them.  Fix: only cache when row_count > 0; otherwise return
    (None, None) so HA shows Unknown.
    """

    @pytest.mark.asyncio
    async def test_get_total_returns_none_when_query_returned_no_rows(self, redis):
        calc = BatteryEnergyCalculator(redis, db_url="postgres://x")
        redis.get = AsyncMock(return_value=None)
        calc._query_db_total = AsyncMock(return_value=(0.0, 0.0, 0))

        charge, discharge = await calc._get_total(SERIAL)

        assert charge is None
        assert discharge is None
        redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_total_caches_and_returns_when_query_has_rows(self, redis):
        calc = BatteryEnergyCalculator(redis, db_url="postgres://x")
        redis.get = AsyncMock(return_value=None)
        calc._query_db_total = AsyncMock(return_value=(42.5, 17.25, 314))

        charge, discharge = await calc._get_total(SERIAL)

        assert charge == 42.5
        assert discharge == 17.25
        # Both keys cached
        assert redis.setex.call_count == 2


class TestInverterClose:
    """Tests for lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_with_no_pool_is_safe(self, redis):
        calc = InverterEnergyCalculator(redis)
        # Should not raise
        await calc.close()

    @pytest.mark.asyncio
    async def test_close_calls_pool_close(self, redis):
        calc = InverterEnergyCalculator(redis)
        mock_pool = AsyncMock()
        calc._db_pool = mock_pool

        await calc.close()

        mock_pool.close.assert_called_once()
        assert calc._db_pool is None
