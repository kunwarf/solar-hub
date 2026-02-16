import { useState } from "react";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, DollarSign, Trash2 } from "lucide-react";
import { DataTable, Column, StatusBadge } from "@/components/admin/common/DataTable";
import { StatCard } from "@/components/admin/common/StatCard";
import { ConfirmDialog } from "@/components/admin/common/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import type { TariffPlan } from "@/types/admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Mock data
const mockTariffs: TariffPlan[] = [
  {
    id: "t1",
    providerId: "p1",
    name: "Residential Unprotected",
    category: "residential",
    type: "slab",
    rates: {
      slabs: [
        { minUnits: 0, maxUnits: 100, ratePerKwh: 7.74 },
        { minUnits: 101, maxUnits: 200, ratePerKwh: 11.50 },
        { minUnits: 201, maxUnits: 300, ratePerKwh: 16.00 },
        { minUnits: 301, maxUnits: 700, ratePerKwh: 24.00 },
        { minUnits: 701, maxUnits: null, ratePerKwh: 32.00 },
      ],
    },
    fixedCharges: 150,
    effectiveFrom: "2024-01-01",
    effectiveTo: null,
    status: "active",
  },
];

const mockProviders = [
  { id: "p1", name: "LESCO" },
  { id: "p2", name: "K-Electric" },
  { id: "p3", name: "MEPCO" },
];

interface SlabFormData {
  minUnits: number;
  maxUnits: number | null;
  ratePerKwh: number;
}

export default function TariffManagement() {
  const { hasPermission, addAuditEntry } = useAdminAuth();
  const canEdit = hasPermission("manage_tariffs");

  const [tariffs, setTariffs] = useState<TariffPlan[]>(mockTariffs);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingTariff, setEditingTariff] = useState<TariffPlan | null>(null);
  const [deletingTariff, setDeletingTariff] = useState<TariffPlan | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    providerId: "",
    name: "",
    category: "residential" as "residential" | "commercial" | "industrial",
    type: "slab" as "slab" | "tou" | "flat",
    fixedCharges: 0,
    effectiveFrom: "",
    status: "active" as "active" | "inactive" | "draft",
  });

  const [slabs, setSlabs] = useState<SlabFormData[]>([
    { minUnits: 0, maxUnits: 100, ratePerKwh: 0 },
  ]);

  const [touRates, setTouRates] = useState({
    peakRate: 0,
    offPeakRate: 0,
  });

  const [flatRate, setFlatRate] = useState(0);

  const filteredTariffs = tariffs.filter(
    (tariff) =>
      tariff.name.toLowerCase().includes(search.toLowerCase()) ||
      tariff.category.toLowerCase().includes(search.toLowerCase())
  );

  const stats = [
    {
      title: "Total Tariff Plans",
      value: tariffs.length,
      description: "Configured tariff plans",
      icon: <DollarSign className="h-4 w-4" />,
    },
    {
      title: "Active Plans",
      value: tariffs.filter((t) => t.status === "active").length,
      description: "Currently in use",
      icon: <DollarSign className="h-4 w-4" />,
    },
  ];

  const columns: Column<TariffPlan>[] = [
    {
      key: "name",
      label: "Tariff Name",
      sortable: true,
      render: (value) => <span className="font-semibold">{value}</span>,
    },
    {
      key: "category",
      label: "Category",
      sortable: true,
      render: (value) => (
        <span className="capitalize text-muted-foreground">{value}</span>
      ),
    },
    {
      key: "type",
      label: "Type",
      sortable: true,
      render: (value) => (
        <span className="uppercase text-xs font-medium">{value}</span>
      ),
    },
    {
      key: "fixedCharges",
      label: "Fixed Charges",
      sortable: true,
      render: (value) => `PKR ${value}`,
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (value) => <StatusBadge status={value} />,
    },
  ];

  const handleCreate = () => {
    setEditingTariff(null);
    setFormData({
      providerId: "",
      name: "",
      category: "residential",
      type: "slab",
      fixedCharges: 0,
      effectiveFrom: new Date().toISOString().split("T")[0],
      status: "draft",
    });
    setSlabs([{ minUnits: 0, maxUnits: 100, ratePerKwh: 0 }]);
    setTouRates({ peakRate: 0, offPeakRate: 0 });
    setFlatRate(0);
    setDialogOpen(true);
  };

  const handleEdit = (tariff: TariffPlan) => {
    setEditingTariff(tariff);
    setFormData({
      providerId: tariff.providerId,
      name: tariff.name,
      category: tariff.category,
      type: tariff.type,
      fixedCharges: tariff.fixedCharges,
      effectiveFrom: tariff.effectiveFrom,
      status: tariff.status,
    });

    if (tariff.type === "slab" && tariff.rates.slabs) {
      setSlabs(tariff.rates.slabs);
    } else if (tariff.type === "tou") {
      setTouRates({
        peakRate: tariff.rates.touPeakRate || 0,
        offPeakRate: tariff.rates.touOffPeakRate || 0,
      });
    } else if (tariff.type === "flat") {
      setFlatRate(tariff.rates.flatRate || 0);
    }

    setDialogOpen(true);
  };

  const handleDelete = (tariff: TariffPlan) => {
    setDeletingTariff(tariff);
    setDeleteDialogOpen(true);
  };

  const addSlab = () => {
    const lastSlab = slabs[slabs.length - 1];
    const newMinUnits = lastSlab.maxUnits ? lastSlab.maxUnits + 1 : 0;
    setSlabs([...slabs, { minUnits: newMinUnits, maxUnits: null, ratePerKwh: 0 }]);
  };

  const removeSlab = (index: number) => {
    if (slabs.length > 1) {
      setSlabs(slabs.filter((_, i) => i !== index));
    }
  };

  const updateSlab = (index: number, field: keyof SlabFormData, value: any) => {
    const updated = [...slabs];
    updated[index] = { ...updated[index], [field]: value };
    setSlabs(updated);
  };

  const handleSubmit = () => {
    if (!formData.name || !formData.providerId) {
      toast.error("Please fill in all required fields");
      return;
    }

    let rates: TariffPlan["rates"] = {};
    if (formData.type === "slab") {
      rates.slabs = slabs;
    } else if (formData.type === "tou") {
      rates.touPeakRate = touRates.peakRate;
      rates.touOffPeakRate = touRates.offPeakRate;
    } else if (formData.type === "flat") {
      rates.flatRate = flatRate;
    }

    if (editingTariff) {
      const updated: TariffPlan = {
        ...editingTariff,
        ...formData,
        rates,
      };
      setTariffs(tariffs.map((t) => (t.id === editingTariff.id ? updated : t)));

      addAuditEntry({
        action: "update",
        entity: "tariff",
        entityId: editingTariff.id,
        details: {
          before: editingTariff,
          after: updated,
        },
      });

      toast.success("Tariff plan updated successfully");
    } else {
      const newTariff: TariffPlan = {
        id: `t${Date.now()}`,
        ...formData,
        rates,
        effectiveTo: null,
      };
      setTariffs([...tariffs, newTariff]);

      addAuditEntry({
        action: "create",
        entity: "tariff",
        entityId: newTariff.id,
        details: {
          after: newTariff,
        },
      });

      toast.success("Tariff plan created successfully");
    }

    setDialogOpen(false);
  };

  const confirmDelete = () => {
    if (!deletingTariff) return;

    setTariffs(tariffs.filter((t) => t.id !== deletingTariff.id));

    addAuditEntry({
      action: "delete",
      entity: "tariff",
      entityId: deletingTariff.id,
      details: {
        before: deletingTariff,
      },
    });

    toast.success("Tariff plan deleted successfully");
    setDeleteDialogOpen(false);
    setDeletingTariff(null);
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Tariff Management" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Tariff Management</h1>
            <p className="text-muted-foreground mt-1">
              Configure electricity tariff plans and rate structures
            </p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add Tariff Plan
            </Button>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {stats.map((stat, index) => (
            <StatCard key={index} {...stat} />
          ))}
        </div>

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search tariff plans..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Table */}
        <DataTable
          data={filteredTariffs}
          columns={columns}
          onEdit={canEdit ? handleEdit : undefined}
          onDelete={canEdit ? handleDelete : undefined}
          emptyMessage="No tariff plans found"
        />

        {/* Create/Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingTariff ? "Edit Tariff Plan" : "Add New Tariff Plan"}
              </DialogTitle>
              <DialogDescription>
                {editingTariff
                  ? "Update the tariff plan details and rate structure"
                  : "Configure a new electricity tariff plan"}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="provider">Provider *</Label>
                  <Select
                    value={formData.providerId}
                    onValueChange={(value) =>
                      setFormData({ ...formData, providerId: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {mockProviders.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="name">Tariff Name *</Label>
                  <Input
                    id="name"
                    placeholder="e.g., Residential Unprotected"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="category">Category *</Label>
                  <Select
                    value={formData.category}
                    onValueChange={(value: any) =>
                      setFormData({ ...formData, category: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="residential">Residential</SelectItem>
                      <SelectItem value="commercial">Commercial</SelectItem>
                      <SelectItem value="industrial">Industrial</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="type">Tariff Type *</Label>
                  <Select
                    value={formData.type}
                    onValueChange={(value: any) =>
                      setFormData({ ...formData, type: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="slab">Slab-based</SelectItem>
                      <SelectItem value="tou">Time of Use (ToU)</SelectItem>
                      <SelectItem value="flat">Flat Rate</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="fixedCharges">Fixed Charges (PKR) *</Label>
                  <Input
                    id="fixedCharges"
                    type="number"
                    value={formData.fixedCharges}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        fixedCharges: Number(e.target.value),
                      })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="effectiveFrom">Effective From *</Label>
                  <Input
                    id="effectiveFrom"
                    type="date"
                    value={formData.effectiveFrom}
                    onChange={(e) =>
                      setFormData({ ...formData, effectiveFrom: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="status">Status *</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value: any) =>
                      setFormData({ ...formData, status: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Rate Structure */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Rate Structure</CardTitle>
                </CardHeader>
                <CardContent>
                  {formData.type === "slab" && (
                    <div className="space-y-3">
                      {slabs.map((slab, index) => (
                        <div key={index} className="flex items-end gap-2">
                          <div className="flex-1 space-y-2">
                            <Label className="text-xs">Min Units</Label>
                            <Input
                              type="number"
                              value={slab.minUnits}
                              onChange={(e) =>
                                updateSlab(index, "minUnits", Number(e.target.value))
                              }
                            />
                          </div>
                          <div className="flex-1 space-y-2">
                            <Label className="text-xs">Max Units</Label>
                            <Input
                              type="number"
                              value={slab.maxUnits || ""}
                              onChange={(e) =>
                                updateSlab(
                                  index,
                                  "maxUnits",
                                  e.target.value ? Number(e.target.value) : null
                                )
                              }
                              placeholder="Unlimited"
                            />
                          </div>
                          <div className="flex-1 space-y-2">
                            <Label className="text-xs">Rate (PKR/kWh)</Label>
                            <Input
                              type="number"
                              step="0.01"
                              value={slab.ratePerKwh}
                              onChange={(e) =>
                                updateSlab(index, "ratePerKwh", Number(e.target.value))
                              }
                            />
                          </div>
                          {slabs.length > 1 && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeSlab(index)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      ))}
                      <Button variant="outline" size="sm" onClick={addSlab}>
                        <Plus className="mr-2 h-3 w-3" />
                        Add Slab
                      </Button>
                    </div>
                  )}

                  {formData.type === "tou" && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Peak Rate (PKR/kWh)</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={touRates.peakRate}
                          onChange={(e) =>
                            setTouRates({ ...touRates, peakRate: Number(e.target.value) })
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Off-Peak Rate (PKR/kWh)</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={touRates.offPeakRate}
                          onChange={(e) =>
                            setTouRates({
                              ...touRates,
                              offPeakRate: Number(e.target.value),
                            })
                          }
                        />
                      </div>
                    </div>
                  )}

                  {formData.type === "flat" && (
                    <div className="space-y-2">
                      <Label>Flat Rate (PKR/kWh)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={flatRate}
                        onChange={(e) => setFlatRate(Number(e.target.value))}
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit}>
                {editingTariff ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <ConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={confirmDelete}
          title="Delete Tariff Plan"
          description={`Are you sure you want to delete "${deletingTariff?.name}"? This action cannot be undone.`}
          confirmText="Delete"
          variant="destructive"
        />
      </div>
    </AdminLayout>
  );
}
