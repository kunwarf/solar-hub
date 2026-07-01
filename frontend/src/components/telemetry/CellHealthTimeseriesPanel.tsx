/**
 * CellHealthTimeseriesPanel — surfaces cells flagged by the System A
 * time-series detector as "charges quickly" or "discharges quickly".
 * Data is fetched by the parent (BatteryCellGrid) so this component stays
 * presentational.
 *
 * See ``docs/CELL_HEALTH_ANALYSIS.md`` for the algorithm.
 */
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Info,
} from "lucide-react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// ─── Types (mirror the backend detector output) ─────────────────────────────

export type TimeseriesSymptomType = "fast_full" | "fast_empty";
export type TimeseriesSeverity = "critical" | "warning" | "watch";
export type TimeseriesConfidence = "high" | "medium" | "low";

export interface TimeseriesSymptom {
  type: TimeseriesSymptomType;
  severity: TimeseriesSeverity;
  source: "computed";
  evidence: Record<string, string | number | boolean>;
}

export interface TimeseriesPhaseSample {
  symptom: TimeseriesSymptomType;
  dv_v: number;
}

export interface TimeseriesCandidate {
  cell_index: number;
  score: number;
  confidence: TimeseriesConfidence;
  symptoms: TimeseriesSymptom[];
  phase_history: TimeseriesPhaseSample[];
}

export interface TimeseriesUnit {
  unit_index: number;
  candidates: TimeseriesCandidate[];
}

export interface TimeseriesReport {
  algorithm: string;
  generated_at: string;
  available: boolean;
  reason:
    | null
    | "no_history"
    | "no_active_phases"
    | "device_not_registered";
  window_hours: number;
  phases_analysed: { charge: number; discharge: number };
  units: TimeseriesUnit[];
  total_candidates: number;
}

interface Props {
  report?: TimeseriesReport | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const SYMPTOM_LABEL: Record<TimeseriesSymptomType, string> = {
  fast_full: "Charges fast",
  fast_empty: "Discharges fast",
};

const SYMPTOM_ICON: Record<TimeseriesSymptomType, React.ReactNode> = {
  fast_full: <ArrowUpRight className="w-3 h-3" />,
  fast_empty: <ArrowDownRight className="w-3 h-3" />,
};

function severityBadgeClass(sev: TimeseriesSeverity): string {
  switch (sev) {
    case "critical":
      return "bg-destructive/20 text-destructive border-destructive/40";
    case "warning":
      return "bg-warning/20 text-warning border-warning/40";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

function confidenceLabel(c: TimeseriesConfidence): string {
  return c === "high" ? "High" : c === "medium" ? "Medium" : "Low";
}

function formatEvidence(evidence: Record<string, string | number | boolean>): string {
  return Object.entries(evidence)
    .map(([k, v]) => `${k}: ${typeof v === "number" ? formatNumber(k, v) : v}`)
    .join(" · ");
}

function formatNumber(key: string, v: number): string {
  if (key === "ratio") return v.toFixed(2);
  if (key.endsWith("_phases")) return String(Math.round(v));
  return String(v);
}

// ─── Component ──────────────────────────────────────────────────────────────

const CellHealthTimeseriesPanel = ({ report }: Props) => {
  if (!report) return null;

  if (!report.available) {
    // Quiet muted line for "no history yet" — this is normal during the
    // first hours after Phase 2 deploys, before enough phases accumulate.
    if (report.reason === "no_history") {
      return (
        <div className="glass-card p-3 text-xs text-muted-foreground border border-border/40">
          Building charge/discharge history — no analysable phases yet.
        </div>
      );
    }
    if (report.reason === "no_active_phases") {
      return (
        <div className="glass-card p-3 text-xs text-muted-foreground border border-border/40">
          No charge or discharge phases in the last {report.window_hours}h —
          pack has been idle.
        </div>
      );
    }
    // device_not_registered / other: stay silent.
    return null;
  }

  const allCandidates = report.units.flatMap((u) =>
    u.candidates.map((c) => ({ ...c, unit_index: u.unit_index })),
  );

  const phasesLabel = `${report.phases_analysed.charge} charge · ${report.phases_analysed.discharge} discharge over ${report.window_hours}h`;

  if (allCandidates.length === 0) {
    return (
      <div className="glass-card p-3 border border-success/30 bg-success/5">
        <div className="flex items-center gap-2 text-xs">
          <Info className="w-3.5 h-3.5 text-success" />
          <span className="text-success font-medium">
            No fast-charging or fast-discharging cells detected
          </span>
          <span className="text-muted-foreground">({phasesLabel})</span>
        </div>
      </div>
    );
  }

  const hasCritical = allCandidates.some((c) =>
    c.symptoms.some((s) => s.severity === "critical"),
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className={
        "glass-card p-4 border " +
        (hasCritical
          ? "border-destructive/40 bg-destructive/5"
          : "border-warning/40 bg-warning/5")
      }
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle
            className={
              "w-4 h-4 " + (hasCritical ? "text-destructive" : "text-warning")
            }
          />
          <div>
            <div className="font-semibold text-sm text-foreground">
              Charge / discharge cycle analysis
            </div>
            <div className="text-[11px] text-muted-foreground">
              {allCandidates.length} cell{allCandidates.length === 1 ? "" : "s"}
              {" "}flagged · {phasesLabel} · algorithm {report.algorithm}
            </div>
          </div>
        </div>
      </div>

      <TooltipProvider delayDuration={150}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground text-left border-b border-border/30">
                <th className="py-1.5 pr-3 font-medium">Unit</th>
                <th className="py-1.5 pr-3 font-medium">Cell</th>
                <th className="py-1.5 pr-3 font-medium">Symptoms</th>
                <th className="py-1.5 pr-3 font-medium">Score</th>
                <th className="py-1.5 pr-3 font-medium">Confidence</th>
                <th className="py-1.5 pr-3 font-medium">Recent dV per phase</th>
              </tr>
            </thead>
            <tbody>
              {allCandidates.map((c, idx) => (
                <tr
                  key={`${c.unit_index}-${c.cell_index}-${idx}`}
                  className="border-b border-border/10 last:border-b-0"
                >
                  <td className="py-1.5 pr-3 font-mono">{c.unit_index}</td>
                  <td className="py-1.5 pr-3 font-mono font-semibold">
                    {c.cell_index}
                  </td>
                  <td className="py-1.5 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {c.symptoms.map((s, i) => (
                        <Tooltip key={i}>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              className={
                                "flex items-center gap-1 border " +
                                severityBadgeClass(s.severity)
                              }
                            >
                              {SYMPTOM_ICON[s.type]}
                              <span>{SYMPTOM_LABEL[s.type]}</span>
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs text-xs">
                            <div className="font-semibold mb-1 capitalize">
                              {s.severity}
                            </div>
                            <div className="text-muted-foreground">
                              {formatEvidence(s.evidence)}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                  </td>
                  <td className="py-1.5 pr-3 font-mono">
                    {c.score.toFixed(1)}
                  </td>
                  <td className="py-1.5 pr-3">
                    <Badge variant="outline" className="text-[10px]">
                      {confidenceLabel(c.confidence)}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-3 w-24">
                    <Sparkline history={c.phase_history} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TooltipProvider>

      <div className="mt-3 text-[10px] text-muted-foreground leading-relaxed">
        Diagnostic heuristic — not a warranty claim. Fast-charging /
        fast-discharging cells are candidates for capacity or internal-resistance
        inspection at the next service window.
      </div>
    </motion.div>
  );
};

// ─── Sparkline ──────────────────────────────────────────────────────────────

interface SparklineProps {
  history: TimeseriesPhaseSample[];
}

const Sparkline = ({ history }: SparklineProps) => {
  if (!history || history.length === 0) {
    return <span className="text-muted-foreground text-[10px]">no data</span>;
  }
  // Show absolute dV so charge and discharge sit on the same axis; the
  // symptom tag above tells the operator which direction.
  const data = history.map((h, i) => ({
    idx: i,
    dv: Math.abs(h.dv_v * 1000),  // mV
  }));

  return (
    <div style={{ width: 96, height: 28 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="dv"
            stroke="currentColor"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default CellHealthTimeseriesPanel;
