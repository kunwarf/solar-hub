# Register Chunk Optimization

## Overview

This directory contains pre-computed register chunk definitions that optimize Modbus read operations for device settings queries.

Instead of reading each register individually (75 separate Modbus operations), registers are grouped into consecutive chunks that can be read in bulk (3 bulk operations).

## Performance Impact

### Powdrive Inverter Example

**Before optimization:**
- 75 individual Modbus read operations
- Each operation requires network round-trip + protocol overhead
- Total time: ~750ms - 1500ms (assuming 10-20ms per read)

**After optimization:**
- 3 bulk chunk reads
- 72 fewer Modbus operations (96% reduction)
- Total time: ~30ms - 60ms
- **Speed improvement: 12-25x faster**

## How It Works

1. **Analysis**: Register addresses are analyzed to find consecutive or near-consecutive groups
2. **Chunking**: Registers are grouped with a configurable gap tolerance (max_gap parameter)
3. **Trade-off**: Reading a few extra unused registers is much faster than individual reads
4. **Mapping**: Each chunk knows which register IDs it contains for value extraction

## Chunk Configuration Format

```json
{
  "total_registers": 75,
  "total_chunks": 3,
  "chunks": [
    {
      "start_address": 99,
      "count": 93,
      "register_ids": [
        "battery_capacity_ah",
        "grid_charge_current_a",
        ...
      ]
    }
  ]
}
```

## Naming Convention

Chunk files must be named: `{protocol_id}_chunks.json`

Where `protocol_id` matches the protocol definition (e.g., "powdrive", "goodwe", "solaredge").

## Generating Chunks for New Protocols

1. Extract register addresses from your register map or protocol definition
2. Use the chunk analysis script to find optimal groupings:

```python
python analyze_register_chunks.py
```

3. Save the generated `{protocol_id}_chunks.json` to this directory
4. The command executor will automatically detect and use it

## Tuning Parameters

The `max_gap` parameter controls the chunking strategy:

- **max_gap=0**: Only truly consecutive registers (most efficient, most chunks)
- **max_gap=2**: Allow small 1-2 register gaps (good balance)
- **max_gap=5**: Allow larger gaps (fewer chunks, some wasted reads)

For Powdrive with max_gap=5:
- Reduces from 75 reads to 3 chunks
- Only 20 wasted register reads (78.9% efficiency)
- Still 96% fewer Modbus operations

## Fallback Behavior

If no chunk configuration exists for a protocol, the executor automatically falls back to individual register reads (backward compatible).

## When to Use Chunks

**Use chunks when:**
- Protocol has 20+ configurable registers
- Registers have some sequential grouping
- Network latency matters (remote devices, cellular connections)
- Fast settings queries are important

**Skip chunks when:**
- Protocol has very few registers (<10)
- Registers are extremely scattered (no grouping possible)
- Register map is unstable (frequently changing)

## Maintenance

When register maps change:
1. Re-run the chunk analysis script with updated addresses
2. Regenerate the chunk configuration file
3. Test to ensure all expected registers are captured
4. Update this README if new protocols are added
