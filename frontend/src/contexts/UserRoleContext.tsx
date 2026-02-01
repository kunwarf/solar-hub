import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { useAuth } from "@/hooks/use-auth";
import { usersService } from "@/api/services/users.service";
import type { User as ApiUser, UserRole as ApiUserRole } from "@/api/types";

export type UserRole = "owner" | "admin" | "viewer" | "installer";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: "active" | "pending";
  lastActive?: string;
  avatarUrl?: string;
  installerExpiresAt?: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: UserRole;
  sentAt: string;
  expiresAt: string;
  message?: string;
}

export interface ActivityLogEntry {
  id: string;
  userId: string;
  userName: string;
  action: string;
  details: string;
  timestamp: string;
}

interface UserRoleContextType {
  currentUser: User | null;
  users: User[];
  invitations: Invitation[];
  activityLog: ActivityLogEntry[];
  hasPermission: (permission: Permission) => boolean;
  isInstaller: boolean;
  updateUserRole: (userId: string, role: UserRole) => void;
  removeUser: (userId: string) => void;
  inviteUser: (email: string, role: UserRole, message?: string, duration?: number) => void;
  cancelInvitation: (invitationId: string) => void;
  resendInvitation: (invitationId: string) => void;
}

type Permission =
  | "view_dashboard"
  | "manage_devices"
  | "edit_settings"
  | "manage_users"
  | "view_billing"
  | "manage_subscription"
  | "commissioning_mode";

const rolePermissions: Record<UserRole, Permission[]> = {
  owner: [
    "view_dashboard",
    "manage_devices",
    "edit_settings",
    "manage_users",
    "view_billing",
    "manage_subscription",
  ],
  admin: [
    "view_dashboard",
    "manage_devices",
    "edit_settings",
    "manage_users",
    "view_billing",
  ],
  viewer: [
    "view_dashboard",
    "view_billing",
  ],
  installer: [
    "view_dashboard",
    "manage_devices",
    "edit_settings",
    "commissioning_mode",
  ],
};

const roleDescriptions: Record<UserRole, string> = {
  owner: "Full access to all features including billing, subscription management, and user control",
  admin: "Can manage devices, settings, and users but cannot access subscription or transfer ownership",
  viewer: "Read-only access to dashboard and billing information",
  installer: "Temporary access for system commissioning with device and settings control",
};

function mapApiRoleToLocal(apiRole: ApiUserRole | string): UserRole {
  const roleMap: Record<string, UserRole> = {
    owner: "owner",
    admin: "admin",
    viewer: "viewer",
    installer: "installer",
    super_admin: "owner",
    manager: "admin",
  };
  return roleMap[apiRole] || "viewer";
}

function mapApiUserToLocal(apiUser: ApiUser): User {
  return {
    id: apiUser.id,
    name: `${apiUser.first_name} ${apiUser.last_name}`.trim(),
    email: apiUser.email,
    role: mapApiRoleToLocal(apiUser.role),
    status: apiUser.status === "active" ? "active" : "pending",
    lastActive: apiUser.updated_at,
  };
}

const UserRoleContext = createContext<UserRoleContextType | undefined>(undefined);

export function UserRoleProvider({ children }: { children: ReactNode }) {
  const { user: authUser } = useAuth();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([]);

  // Derive currentUser from auth context
  useEffect(() => {
    if (authUser) {
      setCurrentUser(mapApiUserToLocal(authUser));
    } else {
      setCurrentUser(null);
    }
  }, [authUser]);

  // Fetch users list from API (only if user has manage_users permission)
  useEffect(() => {
    const fetchUsers = async () => {
      // Only fetch users if current user has permission to manage users
      if (!currentUser) return;

      const hasManageUsersPermission = rolePermissions[currentUser.role].includes('manage_users');
      if (!hasManageUsersPermission) {
        console.log('[UserRoleContext] User does not have manage_users permission, skipping users fetch');
        return;
      }

      try {
        const response = await usersService.listUsers();
        setUsers(response.items.map(mapApiUserToLocal));
      } catch (error) {
        console.error('Failed to fetch users:', error);
      }
    };

    if (currentUser) {
      fetchUsers();
    }
  }, [currentUser]);

  const hasPermission = useCallback((permission: Permission): boolean => {
    if (!currentUser) return false;
    return rolePermissions[currentUser.role].includes(permission);
  }, [currentUser]);

  const isInstaller = currentUser?.role === "installer";

  const updateUserRole = useCallback(async (userId: string, role: UserRole) => {
    try {
      const apiRoleMap: Record<UserRole, string> = {
        owner: "owner",
        admin: "admin",
        viewer: "viewer",
        installer: "installer",
      };
      await usersService.updateUserRole(userId, apiRoleMap[role] as ApiUserRole);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role } : u));
      if (currentUser) {
        setActivityLog(prev => [{
          id: `log_${Date.now()}`,
          userId: currentUser.id,
          userName: currentUser.name,
          action: "Changed user role",
          details: `Updated ${users.find(u => u.id === userId)?.name} to ${role}`,
          timestamp: new Date().toISOString(),
        }, ...prev]);
      }
    } catch (error) {
      console.error('Failed to update user role:', error);
    }
  }, [currentUser, users]);

  const removeUser = useCallback(async (userId: string) => {
    try {
      await usersService.updateUserStatus(userId, 'deactivated' as ApiUserRole);
      const removedUser = users.find(u => u.id === userId);
      setUsers(prev => prev.filter(u => u.id !== userId));
      if (currentUser) {
        setActivityLog(prev => [{
          id: `log_${Date.now()}`,
          userId: currentUser.id,
          userName: currentUser.name,
          action: "Removed user",
          details: `Removed ${removedUser?.name} (${removedUser?.email})`,
          timestamp: new Date().toISOString(),
        }, ...prev]);
      }
    } catch (error) {
      console.error('Failed to remove user:', error);
    }
  }, [currentUser, users]);

  const inviteUser = useCallback((email: string, role: UserRole, message?: string, duration?: number) => {
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + (duration || 7));

    const newInvitation: Invitation = {
      id: `inv_${Date.now()}`,
      email,
      role,
      sentAt: new Date().toISOString(),
      expiresAt: expiresAt.toISOString(),
      message,
    };

    setInvitations(prev => [...prev, newInvitation]);
    if (currentUser) {
      setActivityLog(prev => [{
        id: `log_${Date.now()}`,
        userId: currentUser.id,
        userName: currentUser.name,
        action: "Invited user",
        details: `Sent ${role} invitation to ${email}`,
        timestamp: new Date().toISOString(),
      }, ...prev]);
    }
  }, [currentUser]);

  const cancelInvitation = useCallback((invitationId: string) => {
    const invitation = invitations.find(i => i.id === invitationId);
    setInvitations(prev => prev.filter(i => i.id !== invitationId));
    if (currentUser) {
      setActivityLog(prev => [{
        id: `log_${Date.now()}`,
        userId: currentUser.id,
        userName: currentUser.name,
        action: "Cancelled invitation",
        details: `Cancelled invitation to ${invitation?.email}`,
        timestamp: new Date().toISOString(),
      }, ...prev]);
    }
  }, [currentUser, invitations]);

  const resendInvitation = useCallback((invitationId: string) => {
    setInvitations(prev => prev.map(i =>
      i.id === invitationId
        ? { ...i, sentAt: new Date().toISOString() }
        : i
    ));
  }, []);

  return (
    <UserRoleContext.Provider value={{
      currentUser,
      users,
      invitations,
      activityLog,
      hasPermission,
      isInstaller,
      updateUserRole,
      removeUser,
      inviteUser,
      cancelInvitation,
      resendInvitation,
    }}>
      {children}
    </UserRoleContext.Provider>
  );
}

export function useUserRole() {
  const context = useContext(UserRoleContext);
  if (!context) {
    throw new Error("useUserRole must be used within a UserRoleProvider");
  }
  return context;
}

export { roleDescriptions, rolePermissions };
