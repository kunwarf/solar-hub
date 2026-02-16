# Solar Hub - Admin Portal Design Document

**Project**: Solar Hub
**Feature**: Complete Admin Web Portal
**Date**: 2026-02-16
**Version**: 1.0
**Status**: Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Scope and Requirements](#scope-and-requirements)
3. [Architecture Design](#architecture-design)
4. [Component Structure](#component-structure)
5. [API Integration](#api-integration)
6. [Security & Authorization](#security--authorization)
7. [Data Management](#data-management)
8. [Implementation Phases](#implementation-phases)
9. [Testing Strategy](#testing-strategy)
10. [Risk Mitigation](#risk-mitigation)

---

## Executive Summary

### Purpose
Create a comprehensive administrative web portal at `/admin/*` routes to manage all platform configuration, monitoring, and operational tasks.

### Scope
**Complete admin feature set** including:
- Platform configuration (providers, tariffs, schedules)
- Subscription & feature management
- Device & protocol configuration
- OTA firmware management
- User administration
- Audit logging

### Key Metrics
- **13 Admin Pages**: Full feature coverage
- **50+ Components**: Reusable admin UI components
- **8 OTA APIs**: Firmware management integration
- **10+ CRUD Entities**: Electricity providers, tariffs, tiers, devices, etc.
- **Role-Based Access**: 5 admin roles with granular permissions

---

## Scope and Requirements

### 1.1 Reference Application
**Source**: https://github.com/kunwarf/start-from-code-9c314cf4.git

**Analysis Results**:
- React 18.3 + TypeScript 5.8
- Vite 5.4 build system
- shadcn/ui component library
- React Query for state management
- React Hook Form + Zod validation
- Permission-based access control
- Complete audit logging system

### 1.2 Complete Feature List

#### Configuration Management
- ✅ Electricity Providers (LESCO, K-Electric, MEPCO, etc.)
- ✅ Tariff Plans (slab-based, ToU, flat rate)
- ✅ Load Shedding Schedules (by provider/zone/time)
- ✅ Subscription Tiers (pricing, limits, features)
- ✅ Feature Flags (enable/disable per tier)

#### Device & Protocol Management
- ✅ Device Catalog (supported inverters, batteries, meters)
- ✅ Protocol Adapters (Modbus TCP/RTU, MQTT, HTTP)
- ✅ Weather Stations (data sources, APIs)

#### OTA Firmware Management
- ✅ Firmware Versions (upload, manage, deprecate)
- ✅ Update Campaigns (staged rollouts, monitoring)
- ✅ Device Fleet Status (version distribution, update progress)

#### User & Audit
- ✅ Admin User Management (roles, permissions)
- ✅ Audit Log (complete action history)

---

## Architecture Design

### 2.1 System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                    │
│                                                                │
│  ┌──────────────────┐         ┌──────────────────────────┐   │
│  │   User Portal    │         │      Admin Portal        │   │
│  │   /dashboard     │         │      /admin/*            │   │
│  │   /devices       │         │   ┌──────────────────┐   │   │
│  │   /billing       │         │   │ Configuration    │   │   │
│  │   /settings      │         │   │ Management       │   │   │
│  └──────────────────┘         │   ├──────────────────┤   │   │
│          │                    │   │ Device & Protocol│   │   │
│          │                    │   ├──────────────────┤   │   │
│          │                    │   │ OTA Firmware     │   │   │
│          │                    │   ├──────────────────┤   │   │
│          │                    │   │ User & Audit     │   │   │
│          │                    │   └──────────────────┘   │   │
│          │                    └──────────────────────────┘   │
│          │                               │                   │
└──────────┼───────────────────────────────┼───────────────────┘
           │                               │
           ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND APIs                             │
│                                                              │
│  ┌────────────────────┐       ┌────────────────────────┐   │
│  │    System A API     │       │    System B API        │   │
│  │    (Port 8000)      │       │    (Port 8001)         │   │
│  │                     │       │                        │   │
│  │ • Users             │       │ • Devices              │   │
│  │ • Organizations     │       │ • Telemetry            │   │
│  │ • Sites             │       │ • Commands             │   │
│  │ • Billing           │       │ • Firmware (OTA)       │   │
│  │ • Tariffs           │       │ • Protocol Adapters    │   │
│  │ • Alerts            │       │                        │   │
│  └────────────────────┘       └────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Admin Portal Architecture

```
frontend/src/
├── pages/admin/              # 13 Admin Pages
│   ├── Index.tsx             # Dashboard
│   ├── AuditLog.tsx
│   ├── ElectricityProviders.tsx
│   ├── TariffManagement.tsx
│   ├── LoadSheddingSchedule.tsx
│   ├── SubscriptionTiers.tsx
│   ├── FeatureManagement.tsx
│   ├── DeviceCatalog.tsx
│   ├── ProtocolAdapters.tsx
│   ├── WeatherStations.tsx
│   ├── FirmwareVersions.tsx
│   ├── OTACampaigns.tsx
│   └── UserManagement.tsx
│
├── components/admin/         # Admin Components
│   ├── layout/
│   │   ├── AdminLayout.tsx
│   │   ├── AdminSidebar.tsx
│   │   └── AdminHeader.tsx
│   │
│   ├── configuration/
│   │   ├── ProviderCard.tsx
│   │   ├── TariffEditor.tsx
│   │   └── ScheduleCalendar.tsx
│   │
│   ├── firmware/
│   │   ├── VersionCard.tsx
│   │   ├── FileUploader.tsx
│   │   ├── CampaignWizard.tsx
│   │   ├── DeviceTable.tsx
│   │   └── RolloutProgress.tsx
│   │
│   └── common/
│       ├── ConfirmDialog.tsx
│       ├── DataTable.tsx
│       ├── StatCard.tsx
│       └── AdminGuard.tsx
│
├── contexts/
│   └── AdminAuthContext.tsx  # Admin authentication
│
├── api/services/
│   ├── admin.service.ts      # System A admin APIs
│   └── firmware.service.ts   # System B firmware APIs
│
└── types/
    ├── admin.ts              # Admin types
    └── firmware.ts           # OTA types
```

---

## Component Structure

### 3.1 Admin Layout Hierarchy

```
<AdminLayout>
  ├── <AdminSidebar>
  │   ├── Logo & Branding
  │   ├── Navigation Groups
  │   │   ├── Overview (Dashboard, Audit Log)
  │   │   ├── Providers & Billing
  │   │   ├── Subscriptions
  │   │   ├── Devices
  │   │   └── OTA Updates
  │   └── User Profile
  │
  └── <main>
      ├── <AdminHeader>
      │   ├── Breadcrumbs
      │   └── Quick Actions
      │
      └── Page Content
          ├── Header Section (Title, Description, Actions)
          ├── Stats Cards (Metrics Overview)
          ├── Filters Section (Search, Dropdowns)
          └── Data Display (Tables, Cards, Forms)
```

### 3.2 Page Structure Pattern

Every admin page follows this consistent structure:

```typescript
export default function AdminPageTemplate() {
  // State management
  const [data, setData] = useState([]);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);

  // Auth & permissions
  const { hasPermission, addAuditEntry } = useAdminAuth();
  const canEdit = hasPermission("manage_entity");

  // API hooks
  const { data: apiData, isLoading } = useQuery({...});
  const createMutation = useMutation({...});

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1>Page Title</h1>
            <p className="text-muted-foreground">Description</p>
          </div>
          {canEdit && (
            <Button onClick={handleCreate}>
              <Plus /> Create New
            </Button>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Icon} label="Metric" value={count} />
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <SearchInput value={search} onChange={setSearch} />
          <FilterDropdown {...} />
        </div>

        {/* Data Table */}
        <DataTable
          data={filtered}
          columns={columns}
          onEdit={canEdit ? handleEdit : undefined}
          onDelete={canEdit ? handleDelete : undefined}
        />

        {/* Dialogs */}
        <CreateEditDialog {...} />
      </div>
    </AdminLayout>
  );
}
```

---

## API Integration

### 4.1 System A APIs (Configuration)

#### Electricity Providers
```typescript
// GET /api/v1/admin/providers
interface ElectricityProvider {
  id: string;
  name: string;
  shortName: string;  // "LESCO", "K-Electric"
  region: string;     // "Punjab", "Sindh"
  status: "active" | "inactive";
  tariffCount: number;
  createdAt: string;
  updatedAt: string;
}

// POST /api/v1/admin/providers
// PUT /api/v1/admin/providers/{id}
// DELETE /api/v1/admin/providers/{id}
```

#### Tariff Plans
```typescript
// GET /api/v1/admin/tariffs
interface TariffPlan {
  id: string;
  providerId: string;
  name: string;
  category: "residential" | "commercial" | "industrial";
  type: "slab" | "tou" | "flat";
  rates: {
    slabs?: Array<{
      minUnits: number;
      maxUnits: number | null;
      ratePerKwh: number;
    }>;
    touPeakRate?: number;
    touOffPeakRate?: number;
    flatRate?: number;
  };
  fixedCharges: number;
  effectiveFrom: string;
  effectiveTo: string | null;
  status: "active" | "inactive" | "draft";
}

// POST /api/v1/admin/tariffs
// PUT /api/v1/admin/tariffs/{id}
```

#### Load Shedding Schedules
```typescript
// GET /api/v1/admin/load-shedding
interface LoadSheddingSchedule {
  id: string;
  providerId: string;
  zone: string;
  dayOfWeek: number;  // 0-6
  startTime: string;  // "HH:mm"
  endTime: string;
  duration: number;   // minutes
  isActive: boolean;
}

// POST /api/v1/admin/load-shedding
// PUT /api/v1/admin/load-shedding/{id}
```

#### Subscription Tiers
```typescript
// GET /api/v1/admin/subscription-tiers
interface SubscriptionTier {
  id: string;
  name: string;
  displayName: string;
  pricePerMonth: number;
  currency: "PKR";
  limits: {
    maxDevices: number;
    pollingInterval: number;  // seconds
    dataRetention: number;    // days
    maxUsers: number;
  };
  features: string[];  // Feature IDs
  isActive: boolean;
}

// POST /api/v1/admin/subscription-tiers
// PUT /api/v1/admin/subscription-tiers/{id}
```

#### Feature Flags
```typescript
// GET /api/v1/admin/features
interface Feature {
  id: string;
  name: string;
  description: string;
  category: "core" | "premium" | "experimental";
  enabledForTiers: string[];  // Tier IDs
  isActive: boolean;
}

// PUT /api/v1/admin/features/{id}/tiers
```

#### Device Catalog
```typescript
// GET /api/v1/admin/device-catalog
interface DeviceModel {
  id: string;
  manufacturer: string;
  model: string;
  type: "inverter" | "battery" | "meter";
  protocol: "modbus_tcp" | "modbus_rtu" | "mqtt";
  specifications: {
    maxPowerKw?: number;
    capacityKwh?: number;
    phases?: 1 | 3;
  };
  registerMapFile?: string;
  isSupported: boolean;
}

// POST /api/v1/admin/device-catalog
// PUT /api/v1/admin/device-catalog/{id}
```

#### Protocol Adapters
```typescript
// GET /api/v1/admin/protocol-adapters
interface ProtocolAdapter {
  id: string;
  name: string;
  protocol: string;
  deviceType: string;
  adapterClass: string;
  configuration: {
    defaultPort?: number;
    timeout?: number;
    retries?: number;
  };
  isActive: boolean;
}

// PUT /api/v1/admin/protocol-adapters/{id}
```

### 4.2 System B APIs (OTA Firmware)

Already documented in `DESIGN_OTA_SYSTEM.md`:

```typescript
// Firmware Versions
POST   /api/v1/firmware/versions
GET    /api/v1/firmware/versions
POST   /api/v1/firmware/versions/{id}/files
GET    /api/v1/firmware/versions/{id}/files

// Update Campaigns
POST   /api/v1/firmware/campaigns
POST   /api/v1/firmware/campaigns/{id}/activate
GET    /api/v1/firmware/campaigns/{id}/status

// Device Status
GET    /api/v1/firmware/devices/status
```

---

## Security & Authorization

### 5.1 Admin Roles & Permissions

```typescript
export type AdminRole =
  | "super_admin"      // Full access to everything
  | "ops_admin"        // Providers, tariffs, load shedding
  | "billing_admin"    // Subscription tiers, features
  | "device_admin"     // Device catalog, protocols
  | "firmware_admin"   // OTA firmware management
  | "read_only";       // View-only access

export type AdminPermission =
  // Configuration
  | "manage_providers"
  | "manage_tariffs"
  | "manage_load_shedding"
  // Subscriptions
  | "manage_tiers"
  | "manage_features"
  // Devices
  | "manage_devices"
  | "manage_adapters"
  | "manage_weather"
  // OTA
  | "manage_firmware"
  | "manage_campaigns"
  // Users
  | "manage_users"
  | "view_audit_log"
  | "export_data";

const rolePermissions: Record<AdminRole, AdminPermission[]> = {
  super_admin: [/* all permissions */],
  ops_admin: ["manage_providers", "manage_tariffs", "manage_load_shedding"],
  billing_admin: ["manage_tiers", "manage_features"],
  device_admin: ["manage_devices", "manage_adapters", "manage_weather"],
  firmware_admin: ["manage_firmware", "manage_campaigns"],
  read_only: ["view_audit_log"],
};
```

### 5.2 Authentication Flow

```typescript
// AdminAuthContext.tsx
interface AdminAuthContextType {
  adminUser: AdminUser | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  hasPermission: (permission: AdminPermission) => boolean;
  hasAnyPermission: (permissions: AdminPermission[]) => boolean;
  auditLog: AuditLogEntry[];
  addAuditEntry: (entry: Omit<AuditLogEntry, "id" | "actor" | "timestamp">) => void;
}

// Login flow
const login = async (email: string, password: string) => {
  // POST /api/v1/admin/auth/login
  const response = await adminAuthService.login(email, password);

  if (response.success) {
    setAdminUser(response.user);
    localStorage.setItem("admin_token", response.token);
    return true;
  }
  return false;
};

// Permission check
const hasPermission = (permission: AdminPermission) => {
  if (!adminUser) return false;
  const permissions = rolePermissions[adminUser.role];
  return permissions.includes(permission);
};
```

### 5.3 Route Protection

```typescript
// AdminGuard.tsx
export function AdminGuard({
  children,
  requiredPermission
}: {
  children: React.ReactNode;
  requiredPermission?: AdminPermission;
}) {
  const { isAuthenticated, hasPermission } = useAdminAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/admin/login");
      return;
    }

    if (requiredPermission && !hasPermission(requiredPermission)) {
      toast.error("You don't have permission to access this page");
      navigate("/admin");
    }
  }, [isAuthenticated, requiredPermission]);

  if (!isAuthenticated) return null;

  return <>{children}</>;
}

// Usage in routes
<Route
  path="/admin/providers"
  element={
    <AdminGuard requiredPermission="manage_providers">
      <ElectricityProviders />
    </AdminGuard>
  }
/>
```

### 5.4 Audit Logging

All administrative actions must be logged:

```typescript
interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor: string;       // Admin email
  actorRole: AdminRole;
  action: "create" | "update" | "delete" | "activate" | "deactivate" | "view";
  entity: string;      // "provider", "tariff", "tier", etc.
  entityId: string;
  details: {
    before?: any;
    after?: any;
    metadata?: Record<string, any>;
  };
  ipAddress?: string;
  userAgent?: string;
}

// Example usage
const handleCreateProvider = async (data: ProviderFormData) => {
  const newProvider = await createProvider(data);

  addAuditEntry({
    action: "create",
    entity: "provider",
    entityId: newProvider.id,
    details: {
      after: newProvider,
      metadata: { source: "admin_ui" }
    }
  });

  toast.success("Provider created successfully");
};
```

---

## Data Management

### 6.1 State Management Strategy

**Server State** (via TanStack Query):
```typescript
// hooks/admin/useProviders.ts
export function useProviders() {
  return useQuery({
    queryKey: ["admin", "providers"],
    queryFn: () => adminService.getProviders(),
    staleTime: 5 * 60 * 1000,  // 5 minutes
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProviderData) => adminService.createProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "providers"] });
      toast.success("Provider created successfully");
    },
    onError: (error) => {
      toast.error(`Failed to create provider: ${error.message}`);
    },
  });
}
```

**Local State** (via useState):
- Search filters
- Dialog open/close states
- Form data (before submission)
- UI preferences (sidebar collapsed, theme)

**Context State** (via React Context):
- Admin authentication
- Current admin user
- Permissions
- Audit log (in-memory for session)

### 6.2 Data Validation

**Frontend Validation** (Zod schemas):
```typescript
// schemas/provider.schema.ts
import { z } from "zod";

export const providerSchema = z.object({
  name: z.string().min(3, "Name must be at least 3 characters"),
  shortName: z.string().min(2).max(10),
  region: z.enum(["Punjab", "Sindh", "KPK", "Balochistan", "ICT"]),
  status: z.enum(["active", "inactive"]).default("active"),
});

export type ProviderFormData = z.infer<typeof providerSchema>;

// Usage with React Hook Form
const form = useForm<ProviderFormData>({
  resolver: zodResolver(providerSchema),
  defaultValues: {
    status: "active",
  },
});
```

### 6.3 Mock Data (Development)

For initial development without backend integration:

```typescript
// data/adminMockData.ts
export const mockProviders: ElectricityProvider[] = [
  {
    id: "p1",
    name: "Lahore Electric Supply Company",
    shortName: "LESCO",
    region: "Punjab",
    status: "active",
    tariffCount: 5,
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-15T10:00:00Z",
  },
  // ... more providers
];

export const mockTariffs: TariffPlan[] = [
  {
    id: "t1",
    providerId: "p1",
    name: "Residential Unprotected",
    category: "residential",
    type: "slab",
    rates: {
      slabs: [
        { minUnits: 0, maxUnits: 100, ratePerKwh: 7.74 },
        { minUnits: 101, maxUnits: 200, ratePerKwh: 11.50 },
        { minUnits: 201, maxUnits: 300, ratePerKwh: 16.00 },
        { minUnits: 301, maxUnits: 700, ratePerKwh: 24.00 },
        { minUnits: 701, maxUnits: null, ratePerKwh: 32.00 },
      ],
    },
    fixedCharges: 150,
    effectiveFrom: "2024-01-01",
    effectiveTo: null,
    status: "active",
  },
  // ... more tariffs
];
```

---

## Migration Strategy

### 9.1 Existing Features to Admin Portal

Several features currently in the user-facing application should be moved to admin-only access:

#### 9.1.1 TariffSettings.tsx Migration

**Current Location**: `frontend/src/pages/TariffSettings.tsx`

**Admin-Only Features** (Move to Admin Portal):
- ✅ **DISCO Provider Management**
  - Creating/editing/deleting electricity providers (LESCO, K-Electric, etc.)
  - Provider region and coverage configuration
  - Provider status management (active/inactive)
  - **New Location**: `/admin/providers` (ElectricityProviders page)

- ✅ **Master Tariff Configuration**
  - Creating/editing tariff plans (slab-based, ToU, flat rate)
  - Slab definitions and rate configuration
  - Consumer category management (residential, commercial, industrial)
  - Net metering configuration
  - Monthly adjustment factors
  - **New Location**: `/admin/tariffs` (TariffManagement page)

**User-Facing Features** (Keep in Current Location):
- ❌ **Personal Tariff Selection**
  - Selecting their electricity provider from available options
  - Choosing their tariff plan (from admin-configured options)
  - Viewing their current tariff details
  - **Remains At**: `/settings/tariffs` (simplified user view)

- ❌ **Bill Calculator**
  - Calculating estimated bills based on selected tariff
  - Viewing slab breakdowns
  - Comparing different consumption scenarios
  - **Remains At**: `/settings/tariffs` (user tool)

**Migration Plan**:
1. Create `ElectricityProviders.tsx` and `TariffManagement.tsx` in admin portal
2. Move CRUD operations to admin API endpoints
3. Simplify TariffSettings.tsx to read-only selection + calculator
4. Update permissions to restrict editing to admin roles

#### 9.1.2 UserManagement.tsx Migration

**Current Location**: `frontend/src/pages/UserManagement.tsx`

**Dual Access Model** (Admin + Organization Owners):

- ✅ **Platform-Wide User Management** (Admin-Only)
  - View all users across all organizations
  - Manage admin roles and permissions
  - Suspend/activate user accounts globally
  - View cross-organization activity logs
  - **New Location**: `/admin/users` (UserManagement page)

- ❌ **Organization-Scoped User Management** (Keep for Org Owners)
  - Invite users to their organization
  - Manage roles within their organization
  - View activity logs for their organization only
  - Remove users from their organization
  - **Remains At**: `/settings/team` (organization-scoped)

**Migration Plan**:
1. Create admin version at `/admin/users` with global scope
2. Keep existing `/settings/team` with organization filters
3. Add permission checks: `is_admin` for admin portal, `is_owner` for team page
4. Admin view shows all organizations, team view shows only user's org

#### 9.1.3 Settings.tsx Migration

**Current Location**: `frontend/src/pages/Settings.tsx`

**Admin-Only Features** (Move to Admin Portal):
- ✅ **System-Wide MQTT Configuration**
  - Default MQTT broker settings
  - System-level credentials and certificates
  - Global MQTT topics structure
  - **New Location**: `/admin/settings` (System Settings page)

- ✅ **Default Location & Timezone**
  - System default timezone
  - Default location coordinates
  - Regional settings (currency, date format)
  - **New Location**: `/admin/settings` (System Settings page)

- ✅ **Global Hierarchy Templates**
  - Pre-configured hierarchy templates for new installations
  - Default inverter array configurations
  - Default battery array setups
  - **New Location**: `/admin/device-catalog` (as templates)

**User-Facing Features** (Keep in Current Location):
- ❌ **Personal Preferences**
  - User mode toggle (simple vs advanced)
  - Personal notification settings
  - Theme preferences
  - **Remains At**: `/settings/preferences` (user-specific)

- ❌ **Site-Specific Settings**
  - Site location and timezone override
  - Site-specific MQTT configuration (if different from system)
  - Custom hierarchy for their installation
  - **Remains At**: `/settings/site` (site-scoped)

**Migration Plan**:
1. Extract system-wide settings to admin portal
2. Keep user/site-specific settings in current location
3. Add clear visual distinction: "System Settings (Admin)" vs "Your Settings"
4. Admin settings become defaults for new users/sites

### 9.2 Migration Implementation Timeline

**Phase 0: Pre-Migration** (Days 1-2)
- ✅ Audit all existing user-facing pages
- ✅ Document current permission checks
- ✅ Identify data dependencies
- ✅ Create migration checklist

**Phase 1: Admin Portal Foundation** (Week 1)
- ✅ Build admin layout and routing
- ✅ Implement admin authentication
- ✅ Create admin versions of pages (with full CRUD)

**Phase 2: Simplify User Pages** (Week 2)
- ✅ Simplify TariffSettings.tsx to selection + calculator only
- ✅ Add organization scope filter to UserManagement.tsx
- ✅ Split Settings.tsx into admin and user sections
- ✅ Update permission checks throughout

**Phase 3: API Updates** (Week 2-3)
- ✅ Create admin API endpoints for provider/tariff CRUD
- ✅ Add organization filtering to user management APIs
- ✅ Separate system settings from user preferences in API
- ✅ Add permission middleware for admin-only endpoints

**Phase 4: Testing & Validation** (Week 4)
- ✅ Test admin CRUD operations
- ✅ Verify users can't access admin features
- ✅ Ensure org owners can still manage their teams
- ✅ Validate backward compatibility

### 9.3 Backward Compatibility

**Maintaining Compatibility**:
1. **Existing Users**: No disruption to current user workflows
2. **API Contracts**: All existing user APIs remain unchanged
3. **Data Migration**: No data structure changes required
4. **Permissions**: Existing role checks continue to work
5. **Navigation**: User-facing routes remain accessible

**New Restrictions**:
- ⚠️ Regular users can no longer create/edit electricity providers
- ⚠️ Regular users can no longer create/edit tariff plans
- ⚠️ Org owners can only manage users in their organization
- ⚠️ System-wide settings require admin access

**Mitigation**:
- Display clear "Admin-Only" badges on restricted features
- Show helpful messages directing users to contact admin
- Provide request workflow for users to suggest new providers/tariffs

### 9.4 Affected Components

| Component | Change Type | Impact |
|-----------|-------------|---------|
| **TariffSettings.tsx** | Simplify | Remove edit capabilities, keep selection + calculator |
| **UserManagement.tsx** | Scope | Add organization filtering, keep for org owners |
| **Settings.tsx** | Split | Move system settings to admin, keep user preferences |
| **Navigation** | Update | Add conditional admin link in sidebar |
| **PermissionContext** | Extend | Add admin role and permission checks |
| **API Routes** | New | Add admin CRUD endpoints |
| **Database** | No change | Existing tables support new access patterns |

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Day 1-2: Setup & Core Components**
- ✅ Install dependencies (shadcn/ui, React Query, React Hook Form, Zod)
- ✅ Create AdminLayout, AdminSidebar, AdminHeader
- ✅ Setup AdminAuthContext with mock authentication
- ✅ Configure admin routes in App.tsx
- ✅ Create AdminGuard component
- ✅ Setup audit logging system

**Day 3-4: Configuration Pages (Part 1)**
- ✅ Admin Dashboard (overview metrics)
- ✅ Electricity Providers (CRUD)
- ✅ Tariff Management (CRUD with complex forms)

**Day 5: Configuration Pages (Part 2)**
- ✅ Load Shedding Schedule (calendar UI)
- ✅ Audit Log (read-only table)

### Phase 2: Subscriptions & Devices (Week 2)

**Day 1-2: Subscription Management**
- ✅ Subscription Tiers (CRUD)
- ✅ Feature Management (toggle features per tier)

**Day 3-4: Device Management**
- ✅ Device Catalog (CRUD)
- ✅ Protocol Adapters (configuration UI)
- ✅ Weather Stations (API configuration)

**Day 5: API Integration (System A)**
- ✅ Replace mock data with real API calls
- ✅ Error handling and loading states
- ✅ Optimistic updates

### Phase 3: OTA Firmware (Week 3)

**Day 1-2: Firmware Management**
- ✅ Firmware Versions (upload UI)
- ✅ File uploader component (multi-file, checksums)

**Day 3-4: Campaign Management**
- ✅ Campaign creation wizard
- ✅ Campaign monitoring (real-time polling)
- ✅ Device status table

**Day 5: API Integration (System B)**
- ✅ Integrate OTA APIs
- ✅ WebSocket/polling for real-time updates
- ✅ Progress indicators

### Phase 4: Polish & Testing (Week 4)

**Day 1-2: User Management**
- ✅ Admin user CRUD
- ✅ Real authentication integration

**Day 3: UI/UX Polish**
- ✅ Responsive design refinement
- ✅ Loading skeletons
- ✅ Error boundaries
- ✅ Toast notifications

**Day 4-5: Testing**
- ✅ Unit tests (components, hooks)
- ✅ Integration tests (API calls)
- ✅ E2E tests (critical flows)
- ✅ Accessibility audit

---

## Testing Strategy

### 7.1 Unit Tests (Vitest)

**Component Tests:**
```typescript
// AdminSidebar.test.tsx
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { AdminSidebar } from "./AdminSidebar";
import { AdminAuthProvider } from "@/contexts/AdminAuthContext";

describe("AdminSidebar", () => {
  it("renders navigation items", () => {
    render(
      <BrowserRouter>
        <AdminAuthProvider>
          <AdminSidebar />
        </AdminAuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Audit Log")).toBeInTheDocument();
  });

  it("highlights active route", () => {
    // ... test active state
  });

  it("hides items without permission", () => {
    // ... test permission-based rendering
  });
});
```

**Hook Tests:**
```typescript
// useProviders.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useProviders } from "./useProviders";

describe("useProviders", () => {
  it("fetches providers successfully", async () => {
    const { result } = renderHook(() => useProviders(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={new QueryClient()}>
          {children}
        </QueryClientProvider>
      ),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(5);
  });
});
```

### 7.2 Integration Tests

**API Integration:**
```typescript
// adminService.test.ts
import { adminService } from "@/api/services/admin.service";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const server = setupServer(
  http.get("/api/v1/admin/providers", () => {
    return HttpResponse.json([{ id: "p1", name: "LESCO" }]);
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("Admin Service", () => {
  it("fetches providers", async () => {
    const providers = await adminService.getProviders();
    expect(providers).toHaveLength(1);
    expect(providers[0].name).toBe("LESCO");
  });

  it("handles API errors", async () => {
    server.use(
      http.get("/api/v1/admin/providers", () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    await expect(adminService.getProviders()).rejects.toThrow();
  });
});
```

### 7.3 E2E Tests (Playwright)

**Critical User Flows:**
```typescript
// admin.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Admin Portal", () => {
  test("admin can login and view dashboard", async ({ page }) => {
    await page.goto("/admin/login");
    await page.fill('input[name="email"]', "admin@solarhub.com");
    await page.fill('input[name="password"]', "admin123");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL("/admin");
    await expect(page.locator("h1")).toContainText("Admin Dashboard");
  });

  test("admin can create electricity provider", async ({ page }) => {
    await page.goto("/admin/providers");
    await page.click('button:has-text("Add Provider")');

    await page.fill('input[name="name"]', "Test Electric Co");
    await page.fill('input[name="shortName"]', "TEC");
    await page.selectOption('select[name="region"]', "Punjab");
    await page.click('button:has-text("Save")');

    await expect(page.locator("text=Test Electric Co")).toBeVisible();
  });

  test("admin can upload firmware version", async ({ page }) => {
    await page.goto("/admin/firmware");
    await page.click('button:has-text("Upload Firmware")');

    await page.fill('input[name="version"]', "2.0.0");
    await page.setInputFiles('input[type="file"]', [
      "test-files/main.py",
      "test-files/config.json"
    ]);
    await page.click('button:has-text("Upload")');

    await expect(page.locator("text=2.0.0")).toBeVisible();
  });
});
```

---

## Risk Mitigation

### 8.1 Security Risks

| Risk | Mitigation Strategy |
|------|-------------------|
| **Unauthorized Admin Access** | 1. JWT-based authentication<br>2. HTTP-only cookies<br>3. Token expiry (1 hour)<br>4. Refresh token rotation<br>5. IP-based rate limiting |
| **CSRF Attacks** | 1. CSRF tokens on all mutating requests<br>2. SameSite cookie policy<br>3. Origin validation |
| **XSS Attacks** | 1. React's automatic escaping<br>2. DOMPurify for rich text<br>3. CSP headers |
| **Malicious File Uploads** | 1. File type validation (Python files only)<br>2. File size limits (500KB max)<br>3. Virus scanning (Phase 2)<br>4. Checksum verification<br>5. Sandboxed preview |
| **SQL Injection** | 1. Parameterized queries (SQLAlchemy ORM)<br>2. Input validation (Zod schemas)<br>3. Prepared statements only |

### 8.2 Operational Risks

| Risk | Mitigation Strategy |
|------|-------------------|
| **Accidental Mass Updates** | 1. Confirmation dialogs<br>2. Dry-run mode<br>3. Audit trail<br>4. Rollback capability |
| **Data Loss** | 1. Database backups (hourly)<br>2. Soft deletes<br>3. Versioning for critical entities<br>4. Point-in-time recovery |
| **Service Disruption** | 1. Graceful degradation<br>2. Offline mode for viewing<br>3. Background sync<br>4. Circuit breakers |
| **Performance Degradation** | 1. Pagination (50 items/page)<br>2. Virtual scrolling for large lists<br>3. Debounced search<br>4. Query optimization<br>5. CDN for static assets |

### 8.3 User Experience Risks

| Risk | Mitigation Strategy |
|------|-------------------|
| **Confusing Navigation** | 1. Breadcrumbs<br>2. Clear active state<br>3. Grouped navigation<br>4. Search functionality |
| **Data Entry Errors** | 1. Inline validation<br>2. Clear error messages<br>3. Auto-save drafts<br>4. Confirmation before submit |
| **Lost Progress** | 1. Form state preservation<br>2. Browser storage backup<br>3. Warning on navigation<br>4. Auto-save every 30s |

---

## Appendix

### A. Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Framework** | React | 18.3 |
| **Language** | TypeScript | 5.8 |
| **Build Tool** | Vite | 5.4 |
| **Router** | React Router | 6.30 |
| **State** | TanStack Query | 5.83 |
| **Forms** | React Hook Form | 7.61 |
| **Validation** | Zod | 3.25 |
| **UI Components** | shadcn/ui | Latest |
| **Styling** | Tailwind CSS | 3.4 |
| **Icons** | Lucide React | 0.462 |
| **Charts** | Recharts | 2.15 |
| **Animations** | Framer Motion | 12.23 |
| **Testing** | Vitest + Playwright | Latest |

### B. File Size Estimates

```
frontend/src/
├── pages/admin/          ~15 KB (13 pages × ~1 KB)
├── components/admin/     ~30 KB (50+ components)
├── contexts/             ~5 KB
├── api/services/         ~10 KB
├── hooks/admin/          ~8 KB
├── types/                ~5 KB
└── data/adminMockData.ts ~20 KB

Total New Code: ~95 KB
```

### C. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Initial Load** | < 2s | Lighthouse |
| **Page Transitions** | < 200ms | Chrome DevTools |
| **Table Rendering** | < 100ms for 50 rows | React Profiler |
| **API Response** | < 500ms (p95) | Network tab |
| **Bundle Size** | < 500 KB (gzipped) | Vite build output |

### D. Browser Support

| Browser | Version |
|---------|---------|
| Chrome | Last 2 versions |
| Firefox | Last 2 versions |
| Safari | Last 2 versions |
| Edge | Last 2 versions |

### E. Accessibility Compliance

- ✅ WCAG 2.1 Level AA
- ✅ Keyboard navigation
- ✅ Screen reader support
- ✅ Focus management
- ✅ ARIA labels
- ✅ Color contrast (4.5:1 minimum)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-16 | System Team | Initial design document |
| 1.1 | 2026-02-16 | System Team | Added Migration Strategy section (Section 9) |

---

**Status**: ✅ Design Complete - Ready for Implementation

**Next Steps**:
1. ✅ Complete migration strategy analysis
2. Begin Phase 1 development (Foundation)
3. Write unit tests alongside implementation
4. Implement feature migrations in parallel
5. Document API integration points

---

**End of Design Document**
