import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import {
  LayoutDashboard,
  FileText,
  Zap,
  DollarSign,
  CalendarClock,
  Crown,
  Flag,
  HardDrive,
  Wifi,
  Cloud,
  Package,
  Receipt,
  Rocket,
  Users,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface NavItem {
  title: string;
  href: string;
  icon: React.ReactNode;
  permission?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

export function AdminSidebar() {
  const location = useLocation();
  const { hasPermission } = useAdminAuth();

  const navGroups: NavGroup[] = [
    {
      title: "Overview",
      items: [
        {
          title: "Dashboard",
          href: "/admin",
          icon: <LayoutDashboard className="w-4 h-4" />,
        },
        {
          title: "Audit Log",
          href: "/admin/audit-log",
          icon: <FileText className="w-4 h-4" />,
          permission: "view_audit_log",
        },
      ],
    },
    {
      title: "Providers & Billing",
      items: [
        {
          title: "Electricity Providers",
          href: "/admin/providers",
          icon: <Zap className="w-4 h-4" />,
          permission: "manage_providers",
        },
        {
          title: "Tariff Management",
          href: "/admin/tariffs",
          icon: <DollarSign className="w-4 h-4" />,
          permission: "manage_tariffs",
        },
        {
          title: "Billing Schedules",
          href: "/admin/billing-schedules",
          icon: <Receipt className="w-4 h-4" />,
          permission: "manage_tariffs",
        },
        {
          title: "Load Shedding",
          href: "/admin/load-shedding",
          icon: <CalendarClock className="w-4 h-4" />,
          permission: "manage_load_shedding",
        },
      ],
    },
    {
      title: "Subscriptions",
      items: [
        {
          title: "Subscription Tiers",
          href: "/admin/subscription-tiers",
          icon: <Crown className="w-4 h-4" />,
          permission: "manage_tiers",
        },
        {
          title: "Feature Management",
          href: "/admin/features",
          icon: <Flag className="w-4 h-4" />,
          permission: "manage_features",
        },
      ],
    },
    {
      title: "Devices",
      items: [
        {
          title: "Device Catalog",
          href: "/admin/device-catalog",
          icon: <HardDrive className="w-4 h-4" />,
          permission: "manage_devices",
        },
        {
          title: "Protocol Adapters",
          href: "/admin/protocol-adapters",
          icon: <Wifi className="w-4 h-4" />,
          permission: "manage_adapters",
        },
        {
          title: "Weather Stations",
          href: "/admin/weather-stations",
          icon: <Cloud className="w-4 h-4" />,
          permission: "manage_weather",
        },
      ],
    },
    {
      title: "OTA Updates",
      items: [
        {
          title: "Firmware Versions",
          href: "/admin/firmware-versions",
          icon: <Package className="w-4 h-4" />,
          permission: "manage_firmware",
        },
        {
          title: "Update Campaigns",
          href: "/admin/ota-campaigns",
          icon: <Rocket className="w-4 h-4" />,
          permission: "manage_campaigns",
        },
      ],
    },
    {
      title: "AI Intelligence",
      items: [
        {
          title: "AI Prompt Templates",
          href: "/admin/ai-prompts",
          icon: <Sparkles className="w-4 h-4" />,
        },
      ],
    },
    {
      title: "Administration",
      items: [
        {
          title: "User Management",
          href: "/admin/users",
          icon: <Users className="w-4 h-4" />,
          permission: "manage_users",
        },
      ],
    },
  ];

  const isActive = (href: string) => {
    if (href === "/admin") {
      return location.pathname === href;
    }
    return location.pathname.startsWith(href);
  };

  const filterByPermission = (items: NavItem[]) => {
    return items.filter(item => {
      if (!item.permission) return true;
      return hasPermission(item.permission as any);
    });
  };

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        <Link to="/admin" className="flex items-center gap-2 font-semibold">
          <Zap className="h-5 w-5 text-primary" />
          <span>Solar Hub Admin</span>
        </Link>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-4">
        {navGroups.map((group, groupIndex) => {
          const visibleItems = filterByPermission(group.items);
          if (visibleItems.length === 0) return null;

          return (
            <div key={group.title} className={cn(groupIndex > 0 && "mt-6")}>
              <h4 className="mb-2 px-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {group.title}
              </h4>
              <div className="space-y-1">
                {visibleItems.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive(item.href)
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    {item.icon}
                    <span className="flex-1">{item.title}</span>
                    {isActive(item.href) && (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </ScrollArea>

      {/* User Info */}
      <Separator />
      <div className="p-4">
        <Link
          to="/admin/profile"
          className="flex items-center gap-3 rounded-md p-2 text-sm hover:bg-accent transition-colors"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground font-semibold">
            A
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Admin</p>
            <p className="text-xs text-muted-foreground truncate">View Profile</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
