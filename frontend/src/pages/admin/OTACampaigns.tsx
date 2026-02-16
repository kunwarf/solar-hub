import { useState } from "react";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Rocket, Play, Pause, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { DataTable, Column } from "@/components/admin/common/DataTable";
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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import type { FirmwareUpdateCampaign, DeviceFirmwareStatus } from "@/types/firmware";
import { format } from "date-fns";
import { Slider } from "@/components/ui/slider";

// Mock data
const mockCampaigns: FirmwareUpdateCampaign[] = [
  {
    id: "c1",
    name: "v2.1.0 Production Rollout",
    description: "Battery optimization update for all devices",
    versionId: "v1",
    version: "2.1.0",
    targetDevices: ["all"],
    rolloutStrategy: "staged",
    rolloutPercentage: 50,
    status: "active",
    startedAt: "2024-02-15T10:00:00Z",
    statistics: {
      totalDevices: 1834,
      pending: 234,
      downloading: 45,
      applying: 12,
      success: 826,
      failed: 17,
    },
    createdAt: "2024-02-15T09:00:00Z",
    createdBy: "admin@solarhub.com",
  },
  {
    id: "c2",
    name: "v2.0.0 Canary Test",
    description: "Testing major update on canary devices",
    versionId: "v2",
    version: "2.0.0",
    targetDevices: ["SH01IN001", "SH01IN002"],
    rolloutStrategy: "canary",
    rolloutPercentage: 5,
    status: "completed",
    startedAt: "2024-02-01T10:00:00Z",
    completedAt: "2024-02-02T15:30:00Z",
    statistics: {
      totalDevices: 2,
      pending: 0,
      downloading: 0,
      applying: 0,
      success: 2,
      failed: 0,
    },
    createdAt: "2024-02-01T09:00:00Z",
    createdBy: "firmware@solarhub.com",
  },
];

const mockDeviceStatuses: DeviceFirmwareStatus[] = [
  {
    deviceSerial: "SH01IN001",
    deviceName: "Site A - Main Inverter",
    currentVersion: "2.1.0",
    updateStatus: "up_to_date",
    progress: 100,
    lastCheckAt: "2024-02-15T14:30:00Z",
    deviceInfo: {
      freeMemory: 45678,
      totalMemory: 524288,
      uptime: 86400,
    },
  },
  {
    deviceSerial: "SH01IN002",
    deviceName: "Site B - Secondary",
    currentVersion: "2.0.0",
    targetVersion: "2.1.0",
    updateStatus: "downloading",
    progress: 45,
    lastCheckAt: "2024-02-15T14:32:00Z",
    deviceInfo: {
      freeMemory: 38912,
      totalMemory: 524288,
      uptime: 172800,
    },
  },
  {
    deviceSerial: "SH01IN003",
    deviceName: "Site C - Test Unit",
    currentVersion: "2.0.0",
    targetVersion: "2.1.0",
    updateStatus: "failed",
    progress: 0,
    lastCheckAt: "2024-02-15T14:25:00Z",
    errorMessage: "Insufficient memory",
    deviceInfo: {
      freeMemory: 12345,
      totalMemory: 524288,
      uptime: 259200,
    },
  },
];

const mockVersions = [
  { id: "v1", version: "2.1.0" },
  { id: "v2", version: "2.0.0" },
  { id: "v3", version: "1.5.2" },
];

export default function OTACampaigns() {
  const { hasPermission, addAuditEntry } = useAdminAuth();
  const canEdit = hasPermission("manage_campaigns");

  const [campaigns, setCampaigns] = useState<FirmwareUpdateCampaign[]>(mockCampaigns);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<FirmwareUpdateCampaign | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    versionId: "",
    rolloutStrategy: "staged" as "immediate" | "staged" | "canary",
    rolloutPercentage: 10,
    targetDevices: "all",
  });

  const filteredCampaigns = campaigns.filter(
    (campaign) =>
      campaign.name.toLowerCase().includes(search.toLowerCase()) ||
      campaign.version.toLowerCase().includes(search.toLowerCase())
  );

  const activeCampaigns = campaigns.filter((c) => c.status === "active");
  const totalDevicesUpdating = activeCampaigns.reduce(
    (sum, c) => sum + c.statistics.downloading + c.statistics.applying,
    0
  );

  const stats = [
    {
      title: "Total Campaigns",
      value: campaigns.length,
      description: "All update campaigns",
      icon: <Rocket className="h-4 w-4" />,
    },
    {
      title: "Active Campaigns",
      value: activeCampaigns.length,
      description: "Currently running",
      icon: <Play className="h-4 w-4" />,
    },
    {
      title: "Devices Updating",
      value: totalDevicesUpdating,
      description: "In progress",
      icon: <Loader2 className="h-4 w-4" />,
    },
  ];

  const columns: Column<FirmwareUpdateCampaign>[] = [
    {
      key: "name",
      label: "Campaign Name",
      sortable: true,
      render: (value, row) => (
        <div>
          <p className="font-semibold">{value}</p>
          <p className="text-xs text-muted-foreground">Version {row.version}</p>
        </div>
      ),
    },
    {
      key: "rolloutStrategy",
      label: "Strategy",
      sortable: true,
      render: (value, row) => (
        <div>
          <Badge variant="outline" className="capitalize">
            {value}
          </Badge>
          {row.rolloutPercentage < 100 && (
            <p className="text-xs text-muted-foreground mt-1">
              {row.rolloutPercentage}% rollout
            </p>
          )}
        </div>
      ),
    },
    {
      key: "statistics",
      label: "Progress",
      render: (stats) => {
        const total = stats.totalDevices;
        const completed = stats.success + stats.failed;
        const percentage = total > 0 ? (completed / total) * 100 : 0;

        return (
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Progress value={percentage} className="h-2 w-24" />
              <span className="text-xs text-muted-foreground">
                {percentage.toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.success} success, {stats.failed} failed
            </p>
          </div>
        );
      },
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (value) => {
        const variants: Record<string, any> = {
          active: "default",
          completed: "secondary",
          paused: "outline",
          cancelled: "destructive",
        };
        return (
          <Badge variant={variants[value]} className="capitalize">
            {value}
          </Badge>
        );
      },
    },
    {
      key: "startedAt",
      label: "Started",
      sortable: true,
      render: (value) =>
        value ? (
          <span className="text-sm text-muted-foreground">
            {format(new Date(value), "MMM dd, HH:mm")}
          </span>
        ) : (
          "-"
        ),
    },
  ];

  const deviceColumns: Column<DeviceFirmwareStatus>[] = [
    {
      key: "deviceSerial",
      label: "Device",
      render: (value, row) => (
        <div>
          <p className="font-medium">{row.deviceName || value}</p>
          <p className="text-xs text-muted-foreground font-mono">{value}</p>
        </div>
      ),
    },
    {
      key: "currentVersion",
      label: "Current Version",
      render: (value) => <span className="font-mono text-sm">{value}</span>,
    },
    {
      key: "targetVersion",
      label: "Target Version",
      render: (value) =>
        value ? <span className="font-mono text-sm">{value}</span> : "-",
    },
    {
      key: "updateStatus",
      label: "Status",
      render: (value, row) => {
        const statusConfig: Record<
          string,
          { icon: any; color: string; label: string }
        > = {
          up_to_date: {
            icon: CheckCircle2,
            color: "text-green-600",
            label: "Up to date",
          },
          pending: { icon: Loader2, color: "text-blue-600", label: "Pending" },
          downloading: {
            icon: Loader2,
            color: "text-blue-600",
            label: "Downloading",
          },
          applying: { icon: Loader2, color: "text-blue-600", label: "Applying" },
          success: { icon: CheckCircle2, color: "text-green-600", label: "Success" },
          failed: { icon: XCircle, color: "text-destructive", label: "Failed" },
        };

        const config = statusConfig[value] || statusConfig.pending;
        const Icon = config.icon;

        return (
          <div className="flex items-center gap-2">
            <Icon className={`h-4 w-4 ${config.color}`} />
            <div>
              <p className="text-sm font-medium">{config.label}</p>
              {(value === "downloading" || value === "applying") && (
                <Progress value={row.progress} className="h-1 w-20 mt-1" />
              )}
              {row.errorMessage && (
                <p className="text-xs text-destructive mt-1">{row.errorMessage}</p>
              )}
            </div>
          </div>
        );
      },
    },
  ];

  const handleCreate = () => {
    setFormData({
      name: "",
      description: "",
      versionId: "",
      rolloutStrategy: "staged",
      rolloutPercentage: 10,
      targetDevices: "all",
    });
    setDialogOpen(true);
  };

  const handleViewDetails = (campaign: FirmwareUpdateCampaign) => {
    setSelectedCampaign(campaign);
    setDetailsDialogOpen(true);
  };

  const handlePauseCampaign = (campaign: FirmwareUpdateCampaign) => {
    const updated = { ...campaign, status: "paused" as const };
    setCampaigns(campaigns.map((c) => (c.id === campaign.id ? updated : c)));

    addAuditEntry({
      action: "update",
      entity: "campaign",
      entityId: campaign.id,
      details: {
        before: campaign,
        after: updated,
        metadata: { action: "pause" },
      },
    });

    toast.success(`Campaign "${campaign.name}" paused`);
  };

  const handleResumeCampaign = (campaign: FirmwareUpdateCampaign) => {
    const updated = { ...campaign, status: "active" as const };
    setCampaigns(campaigns.map((c) => (c.id === campaign.id ? updated : c)));

    addAuditEntry({
      action: "update",
      entity: "campaign",
      entityId: campaign.id,
      details: {
        before: campaign,
        after: updated,
        metadata: { action: "resume" },
      },
    });

    toast.success(`Campaign "${campaign.name}" resumed`);
  };

  const handleSubmit = () => {
    if (!formData.name || !formData.versionId) {
      toast.error("Please fill in all required fields");
      return;
    }

    const selectedVersion = mockVersions.find((v) => v.id === formData.versionId);
    if (!selectedVersion) return;

    const newCampaign: FirmwareUpdateCampaign = {
      id: `c${Date.now()}`,
      ...formData,
      version: selectedVersion.version,
      targetDevices: formData.targetDevices === "all" ? ["all"] : [],
      status: "draft",
      statistics: {
        totalDevices: 0,
        pending: 0,
        downloading: 0,
        applying: 0,
        success: 0,
        failed: 0,
      },
      createdAt: new Date().toISOString(),
      createdBy: "admin@solarhub.com",
    };

    setCampaigns([newCampaign, ...campaigns]);

    addAuditEntry({
      action: "create",
      entity: "campaign",
      entityId: newCampaign.id,
      details: {
        after: newCampaign,
      },
    });

    toast.success(`Campaign "${formData.name}" created successfully`);
    setDialogOpen(false);
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Update Campaigns" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">OTA Update Campaigns</h1>
            <p className="text-muted-foreground mt-1">
              Manage firmware rollout campaigns and monitor device updates
            </p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Create Campaign
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
              placeholder="Search campaigns..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Table */}
        <DataTable
          data={filteredCampaigns}
          columns={columns}
          emptyMessage="No campaigns found"
          actions={
            canEdit
              ? [
                  {
                    label: "View Details",
                    onClick: handleViewDetails,
                  },
                  {
                    label: "Pause",
                    icon: <Pause className="h-4 w-4" />,
                    onClick: handlePauseCampaign,
                  },
                  {
                    label: "Resume",
                    icon: <Play className="h-4 w-4" />,
                    onClick: handleResumeCampaign,
                  },
                ]
              : undefined
          }
        />

        {/* Create Campaign Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Update Campaign</DialogTitle>
              <DialogDescription>
                Configure a new firmware update rollout campaign
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Campaign Name *</Label>
                <Input
                  id="name"
                  placeholder="e.g., v2.1.0 Production Rollout"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Describe the purpose of this campaign..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="version">Firmware Version *</Label>
                  <Select
                    value={formData.versionId}
                    onValueChange={(value) =>
                      setFormData({ ...formData, versionId: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select version" />
                    </SelectTrigger>
                    <SelectContent>
                      {mockVersions.map((version) => (
                        <SelectItem key={version.id} value={version.id}>
                          {version.version}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="strategy">Rollout Strategy *</Label>
                  <Select
                    value={formData.rolloutStrategy}
                    onValueChange={(value: any) =>
                      setFormData({ ...formData, rolloutStrategy: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="immediate">Immediate (100%)</SelectItem>
                      <SelectItem value="staged">Staged Rollout</SelectItem>
                      <SelectItem value="canary">Canary (1-5%)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {formData.rolloutStrategy !== "immediate" && (
                <div className="space-y-2">
                  <Label>Rollout Percentage: {formData.rolloutPercentage}%</Label>
                  <Slider
                    value={[formData.rolloutPercentage]}
                    onValueChange={([value]) =>
                      setFormData({ ...formData, rolloutPercentage: value })
                    }
                    min={1}
                    max={100}
                    step={1}
                    className="py-4"
                  />
                  <p className="text-xs text-muted-foreground">
                    Deploy to {formData.rolloutPercentage}% of target devices
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="targetDevices">Target Devices *</Label>
                <Select
                  value={formData.targetDevices}
                  onValueChange={(value) =>
                    setFormData({ ...formData, targetDevices: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Devices</SelectItem>
                    <SelectItem value="specific">Specific Devices</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit}>Create Campaign</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Campaign Details Dialog */}
        <Dialog open={detailsDialogOpen} onOpenChange={setDetailsDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{selectedCampaign?.name}</DialogTitle>
              <DialogDescription>
                Campaign details and device update status
              </DialogDescription>
            </DialogHeader>

            {selectedCampaign && (
              <Tabs defaultValue="overview" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="devices">Device Status</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Campaign Info</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2 text-sm">
                        <div>
                          <p className="text-muted-foreground">Version</p>
                          <p className="font-mono">{selectedCampaign.version}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Strategy</p>
                          <p className="capitalize">
                            {selectedCampaign.rolloutStrategy} (
                            {selectedCampaign.rolloutPercentage}%)
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Status</p>
                          <Badge className="capitalize">
                            {selectedCampaign.status}
                          </Badge>
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Statistics</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total Devices</span>
                          <span className="font-semibold">
                            {selectedCampaign.statistics.totalDevices}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Success</span>
                          <span className="font-semibold text-green-600">
                            {selectedCampaign.statistics.success}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Failed</span>
                          <span className="font-semibold text-destructive">
                            {selectedCampaign.statistics.failed}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">In Progress</span>
                          <span className="font-semibold">
                            {selectedCampaign.statistics.downloading +
                              selectedCampaign.statistics.applying}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>

                <TabsContent value="devices">
                  <DataTable
                    data={mockDeviceStatuses}
                    columns={deviceColumns}
                    emptyMessage="No devices in this campaign"
                  />
                </TabsContent>
              </Tabs>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
}
