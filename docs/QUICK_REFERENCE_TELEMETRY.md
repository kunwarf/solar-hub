# Telemetry Data Integration - Quick Reference

## 🚀 Quick Start

### Using the useTelemetryData Hook

```typescript
import { useTelemetryData } from '@/hooks/useTelemetryData';

const MyComponent = ({ device }) => {
  const {
    metrics,          // Extended inverter metrics (null if unavailable)
    mpptChannels,     // Solar array/MPPT data (empty array if unavailable)
    historicalData,   // 24-hour power history (empty array if unavailable)
    isLoading,        // Initial load state
    error,            // Error object if fetch failed
    refresh,          // Manual refresh function
  } = useTelemetryData({
    deviceId: device.id,
    serialNumber: device.serialNumber,
    pollingInterval: 5000,      // Poll every 5 seconds
    enableHistorical: true,     // Fetch historical data
    enableMPPT: true,          // Fetch MPPT channel data
  });

  return (
    <div>
      {isLoading ? <LoadingSpinner /> : (
        <>
          {mpptChannels.length === 0 ? <EmptyState /> : (
            mpptChannels.map(channel => <MPPTCard key={channel.channel_id} data={channel} />)
          )}
          {metrics && <MetricsDisplay metrics={metrics} />}
        </>
      )}
    </div>
  );
};
```

## 📊 Data Structures

### Extended Inverter Metrics
```typescript
{
  dc_voltage_v: 580,          // DC bus voltage
  ac_voltage_v: 238,          // AC output voltage
  ac_frequency_hz: 50.0,      // Grid frequency
  efficiency_pct: 97.5,       // Conversion efficiency
  temperature_c: 42,          // Inverter temperature
  battery_soc_pct: 80,        // Battery state of charge
  timestamp: "2024-01-01T12:00:00Z",
  online: true
}
```

### MPPT Channel Data
```typescript
{
  channel_id: 1,
  name: "Array 1 (East Roof)",
  power_w: 2850,              // Current power output
  voltage_v: 385.2,           // String voltage
  current_a: 7.4,             // String current
  status: "optimal",          // optimal | shaded | offline | low
  panel_count: 12,
  efficiency_pct: 95.5
}
```

### Historical Power Point
```typescript
{
  timestamp: "2024-01-01T12:00:00Z",
  solar_power_kw: 7.5,
  battery_power_kw: 2.0,      // Positive = charging
  load_power_kw: 5.0,
  grid_power_kw: 0.5,         // Positive = import, negative = export
  efficiency_pct: 97.0,
  temperature_c: 42
}
```

## 🔧 API Endpoints Reference

| Endpoint | Method | Response |
|----------|--------|----------|
| `/devices/{id}/snapshot` | GET | DeviceMetrics |
| `/dashboard/power-flow` | GET | PowerFlowData |
| `/dashboard/energy-chart?period=day` | GET | EnergyChartResponse |

## ⚠️ Common Patterns

### Handling Empty Data
```typescript
const { mpptChannels, historicalData, error } = useTelemetryData({...});

// Show empty state when no data available
{mpptChannels.length === 0 && (
  <div className="text-center py-8">
    <Sun className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-50" />
    <p className="text-sm text-muted-foreground">No MPPT channel data available</p>
    {error && <p className="text-xs text-destructive mt-2">Error loading data</p>}
  </div>
)}
```

### Manual Refresh
```typescript
const { refresh, isPolling } = useTelemetryData({...});

<Button onClick={refresh} disabled={isPolling}>
  <RefreshCw className={isPolling ? "animate-spin" : ""} />
  Refresh
</Button>
```

### Conditional Data Fetching
```typescript
// Only fetch MPPT data for inverters
const { mpptChannels } = useTelemetryData({
  deviceId: device.id,
  serialNumber: device.serialNumber,
  enableMPPT: device.type === 'inverter',  // Only for inverters
  enableHistorical: false,                 // Skip if not needed
});
```

## 🐛 Debugging

### Check Console Logs
```javascript
// Hook logs all major operations
[useTelemetryData] Starting query for device: xxx
[useTelemetryData] SUCCESS! Got settings
[useTelemetryData] CATCH BLOCK - Error occurred
```

### Check Network Tab
```
✅ 200: /devices/{id}/snapshot - Metrics loaded
✅ 200: /dashboard/power-flow - Real-time data OK
❌ 500: /dashboard/energy-chart - Using fallback
```

### Common Issues

**Issue:** No data showing (empty states)
```typescript
// Solution: Check API availability and data
console.log('Metrics:', metrics);
console.log('MPPT Channels:', mpptChannels);
console.log('Historical Data:', historicalData);
console.log('Error:', error);
```

**Issue:** Polling not working
```typescript
// Solution: Ensure pollingInterval > 0
pollingInterval: 5000  // ✅ Correct
pollingInterval: 0     // ❌ Disabled
```

**Issue:** Memory leak warnings
```typescript
// Solution: Hook auto-cleans up, but ensure component unmounts properly
useEffect(() => {
  return () => {
    // Cleanup happens automatically
  };
}, []);
```

## 📈 Performance Tips

1. **Disable unnecessary features:**
   ```typescript
   // If you don't need historical charts
   enableHistorical: false
   ```

2. **Increase polling interval for background tabs:**
   ```typescript
   const pollingInterval = document.visibilityState === 'visible' ? 5000 : 30000;
   ```

3. **Memoize expensive computations:**
   ```typescript
   const totalPower = useMemo(
     () => mpptChannels.reduce((sum, ch) => sum + ch.power_w, 0),
     [mpptChannels]
   );
   ```

## 🔐 Security Notes

- ✅ All API calls use authenticated endpoints
- ✅ Device IDs validated before fetching
- ✅ No sensitive data logged to console in production
- ✅ CORS configured for allowed origins only

## 📞 Quick Help

**Telemetry not updating?**
1. Check device is online
2. Verify API endpoints are responding (check Network tab)
3. Check browser console for errors
4. Ensure `pollingInterval > 0`
5. Verify backend services are running

**Seeing empty states?**
1. Check API endpoints return data (not empty arrays)
2. Verify backend has implemented MPPT and extended telemetry endpoints
3. Check `serialNumber` matches device
4. Verify `deviceId` is correct UUID
5. Check backend logs for data processing issues

**Tests failing?**
```bash
# Run unit tests
npm run test -- useTelemetryData.test.ts

# Run E2E tests
npx playwright test telemetry.spec.ts

# Type check
npx tsc --noEmit
```

---

**Last Updated:** 2026-02-01
**See Full Documentation:** `TELEMETRY_REAL_DATA_INTEGRATION.md`
