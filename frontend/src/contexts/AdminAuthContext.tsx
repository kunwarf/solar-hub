import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from "react";
import type { AdminUser, AdminRole, AdminPermission, AuditLogEntry } from "@/types/admin";
import { adminAuthService, ADMIN_TOKEN_KEY } from "@/api/services/admin.service";

interface AdminAuthContextType {
  adminUser: AdminUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  hasPermission: (permission: AdminPermission) => boolean;
  hasAnyPermission: (permissions: AdminPermission[]) => boolean;
  hasRole: (role: AdminRole) => boolean;
  /** @deprecated Backend creates audit entries automatically. This is a no-op. */
  auditLog: AuditLogEntry[];
  /** @deprecated Backend creates audit entries automatically. This is a no-op. */
  addAuditEntry: (entry: Omit<AuditLogEntry, "id" | "actor" | "actorRole" | "timestamp">) => void;
}

const AdminAuthContext = createContext<AdminAuthContextType | undefined>(undefined);

// Role permissions mapping
const rolePermissions: Record<AdminRole, AdminPermission[]> = {
  super_admin: [
    "manage_providers",
    "manage_tariffs",
    "manage_load_shedding",
    "manage_tiers",
    "manage_features",
    "manage_devices",
    "manage_adapters",
    "manage_weather",
    "manage_firmware",
    "manage_campaigns",
    "manage_users",
    "view_audit_log",
    "export_data",
  ],
  ops_admin: [
    "manage_providers",
    "manage_tariffs",
    "manage_load_shedding",
    "view_audit_log",
  ],
  billing_admin: [
    "manage_tiers",
    "manage_features",
    "view_audit_log",
  ],
  device_admin: [
    "manage_devices",
    "manage_adapters",
    "manage_weather",
    "view_audit_log",
  ],
  firmware_admin: [
    "manage_firmware",
    "manage_campaigns",
    "view_audit_log",
  ],
  read_only: [
    "view_audit_log",
  ],
};

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount by validating stored token with backend
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const token = localStorage.getItem(ADMIN_TOKEN_KEY);
        if (!token) return;

        // Validate token with backend — get current user profile
        const user = await adminAuthService.me();
        setAdminUser(user);
      } catch {
        // Token expired or invalid — clear it
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        localStorage.removeItem("admin_user");
      } finally {
        setIsLoading(false);
      }
    };

    restoreSession();
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const result = await adminAuthService.login(email, password);
      localStorage.setItem(ADMIN_TOKEN_KEY, result.access_token);
      localStorage.setItem("admin_user", JSON.stringify(result.user));
      setAdminUser(result.user);
      return true;
    } catch (error: any) {
      console.error("Admin login failed:", error);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    adminAuthService.logout().catch(() => {});
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem("admin_user");
    setAdminUser(null);
  }, []);

  const hasPermission = useCallback((permission: AdminPermission): boolean => {
    if (!adminUser) return false;
    const permissions = rolePermissions[adminUser.role] ?? [];
    return permissions.includes(permission);
  }, [adminUser]);

  const hasAnyPermission = useCallback((permissions: AdminPermission[]): boolean => {
    if (!adminUser) return false;
    return permissions.some(permission => hasPermission(permission));
  }, [adminUser, hasPermission]);

  const hasRole = useCallback((role: AdminRole): boolean => {
    return adminUser?.role === role;
  }, [adminUser]);

  // Kept for backward-compatibility with pages not yet wired to real API
  const addAuditEntry = useCallback(
    (_entry: Omit<AuditLogEntry, "id" | "actor" | "actorRole" | "timestamp">) => {
      // No-op: backend records audit entries automatically on mutations
    },
    []
  );

  const value: AdminAuthContextType = {
    adminUser,
    isAuthenticated: !!adminUser,
    isLoading,
    login,
    logout,
    hasPermission,
    hasAnyPermission,
    hasRole,
    auditLog: [],
    addAuditEntry,
  };

  return (
    <AdminAuthContext.Provider value={value}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  const context = useContext(AdminAuthContext);
  if (!context) {
    throw new Error("useAdminAuth must be used within AdminAuthProvider");
  }
  return context;
}

export { rolePermissions };
