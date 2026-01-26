/**
 * Organizations Service
 *
 * Handles all organization management API calls including CRUD, member management,
 * and invitations.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  Organization,
  OrganizationMember,
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

class OrganizationsService {
  /**
   * List organizations (user's organizations)
   */
  async listOrganizations(
    filters?: OrganizationFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Organization>> {
    const response = await apiClient.get<PaginatedResponse<Organization>>(
      API_ENDPOINTS.organizations.list,
      { params: { ...filters, ...pagination } }
    );
    return response.data;
  }

  /**
   * Get organization by ID
   */
  async getOrganization(orgId: string): Promise<Organization> {
    const response = await apiClient.get<Organization>(
      API_ENDPOINTS.organizations.byId(orgId)
    );
    return response.data;
  }

  /**
   * Create a new organization
   */
  async createOrganization(data: {
    name: string;
    description?: string;
  }): Promise<Organization> {
    const response = await apiClient.post<Organization>(
      API_ENDPOINTS.organizations.create,
      data
    );
    return response.data;
  }

  /**
   * Update organization
   */
  async updateOrganization(
    orgId: string,
    updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>
  ): Promise<Organization> {
    const response = await apiClient.patch<Organization>(
      API_ENDPOINTS.organizations.byId(orgId),
      updates
    );
    return response.data;
  }

  /**
   * Delete organization (owner only)
   */
  async deleteOrganization(orgId: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.organizations.byId(orgId));
  }

  /**
   * Get organization members
   */
  async getMembers(orgId: string): Promise<OrganizationMember[]> {
    const response = await apiClient.get<OrganizationMember[]>(
      API_ENDPOINTS.organizations.members(orgId)
    );
    return response.data;
  }

  /**
   * Invite a user to the organization
   */
  async inviteMember(orgId: string, invite: InviteRequest): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post<{ success: boolean; message: string }>(
      API_ENDPOINTS.organizations.invite(orgId),
      invite
    );
    return response.data;
  }

  /**
   * Update member role
   */
  async updateMemberRole(orgId: string, userId: string, role: UserRole): Promise<OrganizationMember> {
    const response = await apiClient.put<OrganizationMember>(
      API_ENDPOINTS.organizations.memberRole(orgId, userId),
      { role }
    );
    return response.data;
  }

  /**
   * Remove member from organization
   */
  async removeMember(orgId: string, userId: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.organizations.removeMember(orgId, userId));
  }

  /**
   * Transfer organization ownership
   */
  async transferOwnership(orgId: string, newOwnerId: string): Promise<Organization> {
    const response = await apiClient.post<Organization>(
      API_ENDPOINTS.organizations.transferOwnership(orgId),
      { new_owner_id: newOwnerId }
    );
    return response.data;
  }
}

export const organizationsService = new OrganizationsService();
export default organizationsService;
