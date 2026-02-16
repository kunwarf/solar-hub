import { useState } from "react";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Zap } from "lucide-react";
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
import type { ElectricityProvider } from "@/types/admin";

// Mock data - replace with API calls
const mockProviders: ElectricityProvider[] = [
  {
    id: "p1",
    name: "Lahore Electric Supply Company",
    shortName: "LESCO",
    region: "Punjab",
    status: "active",
    tariffCount: 5,
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-15T10:00:00Z",
  },
  {
    id: "p2",
    name: "K-Electric Limited",
    shortName: "K-Electric",
    region: "Sindh",
    status: "active",
    tariffCount: 8,
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-15T10:00:00Z",
  },
  {
    id: "p3",
    name: "Multan Electric Power Company",
    shortName: "MEPCO",
    region: "Punjab",
    status: "active",
    tariffCount: 4,
    createdAt: "2024-01-16T10:00:00Z",
    updatedAt: "2024-01-16T10:00:00Z",
  },
  {
    id: "p4",
    name: "Islamabad Electric Supply Company",
    shortName: "IESCO",
    region: "ICT",
    status: "active",
    tariffCount: 6,
    createdAt: "2024-01-17T10:00:00Z",
    updatedAt: "2024-01-17T10:00:00Z",
  },
];

const regions = ["Punjab", "Sindh", "KPK", "Balochistan", "ICT"];

export default function ElectricityProviders() {
  const { hasPermission, addAuditEntry } = useAdminAuth();
  const canEdit = hasPermission("manage_providers");

  const [providers, setProviders] = useState<ElectricityProvider[]>(mockProviders);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ElectricityProvider | null>(null);
  const [deletingProvider, setDeletingProvider] = useState<ElectricityProvider | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    shortName: "",
    region: "",
    status: "active" as "active" | "inactive",
  });

  const filteredProviders = providers.filter(
    (provider) =>
      provider.name.toLowerCase().includes(search.toLowerCase()) ||
      provider.shortName.toLowerCase().includes(search.toLowerCase()) ||
      provider.region.toLowerCase().includes(search.toLowerCase())
  );

  const stats = [
    {
      title: "Total Providers",
      value: providers.length,
      description: "Configured electricity providers",
      icon: <Zap className="h-4 w-4" />,
    },
    {
      title: "Active Providers",
      value: providers.filter((p) => p.status === "active").length,
      description: "Currently operational",
      icon: <Zap className="h-4 w-4" />,
    },
  ];

  const columns: Column<ElectricityProvider>[] = [
    {
      key: "shortName",
      label: "Short Name",
      sortable: true,
      render: (value) => <span className="font-semibold">{value}</span>,
    },
    {
      key: "name",
      label: "Full Name",
      sortable: true,
    },
    {
      key: "region",
      label: "Region",
      sortable: true,
    },
    {
      key: "tariffCount",
      label: "Tariff Plans",
      sortable: true,
      render: (value) => <span className="text-muted-foreground">{value}</span>,
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (value) => <StatusBadge status={value} />,
    },
  ];

  const handleCreate = () => {
    setEditingProvider(null);
    setFormData({
      name: "",
      shortName: "",
      region: "",
      status: "active",
    });
    setDialogOpen(true);
  };

  const handleEdit = (provider: ElectricityProvider) => {
    setEditingProvider(provider);
    setFormData({
      name: provider.name,
      shortName: provider.shortName,
      region: provider.region,
      status: provider.status,
    });
    setDialogOpen(true);
  };

  const handleDelete = (provider: ElectricityProvider) => {
    setDeletingProvider(provider);
    setDeleteDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!formData.name || !formData.shortName || !formData.region) {
      toast.error("Please fill in all required fields");
      return;
    }

    if (editingProvider) {
      // Update existing
      const updated: ElectricityProvider = {
        ...editingProvider,
        ...formData,
        updatedAt: new Date().toISOString(),
      };
      setProviders(providers.map((p) => (p.id === editingProvider.id ? updated : p)));

      addAuditEntry({
        action: "update",
        entity: "provider",
        entityId: editingProvider.id,
        details: {
          before: editingProvider,
          after: updated,
        },
      });

      toast.success("Provider updated successfully");
    } else {
      // Create new
      const newProvider: ElectricityProvider = {
        id: `p${Date.now()}`,
        ...formData,
        tariffCount: 0,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      setProviders([...providers, newProvider]);

      addAuditEntry({
        action: "create",
        entity: "provider",
        entityId: newProvider.id,
        details: {
          after: newProvider,
        },
      });

      toast.success("Provider created successfully");
    }

    setDialogOpen(false);
  };

  const confirmDelete = () => {
    if (!deletingProvider) return;

    setProviders(providers.filter((p) => p.id !== deletingProvider.id));

    addAuditEntry({
      action: "delete",
      entity: "provider",
      entityId: deletingProvider.id,
      details: {
        before: deletingProvider,
      },
    });

    toast.success("Provider deleted successfully");
    setDeleteDialogOpen(false);
    setDeletingProvider(null);
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Electricity Providers" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Electricity Providers</h1>
            <p className="text-muted-foreground mt-1">
              Manage electricity distribution companies (DISCOs) and their configurations
            </p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add Provider
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
              placeholder="Search providers..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Table */}
        <DataTable
          data={filteredProviders}
          columns={columns}
          onEdit={canEdit ? handleEdit : undefined}
          onDelete={canEdit ? handleDelete : undefined}
          emptyMessage="No providers found"
        />

        {/* Create/Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingProvider ? "Edit Provider" : "Add New Provider"}
              </DialogTitle>
              <DialogDescription>
                {editingProvider
                  ? "Update the electricity provider details"
                  : "Configure a new electricity distribution company"}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name *</Label>
                <Input
                  id="name"
                  placeholder="e.g., Lahore Electric Supply Company"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="shortName">Short Name *</Label>
                <Input
                  id="shortName"
                  placeholder="e.g., LESCO"
                  value={formData.shortName}
                  onChange={(e) => setFormData({ ...formData, shortName: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="region">Region *</Label>
                <Select
                  value={formData.region}
                  onValueChange={(value) => setFormData({ ...formData, region: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select region" />
                  </SelectTrigger>
                  <SelectContent>
                    {regions.map((region) => (
                      <SelectItem key={region} value={region}>
                        {region}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="status">Status *</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value: "active" | "inactive") =>
                    setFormData({ ...formData, status: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit}>
                {editingProvider ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <ConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={confirmDelete}
          title="Delete Provider"
          description={`Are you sure you want to delete "${deletingProvider?.name}"? This action cannot be undone.`}
          confirmText="Delete"
          variant="destructive"
        />
      </div>
    </AdminLayout>
  );
}
