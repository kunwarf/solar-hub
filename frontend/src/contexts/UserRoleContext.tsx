import { createContext, useContext, useState, ReactNode } from "react";

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
  currentUser: User;
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

// Mock data
const mockCurrentUser: User = {
  id: "user_1",
  name: "Ahmad Khan",
  email: "ahmad.khan@example.com",
  role: "owner",
  status: "active",
  lastActive: new Date().toISOString(),
};

const mockUsers: User[] = [
  mockCurrentUser,
  {
    id: "user_2",
    name: "Fatima Ahmed",
    email: "fatima.ahmed@example.com",
    role: "admin",
    status: "active",
    lastActive: "2024-01-15T10:30:00Z",
  },
  {
    id: "user_3",
    name: "Hassan Ali",
    email: "hassan.ali@example.com",
    role: "viewer",
    status: "active",
    lastActive: "2024-01-14T15:45:00Z",
  },
  {
    id: "user_4",
    name: "SolarTech Installer",
    email: "tech@solartech.pk",
    role: "installer",
    status: "active",
    lastActive: "2024-01-15T09:00:00Z",
    installerExpiresAt: "2024-01-22T09:00:00Z",
  },
];

const mockInvitations: Invitation[] = [
  {
    id: "inv_1",
    email: "newuser@example.com",
    role: "viewer",
    sentAt: "2024-01-14T12:00:00Z",
    expiresAt: "2024-01-21T12:00:00Z",
  },
  {
    id: "inv_2",
    email: "installer@pvexpert.pk",
    role: "installer",
    sentAt: "2024-01-15T08:00:00Z",
    expiresAt: "2024-01-18T08:00:00Z",
    message: "Access for system commissioning",
  },
];

const mockActivityLog: ActivityLogEntry[] = [
  {
    id: "log_1",
    userId: "user_1",
    userName: "Ahmad Khan",
    action: "Updated tariff settings",
    details: "Changed DISCO from LESCO to FESCO",
    timestamp: "2024-01-15T14:30:00Z",
  },
  {
    id: "log_2",
    userId: "user_4",
    userName: "SolarTech Installer",
    action: "Added new device",
    details: "Registered Inverter: Senergy 5kW",
    timestamp: "2024-01-15T09:15:00Z",
  },
  {
    id: "log_3",
    userId: "user_2",
    userName: "Fatima Ahmed",
    action: "Invited user",
    details: "Sent invitation to newuser@example.com",
    timestamp: "2024-01-14T12:00:00Z",
  },
  {
    id: "log_4",
    userId: "user_1",
    userName: "Ahmad Khan",
    action: "Changed user role",
    details: "Updated Hassan Ali from Admin to Viewer",
    timestamp: "2024-01-13T16:45:00Z",
  },
  {
    id: "log_5",
    userId: "user_3",
    userName: "Hassan Ali",
    action: "Viewed billing report",
    details: "Accessed January 2024 billing summary",
    timestamp: "2024-01-13T11:20:00Z",
  },
];

const UserRoleContext = createContext<UserRoleContextType | undefined>(undefined);

export function UserRoleProvider({ children }: { children: ReactNode }) {
  const [currentUser] = useState<User>(mockCurrentUser);
  const [users, setUsers] = useState<User[]>(mockUsers);
  const [invitations, setInvitations] = useState<Invitation[]>(mockInvitations);
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>(mockActivityLog);

  const hasPermission = (permission: Permission): boolean => {
    return rolePermissions[currentUser.role].includes(permission);
  };

  const isInstaller = currentUser.role === "installer";

  const updateUserRole = (userId: string, role: UserRole) => {
    setUsers(prev => prev.map(u => u.id === userId ? { ...u, role } : u));
    setActivityLog(prev => [{
      id: `log_${Date.now()}`,
      userId: currentUser.id,
      userName: currentUser.name,
      action: "Changed user role",
      details: `Updated ${users.find(u => u.id === userId)?.name} to ${role}`,
      timestamp: new Date().toISOString(),
    }, ...prev]);
  };

  const removeUser = (userId: string) => {
    const removedUser = users.find(u => u.id === userId);
    setUsers(prev => prev.filter(u => u.id !== userId));
    setActivityLog(prev => [{
      id: `log_${Date.now()}`,
      userId: currentUser.id,
      userName: currentUser.name,
      action: "Removed user",
      details: `Removed ${removedUser?.name} (${removedUser?.email})`,
      timestamp: new Date().toISOString(),
    }, ...prev]);
  };

  const inviteUser = (email: string, role: UserRole, message?: string, duration?: number) => {
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
    setActivityLog(prev => [{
      id: `log_${Date.now()}`,
      userId: currentUser.id,
      userName: currentUser.name,
      action: "Invited user",
      details: `Sent ${role} invitation to ${email}`,
      timestamp: new Date().toISOString(),
    }, ...prev]);
  };

  const cancelInvitation = (invitationId: string) => {
    const invitation = invitations.find(i => i.id === invitationId);
    setInvitations(prev => prev.filter(i => i.id !== invitationId));
    setActivityLog(prev => [{
      id: `log_${Date.now()}`,
      userId: currentUser.id,
      userName: currentUser.name,
      action: "Cancelled invitation",
      details: `Cancelled invitation to ${invitation?.email}`,
      timestamp: new Date().toISOString(),
    }, ...prev]);
  };

  const resendInvitation = (invitationId: string) => {
    setInvitations(prev => prev.map(i => 
      i.id === invitationId 
        ? { ...i, sentAt: new Date().toISOString() }
        : i
    ));
  };

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
