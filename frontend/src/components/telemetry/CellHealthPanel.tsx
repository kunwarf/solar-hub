/**
 * CellHealthPanel — surfaces cells flagged for inspection by the System A
 * snapshot detector. Data arrives already computed on `BatteryBankResponse.cell_health`;
 * no extra fetch is performed here.
 *
 * Wording: candidates are "candidates for inspection", not "faulty" — the
 * heuristic is diagnostic, not a warranty claim. See docs/CELL_HEALTH_ANALYSIS.md.
 */
import { AlertTriangle, Info, ShieldAlert, ThermometerSun, Zap } from "lucide-react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// ─── Types (mirror the backend detector output) ─────────────────────────────

export type SymptomType =
  | "vendor_flag"
  | "voltage_outlier"
  | "temp_outlier"
  | "current_mismatch";

export type Severity = "critical" | "warning" | "watch";

export type Confidence = "high" | "medium" | "low";

export interface Symptom {
  type: SymptomType;
  severity: Severity;
  source: "vendor" | "computed";
  evidence: Record<string, string | number | boolean>;
}

export interface Candidate {
  cell_index: number;
  score: number;
  confidence: Confidence;
  symptoms: Symptom[];
}

export interface UnitReport {
  unit_index: number;
  cell_count: number;
  candidates: Candidate[];
  stats: Record<string, number | null>;
}

export interface CellHealthReport {
  algorithm: string;
  generated_at: string;
  available: boolean;
  reason: null | "pack_level_only" | "no_recent_data";
  units: UnitReport[];
  total_candidates: number;
}

interface CellHealthPanelProps {
  report?: CellHealthReport | null;
}

// ─── Presentation helpers ───────────────────────────────────────────────────

const SYMPTOM_LABEL: Record<SymptomType, string> = {
  vendor_flag: "Vendor flag",
  voltage_outlier: "Voltage outlier",
  temp_outlier: "Temperature outlier",
  current_mismatch: "Current mismatch",
};

const SYMPTOM_ICON: Record<SymptomType, React.ReactNode> = {
  vendor_flag: <ShieldAlert className="w-3 h-3" />,
  voltage_outlier: <Zap className="w-3 h-3" />,
  temp_outlier: <ThermometerSun className="w-3 h-3" />,
  current_mismatch: <Zap className="w-3 h-3" />,
};

function severityBadgeClass(sev: Severity): string {
  switch (sev) {
    case "critical":
      return "bg-destructive/20 text-destructive border-destructive/40";
    case "warning":
      return "bg-warning/20 text-warning border-warning/40";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

function confidenceLabel(c: Confidence): string {
  return c === "high" ? "High" : c === "medium" ? "Medium" : "Low";
}

function formatEvidence(evidence: Record<string, string | number | boolean>): string {
  return Object.entries(evidence)
    .map(([k, v]) => `${k}: ${typeof v === "number" ? formatNumber(k, v) : v}`)
    .join(" · ");
}

function formatNumber(key: string, v: number): string {
  if (key.endsWith("_mv") || key.endsWith("_a") || key.endsWith("_c")) {
    return v.toFixed(2);
  }
  if (key.endsWith("_v")) return v.toFixed(3);
  if (key === "robust_z") return v.toFixed(2);
  return v.toString();
}

// ─── Component ──────────────────────────────────────────────────────────────

const CellHealthPanel = ({ report }: CellHealthPanelProps) => {
  if (!report) return null;

  // Explicit unavailable state — not per-cell-capable adapters (e.g. Senergy).
  if (!report.available) {
    if (report.reason === "pack_level_only") {
      return (
        <div className="glass-card p-3 text-xs text-muted-foreground border border-border/40">
          Per-cell diagnostics not available for this battery type.
        </div>
      );
    }
    // no_recent_data — say nothing (the whole bank card already indicates offline).
    return null;
  }

  const allCandidates = report.units.flatMap((u) =>
    u.candidates.map((c) => ({ ...c, unit_index: u.unit_index })),
  );

  // Healthy pack: quiet green line.
  if (allCandidates.length === 0) {
    return (
      <div className="glass-card p-3 border border-success/30 bg-success/5">
        <div className="flex items-center gap-2 text-xs">
          <Info className="w-3.5 h-3.5 text-success" />
          <span className="text-success font-medium">
            No candidate cells for inspection
          </span>
          <span className="text-muted-foreground">
            ({report.units.reduce((sum, u) => sum + u.cell_count, 0)} cells analysed)
          </span>
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
              Candidate cells for inspection
            </div>
            <div className="text-[11px] text-muted-foreground">
              {allCandidates.length} cell{allCandidates.length === 1 ? "" : "s"} flagged
              across {report.units.length} unit{report.units.length === 1 ? "" : "s"}
              {" · "}algorithm {report.algorithm}
            </div>
          </div>
        </div>
      </div>

      <TooltipProvider delayDuration={150}>
        {/* Mobile: candidate cards stacked vertically */}
        <div className="sm:hidden space-y-2">
          {allCandidates.map((c, idx) => (
            <div
              key={`${c.unit_index}-${c.cell_index}-${idx}-mobile`}
              className="rounded-md border border-border/30 p-2.5 bg-background/40"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Badge variant="outline" className="text-[10px] font-mono shrink-0">
                    Unit {c.unit_index}
                  </Badge>
                  <span className="text-xs font-mono font-semibold truncate">
                    Cell {c.cell_index}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    score {c.score.toFixed(1)}
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {confidenceLabel(c.confidence)}
                  </Badge>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {c.symptoms.map((s, i) => (
                  <Tooltip key={i}>
                    <TooltipTrigger asChild>
                      <Badge
                        variant="outline"
                        className={
                          "flex items-center gap-1 border text-[10px] " +
                          severityBadgeClass(s.severity)
                        }
                      >
                        {SYMPTOM_ICON[s.type]}
                        <span>{SYMPTOM_LABEL[s.type]}</span>
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[280px] text-xs">
                      <div className="font-semibold mb-1 capitalize">
                        {s.severity} · {s.source}
                      </div>
                      <div className="text-muted-foreground break-words">
                        {formatEvidence(s.evidence)}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Desktop: table */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground text-left border-b border-border/30">
                <th className="py-1.5 pr-3 font-medium">Unit</th>
                <th className="py-1.5 pr-3 font-medium">Cell</th>
                <th className="py-1.5 pr-3 font-medium">Symptoms</th>
                <th className="py-1.5 pr-3 font-medium">Score</th>
                <th className="py-1.5 pr-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {allCandidates.map((c, idx) => (
                <tr
                  key={`${c.unit_index}-${c.cell_index}-${idx}`}
                  className="border-b border-border/10 last:border-b-0"
                >
                  <td className="py-1.5 pr-3 font-mono">{c.unit_index}</td>
                  <td className="py-1.5 pr-3 font-mono font-semibold">{c.cell_index}</td>
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
                              {s.severity} · {s.source}
                            </div>
                            <div className="text-muted-foreground">
                              {formatEvidence(s.evidence)}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                  </td>
                  <td className="py-1.5 pr-3 font-mono">{c.score.toFixed(1)}</td>
                  <td className="py-1.5 pr-3">
                    <Badge variant="outline" className="text-[10px]">
                      {confidenceLabel(c.confidence)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TooltipProvider>

      <div className="mt-3 text-[10px] text-muted-foreground leading-relaxed">
        Diagnostic heuristic — not a warranty claim. Cells are ranked by symptom
        severity within each unit. Hover a symptom for evidence.
      </div>
    </motion.div>
  );
};

export default CellHealthPanel;
