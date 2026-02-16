import { AdminLayout } from "@/components/admin/layout/AdminLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import {
  Zap,
  DollarSign,
  HardDrive,
  Package,
  Users,
  TrendingUp,
  Activity,
  Clock,
} from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  description: string;
  icon: React.ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

function StatCard({ title, value, description, icon, trend }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="h-4 w-4 text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
        {trend && (
          <div className={`flex items-center gap-1 mt-2 text-xs ${trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
            <TrendingUp className="h-3 w-3" />
            <span>{trend.isPositive ? '+' : ''}{trend.value}% from last month</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminDashboard() {
  const { adminUser } = useAdminAuth();

  // Mock data - replace with actual API calls
  const stats = [
    {
      title: "Total Organizations",
      value: "247",
      description: "Active customers",
      icon: <Users className="h-4 w-4" />,
      trend: { value: 12.5, isPositive: true },
    },
    {
      title: "Total Devices",
      value: "1,834",
      description: "Connected devices",
      icon: <HardDrive className="h-4 w-4" />,
      trend: { value: 8.2, isPositive: true },
    },
    {
      title: "Electricity Providers",
      value: "12",
      description: "Configured providers",
      icon: <Zap className="h-4 w-4" />,
    },
    {
      title: "Tariff Plans",
      value: "47",
      description: "Active tariff plans",
      icon: <DollarSign className="h-4 w-4" />,
    },
    {
      title: "Firmware Versions",
      value: "8",
      description: "Available versions",
      icon: <Package className="h-4 w-4" />,
    },
    {
      title: "Active Campaigns",
      value: "3",
      description: "OTA update campaigns",
      icon: <Activity className="h-4 w-4" />,
    },
  ];

  const recentActivity = [
    {
      id: "1",
      action: "Created tariff plan",
      user: "ops@solarhub.com",
      entity: "LESCO Residential 2024",
      timestamp: "2 minutes ago",
    },
    {
      id: "2",
      action: "Started OTA campaign",
      user: "firmware@solarhub.com",
      entity: "Version 2.1.0 Rollout",
      timestamp: "15 minutes ago",
    },
    {
      id: "3",
      action: "Added device model",
      user: "device@solarhub.com",
      entity: "Growatt SPH 10000TL3",
      timestamp: "1 hour ago",
    },
    {
      id: "4",
      action: "Updated subscription tier",
      user: "billing@solarhub.com",
      entity: "Premium Plan",
      timestamp: "2 hours ago",
    },
  ];

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Welcome back, {adminUser?.firstName}! Here's your system overview.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((stat, index) => (
            <StatCard key={index} {...stat} />
          ))}
        </div>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Recent Activity
            </CardTitle>
            <CardDescription>
              Latest administrative actions across the platform
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-start justify-between p-3 rounded-lg border hover:bg-accent transition-colors"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{activity.action}</p>
                    <p className="text-sm text-muted-foreground">
                      {activity.entity}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      by {activity.user}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {activity.timestamp}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>
              Common administrative tasks
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <a
              href="/admin/providers"
              className="flex items-center gap-3 p-4 rounded-lg border hover:bg-accent transition-colors"
            >
              <Zap className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Add Electricity Provider</p>
                <p className="text-xs text-muted-foreground">Configure new DISCO</p>
              </div>
            </a>
            <a
              href="/admin/firmware-versions"
              className="flex items-center gap-3 p-4 rounded-lg border hover:bg-accent transition-colors"
            >
              <Package className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Upload Firmware</p>
                <p className="text-xs text-muted-foreground">Deploy new version</p>
              </div>
            </a>
            <a
              href="/admin/tariffs"
              className="flex items-center gap-3 p-4 rounded-lg border hover:bg-accent transition-colors"
            >
              <DollarSign className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Create Tariff Plan</p>
                <p className="text-xs text-muted-foreground">Add new tariff</p>
              </div>
            </a>
            <a
              href="/admin/device-catalog"
              className="flex items-center gap-3 p-4 rounded-lg border hover:bg-accent transition-colors"
            >
              <HardDrive className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Add Device Model</p>
                <p className="text-xs text-muted-foreground">Expand catalog</p>
              </div>
            </a>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
