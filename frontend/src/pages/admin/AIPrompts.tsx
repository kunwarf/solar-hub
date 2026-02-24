/**
 * Admin AI Prompts page.
 *
 * Allows admins to view and edit the 6 Claude prompt templates
 * (hourly/monthly/yearly × system/user) stored in the database.
 *
 * Each template edit creates an immutable version snapshot.
 * The page shows a variable reference panel so admins know what
 * {placeholders} are available in each template.
 */
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sparkles,
  ChevronDown,
  Save,
  History,
  RotateCcw,
  Loader2,
  CheckCircle2,
  Code2,
} from "lucide-react";
import { toast } from "sonner";
import {
  aiPromptsService,
  type PromptTemplate,
  type PromptTemplateVersion,
} from "@/api/services/admin.service";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TIER_LABELS: Record<string, string> = {
  hourly: "Hourly",
  monthly: "Monthly",
  yearly: "Yearly",
};

const TIER_DESCRIPTIONS: Record<string, string> = {
  hourly: "Called every hour using live telemetry. Cached 60 minutes.",
  monthly: "Called once per day with billing month data. Cached 24 hours.",
  yearly: "Called once per billing month with year-to-date data. Cached 30 days.",
};

const AVAILABLE_MODELS = [
  { value: "claude-haiku-4-5-20251001", label: "Haiku 4.5 (Fastest)" },
  { value: "claude-sonnet-4-6",         label: "Sonnet 4.6 (Balanced)" },
  { value: "claude-opus-4-6",           label: "Opus 4.6 (Most Capable)" },
];

const TIER_MODEL_DEFAULTS: Record<string, string> = {
  hourly:  "claude-haiku-4-5-20251001",
  monthly: "claude-sonnet-4-6",
  yearly:  "claude-sonnet-4-6",
};

const TYPE_LABELS: Record<string, string> = {
  system: "System Prompt",
  user: "User Prompt",
};

const TIER_COLORS: Record<string, string> = {
  hourly: "bg-blue-100 text-blue-800",
  monthly: "bg-purple-100 text-purple-800",
  yearly: "bg-orange-100 text-orange-800",
};

// Group templates by tier
function groupByTier(templates: PromptTemplate[]) {
  const groups: Record<string, PromptTemplate[]> = {};
  for (const t of templates) {
    if (!groups[t.tier]) groups[t.tier] = [];
    groups[t.tier].push(t);
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Variable reference panel
// ---------------------------------------------------------------------------

function VariablePanel({ variables }: { variables: PromptTemplate["variables"] }) {
  const [open, setOpen] = useState(false);
  if (!variables?.length) return null;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="flex items-center gap-1 text-xs">
          <Code2 className="h-3 w-3" />
          Variable reference ({variables.length})
          <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 rounded-md border bg-muted/40 p-3 text-xs space-y-1">
          {variables.map((v) => (
            <div key={v.name} className="flex gap-2">
              <code className="font-mono text-blue-700 min-w-[180px]">{`{${v.name}}`}</code>
              <span className="text-muted-foreground">{v.description}</span>
              {v.example && (
                <span className="text-muted-foreground italic">e.g. {v.example}</span>
              )}
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Template editor dialog
// ---------------------------------------------------------------------------

interface EditorDialogProps {
  template: PromptTemplate | null;
  onClose: () => void;
}

function EditorDialog({ template, onClose }: EditorDialogProps) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(template?.template ?? "");
  const [changeNote, setChangeNote] = useState("");
  const [versionsOpen, setVersionsOpen] = useState(false);

  const updateMutation = useMutation({
    mutationFn: () =>
      aiPromptsService.update(template!.key, text, changeNote || undefined),
    onSuccess: () => {
      toast.success("Prompt template saved and cache invalidated.");
      queryClient.invalidateQueries({ queryKey: ["adminAiPrompts"] });
      onClose();
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? "Failed to save template.");
    },
  });

  const { data: versions, isLoading: versionsLoading } = useQuery({
    queryKey: ["adminAiPromptVersions", template?.key],
    queryFn: () => aiPromptsService.listVersions(template!.key),
    enabled: !!template && versionsOpen,
  });

  const revertMutation = useMutation({
    mutationFn: (version: number) =>
      aiPromptsService.revert(template!.key, version),
    onSuccess: () => {
      toast.success("Reverted to selected version.");
      queryClient.invalidateQueries({ queryKey: ["adminAiPrompts"] });
      onClose();
    },
    onError: () => toast.error("Failed to revert template."),
  });

  if (!template) return null;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-600" />
            Edit: {template.key}
          </DialogTitle>
          <DialogDescription>
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mr-2 ${TIER_COLORS[template.tier]}`}>
              {TIER_LABELS[template.tier]}
            </span>
            <span className="text-muted-foreground">
              {TYPE_LABELS[template.prompt_type]} — v{template.version}
            </span>
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="edit" className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="w-fit">
            <TabsTrigger value="edit">Edit</TabsTrigger>
            <TabsTrigger value="history" onClick={() => setVersionsOpen(true)}>
              <History className="h-3.5 w-3.5 mr-1" /> History
            </TabsTrigger>
          </TabsList>

          {/* Edit tab */}
          <TabsContent value="edit" className="flex-1 overflow-auto space-y-3">
            <VariablePanel variables={template.variables} />
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="font-mono text-xs min-h-[350px] resize-none"
              placeholder="Enter prompt template text…"
            />
            <div className="space-y-1">
              <Label htmlFor="change-note" className="text-xs">
                Change note (optional)
              </Label>
              <Input
                id="change-note"
                value={changeNote}
                onChange={(e) => setChangeNote(e.target.value)}
                placeholder="Briefly describe what you changed…"
                className="text-sm"
              />
            </div>
          </TabsContent>

          {/* History tab */}
          <TabsContent value="history" className="flex-1 overflow-auto">
            {versionsLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading versions…
              </div>
            ) : versions && versions.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Version</TableHead>
                    <TableHead>Changed</TableHead>
                    <TableHead>Note</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {versions.map((v: PromptTemplateVersion) => (
                    <TableRow key={v.id}>
                      <TableCell className="font-mono text-xs">v{v.version}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(v.changed_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-xs">{v.change_note ?? "—"}</TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs"
                          disabled={revertMutation.isPending}
                          onClick={() => revertMutation.mutate(v.version)}
                        >
                          <RotateCcw className="h-3 w-3 mr-1" />
                          Revert
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-muted-foreground text-sm py-8 text-center">
                No version history yet.
              </p>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending || !text.trim()}
          >
            {updateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save & Publish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AIPrompts() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [tierModels, setTierModels] = useState<Record<string, string>>(TIER_MODEL_DEFAULTS);

  const { data, isLoading, error } = useQuery({
    queryKey: ["adminAiPrompts"],
    queryFn: aiPromptsService.list,
  });

  // Initialise tier models from the first template per tier that has a model set
  useEffect(() => {
    if (data) {
      const resolved: Record<string, string> = { ...TIER_MODEL_DEFAULTS };
      for (const tmpl of data) {
        if (tmpl.model && !resolved[tmpl.tier + "_set"]) {
          resolved[tmpl.tier] = tmpl.model;
          resolved[tmpl.tier + "_set"] = "1"; // mark as loaded from server
        }
      }
      // Clean up sentinel keys
      const clean: Record<string, string> = {};
      for (const [k, v] of Object.entries(resolved)) {
        if (!k.endsWith("_set")) clean[k] = v;
      }
      setTierModels(clean);
    }
  }, [data]);

  const setTierModelMutation = useMutation({
    mutationFn: ({ tier, model }: { tier: string; model: string }) =>
      aiPromptsService.setTierModel(tier, model),
    onSuccess: (_data, { tier, model }) => {
      setTierModels((prev) => ({ ...prev, [tier]: model }));
      const label = AVAILABLE_MODELS.find((m) => m.value === model)?.label ?? model;
      toast.success(`${TIER_LABELS[tier]} tier model updated to ${label}.`);
      queryClient.invalidateQueries({ queryKey: ["adminAiPrompts"] });
    },
    onError: () => toast.error("Failed to update model."),
  });

  const grouped = data ? groupByTier(data) : {};
  const tierOrder = ["hourly", "monthly", "yearly"];

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-7 w-7 text-purple-600" />
            AI Prompt Templates
          </h1>
          <p className="text-muted-foreground mt-1">
            Edit the Claude prompts used for hourly, monthly, and yearly energy insights.
            Changes take effect immediately (Redis cache invalidated on save).
          </p>
        </div>

        {/* Info banner */}
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-start gap-3 text-sm">
              <CheckCircle2 className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-blue-900">How it works</p>
                <p className="text-blue-700 mt-0.5">
                  Templates use Python-style <code className="font-mono bg-blue-100 px-1 rounded">{"{variable}"}</code> placeholders.
                  Unknown placeholders are left unchanged.
                  Every save creates an immutable version — you can always revert.
                  The prompt loader caches from DB for 5 minutes; saving here invalidates the cache immediately.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Template cards grouped by tier */}
        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading templates…
          </div>
        )}

        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-4 text-sm text-red-700">
              Failed to load prompt templates. Check that you are logged in as admin.
            </CardContent>
          </Card>
        )}

        {tierOrder.map((tier) => {
          const templates = grouped[tier];
          if (!templates?.length) return null;
          return (
            <Card key={tier}>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between gap-2 text-base">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[tier]}`}>
                      {TIER_LABELS[tier]}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-normal">Model:</span>
                    <Select
                      value={tierModels[tier] ?? TIER_MODEL_DEFAULTS[tier]}
                      onValueChange={(model) =>
                        setTierModelMutation.mutate({ tier, model })
                      }
                      disabled={setTierModelMutation.isPending}
                    >
                      <SelectTrigger className="h-7 w-[200px] text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {AVAILABLE_MODELS.map((m) => (
                          <SelectItem key={m.value} value={m.value} className="text-xs">
                            {m.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardTitle>
                <CardDescription className="text-xs">
                  {TIER_DESCRIPTIONS[tier]}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {templates
                    .sort((a, b) => a.prompt_type.localeCompare(b.prompt_type))
                    .map((tmpl) => (
                      <div
                        key={tmpl.key}
                        className="rounded-lg border p-4 space-y-3 hover:bg-muted/30 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium">{TYPE_LABELS[tmpl.prompt_type]}</p>
                            <p className="text-xs text-muted-foreground font-mono">{tmpl.key}</p>
                          </div>
                          <Badge variant="outline" className="text-xs">
                            v{tmpl.version}
                          </Badge>
                        </div>
                        <pre className="text-xs text-muted-foreground bg-muted rounded p-2 overflow-hidden max-h-20 whitespace-pre-wrap line-clamp-3">
                          {tmpl.template.slice(0, 200)}
                          {tmpl.template.length > 200 ? "…" : ""}
                        </pre>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">
                            {tmpl.variables?.length ?? 0} variable(s) available
                          </span>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditing(tmpl)}
                          >
                            Edit
                          </Button>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Editor dialog */}
      {editing && (
        <EditorDialog template={editing} onClose={() => setEditing(null)} />
      )}
    </AdminLayout>
  );
}
