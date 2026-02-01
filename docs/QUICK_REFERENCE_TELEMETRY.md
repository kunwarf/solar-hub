# Telemetry Data Integration - Quick Reference

## 🚀 Quick Start

### Using the useTelemetryData Hook

```typescript
import { useTelemetryData } from '@/hooks/useTelemetryData';

const MyComponent = ({ device }) => {
  const {
    metrics,          // Extended inverter metrics
    mpptChannels,     // Solar array/MPPT data
    historicalData,   // 24-hour power history
    isLoading,        // Initial load state
    usingFallback,    // True if using simulated data
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
      {usingFallback && <FallbackWarning />}
      {metrics && <MetricsDisplay metrics={metrics} />}
      {mpptChannels.map(channel => <MPPTCard key={channel.channel_id} data={channel} />)}
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

### Handling Fallback Data
```typescript
const { usingFallback } = useTelemetryData({...});

// Show warning to user
{usingFallback && (
  <Alert className="bg-warning/10">
    <AlertCircle className="h-4 w-4" />
    <AlertDescription>
      Using simulated data - real-time data unavailable
    </AlertDescription>
  </Alert>
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

**Issue:** All data showing as "Simulated"
```typescript
// Solution: Check API availability
console.log('Metrics:', metrics);
console.log('Using Fallback:', usingFallback);
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
2. Verify API endpoints are responding
3. Check browser console for errors
4. Ensure `pollingInterval > 0`

**Seeing wrong data?**
1. Check `serialNumber` matches device
2. Verify `deviceId` is correct UUID
3. Clear browser cache and reload
4. Check backend logs for mapping issues

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
