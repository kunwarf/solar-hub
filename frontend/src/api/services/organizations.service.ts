/**
 * Organizations Service
 *
 * Handles all organization management API calls including CRUD, member management,
 * and invitations. Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import type {
  Organization,
  OrganizationSettings,
  OrganizationMember,
  User,
  UserRole,
  PaginatedResponse,
  PaginationParams,
} from '../types';

// Organization filters
export interface OrganizationFilters {
  status?: 'active' | 'inactive';
  search?: string;
}

// Invite request
export interface InviteRequest {
  email: string;
  role: UserRole;
  message?: string;
}

// Mock organizations data
const mockOrganizations: Organization[] = [
  {
    id: 'org-001',
    name: 'Solar Hub Pakistan',
    slug: 'solar-hub-pk',
    description: 'Pakistan\'s leading solar monitoring platform',
    owner_id: 'user-001',
    status: 'active',
    settings: {
      max_sites: 100,
      max_users: 50,
      alert_email_enabled: true,
      alert_sms_enabled: true,
    },
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 'org-002',
    name: 'Green Energy Solutions',
    slug: 'green-energy',
    description: 'Sustainable energy for a better tomorrow',
    owner_id: 'user-003',
    status: 'active',
    settings: {
      max_sites: 25,
      max_users: 10,
      alert_email_enabled: true,
      alert_sms_enabled: false,
    },
    created_at: '2024-01-05T00:00:00Z',
    updated_at: '2024-01-10T14:30:00Z',
  },
];

// Mock organization members
const mockMembers: Map<string, OrganizationMember[]> = new Map([
  [
    'org-001',
    [
      {
        user_id: 'user-001',
        organization_id: 'org-001',
        role: 'owner' as UserRole,
        joined_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-001',
          email: 'john.doe@example.com',
          first_name: 'John',
          last_name: 'Doe',
          role: 'owner' as UserRole,
          status: 'active' as const,
          is_verified: true,
          preferences: {
            timezone: 'Asia/Karachi',
            language: 'en',
            currency: 'PKR',
            date_format: 'DD/MM/YYYY',
            dark_mode: true,
            notifications_enabled: true,
            email_notifications: true,
            sms_notifications: false,
          },
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-15T10:00:00Z',
        },
      },
      {
        user_id: 'user-002',
        organization_id: 'org-001',
        role: 'admin' as UserRole,
        joined_at: '2024-01-02T00:00:00Z',
        user: {
          id: 'user-002',
          email: 'admin@solarhub.pk',
          first_name: 'Admin',
          last_name: 'User',
          role: 'admin' as UserRole,
          status: 'active' as const,
          is_verified: true,
          preferences: {
            timezone: 'Asia/Karachi',
            language: 'en',
            currency: 'PKR',
            date_format: 'DD/MM/YYYY',
            dark_mode: false,
            notifications_enabled: true,
            email_notifications: true,
            sms_notifications: true,
          },
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-10T08:30:00Z',
        },
      },
      {
        user_id: 'user-003',
        organization_id: 'org-001',
        role: 'manager' as UserRole,
        joined_at: '2024-01-05T00:00:00Z',
        user: {
          id: 'user-003',
          email: 'manager@solarhub.pk',
          first_name: 'Site',
          last_name: 'Manager',
          role: 'manager' as UserRole,
          status: 'active' as const,
          is_verified: true,
          preferences: {
            timezone: 'Asia/Karachi',
            language: 'en',
            currency: 'PKR',
            date_format: 'DD/MM/YYYY',
            dark_mode: true,
            notifications_enabled: true,
            email_notifications: true,
            sms_notifications: false,
          },
          created_at: '2024-01-05T00:00:00Z',
          updated_at: '2024-01-14T15:20:00Z',
        },
      },
    ],
  ],
  [
    'org-002',
    [
      {
        user_id: 'user-003',
        organization_id: 'org-002',
        role: 'owner' as UserRole,
        joined_at: '2024-01-05T00:00:00Z',
        user: {
          id: 'user-003',
          email: 'manager@solarhub.pk',
          first_name: 'Site',
          last_name: 'Manager',
          role: 'owner' as UserRole,
          status: 'active' as const,
          is_verified: true,
          preferences: {
            timezone: 'Asia/Karachi',
            language: 'en',
            currency: 'PKR',
            date_format: 'DD/MM/YYYY',
            dark_mode: true,
            notifications_enabled: true,
            email_notifications: true,
            sms_notifications: false,
          },
          created_at: '2024-01-05T00:00:00Z',
          updated_at: '2024-01-14T15:20:00Z',
        },
      },
    ],
  ],
]);

class OrganizationsService {
  private apiAvailable: boolean | null = null;

  private async isApiAvailable(): Promise<boolean> {
    if (this.apiAvailable !== null) {
      return this.apiAvailable;
    }
    this.apiAvailable = await checkApiHealth();
    setTimeout(() => {
      this.apiAvailable = null;
    }, 30000);
    return this.apiAvailable;
  }

  /**
   * List organizations (user's organizations)
   */
  async listOrganizations(
    filters?: OrganizationFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Organization>> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PaginatedResponse<Organization>>(
          API_ENDPOINTS.organizations.list,
          { params: { ...filters, ...pagination } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch organizations, using mock data:', error);
      }
    }

    // Mock fallback with filtering
    if (API_CONFIG.useMockFallback) {
      let filtered = [...mockOrganizations];

      if (filters?.status) {
        filtered = filtered.filter(o => o.status === filters.status);
      }
      if (filters?.search) {
        const search = filters.search.toLowerCase();
        filtered = filtered.filter(o =>
          o.name.toLowerCase().includes(search) ||
          o.description?.toLowerCase().includes(search)
        );
      }

      const page = pagination?.page || 1;
      const pageSize = pagination?.page_size || 20;
      const start = (page - 1) * pageSize;
      const items = filtered.slice(start, start + pageSize);

      return {
        items,
        total: filtered.length,
        page,
        page_size: pageSize,
        pages: Math.ceil(filtered.length / pageSize),
      };
    }

    throw new Error('API unavailable');
  }

  /**
   * Get organization by ID
   */
  async getOrganization(orgId: string): Promise<Organization> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<Organization>(
          API_ENDPOINTS.organizations.byId(orgId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch organization, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const org = mockOrganizations.find(o => o.id === orgId);
      if (org) return org;
      throw new Error('Organization not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Create a new organization
   */
  async createOrganization(data: {
    name: string;
    description?: string;
  }): Promise<Organization> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<Organization>(
          API_ENDPOINTS.organizations.create,
          data
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to create organization via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const newOrg: Organization = {
        id: `org-${Date.now()}`,
        name: data.name,
        slug: data.name.toLowerCase().replace(/\s+/g, '-'),
        description: data.description,
        owner_id: 'user-001', // Current user
        status: 'active',
        settings: {
          max_sites: 10,
          max_users: 5,
          alert_email_enabled: true,
          alert_sms_enabled: false,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockOrganizations.push(newOrg);
      return newOrg;
    }

    throw new Error('API unavailable');
  }

  /**
   * Update organization
   */
  async updateOrganization(
    orgId: string,
    updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>
  ): Promise<Organization> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.patch<Organization>(
          API_ENDPOINTS.organizations.byId(orgId),
          updates
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to update organization via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const orgIndex = mockOrganizations.findIndex(o => o.id === orgId);
      if (orgIndex >= 0) {
        mockOrganizations[orgIndex] = {
          ...mockOrganizations[orgIndex],
          ...updates,
          updated_at: new Date().toISOString(),
        };
        return mockOrganizations[orgIndex];
      }
      throw new Error('Organization not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Delete organization (owner only)
   */
  async deleteOrganization(orgId: string): Promise<void> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.delete(API_ENDPOINTS.organizations.byId(orgId));
        return;
      } catch (error) {
        console.warn('Failed to delete organization via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const orgIndex = mockOrganizations.findIndex(o => o.id === orgId);
      if (orgIndex >= 0) {
        mockOrganizations.splice(orgIndex, 1);
        return;
      }
      throw new Error('Organization not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Get organization members
   */
  async getMembers(orgId: string): Promise<OrganizationMember[]> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<OrganizationMember[]>(
          API_ENDPOINTS.organizations.members(orgId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch members, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return mockMembers.get(orgId) || [];
    }

    throw new Error('API unavailable');
  }

  /**
   * Invite a user to the organization
   */
  async inviteMember(orgId: string, invite: InviteRequest): Promise<{ success: boolean; message: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<{ success: boolean; message: string }>(
          API_ENDPOINTS.organizations.invite(orgId),
          invite
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to invite member via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return {
        success: true,
        message: `Invitation sent to ${invite.email}`,
      };
    }

    throw new Error('API unavailable');
  }

  /**
   * Update member role
   */
  async updateMemberRole(orgId: string, userId: string, role: UserRole): Promise<OrganizationMember> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.put<OrganizationMember>(
          API_ENDPOINTS.organizations.memberRole(orgId, userId),
          { role }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to update member role via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const members = mockMembers.get(orgId);
      if (members) {
        const memberIndex = members.findIndex(m => m.user_id === userId);
        if (memberIndex >= 0) {
          members[memberIndex] = {
            ...members[memberIndex],
            role,
          };
          return members[memberIndex];
        }
      }
      throw new Error('Member not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Remove member from organization
   */
  async removeMember(orgId: string, userId: string): Promise<void> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.delete(API_ENDPOINTS.organizations.removeMember(orgId, userId));
        return;
      } catch (error) {
        console.warn('Failed to remove member via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const members = mockMembers.get(orgId);
      if (members) {
        const memberIndex = members.findIndex(m => m.user_id === userId);
        if (memberIndex >= 0) {
          members.splice(memberIndex, 1);
          return;
        }
      }
      throw new Error('Member not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Transfer organization ownership
   */
  async transferOwnership(orgId: string, newOwnerId: string): Promise<Organization> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.post<Organization>(
          API_ENDPOINTS.organizations.transferOwnership(orgId),
          { new_owner_id: newOwnerId }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to transfer ownership via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const orgIndex = mockOrganizations.findIndex(o => o.id === orgId);
      if (orgIndex >= 0) {
        mockOrganizations[orgIndex] = {
          ...mockOrganizations[orgIndex],
          owner_id: newOwnerId,
          updated_at: new Date().toISOString(),
        };
        return mockOrganizations[orgIndex];
      }
      throw new Error('Organization not found');
    }

    throw new Error('API unavailable');
  }
}

export const organizationsService = new OrganizationsService();
export default organizationsService;
