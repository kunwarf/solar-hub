/**
 * Range slider with colored safe/warn/danger zone segments, tick marks at
 * zone boundaries, and full pointer + keyboard support.
 *
 * Ported verbatim from D:\Downloads\solar-inverter-settings.html, adapted
 * to TypeScript.  The one non-obvious detail is the invisible touch-padding
 * on the outer wrapper (py-4 -my-4) — the visible bar is 8px but the
 * grab area is ~40px so touch targets meet mobile guidelines while the
 * trackRef math on left/width still measures the visible bar.
 */
import { useCallback, useRef } from "react";
import type { Zone } from "./profiles/types";

function zoneColor(zones: Zone[] | undefined, val: number): string {
  if (!zones || zones.length === 0) return "#3b82f6";
  const z = zones.find((zn) => val >= zn.from && val <= zn.to);
  return z ? z.color : "#3b82f6";
}

export interface SafeZoneSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  zones?: Zone[];
  unit?: string;
  onChange: (v: number) => void;
  formatValue?: (v: number) => string;
  disabled?: boolean;
}

export function SafeZoneSlider({
  label,
  value,
  min,
  max,
  step = 1,
  zones,
  unit = "",
  onChange,
  formatValue,
  disabled,
}: SafeZoneSliderProps) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const pct = ((value - min) / (max - min)) * 100;
  const thumbColor = zoneColor(zones, value);
  const fmt =
    formatValue ||
    ((v: number) => `${v.toLocaleString ? v.toLocaleString() : v}${unit}`);

  const setFromClientX = useCallback(
    (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      let raw = min + ratio * (max - min);
      raw = Math.round(raw / step) * step;
      raw = Math.min(max, Math.max(min, raw));
      onChange(raw);
    },
    [min, max, step, onChange],
  );

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    setFromClientX(e.clientX);
    const move = (ev: PointerEvent) => setFromClientX(ev.clientX);
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    let next = value;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = value + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = value - step;
    else if (e.key === "Home") next = min;
    else if (e.key === "End") next = max;
    else if (e.key === "PageUp") next = value + step * 10;
    else if (e.key === "PageDown") next = value - step * 10;
    else return;
    e.preventDefault();
    onChange(Math.min(max, Math.max(min, next)));
  };

  return (
    <div className={disabled ? "opacity-40 pointer-events-none" : ""}>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </span>
        <span
          className="font-mono tabular-nums text-[13px] font-semibold"
          style={{ color: thumbColor }}
        >
          {fmt(value)}
        </span>
      </div>
      {/* Invisible vertical padding widens the pointer hit area to ~40px
          while the visible bar stays 8px.  trackRef still measures the
          visible bar so drag math stays accurate. */}
      <div
        className="relative py-4 -my-4 cursor-pointer touch-none"
        onPointerDown={onPointerDown}
      >
        <div
          ref={trackRef}
          className="relative h-2 rounded-full bg-zinc-200 dark:bg-zinc-800"
        >
          {zones &&
            zones.map((z, i) => (
              <div
                key={i}
                className="absolute top-0 h-full first:rounded-l-full last:rounded-r-full"
                style={{
                  left: `${((z.from - min) / (max - min)) * 100}%`,
                  width: `${((z.to - z.from) / (max - min)) * 100}%`,
                  backgroundColor: z.color,
                  opacity: 0.35,
                }}
              />
            ))}
          {zones &&
            zones.map(
              (z, i) =>
                i > 0 && (
                  <div
                    key={"tick" + i}
                    className="absolute top-1/2 -translate-y-1/2 w-px h-3.5 bg-zinc-400/70 dark:bg-zinc-500/70"
                    style={{ left: `${((z.from - min) / (max - min)) * 100}%` }}
                  />
                ),
            )}
          <div
            className="absolute top-0 h-full rounded-full"
            style={{ width: `${pct}%`, backgroundColor: thumbColor }}
          />
          <div
            role="slider"
            tabIndex={disabled ? -1 : 0}
            aria-label={label}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={value}
            aria-valuetext={fmt(value)}
            onKeyDown={onKeyDown}
            className="absolute top-1/2 w-5 h-5 rounded-full bg-white border-2 shadow -translate-x-1/2 -translate-y-1/2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            style={{ left: `${pct}%`, borderColor: thumbColor }}
          />
        </div>
      </div>
    </div>
  );
}
