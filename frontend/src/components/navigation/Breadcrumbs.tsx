import { useLocation, Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

interface BreadcrumbSegment {
  label: string;
  href: string;
}

// Route to label mapping
const routeLabels: Record<string, string> = {
  "": "Dashboard",
  "devices": "Devices",
  "manage": "Manage",
  "settings": "Settings",
  "users": "User Management",
  "tariff": "Tariff Settings",
  "telemetry": "Telemetry",
  "scheduler": "Smart Scheduler",
  "billing": "Billing",
  "notifications": "Notifications",
  "profile": "Profile",
  "alerts": "Alert Center",
  "outages": "Outages",
  "savings": "Savings",
  "commissioning": "Commissioning",
  "claim": "Claim Device",
  "install": "Installation Wizard",
};

export function Breadcrumbs() {
  const location = useLocation();

  const pathSegments = location.pathname.split("/").filter(Boolean);

  // Don't show breadcrumbs on dashboard
  if (pathSegments.length === 0) {
    return null;
  }

  const breadcrumbs: BreadcrumbSegment[] = [];

  // Build breadcrumb segments
  pathSegments.forEach((segment, index) => {
    const href = "/" + pathSegments.slice(0, index + 1).join("/");

    // Check if this is a UUID (device ID, site ID, etc.)
    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment);

    if (isUUID) {
      // For UUIDs, show a shortened version or fetch the actual name
      // You can enhance this to fetch device names from your API
      breadcrumbs.push({
        label: `Device ${segment.substring(0, 8)}...`,
        href,
      });
    } else {
      // Use route label or capitalize segment
      const label = routeLabels[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
      breadcrumbs.push({
        label,
        href,
      });
    }
  });

  return (
    <nav className="flex items-center space-x-1 text-sm text-muted-foreground mb-4" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-1">
        {/* Home link */}
        <li className="flex items-center">
          <Link
            to="/"
            className="flex items-center gap-1 hover:text-foreground transition-colors"
            aria-label="Home"
          >
            <Home className="h-4 w-4" />
          </Link>
        </li>

        {breadcrumbs.map((crumb, index) => (
          <li key={crumb.href} className="flex items-center">
            <ChevronRight className="h-4 w-4 mx-1" />
            {index === breadcrumbs.length - 1 ? (
              <span className="font-medium text-foreground" aria-current="page">
                {crumb.label}
              </span>
            ) : (
              <Link
                to={crumb.href}
                className="hover:text-foreground transition-colors"
              >
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
