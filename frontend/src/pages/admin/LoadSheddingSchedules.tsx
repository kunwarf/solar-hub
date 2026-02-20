import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, CalendarClock, Loader2 } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { loadSheddingService } from "@/api/services/admin.service";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface LoadSheddingEntry {
  id: string;
  areaName: string;
  region: string;
  feederCode?: string;
  schedule: Record<string, any>;
  isActive: boolean;
  effectiveFrom?: string;
  effectiveTo?: string;
}

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

export default function LoadSheddingSchedules() {
  const { hasPermission } = useAdminAuth();
  const canEdit = hasPermission("manage_load_shedding");
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<LoadSheddingEntry | null>(null);
  const [deletingEntry, setDeletingEntry] = useState<LoadSheddingEntry | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    area_name: "",
    region: "",
    feeder_code: "",
    effective_from: "",
    effective_to: "",
    is_active: true,
    schedule: {} as Record<string, { start: string; end: string }[]>,
  });

  // Simple schedule form: one time window per day
  const [scheduleWindows, setScheduleWindows] = useState<Record<string, { start: string; end: string }>>({});

  const { data: schedules = [], isLoading, error } = useQuery({
    queryKey: ["admin", "load-shedding"],
    queryFn: () => loadSheddingService.list(),
  });

  const createMutation = useMutation({
    mutationFn: loadSheddingService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "load-shedding"] });
      toast.success("Load shedding schedule created successfully");
      setDialogOpen(false);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Failed to create schedule");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      loadSheddingService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "load-shedding"] });
      toast.success("Schedule updated successfully");
      setDialogOpen(false);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Failed to update schedule");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: loadSheddingService.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "load-shedding"] });
      toast.success("Schedule deleted successfully");
      setDeleteDialogOpen(false);
      setDeletingEntry(null);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Failed to delete schedule");
    },
  });

  const filteredSchedules = (schedules as LoadSheddingEntry[]).filter(
    (s) =>
      (s.areaName || "").toLowerCase().includes(search.toLowerCase()) ||
      (s.region || "").toLowerCase().includes(search.toLowerCase()) ||
      (s.feederCode || "").toLowerCase().includes(search.toLowerCase())
  );

  const stats = [
    {
      title: "Total Schedules",
      value: schedules.length,
      description: "Load shedding zones",
      icon: <CalendarClock className="h-4 w-4" />,
    },
    {
      title: "Active Schedules",
      value: (schedules as LoadSheddingEntry[]).filter((s) => s.isActive).length,
      description: "Currently enforced",
      icon: <CalendarClock className="h-4 w-4" />,
    },
  ];

  const columns: Column<LoadSheddingEntry>[] = [
    {
      key: "areaName",
      label: "Area",
      sortable: true,
      render: (value) => <span className="font-medium">{value}</span>,
    },
    {
      key: "region",
      label: "Region",
      sortable: true,
    },
    {
      key: "feederCode",
      label: "Feeder Code",
      sortable: true,
      render: (value) => value || <span className="text-muted-foreground">—</span>,
    },
    {
      key: "effectiveFrom",
      label: "Effective From",
      sortable: true,
      render: (value) => value || <span className="text-muted-foreground">—</span>,
    },
    {
      key: "isActive",
      label: "Status",
      sortable: true,
      render: (value) => <StatusBadge status={value ? "active" : "inactive"} />,
    },
  ];

  const handleCreate = () => {
    setEditingEntry(null);
    setFormData({
      area_name: "",
      region: "",
      feeder_code: "",
      effective_from: "",
      effective_to: "",
      is_active: true,
      schedule: {},
    });
    setScheduleWindows({});
    setDialogOpen(true);
  };

  const handleEdit = (entry: LoadSheddingEntry) => {
    setEditingEntry(entry);
    setFormData({
      area_name: entry.areaName || "",
      region: entry.region || "",
      feeder_code: entry.feederCode || "",
      effective_from: entry.effectiveFrom || "",
      effective_to: entry.effectiveTo || "",
      is_active: entry.isActive,
      schedule: entry.schedule || {},
    });
    // Populate simple schedule windows from backend schedule
    const windows: Record<string, { start: string; end: string }> = {};
    for (const day of DAYS) {
      const daySchedule = entry.schedule?.[day];
      if (daySchedule && daySchedule.length > 0) {
        windows[day] = { start: daySchedule[0].start, end: daySchedule[0].end };
      }
    }
    setScheduleWindows(windows);
    setDialogOpen(true);
  };

  const handleDelete = (entry: LoadSheddingEntry) => {
    setDeletingEntry(entry);
    setDeleteDialogOpen(true);
  };

  const buildSchedule = () => {
    const schedule: Record<string, { start: string; end: string }[]> = {};
    for (const [day, window] of Object.entries(scheduleWindows)) {
      if (window.start && window.end) {
        schedule[day] = [{ start: window.start, end: window.end }];
      }
    }
    return schedule;
  };

  const handleSubmit = () => {
    if (!formData.area_name || !formData.region) {
      toast.error("Please fill in area name and region");
      return;
    }

    const schedule = buildSchedule();
    const payload = {
      area_name: formData.area_name,
      region: formData.region,
      feeder_code: formData.feeder_code || undefined,
      schedule,
      effective_from: formData.effective_from || undefined,
      effective_to: formData.effective_to || undefined,
      is_active: formData.is_active,
    };

    if (editingEntry) {
      updateMutation.mutate({ id: editingEntry.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const confirmDelete = () => {
    if (!deletingEntry) return;
    deleteMutation.mutate(deletingEntry.id);
  };

  const updateWindow = (day: string, field: "start" | "end", value: string) => {
    setScheduleWindows((prev) => ({
      ...prev,
      [day]: { ...(prev[day] || { start: "", end: "" }), [field]: value },
    }));
  };

  const toggleDay = (day: string, enabled: boolean) => {
    if (enabled) {
      setScheduleWindows((prev) => ({
        ...prev,
        [day]: prev[day] || { start: "06:00", end: "08:00" },
      }));
    } else {
      setScheduleWindows((prev) => {
        const next = { ...prev };
        delete next[day];
        return next;
      });
    }
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Load Shedding" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Load Shedding Schedules</h1>
            <p className="text-muted-foreground mt-1">
              Manage load shedding zones and outage schedules
            </p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add Schedule
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
              placeholder="Search schedules..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {error && (
          <div className="text-sm text-destructive">
            Failed to load schedules. Please check your connection.
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading schedules...
          </div>
        ) : (
          <DataTable
            data={filteredSchedules}
            columns={columns}
            onEdit={canEdit ? handleEdit : undefined}
            onDelete={canEdit ? handleDelete : undefined}
            emptyMessage="No load shedding schedules found"
          />
        )}

        {/* Create/Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingEntry ? "Edit Schedule" : "Add Load Shedding Schedule"}
              </DialogTitle>
              <DialogDescription>
                Configure a load shedding zone with weekly outage windows
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Area Name *</Label>
                  <Input
                    placeholder="e.g., DHA Phase 5"
                    value={formData.area_name}
                    onChange={(e) => setFormData({ ...formData, area_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Region *</Label>
                  <Input
                    placeholder="e.g., Punjab"
                    value={formData.region}
                    onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Feeder Code</Label>
                  <Input
                    placeholder="e.g., LHR-042"
                    value={formData.feeder_code}
                    onChange={(e) => setFormData({ ...formData, feeder_code: e.target.value })}
                  />
                </div>
                <div className="space-y-2 flex items-center gap-3 pt-6">
                  <Switch
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  />
                  <Label>Active</Label>
                </div>
                <div className="space-y-2">
                  <Label>Effective From</Label>
                  <Input
                    type="date"
                    value={formData.effective_from}
                    onChange={(e) => setFormData({ ...formData, effective_from: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Effective To</Label>
                  <Input
                    type="date"
                    value={formData.effective_to}
                    onChange={(e) => setFormData({ ...formData, effective_to: e.target.value })}
                  />
                </div>
              </div>

              {/* Weekly Schedule */}
              <div className="space-y-2">
                <Label className="text-base font-medium">Weekly Outage Schedule</Label>
                <p className="text-xs text-muted-foreground">
                  Enable days and set outage time windows (one window per day)
                </p>
                <div className="space-y-2">
                  {DAYS.map((day) => {
                    const isEnabled = !!scheduleWindows[day];
                    return (
                      <div key={day} className="flex items-center gap-3">
                        <div className="flex items-center gap-2 w-32">
                          <Switch
                            checked={isEnabled}
                            onCheckedChange={(checked) => toggleDay(day, checked)}
                          />
                          <span className="text-sm capitalize">{day}</span>
                        </div>
                        {isEnabled && (
                          <>
                            <Input
                              type="time"
                              value={scheduleWindows[day]?.start || ""}
                              onChange={(e) => updateWindow(day, "start", e.target.value)}
                              className="w-32"
                            />
                            <span className="text-muted-foreground text-sm">to</span>
                            <Input
                              type="time"
                              value={scheduleWindows[day]?.end || ""}
                              onChange={(e) => updateWindow(day, "end", e.target.value)}
                              className="w-32"
                            />
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={isMutating}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={isMutating}>
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingEntry ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <ConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={confirmDelete}
          title="Delete Schedule"
          description={`Are you sure you want to delete the schedule for "${deletingEntry?.areaName}"? This action cannot be undone.`}
          confirmText="Delete"
          variant="destructive"
        />
      </div>
    </AdminLayout>
  );
}
