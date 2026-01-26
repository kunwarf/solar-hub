/**
 * Sites Service
 *
 * Handles all site-related API calls including CRUD operations.
 */

import apiClient from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  Site,
  SiteStatus,
  SiteConfiguration,
  Address,
  GeoLocation,
  PaginatedResponse,
  PaginationParams,
} from '../types';

interface SiteFilters {
  status?: SiteStatus;
  search?: string;
}

class SitesService {
  /**
   * List sites with pagination and filters
   */
  async listSites(
    filters?: SiteFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Site>> {
    const response = await apiClient.get<PaginatedResponse<Site>>(
      API_ENDPOINTS.sites.list,
      { params: { ...filters, ...pagination } }
    );
    return response.data;
  }

  /**
   * Get single site by ID
   */
  async getSite(siteId: string): Promise<Site> {
    const response = await apiClient.get<Site>(
      API_ENDPOINTS.sites.byId(siteId)
    );
    return response.data;
  }

  /**
   * Create new site
   */
  async createSite(data: {
    name: string;
    description?: string;
    address: Address;
    geo_location: GeoLocation;
    timezone?: string;
    configuration: SiteConfiguration;
  }): Promise<{ success: boolean; site?: Site; error?: string }> {
    try {
      const response = await apiClient.post<Site>(
        API_ENDPOINTS.sites.create,
        data
      );
      return { success: true, site: response.data };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to create site' };
    }
  }

  /**
   * Update site
   */
  async updateSite(
    siteId: string,
    data: Partial<Site>
  ): Promise<{ success: boolean; site?: Site; error?: string }> {
    try {
      const response = await apiClient.put<Site>(
        API_ENDPOINTS.sites.byId(siteId),
        data
      );
      return { success: true, site: response.data };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to update site' };
    }
  }

  /**
   * Delete site
   */
  async deleteSite(siteId: string): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.delete(API_ENDPOINTS.sites.byId(siteId));
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to delete site' };
    }
  }

  /**
   * Update site status
   */
  async updateStatus(
    siteId: string,
    status: SiteStatus
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.put(API_ENDPOINTS.sites.status(siteId), { status });
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to update status' };
    }
  }

  /**
   * Get default/primary site
   */
  async getDefaultSite(): Promise<Site | null> {
    try {
      const result = await this.listSites({ status: 'active' as SiteStatus }, { page: 1, page_size: 1 });
      return result.items[0] || null;
    } catch {
      return null;
    }
  }
}

export const sitesService = new SitesService();
export default sitesService;
