import { useState } from "react";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Package, Download, FileCode } from "lucide-react";
import { DataTable, Column, StatusBadge } from "@/components/admin/common/DataTable";
import { StatCard } from "@/components/admin/common/StatCard";
import { ConfirmDialog } from "@/components/admin/common/ConfirmDialog";
import { FileUploader } from "@/components/admin/firmware/FileUploader";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import type { FirmwareVersion } from "@/types/firmware";
import { format } from "date-fns";

// Mock data
const mockVersions: FirmwareVersion[] = [
  {
    id: "v1",
    version: "2.1.0",
    description: "Added battery optimization and improved Modbus stability",
    deviceType: "esp32_datalogger",
    isActive: true,
    fileCount: 3,
    totalSize: 156789,
    createdAt: "2024-02-10T10:00:00Z",
    createdBy: "admin@solarhub.com",
  },
  {
    id: "v2",
    version: "2.0.0",
    description: "Major update with OTA support and configuration improvements",
    deviceType: "esp32_datalogger",
    isActive: true,
    fileCount: 5,
    totalSize: 234567,
    createdAt: "2024-02-01T10:00:00Z",
    createdBy: "admin@solarhub.com",
  },
  {
    id: "v3",
    version: "1.5.2",
    description: "Bug fix for memory leak in telemetry handler",
    deviceType: "esp32_datalogger",
    isActive: false,
    fileCount: 2,
    totalSize: 98765,
    createdAt: "2024-01-15T10:00:00Z",
    createdBy: "firmware@solarhub.com",
  },
];

export default function FirmwareVersions() {
  const { hasPermission, addAuditEntry } = useAdminAuth();
  const canEdit = hasPermission("manage_firmware");

  const [versions, setVersions] = useState<FirmwareVersion[]>(mockVersions);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingVersion, setDeletingVersion] = useState<FirmwareVersion | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    version: "",
    description: "",
    deviceType: "esp32_datalogger",
  });
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);

  const filteredVersions = versions.filter(
    (version) =>
      version.version.toLowerCase().includes(search.toLowerCase()) ||
      version.description.toLowerCase().includes(search.toLowerCase())
  );

  const stats = [
    {
      title: "Total Versions",
      value: versions.length,
      description: "Firmware versions available",
      icon: <Package className="h-4 w-4" />,
    },
    {
      title: "Active Versions",
      value: versions.filter((v) => v.isActive).length,
      description: "Available for deployment",
      icon: <Package className="h-4 w-4" />,
    },
    {
      title: "Total Files",
      value: versions.reduce((sum, v) => sum + v.fileCount, 0),
      description: "Firmware files uploaded",
      icon: <FileCode className="h-4 w-4" />,
    },
  ];

  const columns: Column<FirmwareVersion>[] = [
    {
      key: "version",
      label: "Version",
      sortable: true,
      render: (value) => (
        <div className="flex items-center gap-2">
          <span className="font-semibold font-mono">{value}</span>
        </div>
      ),
    },
    {
      key: "description",
      label: "Description",
      render: (value) => (
        <span className="text-sm text-muted-foreground line-clamp-2">{value}</span>
      ),
    },
    {
      key: "fileCount",
      label: "Files",
      sortable: true,
      render: (value, row) => (
        <div className="text-sm">
          <p className="font-medium">{value} files</p>
          <p className="text-xs text-muted-foreground">
            {(row.totalSize / 1024).toFixed(1)} KB
          </p>
        </div>
      ),
    },
    {
      key: "createdAt",
      label: "Created",
      sortable: true,
      render: (value) => (
        <span className="text-sm text-muted-foreground">
          {format(new Date(value), "MMM dd, yyyy")}
        </span>
      ),
    },
    {
      key: "isActive",
      label: "Status",
      sortable: true,
      render: (value) => (
        <Badge variant={value ? "default" : "secondary"}>
          {value ? "Active" : "Inactive"}
        </Badge>
      ),
    },
  ];

  const handleCreate = () => {
    setFormData({
      version: "",
      description: "",
      deviceType: "esp32_datalogger",
    });
    setUploadedFiles([]);
    setDialogOpen(true);
  };

  const handleDelete = (version: FirmwareVersion) => {
    setDeletingVersion(version);
    setDeleteDialogOpen(true);
  };

  const handleToggleActive = (version: FirmwareVersion) => {
    const updated = { ...version, isActive: !version.isActive };
    setVersions(versions.map((v) => (v.id === version.id ? updated : v)));

    addAuditEntry({
      action: updated.isActive ? "activate" : "deactivate",
      entity: "firmware_version",
      entityId: version.id,
      details: {
        before: version,
        after: updated,
      },
    });

    toast.success(
      `Version ${version.version} ${updated.isActive ? "activated" : "deactivated"}`
    );
  };

  const handleSubmit = () => {
    if (!formData.version || !formData.description) {
      toast.error("Please fill in all required fields");
      return;
    }

    if (uploadedFiles.length === 0) {
      toast.error("Please upload at least one file");
      return;
    }

    // Check for duplicate version
    if (versions.some((v) => v.version === formData.version)) {
      toast.error("Version already exists");
      return;
    }

    const totalSize = uploadedFiles.reduce((sum, file) => sum + file.size, 0);

    const newVersion: FirmwareVersion = {
      id: `v${Date.now()}`,
      ...formData,
      isActive: true,
      fileCount: uploadedFiles.length,
      totalSize,
      createdAt: new Date().toISOString(),
      createdBy: "admin@solarhub.com",
    };

    setVersions([newVersion, ...versions]);

    addAuditEntry({
      action: "create",
      entity: "firmware_version",
      entityId: newVersion.id,
      details: {
        after: newVersion,
        metadata: {
          files: uploadedFiles.map((f) => f.name),
        },
      },
    });

    toast.success(`Firmware version ${formData.version} created successfully`);
    setDialogOpen(false);
  };

  const confirmDelete = () => {
    if (!deletingVersion) return;

    setVersions(versions.filter((v) => v.id !== deletingVersion.id));

    addAuditEntry({
      action: "delete",
      entity: "firmware_version",
      entityId: deletingVersion.id,
      details: {
        before: deletingVersion,
      },
    });

    toast.success(`Version ${deletingVersion.version} deleted successfully`);
    setDeleteDialogOpen(false);
    setDeletingVersion(null);
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Firmware Versions" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Firmware Versions</h1>
            <p className="text-muted-foreground mt-1">
              Manage firmware versions for ESP32 data loggers
            </p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Upload Firmware
            </Button>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {stats.map((stat, index) => (
            <StatCard key={index} {...stat} />
          ))}
        </div>

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search firmware versions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Table */}
        <DataTable
          data={filteredVersions}
          columns={columns}
          onDelete={canEdit ? handleDelete : undefined}
          emptyMessage="No firmware versions found"
          actions={
            canEdit
              ? [
                  {
                    label: "Toggle Active",
                    onClick: handleToggleActive,
                  },
                  {
                    label: "Download",
                    icon: <Download className="h-4 w-4" />,
                    onClick: (version) => {
                      toast.info(`Downloading version ${version.version}...`);
                    },
                  },
                ]
              : undefined
          }
        />

        {/* Create Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Upload Firmware Version</DialogTitle>
              <DialogDescription>
                Upload new firmware files for ESP32 data loggers
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="version">Version Number *</Label>
                  <Input
                    id="version"
                    placeholder="e.g., 2.1.0"
                    value={formData.version}
                    onChange={(e) =>
                      setFormData({ ...formData, version: e.target.value })
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Use semantic versioning (MAJOR.MINOR.PATCH)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="deviceType">Device Type *</Label>
                  <Input
                    id="deviceType"
                    value="ESP32 Data Logger"
                    disabled
                    className="bg-muted"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description *</Label>
                <Textarea
                  id="description"
                  placeholder="Describe the changes in this version..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Firmware Files *</Label>
                <FileUploader
                  onFilesChange={setUploadedFiles}
                  accept=".py,.json"
                  maxFiles={10}
                  maxSize={500 * 1024}
                />
                <p className="text-xs text-muted-foreground">
                  Upload Python (.py) and configuration (.json) files
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={uploadedFiles.length === 0}
              >
                Upload Version
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <ConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={confirmDelete}
          title="Delete Firmware Version"
          description={`Are you sure you want to delete version "${deletingVersion?.version}"? This action cannot be undone and will affect any campaigns using this version.`}
          confirmText="Delete"
          variant="destructive"
        />
      </div>
    </AdminLayout>
  );
}
