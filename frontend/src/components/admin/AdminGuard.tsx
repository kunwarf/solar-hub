import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import type { AdminPermission } from "@/types/admin";
import { toast } from "sonner";

interface AdminGuardProps {
  children: React.ReactNode;
  requiredPermission?: AdminPermission;
  requiredPermissions?: AdminPermission[];  // Require ALL of these
  anyPermission?: AdminPermission[];  // Require ANY of these
}

export function AdminGuard({
  children,
  requiredPermission,
  requiredPermissions,
  anyPermission,
}: AdminGuardProps) {
  const { isAuthenticated, isLoading, hasPermission, hasAnyPermission } = useAdminAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      toast.error("Please login to access admin portal");
      navigate("/admin/login", { replace: true });
      return;
    }

    // Check single required permission
    if (requiredPermission && !hasPermission(requiredPermission)) {
      toast.error("You don't have permission to access this page");
      navigate("/admin", { replace: true });
      return;
    }

    // Check all required permissions
    if (requiredPermissions && requiredPermissions.length > 0) {
      const hasAllPermissions = requiredPermissions.every(permission =>
        hasPermission(permission)
      );
      if (!hasAllPermissions) {
        toast.error("You don't have the required permissions to access this page");
        navigate("/admin", { replace: true });
        return;
      }
    }

    // Check any permission (at least one)
    if (anyPermission && anyPermission.length > 0) {
      if (!hasAnyPermission(anyPermission)) {
        toast.error("You don't have permission to access this page");
        navigate("/admin", { replace: true });
        return;
      }
    }
  }, [
    isAuthenticated,
    isLoading,
    requiredPermission,
    requiredPermissions,
    anyPermission,
    hasPermission,
    hasAnyPermission,
    navigate
  ]);

  // Show nothing while checking authentication
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  // Show nothing if not authenticated
  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
