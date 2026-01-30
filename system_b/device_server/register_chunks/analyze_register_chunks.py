"""
Analyze register addresses and generate optimized chunks for bulk reading.
"""
import json
from typing import List, Dict, Tuple

# Register addresses extracted from frontend mapping (from comments)
REGISTER_ADDRESSES = {
    # Battery Configuration
    'battery_capacity_ah': 102,
    'battery_equalization_voltage_v': 99,
    'battery_floating_voltage_v': 101,
    'battery_max_charge_current_a': 108,
    'battery_max_discharge_current_a': 109,
    'battery_mode_source': 111,
    'battery_shutdown_capacity_pct': 115,
    'battery_restart_capacity_pct': 116,
    'battery_low_capacity_pct': 117,
    'battery_shutdown_voltage_v': 118,
    'battery_restart_voltage_v': 119,
    'battery_low_voltage_v': 120,
    'lithium_battery_type': 223,

    # Grid Settings
    'zero_export_power_w': 104,
    'solar_priority': 141,
    'limit_control_function': 142,
    'max_export_power_w': 143,
    'external_ct_direction': 144,
    'solar_sell': 145,
    'grid_phase_sequence': 147,
    'grid_charging_start_voltage_v': 126,
    'grid_charging_start_capacity_pct': 127,
    'grid_charge_battery_current_a': 128,
    'ac_charge_battery': 130,
    'grid_standard': 182,
    'grid_type_setting': 184,
    'grid_peak_shaving_power_w': 191,

    # TOU Scheduling
    'tou_selling': 146,
    'prog1_time': 148,
    'prog2_time': 149,
    'prog3_time': 150,
    'prog4_time': 151,
    'prog5_time': 152,
    'prog6_time': 153,
    'prog1_power_w': 154,
    'prog2_power_w': 155,
    'prog3_power_w': 156,
    'prog4_power_w': 157,
    'prog5_power_w': 158,
    'prog6_power_w': 159,
    'prog1_voltage_v': 160,
    'prog2_voltage_v': 161,
    'prog3_voltage_v': 162,
    'prog4_voltage_v': 163,
    'prog5_voltage_v': 164,
    'prog6_voltage_v': 165,
    'prog1_capacity_pct': 166,
    'prog2_capacity_pct': 167,
    'prog3_capacity_pct': 168,
    'prog4_capacity_pct': 169,
    'prog5_capacity_pct': 170,
    'prog6_capacity_pct': 171,
    'prog1_charge_mode': 172,
    'prog2_charge_mode': 173,
    'prog3_charge_mode': 174,
    'prog4_charge_mode': 175,
    'prog5_charge_mode': 176,
    'prog6_charge_mode': 177,

    # Generator/Auxiliary
    'generator_max_run_time_h': 121,
    'generator_down_time_h': 122,
    'generator_charging_start_voltage_v': 123,
    'generator_charging_start_capacity_pct': 124,
    'generator_charge_battery_current_a': 125,
    'generator_charge_enabled': 129,
    'generator_port_usage': 133,
    'smartload_off_voltage_v': 134,
    'smartload_off_capacity_pct': 135,
    'smartload_on_voltage_v': 136,
    'smartload_on_capacity_pct': 137,
    'generator_connected_to_grid_input': 189,
    'gen_peak_shaving_power_w': 190,

    # Advanced
    'battery_equalization_day_cycle': 105,
    'battery_equalization_time': 106,
    'solar_arc_fault_mode': 181,
    'max_solar_sell_power_w': 340,
}


def find_consecutive_chunks(addresses: List[int], max_gap: int = 5) -> List[Tuple[int, int]]:
    """
    Group consecutive addresses into chunks.

    Args:
        addresses: Sorted list of register addresses
        max_gap: Maximum gap between registers to still consider them in same chunk

    Returns:
        List of (start_address, count) tuples
    """
    if not addresses:
        return []

    chunks = []
    current_start = addresses[0]
    current_end = addresses[0]

    for addr in addresses[1:]:
        gap = addr - current_end

        if gap == 1:
            # Consecutive - extend current chunk
            current_end = addr
        elif gap <= max_gap:
            # Small gap - still include in chunk (we'll read unused registers too)
            current_end = addr
        else:
            # Large gap - start new chunk
            chunks.append((current_start, current_end - current_start + 1))
            current_start = addr
            current_end = addr

    # Add final chunk
    chunks.append((current_start, current_end - current_start + 1))

    return chunks


def generate_chunk_definitions(register_map: Dict[str, int]) -> Dict[str, any]:
    """Generate optimized chunk reading configuration."""

    # Sort addresses
    sorted_addrs = sorted(register_map.values())

    print(f"Total writable registers: {len(sorted_addrs)}")
    print(f"Address range: {min(sorted_addrs)} - {max(sorted_addrs)}")
    print()

    # Find chunks with different gap tolerances
    for max_gap in [0, 2, 5, 10]:
        chunks = find_consecutive_chunks(sorted_addrs, max_gap=max_gap)

        total_registers_read = sum(count for _, count in chunks)
        wasted = total_registers_read - len(sorted_addrs)
        efficiency = (1 - wasted / total_registers_read) * 100 if total_registers_read > 0 else 0

        print(f"Max gap = {max_gap}:")
        print(f"  Chunks: {len(chunks)} (vs {len(sorted_addrs)} individual reads)")
        print(f"  Total registers read: {total_registers_read}")
        print(f"  Wasted reads: {wasted} ({efficiency:.1f}% efficiency)")
        print(f"  Reduction: {len(sorted_addrs) - len(chunks)} fewer Modbus operations ({(1 - len(chunks)/len(sorted_addrs))*100:.1f}%)")
        print()

    # Use max_gap=5 as optimal balance
    optimal_chunks = find_consecutive_chunks(sorted_addrs, max_gap=5)

    # Build chunk configuration with register IDs
    chunk_config = []
    addr_to_ids = {}
    for reg_id, addr in register_map.items():
        if addr not in addr_to_ids:
            addr_to_ids[addr] = []
        addr_to_ids[addr].append(reg_id)

    for start_addr, count in optimal_chunks:
        chunk = {
            "start_address": start_addr,
            "count": count,
            "register_ids": []
        }

        # Map which register IDs are in this chunk
        for offset in range(count):
            addr = start_addr + offset
            if addr in addr_to_ids:
                chunk["register_ids"].extend(addr_to_ids[addr])

        chunk_config.append(chunk)

    return {
        "total_registers": len(sorted_addrs),
        "total_chunks": len(optimal_chunks),
        "chunks": chunk_config
    }


if __name__ == "__main__":
    print("=" * 70)
    print("REGISTER CHUNK ANALYSIS")
    print("=" * 70)
    print()

    config = generate_chunk_definitions(REGISTER_ADDRESSES)

    print("=" * 70)
    print("OPTIMIZED CHUNK CONFIGURATION")
    print("=" * 70)
    print()

    for i, chunk in enumerate(config["chunks"], 1):
        print(f"Chunk {i}: Read {chunk['count']} registers starting at address {chunk['start_address']}")
        print(f"  Contains: {', '.join(chunk['register_ids'][:5])}{' ...' if len(chunk['register_ids']) > 5 else ''}")
        print()

    # Save configuration
    output_file = "powdrive_register_chunks.json"
    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✓ Chunk configuration saved to {output_file}")
    print()
    print(f"Summary:")
    print(f"  Before: {config['total_registers']} individual Modbus reads")
    print(f"  After:  {config['total_chunks']} bulk chunk reads")
    print(f"  Improvement: {config['total_registers'] - config['total_chunks']} fewer operations ({(1 - config['total_chunks']/config['total_registers'])*100:.1f}% reduction)")
