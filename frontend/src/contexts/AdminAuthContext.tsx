import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from "react";
import type { AdminUser, AdminRole, AdminPermission, AuditLogEntry } from "@/types/admin";

interface AdminAuthContextType {
  adminUser: AdminUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  hasPermission: (permission: AdminPermission) => boolean;
  hasAnyPermission: (permissions: AdminPermission[]) => boolean;
  hasRole: (role: AdminRole) => boolean;
  auditLog: AuditLogEntry[];
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
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);

  // Check for existing session on mount
  useEffect(() => {
    const checkExistingSession = async () => {
      try {
        const token = localStorage.getItem("admin_token");
        const storedUser = localStorage.getItem("admin_user");

        if (token && storedUser) {
          // In a real app, validate token with backend
          const user = JSON.parse(storedUser) as AdminUser;
          setAdminUser(user);
        }
      } catch (error) {
        console.error("Failed to restore admin session:", error);
        localStorage.removeItem("admin_token");
        localStorage.removeItem("admin_user");
      } finally {
        setIsLoading(false);
      }
    };

    checkExistingSession();
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);

    try {
      // TODO: Replace with actual API call to /api/v1/admin/auth/login
      // For now, using mock authentication for development

      // Mock admin users
      const mockAdmins: Record<string, { user: AdminUser; password: string }> = {
        "admin@solarhub.com": {
          password: "admin123",
          user: {
            id: "admin-1",
            email: "admin@solarhub.com",
            firstName: "Super",
            lastName: "Admin",
            role: "super_admin",
            status: "active",
            createdAt: new Date().toISOString(),
            lastLoginAt: new Date().toISOString(),
          },
        },
        "ops@solarhub.com": {
          password: "ops123",
          user: {
            id: "admin-2",
            email: "ops@solarhub.com",
            firstName: "Operations",
            lastName: "Admin",
            role: "ops_admin",
            status: "active",
            createdAt: new Date().toISOString(),
            lastLoginAt: new Date().toISOString(),
          },
        },
      };

      const adminData = mockAdmins[email];

      if (adminData && adminData.password === password) {
        const token = `mock_admin_token_${Date.now()}`;
        localStorage.setItem("admin_token", token);
        localStorage.setItem("admin_user", JSON.stringify(adminData.user));
        setAdminUser(adminData.user);

        // Add login audit entry
        addAuditEntry({
          action: "view",
          entity: "auth",
          entityId: adminData.user.id,
          details: {
            metadata: { action: "login", success: true },
          },
        });

        return true;
      }

      return false;
    } catch (error) {
      console.error("Admin login failed:", error);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    if (adminUser) {
      addAuditEntry({
        action: "view",
        entity: "auth",
        entityId: adminUser.id,
        details: {
          metadata: { action: "logout" },
        },
      });
    }

    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    setAdminUser(null);
  }, [adminUser]);

  const hasPermission = useCallback((permission: AdminPermission): boolean => {
    if (!adminUser) return false;
    const permissions = rolePermissions[adminUser.role];
    return permissions.includes(permission);
  }, [adminUser]);

  const hasAnyPermission = useCallback((permissions: AdminPermission[]): boolean => {
    if (!adminUser) return false;
    return permissions.some(permission => hasPermission(permission));
  }, [adminUser, hasPermission]);

  const hasRole = useCallback((role: AdminRole): boolean => {
    return adminUser?.role === role;
  }, [adminUser]);

  const addAuditEntry = useCallback((
    entry: Omit<AuditLogEntry, "id" | "actor" | "actorRole" | "timestamp">
  ) => {
    if (!adminUser) return;

    const newEntry: AuditLogEntry = {
      id: `audit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      actor: adminUser.email,
      actorRole: adminUser.role,
      ...entry,
    };

    setAuditLog(prev => [newEntry, ...prev]);

    // TODO: Send audit entry to backend
    // await auditService.createEntry(newEntry);
  }, [adminUser]);

  const value: AdminAuthContextType = {
    adminUser,
    isAuthenticated: !!adminUser,
    isLoading,
    login,
    logout,
    hasPermission,
    hasAnyPermission,
    hasRole,
    auditLog,
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
