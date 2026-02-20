import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Input } from "@/components/ui/input";
import { Search, FileText, Download, Filter, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import type { AuditLogEntry } from "@/types/admin";
import { format } from "date-fns";
import { auditLogService } from "@/api/services/admin.service";

export default function AuditLog() {
  const { hasPermission } = useAdminAuth();
  const canExport = hasPermission("export_data");

  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [entityFilter, setEntityFilter] = useState<string>("all");

  // Fetch audit log from backend
  const { data: auditLog = [], isLoading, error } = useQuery({
    queryKey: ["admin", "audit-log", actionFilter, entityFilter],
    queryFn: () =>
      auditLogService.list({
        action: actionFilter !== "all" ? actionFilter : undefined,
        resource_type: entityFilter !== "all" ? entityFilter : undefined,
        limit: 100,
      }),
    refetchInterval: 30_000, // Refresh every 30 seconds
  });

  // Get unique actions and entities for filters
  const uniqueActions = Array.from(new Set(auditLog.map((entry) => entry.action)));
  const uniqueEntities = Array.from(new Set(auditLog.map((entry) => entry.entity)));

  const filteredLog = auditLog.filter((entry) => {
    const matchesSearch =
      entry.actor.toLowerCase().includes(search.toLowerCase()) ||
      entry.entity.toLowerCase().includes(search.toLowerCase()) ||
      (entry.entityId || "").toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  const handleExport = () => {
    const csv = [
      ["Timestamp", "Actor", "Action", "Entity", "Entity ID", "IP Address"],
      ...filteredLog.map((entry) => [
        entry.timestamp,
        entry.actor,
        entry.action,
        entry.entity,
        entry.entityId,
        entry.ipAddress || "",
      ]),
    ]
      .map((row) => row.join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-log-${Date.now()}.csv`;
    a.click();
  };

  const getActionBadgeVariant = (action: string) => {
    switch (action) {
      case "create":
        return "default";
      case "update":
        return "secondary";
      case "delete":
        return "destructive";
      case "activate":
      case "deactivate":
        return "outline";
      default:
        return "secondary";
    }
  };

  const breadcrumbs = [
    { label: "Admin", href: "/admin" },
    { label: "Audit Log" },
  ];

  return (
    <AdminLayout breadcrumbs={breadcrumbs}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Audit Log</h1>
            <p className="text-muted-foreground mt-1">
              Complete history of administrative actions
            </p>
          </div>
          {canExport && filteredLog.length > 0 && (
            <Button onClick={handleExport} variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Export CSV
            </Button>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Total Actions</p>
                  <p className="text-2xl font-bold mt-1">{auditLog.length}</p>
                </div>
                <FileText className="h-8 w-8 text-muted-foreground opacity-50" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Creates</p>
                  <p className="text-2xl font-bold mt-1">
                    {auditLog.filter((e) => e.action === "create").length}
                  </p>
                </div>
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-lg">+</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Updates</p>
                  <p className="text-2xl font-bold mt-1">
                    {auditLog.filter((e) => e.action === "update").length}
                  </p>
                </div>
                <div className="h-8 w-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                  <span className="text-lg">✎</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Deletes</p>
                  <p className="text-2xl font-bold mt-1">
                    {auditLog.filter((e) => e.action === "delete").length}
                  </p>
                </div>
                <div className="h-8 w-8 rounded-full bg-destructive/10 flex items-center justify-center">
                  <span className="text-lg">×</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search audit log..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          <Select value={actionFilter} onValueChange={setActionFilter}>
            <SelectTrigger className="w-[150px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Actions</SelectItem>
              {uniqueActions.map((action) => (
                <SelectItem key={action} value={action}>
                  {action.charAt(0).toUpperCase() + action.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={entityFilter} onValueChange={setEntityFilter}>
            <SelectTrigger className="w-[150px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Entity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Entities</SelectItem>
              {uniqueEntities.map((entity) => (
                <SelectItem key={entity} value={entity}>
                  {entity.charAt(0).toUpperCase() + entity.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {(search || actionFilter !== "all" || entityFilter !== "all") && (
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setActionFilter("all");
                setEntityFilter("all");
              }}
            >
              Clear Filters
            </Button>
          )}
        </div>

        {/* Error state */}
        {error && (
          <div className="text-sm text-destructive">
            Failed to load audit log. Please check your connection.
          </div>
        )}

        {/* Audit Log Table */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading audit log...
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Timestamp</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Entity ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLog.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      {auditLog.length === 0
                        ? "No audit entries yet. Administrative actions will appear here."
                        : "No matching entries found"}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredLog.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="font-mono text-xs">
                        {format(new Date(entry.timestamp), "MMM dd, yyyy HH:mm:ss")}
                      </TableCell>
                      <TableCell className="font-medium">{entry.actor}</TableCell>
                      <TableCell>
                        <Badge variant={getActionBadgeVariant(entry.action) as any}>
                          {entry.action}
                        </Badge>
                      </TableCell>
                      <TableCell className="capitalize">{entry.entity}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {entry.entityId}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}

        {filteredLog.length > 0 && (
          <div className="text-sm text-muted-foreground text-center">
            Showing {filteredLog.length} of {auditLog.length} entries
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
