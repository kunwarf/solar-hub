# Admin Feature Migration Guide

**Date**: 2026-02-16
**Status**: Implementation Guide
**Version**: 1.0

---

## Overview

This document provides step-by-step guidance for migrating existing user-facing admin features to the new admin portal and implementing proper access control.

## Migration Status

### ✅ Completed

1. **Admin Portal Infrastructure**
   - AdminAuthContext with role-based permissions
   - AdminLayout with sidebar navigation
   - AdminGuard for route protection
   - 13 admin pages fully implemented

2. **Configuration Management (Admin-Only)**
   - Electricity Providers CRUD (`/admin/providers`)
   - Tariff Management CRUD (`/admin/tariffs`)
   - Load Shedding Schedules (`/admin/load-shedding`)
   - Audit Log (`/admin/audit-log`)

3. **OTA Firmware Management (Admin-Only)**
   - Firmware Versions (`/admin/firmware-versions`)
   - Update Campaigns (`/admin/ota-campaigns`)
   - Device status monitoring

4. **API Integration Layer**
   - Complete admin API service (System A)
   - Complete firmware API service (System B)
   - React Query hooks for all entities

### 🚧 Requires Backend Implementation

The following features require backend API updates before full migration:

1. **Organization Scoping** - User Management
2. **System-Wide Settings** - Admin configuration
3. **Provider/Tariff Selection** - Link to admin-managed data

---

## Feature-by-Feature Migration

### 1. Tariff Settings (`/settings/tariff`)

**Current State**: User-facing page with DISCO and tariff selection

**Migration Strategy**: **Keep as-is** (mostly complete)

**What's Already Done**:
- Admin can manage providers at `/admin/providers`
- Admin can manage tariffs at `/admin/tariffs`
- User page allows selection from existing providers/tariffs

**What Needs Backend Support**:
```typescript
// Instead of static DISCO_LIST, fetch from admin API
const { data: providers } = useQuery({
  queryKey: ['providers'],
  queryFn: () => api.get('/admin/providers'),
});

// Instead of static tariff slabs, fetch from admin API
const { data: tariffs } = useQuery({
  queryKey: ['tariffs', config.disco],
  queryFn: () => api.get(`/admin/tariffs?providerId=${config.disco}`),
});
```

**User Experience**:
- Users see dropdown of admin-configured DISCOs
- Users see dropdown of admin-configured tariff plans
- Users can still use bill calculator
- No CRUD operations for users

**Admin Experience**:
- Admins manage DISCOs at `/admin/providers`
- Admins manage tariffs at `/admin/tariffs`
- Changes immediately available to users

**Backend Changes Needed**:
1. Create `GET /api/v1/providers` (public read-only)
2. Create `GET /api/v1/tariffs` (public read-only)
3. Filter tariffs by provider
4. Return tariff structure for bill calculation

**Example Backend Response**:
```json
// GET /api/v1/providers
[
  {
    "id": "p1",
    "name": "Lahore Electric Supply Company",
    "shortName": "LESCO",
    "region": "Punjab"
  }
]

// GET /api/v1/tariffs?providerId=p1
[
  {
    "id": "t1",
    "providerId": "p1",
    "name": "Residential Unprotected",
    "category": "residential",
    "type": "slab",
    "rates": {
      "slabs": [
        { "minUnits": 0, "maxUnits": 100, "ratePerKwh": 7.74 },
        { "minUnits": 101, "maxUnits": 200, "ratePerKwh": 11.50 }
      ]
    },
    "fixedCharges": 150
  }
]
```

---

### 2. User Management (`/settings/users`)

**Current State**: Team management with roles and invitations

**Migration Strategy**: **Dual Access Model**

**Admin Version** (`/admin/users` - CREATED ✅):
- View all users across all organizations
- Manage admin roles (super_admin, ops_admin, etc.)
- Suspend/activate accounts globally
- View cross-organization activity

**User Version** (`/settings/users` - EXISTS ✅):
- View users in their organization only
- Invite users to their organization
- Manage roles within organization
- Organization owners can remove users

**What Needs Backend Support**:
```typescript
// In UserManagement.tsx, add organization filter
const { data: users } = useQuery({
  queryKey: ['users', { organizationId: currentUser.organizationId }],
  queryFn: () => usersService.listUsers({
    organizationId: currentUser.organizationId  // Scope to org
  }),
});

// In AdminUsers.tsx, fetch all users
const { data: allUsers } = useQuery({
  queryKey: ['admin', 'users'],
  queryFn: () => adminUsersService.list(),  // No org filter
});
```

**Backend Changes Needed**:
1. Add `organizationId` filter to `GET /api/v1/users`
2. Add `GET /api/v1/admin/users` (no org filter, admin-only)
3. Enforce organization scope in user invite API
4. Add admin role management endpoints

**Permission Matrix**:
| Action | Organization Owner | Admin (ops_admin) | Admin (super_admin) |
|--------|-------------------|-------------------|---------------------|
| View own org users | ✅ | ❌ | ✅ |
| View all users | ❌ | ❌ | ✅ |
| Invite to org | ✅ | ❌ | ✅ |
| Manage org roles | ✅ | ❌ | ✅ |
| Manage admin roles | ❌ | ❌ | ✅ |
| Suspend accounts | ❌ | ❌ | ✅ |

---

### 3. Settings (`/settings`)

**Current State**: Mixed user preferences and system configuration

**Migration Strategy**: **Split Configuration**

**Admin System Settings** (CREATE NEW PAGE):
Location: `/admin/system-settings`

**Features to Move to Admin**:
```typescript
// System-wide MQTT Configuration
interface SystemMqttConfig {
  defaultBrokerUrl: string;
  defaultPort: number;
  systemCredentials: {
    username: string;
    password: string;
  };
  tlsEnabled: boolean;
  caCertificate?: string;
}

// System-wide Location Defaults
interface SystemDefaults {
  timezone: string;           // "Asia/Karachi"
  currency: string;           // "PKR"
  dateFormat: string;         // "DD/MM/YYYY"
  defaultLatitude: number;    // 31.5204
  defaultLongitude: number;   // 74.3587
}

// Global Hierarchy Templates
interface HierarchyTemplate {
  id: string;
  name: string;
  deviceTypes: string[];
  defaultArrays: {
    inverters: number;
    batteries: number;
  };
}
```

**User Settings** (KEEP IN `/settings`):
```typescript
// Personal Preferences
interface UserPreferences {
  userMode: "simple" | "advanced";
  theme: "light" | "dark" | "system";
  notificationEmail: boolean;
  notificationPush: boolean;
  language: string;
}

// Site-Specific Settings
interface SiteSettings {
  siteId: string;
  locationOverride?: {
    latitude: number;
    longitude: number;
  };
  timezoneOverride?: string;
  customMqtt?: {
    enabled: boolean;
    brokerUrl: string;
    port: number;
  };
}
```

**Backend Changes Needed**:
1. Create `GET/PUT /api/v1/admin/system-settings`
2. Create `GET/PUT /api/v1/users/me/preferences`
3. Create `GET/PUT /api/v1/sites/{id}/settings`
4. Separate system-wide from user-specific config

**UI Changes**:
```typescript
// In Settings.tsx, remove system-wide settings
// Add link to admin portal
{hasPermission('manage_system') && (
  <Card>
    <CardHeader>
      <CardTitle>System Settings</CardTitle>
      <CardDescription>
        Configure system-wide settings (admin only)
      </CardDescription>
    </CardHeader>
    <CardContent>
      <Button asChild>
        <Link to="/admin/system-settings">
          <Settings className="mr-2 h-4 w-4" />
          Open Admin Settings
        </Link>
      </Button>
    </CardContent>
  </Card>
)}
```

---

## Backend API Requirements Summary

### New Endpoints Needed

**System A (Port 8000):**

1. **Public Provider/Tariff APIs** (for user selection)
   ```
   GET  /api/v1/providers
   GET  /api/v1/tariffs?providerId={id}
   ```

2. **Admin User Management** (already designed)
   ```
   GET    /api/v1/admin/users
   POST   /api/v1/admin/users
   PUT    /api/v1/admin/users/{id}
   DELETE /api/v1/admin/users/{id}
   ```

3. **Admin Authentication**
   ```
   POST /api/v1/admin/auth/login
   POST /api/v1/admin/auth/logout
   GET  /api/v1/admin/auth/me
   ```

4. **System Settings**
   ```
   GET /api/v1/admin/system-settings
   PUT /api/v1/admin/system-settings
   ```

5. **Organization-Scoped Users**
   ```
   GET /api/v1/users?organizationId={id}
   ```

**System B (Port 8001):**

All firmware endpoints already designed in `firmware.service.ts`.

---

## Implementation Checklist

### Phase 1: Backend Preparation
- [ ] Implement admin authentication endpoints
- [ ] Add admin role to user model
- [ ] Create admin permission middleware
- [ ] Implement admin CRUD endpoints for all entities
- [ ] Add organization scoping to user endpoints
- [ ] Create public read-only provider/tariff endpoints
- [ ] Implement system settings endpoints

### Phase 2: Frontend Integration
- [ ] Update TariffSettings to fetch from admin APIs
- [ ] Add organization filter to UserManagement
- [ ] Create AdminSystemSettings page
- [ ] Update Settings to remove system config
- [ ] Test permission checks
- [ ] Test data flow from admin to users

### Phase 3: Data Migration
- [ ] Export existing DISCO_LIST to database
- [ ] Export existing tariff structures to database
- [ ] Assign initial admin roles
- [ ] Test backward compatibility
- [ ] Verify billing calculations

### Phase 4: Testing
- [ ] Test admin CRUD operations
- [ ] Test organization scoping
- [ ] Test permission enforcement
- [ ] Test user experience (selection from admin data)
- [ ] Test audit logging
- [ ] E2E tests for critical flows

---

## Testing Scenarios

### Scenario 1: Admin Creates New Provider
1. Admin logs in to `/admin/login`
2. Navigates to `/admin/providers`
3. Clicks "Add Provider"
4. Fills form: Name="GEPCO", Region="Punjab"
5. Saves provider
6. **Expected**: Provider immediately appears in user TariffSettings dropdown

### Scenario 2: Organization Owner Manages Team
1. Org owner logs in
2. Navigates to `/settings/users`
3. Clicks "Invite User"
4. Sends invitation
5. **Expected**: Only sees users in their organization
6. **Expected**: Cannot see users from other organizations

### Scenario 3: Super Admin Views All Users
1. Super admin logs in to admin portal
2. Navigates to `/admin/users`
3. **Expected**: Sees users from ALL organizations
4. **Expected**: Can filter by organization
5. **Expected**: Can manage admin roles

### Scenario 4: User Selects Tariff
1. User navigates to `/settings/tariff`
2. Selects DISCO from dropdown
3. **Expected**: Sees only admin-configured DISCOs
4. Selects tariff plan
5. **Expected**: Sees only admin-configured tariffs
6. Uses bill calculator
7. **Expected**: Calculation uses admin-configured rates

---

## Backward Compatibility

### Ensuring Zero Downtime

1. **Dual Data Source** (temporary):
   ```typescript
   // Fallback to static data if API fails
   const { data: providers } = useQuery({
     queryKey: ['providers'],
     queryFn: fetchProviders,
   });

   const providerList = providers || DISCO_LIST; // Fallback
   ```

2. **Feature Flags**:
   ```typescript
   const USE_ADMIN_API = import.meta.env.VITE_USE_ADMIN_API === 'true';

   const providers = USE_ADMIN_API
     ? await fetchProvidersFromAPI()
     : DISCO_LIST;
   ```

3. **Gradual Rollout**:
   - Phase 1: Admin portal accessible, but users still use static data
   - Phase 2: Backend APIs ready, frontend switches to API
   - Phase 3: Remove static data fallbacks

---

## Security Considerations

### Admin Portal Security

1. **Authentication**
   - Separate admin login at `/admin/login`
   - Admin tokens stored separately
   - Admin sessions have shorter timeout (1 hour)

2. **Authorization**
   - Permission checks on every admin route
   - API-level permission validation
   - Audit log for all admin actions

3. **Data Access**
   - Regular users cannot access `/admin/*` routes
   - Regular users cannot call admin APIs
   - Organization owners scoped to their org only
   - Super admins can see all data

### Permission Enforcement

```typescript
// Frontend (AdminGuard)
<Route
  path="/admin/providers"
  element={
    <AdminGuard requiredPermission="manage_providers">
      <ElectricityProviders />
    </AdminGuard>
  }
/>

// Backend (FastAPI)
@router.get("/admin/providers")
async def list_providers(
    current_user: User = Depends(get_current_admin_user),
    _: None = Depends(require_permission("manage_providers"))
):
    return await provider_service.list_all()
```

---

## Next Steps

### Immediate (Backend Team)
1. Review admin API requirements
2. Implement admin authentication
3. Create admin endpoints for providers/tariffs
4. Add organization scoping to user endpoints
5. Deploy to staging

### Once Backend Ready (Frontend Team)
1. Update TariffSettings to use admin APIs
2. Add org scoping to UserManagement
3. Create AdminSystemSettings page
4. Test integration end-to-end
5. Deploy to production

### Future Enhancements
1. Real-time notifications when admin changes data
2. Admin dashboard with usage analytics
3. Bulk operations for admin
4. Import/export functionality
5. Admin API documentation

---

## Support

For questions or issues with migration:
- Frontend: Check `ADMIN_PORTAL_DESIGN.md`
- Backend: Check `DESIGN_OTA_SYSTEM.md`
- API Integration: Check service files in `frontend/src/api/services/`

---

**Document Version**: 1.0
**Last Updated**: 2026-02-16
**Status**: Ready for Backend Implementation
