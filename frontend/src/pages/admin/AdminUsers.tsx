import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Users, Loader2 } from "lucide-react";
import { DataTable, Column, StatusBadge } from "@/components/admin/common/DataTable";
import { StatCard } from "@/components/admin/common/StatCard";
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
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import type { AdminUser, AdminRole } from "@/types/admin";
import { adminUsersService } from "@/api/services/admin.service";
import { format } from "date-fns";

const ROLE_LABELS: Record<AdminRole, string> = {
  super_admin: "Super Admin",
  ops_admin: "Ops Admin",
  billing_admin: "Billing Admin",
  device_admin: "Device Admin",
  firmware_admin: "Firmware Admin",
  read_only: "Read Only",
};

export default function AdminUsers() {
  const { hasPermission, adminUser: currentUser } = useAdminAuth();
  const canManage = hasPermission("manage_users");
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editFormData, setEditFormData] = useState({
    role: "" as AdminRole,
    status: "active" as "active" | "inactive",
  });

  // Data fetching
  const { data: users = [], isLoading, error } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: adminUsersService.list,
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { role?: AdminRole; status?: "active" | "inactive" } }) =>
      adminUsersService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      toast.success("Admin user updated successfully");
      setEditingUser(null);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Failed to update admin user");
    },
  });

  const filteredUsers = users.filter(
    (user) =>
      user.email.toLowerCase().includes(search.toLowerCase()) ||
      user.firstName.toLowerCase().includes(search.toLowerCase()) ||
      user.lastName.toLowerCase().includes(search.toLowerCase())
  );

  const stats = [
    {
      title: "Total Admin Users",
      value: users.length,
      description: "Portal administrators",
      icon: <Users className="h-4 w-4" />,
    },
    {
      title: "Active Admins",
      value: users.filter((u) => u.status === "active").length,
      description: "Currently active accounts",
      icon: <Users className="h-4 w-4" />,
    },
  ];

  const columns: Column<AdminUser>[] = [
    {
      key: "email",
      label: "Email",
      sortable: true,
      render: (value) => <span className="font-medium">{value}</span>,
    },
    {
      key: "firstName",
      label: "Name",
      sortable: true,
      render: (_value, row) => `${row.firstName} ${row.lastName}`,
    },
    {
      key: "role",
      label: "Role",
      sortable: true,
      render: (value) => (
        <Badge variant="outline" className="text-xs">
          {ROLE_LABELS[value as AdminRole] ?? value}
        </Badge>
      ),
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (value) => <StatusBadge status={value} />,
    },
    {
      key: "lastLoginAt",
      label: "Last Login",
      sortable: true,
      render: (value) =>
        value ? format(new Date(value), "MMM dd, yyyy HH:mm") : "Never",
    },
    {
      key: "createdAt",
      label: "Created",
      sortable: true,
      render: (value) => format(new Date(value), "MMM dd, yyyy"),
    },
  ];

  const handleEdit = (user: AdminUser) => {
    setEditingUser(user);
    setEditFormData({ role: user.role, status: user.status });
  };

  const handleUpdateSubmit = () => {
    if (!editingUser) return;
    updateMutation.mutate({
      id: editingUser.id,
      data: editFormData,
    });
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "User Management" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
            <p className="text-muted-foreground mt-1">
              Manage admin portal users and their roles
            </p>
          </div>
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
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="text-sm text-destructive">
            Failed to load users. Please check your connection and try again.
          </div>
        )}

        {/* Table */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading users...
          </div>
        ) : (
          <DataTable
            data={filteredUsers}
            columns={columns}
            onEdit={canManage ? handleEdit : undefined}
            emptyMessage="No admin users found"
          />
        )}

        {/* Edit Dialog */}
        <Dialog open={!!editingUser} onOpenChange={(open) => !open && setEditingUser(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Admin User</DialogTitle>
              <DialogDescription>
                Update role and status for {editingUser?.email}
                {editingUser?.id === currentUser?.id && " (this is you)"}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Role</Label>
                <Select
                  value={editFormData.role}
                  onValueChange={(value: AdminRole) =>
                    setEditFormData({ ...editFormData, role: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROLE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={editFormData.status}
                  onValueChange={(value: "active" | "inactive") =>
                    setEditFormData({ ...editFormData, status: value })
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
              <Button
                variant="outline"
                onClick={() => setEditingUser(null)}
                disabled={updateMutation.isPending}
              >
                Cancel
              </Button>
              <Button onClick={handleUpdateSubmit} disabled={updateMutation.isPending}>
                {updateMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
}
