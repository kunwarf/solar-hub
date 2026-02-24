import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Receipt, Loader2, PlusCircle, XCircle } from "lucide-react";
import { DataTable, Column, StatusBadge } from "@/components/admin/common/DataTable";
import { ConfirmDialog } from "@/components/admin/common/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  billingSchedulesService,
  providersService,
  type BillingSchedule,
  type TouWindow,
} from "@/api/services/admin.service";

const TARIFF_CATEGORIES = [
  "residential",
  "commercial",
  "industrial",
  "agricultural",
  "A-1",
  "B-2",
  "C-1",
  "D",
];

const STATUS_OPTIONS = ["active", "inactive", "draft"] as const;

const defaultForm = (): Omit<BillingSchedule, "id" | "createdAt" | "updatedAt"> => ({
  providerId: "",
  tariffCategory: "residential",
  priceOffpeakImport: 0,
  pricePeakImport: 0,
  priceOffpeakSettlement: 0,
  pricePeakSettlement: 0,
  fixedCharge: 0,
  fuelPriceAdjustment: 0,
  quarterlyTariffAdjustment: 0,
  touWindows: {
    peak_windows: [{ start_hour: 17, end_hour: 22 }],
    timezone: "Asia/Karachi",
  },
  defaultAnchorDay: 15,
  currency: "PKR",
  netMeteringEnabled: true,
  status: "active",
  effectiveFrom: new Date().toISOString().split("T")[0],
  effectiveTo: null,
  description: null,
});

export default function BillingSchedules() {
  const { hasPermission } = useAdminAuth();
  const canEdit = hasPermission("manage_tariffs");
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editing, setEditing] = useState<BillingSchedule | null>(null);
  const [deleting, setDeleting] = useState<BillingSchedule | null>(null);
  const [filterProviderId, setFilterProviderId] = useState<string>("");
  const [form, setForm] = useState(defaultForm());

  // Data
  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ["admin", "billing-schedules", filterProviderId],
    queryFn: () =>
      billingSchedulesService.list(filterProviderId ? { providerId: filterProviderId } : undefined),
  });

  const { data: providers = [] } = useQuery({
    queryKey: ["admin", "providers"],
    queryFn: providersService.list,
  });

  const providerMap = Object.fromEntries(providers.map((p) => [p.id, p]));

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: typeof form) => billingSchedulesService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "billing-schedules"] });
      toast.success("Billing schedule created");
      setDialogOpen(false);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? "Failed to create schedule");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: typeof form }) =>
      billingSchedulesService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "billing-schedules"] });
      toast.success("Billing schedule updated");
      setDialogOpen(false);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? "Failed to update schedule");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => billingSchedulesService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "billing-schedules"] });
      toast.success("Billing schedule deleted");
      setDeleteDialogOpen(false);
    },
    onError: () => toast.error("Failed to delete schedule"),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(defaultForm());
    setDialogOpen(true);
  };

  const openEdit = (s: BillingSchedule) => {
    setEditing(s);
    setForm({
      providerId: s.providerId,
      tariffCategory: s.tariffCategory,
      priceOffpeakImport: s.priceOffpeakImport,
      pricePeakImport: s.pricePeakImport,
      priceOffpeakSettlement: s.priceOffpeakSettlement,
      pricePeakSettlement: s.pricePeakSettlement,
      fixedCharge: s.fixedCharge,
      fuelPriceAdjustment: s.fuelPriceAdjustment,
      quarterlyTariffAdjustment: s.quarterlyTariffAdjustment,
      touWindows: s.touWindows,
      defaultAnchorDay: s.defaultAnchorDay,
      currency: s.currency,
      netMeteringEnabled: s.netMeteringEnabled,
      status: s.status,
      effectiveFrom: s.effectiveFrom,
      effectiveTo: s.effectiveTo,
      description: s.description,
    });
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!form.providerId) {
      toast.error("Please select a provider");
      return;
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const addWindow = () => {
    setForm((f) => ({
      ...f,
      touWindows: {
        ...f.touWindows,
        peak_windows: [...f.touWindows.peak_windows, { start_hour: 9, end_hour: 17 }],
      },
    }));
  };

  const removeWindow = (idx: number) => {
    setForm((f) => ({
      ...f,
      touWindows: {
        ...f.touWindows,
        peak_windows: f.touWindows.peak_windows.filter((_, i) => i !== idx),
      },
    }));
  };

  const updateWindow = (idx: number, field: keyof TouWindow, value: number) => {
    setForm((f) => ({
      ...f,
      touWindows: {
        ...f.touWindows,
        peak_windows: f.touWindows.peak_windows.map((w, i) =>
          i === idx ? { ...w, [field]: value } : w
        ),
      },
    }));
  };

  const columns: Column<BillingSchedule>[] = [
    {
      key: "provider",
      label: "Provider",
      render: (_value, s) => providerMap[s.providerId]?.shortName ?? s.providerId.slice(0, 8),
    },
    { key: "tariffCategory", label: "Tariff Category", render: (_value, s) => s.tariffCategory },
    {
      key: "priceOffpeakImport",
      label: "Off-peak (₨/kWh)",
      render: (_value, s) => s.priceOffpeakImport.toFixed(2),
    },
    {
      key: "pricePeakImport",
      label: "Peak (₨/kWh)",
      render: (_value, s) => s.pricePeakImport.toFixed(2),
    },
    {
      key: "effectiveFrom",
      label: "Effective From",
      render: (_value, s) => s.effectiveFrom,
    },
    {
      key: "status",
      label: "Status",
      render: (_value, s) => <StatusBadge status={s.status} />,
    },
  ];

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <AdminLayout
      breadcrumbs={[
        { label: "Providers & Billing" },
        { label: "Billing Schedules" },
      ]}
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Receipt className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-2xl font-bold">Provider Billing Schedules</h1>
              <p className="text-sm text-muted-foreground">
                Define tariff rates per DISCO + category. Sites with matching disco_provider and
                tariff_category automatically use these rates.
              </p>
            </div>
          </div>
          {canEdit && (
            <Button onClick={openCreate} className="gap-2">
              <Plus className="w-4 h-4" />
              New Schedule
            </Button>
          )}
        </div>

        {/* Provider filter */}
        <div className="flex items-center gap-3">
          <Label className="text-sm">Filter by Provider:</Label>
          <Select
            value={filterProviderId || "all"}
            onValueChange={(v) => setFilterProviderId(v === "all" ? "" : v)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All providers" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All providers</SelectItem>
              {providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.shortName} — {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <DataTable
          columns={columns}
          data={schedules}
          onEdit={canEdit ? openEdit : undefined}
          onDelete={
            canEdit
              ? (s) => {
                  setDeleting(s);
                  setDeleteDialogOpen(true);
                }
              : undefined
          }
          emptyMessage="No billing schedules found. Create one to get started."
        />
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Billing Schedule" : "New Billing Schedule"}</DialogTitle>
            <DialogDescription>
              Define tariff rates for a provider + category combination.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {/* Provider + Category */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Provider *</Label>
                <Select
                  value={form.providerId}
                  onValueChange={(v) => setForm((f) => ({ ...f, providerId: v }))}
                  disabled={!!editing}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.shortName} — {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Tariff Category *</Label>
                <Select
                  value={form.tariffCategory}
                  onValueChange={(v) => setForm((f) => ({ ...f, tariffCategory: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TARIFF_CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Prices */}
            <div>
              <h4 className="text-sm font-semibold mb-3">Import Prices (₨/kWh)</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Off-peak Import</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.priceOffpeakImport}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, priceOffpeakImport: Number(e.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Peak Import</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.pricePeakImport}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, pricePeakImport: Number(e.target.value) }))
                    }
                  />
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold mb-3">Settlement Prices (₨/kWh)</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Off-peak Settlement</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.priceOffpeakSettlement}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, priceOffpeakSettlement: Number(e.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Peak Settlement</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.pricePeakSettlement}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, pricePeakSettlement: Number(e.target.value) }))
                    }
                  />
                </div>
              </div>
            </div>

            {/* Fixed charge & anchor day */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Fixed Monthly Charge (₨)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.fixedCharge}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, fixedCharge: Number(e.target.value) }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Default Anchor Day (1–28)</Label>
                <Input
                  type="number"
                  min={1}
                  max={28}
                  value={form.defaultAnchorDay}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, defaultAnchorDay: Number(e.target.value) }))
                  }
                />
              </div>
            </div>

            {/* Monthly Adjustments (NEPRA surcharges) */}
            <div>
              <h4 className="text-sm font-semibold mb-1">Monthly Adjustments (₨/kWh)</h4>
              <p className="text-xs text-muted-foreground mb-3">
                NEPRA-mandated surcharges applied on top of base import prices each billing cycle.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fuel Price Adjustment (FPA)</Label>
                  <Input
                    type="number"
                    step="0.0001"
                    value={form.fuelPriceAdjustment}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, fuelPriceAdjustment: Number(e.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Quarterly Tariff Adjustment (QTA)</Label>
                  <Input
                    type="number"
                    step="0.0001"
                    value={form.quarterlyTariffAdjustment}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, quarterlyTariffAdjustment: Number(e.target.value) }))
                    }
                  />
                </div>
              </div>
            </div>

            {/* Peak Time Windows */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold">Peak Time Windows</h4>
                <Button variant="outline" size="sm" onClick={addWindow} className="gap-1">
                  <PlusCircle className="w-3 h-3" />
                  Add Window
                </Button>
              </div>
              <div className="space-y-2">
                {form.touWindows.peak_windows.map((w, idx) => (
                  <div key={idx} className="flex items-center gap-3">
                    <div className="flex items-center gap-2 flex-1">
                      <Label className="text-xs w-12">Start</Label>
                      <Input
                        type="number"
                        min={0}
                        max={23}
                        value={w.start_hour}
                        onChange={(e) => updateWindow(idx, "start_hour", Number(e.target.value))}
                        className="w-20"
                      />
                      <span className="text-xs text-muted-foreground">:00</span>
                    </div>
                    <div className="flex items-center gap-2 flex-1">
                      <Label className="text-xs w-12">End</Label>
                      <Input
                        type="number"
                        min={0}
                        max={23}
                        value={w.end_hour}
                        onChange={(e) => updateWindow(idx, "end_hour", Number(e.target.value))}
                        className="w-20"
                      />
                      <span className="text-xs text-muted-foreground">:00</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeWindow(idx)}
                      disabled={form.touWindows.peak_windows.length <= 1}
                    >
                      <XCircle className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Status & Dates */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={form.status}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, status: v as BillingSchedule["status"] }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Effective From</Label>
                <Input
                  type="date"
                  value={form.effectiveFrom}
                  onChange={(e) => setForm((f) => ({ ...f, effectiveFrom: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Effective To (optional)</Label>
                <Input
                  type="date"
                  value={form.effectiveTo ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, effectiveTo: e.target.value || null }))
                  }
                />
              </div>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Input
                value={form.description ?? ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value || null }))
                }
                placeholder="e.g. LESCO residential rates effective Jan 2026"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Save Changes" : "Create Schedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete Billing Schedule"
        description={`Delete the ${deleting?.tariffCategory} schedule for ${
          deleting ? (providerMap[deleting.providerId]?.shortName ?? "this provider") : ""
        }? Sites using this schedule will fall back to per-site configuration.`}
        confirmText="Delete"
        variant="destructive"
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </AdminLayout>
  );
}
