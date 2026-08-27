"""
Unit tests for LastKnownCache.

The cache exists to make sure no HA sensor ever publishes as `null` when
a source register misses a reading, because HA treats null as Unavailable
— which breaks the Energy dashboard baseline and creates statistics gaps.
"""
import pytest

from system_b.device_server.ha.last_known import LastKnownCache, _ZERO_OK_METRICS


class FakeRedisPipe:
    def __init__(self, parent):
        self.parent = parent
        self.ops = []

    def setex(self, key, ttl, value):
        self.ops.append((key, ttl, value))

    async def execute(self):
        for key, ttl, value in self.ops:
            self.parent._store[key] = value
        return [True] * len(self.ops)


class FakeRedis:
    def __init__(self, initial=None):
        self._store = dict(initial or {})
        self.mget_error = False
        self.pipeline_error = False
        self._pipe = None

    async def mget(self, *keys):
        if self.mget_error:
            raise RuntimeError("simulated mget failure")
        return [self._store.get(k) for k in keys]

    def pipeline(self):
        if self.pipeline_error:
            raise RuntimeError("simulated pipeline failure")
        self._pipe = FakeRedisPipe(self)
        return self._pipe


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def cache(redis):
    return LastKnownCache(redis)


class TestFirstPublishBehaviour:
    async def test_zero_ok_metrics_default_to_zero_when_no_cache(self, cache):
        state = {"pv_power_w": None, "grid_power_w": None, "battery_power_w": None}
        await cache.fill_and_update("SN1", state)
        assert state["pv_power_w"] == 0.0
        assert state["grid_power_w"] == 0.0
        assert state["battery_power_w"] == 0.0

    async def test_energy_today_defaults_to_zero_when_no_cache(self, cache):
        state = {
            "pv_energy_today_kwh": None,
            "grid_import_today_kwh": None,
        }
        await cache.fill_and_update("SN1", state)
        assert state["pv_energy_today_kwh"] == 0.0
        assert state["grid_import_today_kwh"] == 0.0

    async def test_opaque_metrics_stay_none_when_no_cache(self, cache):
        """
        Fields like SOC, voltage, temperature, cycle_count can't be safely
        defaulted to 0 — a 0% SoC would be a dangerous false reading.
        Only after we've seen a real value once do they get filled from
        the cache.
        """
        state = {
            "battery_soc_percent": None,
            "battery_voltage_v": None,
            "inverter_temp_c": None,
            "battery_cycle_count": None,
        }
        await cache.fill_and_update("SN1", state)
        assert state["battery_soc_percent"] is None
        assert state["battery_voltage_v"] is None
        assert state["inverter_temp_c"] is None
        assert state["battery_cycle_count"] is None

    async def test_zero_ok_metric_list_covers_expected_fields(self):
        """
        Explicit list of what MUST accept a zero default so no future
        refactor accidentally removes them.
        """
        must_be_zero_ok = {
            "pv_power_w", "grid_power_w", "load_power_w", "battery_power_w",
            "pv_energy_today_kwh", "grid_import_today_kwh",
            "grid_export_today_kwh", "load_energy_today_kwh",
            "battery_charge_today_kwh", "battery_discharge_today_kwh",
        }
        missing = must_be_zero_ok - _ZERO_OK_METRICS
        assert not missing, f"metrics missing from zero-ok list: {missing}"


class TestFillFromCache:
    async def test_none_field_gets_last_known(self, cache, redis):
        # Seed the cache
        redis._store["ha:lastpub:SN1:battery_soc_percent"] = "78.0"
        state = {"battery_soc_percent": None}
        await cache.fill_and_update("SN1", state)
        assert state["battery_soc_percent"] == 78.0

    async def test_present_field_is_left_untouched(self, cache, redis):
        redis._store["ha:lastpub:SN1:pv_power_w"] = "500.0"  # stale
        state = {"pv_power_w": 4200.0}  # current
        await cache.fill_and_update("SN1", state)
        assert state["pv_power_w"] == 4200.0  # not overridden

    async def test_present_field_updates_cache(self, cache, redis):
        state = {"pv_power_w": 4200.0}
        await cache.fill_and_update("SN1", state)
        assert redis._store["ha:lastpub:SN1:pv_power_w"] == "4200.0"

    async def test_string_value_from_cache_passes_through_when_not_numeric(self, cache, redis):
        redis._store["ha:lastpub:SN1:some_string_field"] = "custom-value"
        state = {"some_string_field": None}
        await cache.fill_and_update("SN1", state)
        assert state["some_string_field"] == "custom-value"

    async def test_present_and_missing_in_same_call(self, cache, redis):
        redis._store["ha:lastpub:SN1:battery_soc_percent"] = "50.0"
        state = {
            "pv_power_w": 3000.0,           # present, should stay + cache
            "battery_soc_percent": None,    # missing, should fill from cache
            "battery_voltage_v": None,      # missing, no cache, no zero-ok → stays None
        }
        await cache.fill_and_update("SN1", state)
        assert state["pv_power_w"] == 3000.0
        assert state["battery_soc_percent"] == 50.0
        assert state["battery_voltage_v"] is None
        assert redis._store["ha:lastpub:SN1:pv_power_w"] == "3000.0"


class TestMetadataIsSkipped:
    async def test_last_reset_epoch_not_cached_or_filled(self, cache, redis):
        state = {"last_reset_epoch": "1970-01-01T00:00:00+00:00", "pv_power_w": 1000.0}
        await cache.fill_and_update("SN1", state)
        assert state["last_reset_epoch"] == "1970-01-01T00:00:00+00:00"
        assert "ha:lastpub:SN1:last_reset_epoch" not in redis._store


class TestRedisFailureFallback:
    async def test_mget_failure_still_applies_zero_defaults(self, cache, redis):
        redis.mget_error = True
        state = {"pv_power_w": None, "battery_soc_percent": None}
        await cache.fill_and_update("SN1", state)
        # pv_power_w in zero-ok list → gets 0.0 even without cache
        assert state["pv_power_w"] == 0.0
        # battery_soc_percent not in list → stays None (HA will show unavailable,
        # honest given we can't guess safely)
        assert state["battery_soc_percent"] is None

    async def test_pipeline_failure_does_not_raise(self, cache, redis):
        redis.pipeline_error = True
        state = {"pv_power_w": 1000.0}
        # Should not raise — the fill succeeded, the cache update failure
        # is degraded gracefully.
        await cache.fill_and_update("SN1", state)


class TestIsolation:
    async def test_cache_is_per_serial(self, cache, redis):
        redis._store["ha:lastpub:SN1:pv_power_w"] = "1000.0"
        state_sn2 = {"pv_power_w": None}
        await cache.fill_and_update("SN2", state_sn2)
        # SN2 has no cache entry, gets zero default (in _ZERO_OK_METRICS)
        assert state_sn2["pv_power_w"] == 0.0
