/**
 * Sites Service
 *
 * Handles all site-related API calls including CRUD operations.
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import type {
  Site,
  SiteStatus,
  SiteConfiguration,
  Address,
  GeoLocation,
  PaginatedResponse,
  PaginationParams,
  GridConnectionType,
  DiscoProvider,
} from '../types';

// Mock sites data
const mockSites: Site[] = [
  {
    id: 'site-001',
    organization_id: 'org-001',
    name: 'Home Solar System',
    description: 'Main residential solar installation with battery backup',
    status: 'active' as SiteStatus,
    address: {
      street: '123 Solar Street',
      city: 'Lahore',
      state: 'Punjab',
      postal_code: '54000',
      country: 'Pakistan',
    },
    geo_location: {
      latitude: 31.5204,
      longitude: 74.3587,
    },
    timezone: 'Asia/Karachi',
    configuration: {
      system_capacity_kw: 10,
      panel_count: 20,
      panel_wattage: 500,
      inverter_capacity_kw: 10,
      battery_capacity_kwh: 13.5,
      grid_connection_type: 'hybrid' as GridConnectionType,
      net_metering_enabled: true,
      disco_provider: 'lesco' as DiscoProvider,
      tariff_category: 'residential_protected',
    },
    created_at: '2024-01-01T00:00:00Z',
    updated_at: new Date().toISOString(),
  },
  {
    id: 'site-002',
    organization_id: 'org-001',
    name: 'Office Building',
    description: 'Commercial solar installation',
    status: 'active' as SiteStatus,
    address: {
      street: '456 Business Avenue',
      city: 'Lahore',
      state: 'Punjab',
      postal_code: '54000',
      country: 'Pakistan',
    },
    geo_location: {
      latitude: 31.5497,
      longitude: 74.3436,
    },
    timezone: 'Asia/Karachi',
    configuration: {
      system_capacity_kw: 50,
      panel_count: 100,
      panel_wattage: 500,
      inverter_capacity_kw: 50,
      battery_capacity_kwh: undefined,
      grid_connection_type: 'on_grid' as GridConnectionType,
      net_metering_enabled: true,
      disco_provider: 'lesco' as DiscoProvider,
      tariff_category: 'commercial_a1',
    },
    created_at: '2024-02-01T00:00:00Z',
    updated_at: new Date().toISOString(),
  },
];

interface SiteFilters {
  status?: SiteStatus;
  search?: string;
}

class SitesService {
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
   * List sites with pagination and filters
   */
  async listSites(
    filters?: SiteFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Site>> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PaginatedResponse<Site>>(
          API_ENDPOINTS.sites.list,
          { params: { ...filters, ...pagination } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch sites, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      let filtered = [...mockSites];

      if (filters?.status) {
        filtered = filtered.filter((s) => s.status === filters.status);
      }
      if (filters?.search) {
        const search = filters.search.toLowerCase();
        filtered = filtered.filter(
          (s) =>
            s.name.toLowerCase().includes(search) ||
            s.address.city.toLowerCase().includes(search)
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
   * Get single site by ID
   */
  async getSite(siteId: string): Promise<Site> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<Site>(
          API_ENDPOINTS.sites.byId(siteId)
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch site, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const site = mockSites.find((s) => s.id === siteId);
      if (site) {
        return site;
      }
    }

    throw new Error('Site not found');
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
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const newSite: Site = {
        id: `site-${Date.now()}`,
        organization_id: 'org-001',
        name: data.name,
        description: data.description,
        status: 'active' as SiteStatus,
        address: data.address,
        geo_location: data.geo_location,
        timezone: data.timezone || 'Asia/Karachi',
        configuration: data.configuration,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockSites.push(newSite);
      return { success: true, site: newSite };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Update site
   */
  async updateSite(
    siteId: string,
    data: Partial<Site>
  ): Promise<{ success: boolean; site?: Site; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const index = mockSites.findIndex((s) => s.id === siteId);
      if (index >= 0) {
        mockSites[index] = {
          ...mockSites[index],
          ...data,
          updated_at: new Date().toISOString(),
        };
        return { success: true, site: mockSites[index] };
      }
      return { success: false, error: 'Site not found' };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Delete site
   */
  async deleteSite(siteId: string): Promise<{ success: boolean; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.delete(API_ENDPOINTS.sites.byId(siteId));
        return { success: true };
      } catch (error: unknown) {
        const apiError = error as { message?: string };
        return { success: false, error: apiError.message || 'Failed to delete site' };
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const index = mockSites.findIndex((s) => s.id === siteId);
      if (index >= 0) {
        mockSites.splice(index, 1);
        return { success: true };
      }
      return { success: false, error: 'Site not found' };
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Update site status
   */
  async updateStatus(
    siteId: string,
    status: SiteStatus
  ): Promise<{ success: boolean; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.put(API_ENDPOINTS.sites.status(siteId), { status });
        return { success: true };
      } catch (error: unknown) {
        const apiError = error as { message?: string };
        return { success: false, error: apiError.message || 'Failed to update status' };
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const site = mockSites.find((s) => s.id === siteId);
      if (site) {
        site.status = status;
        return { success: true };
      }
      return { success: false, error: 'Site not found' };
    }

    return { success: false, error: 'API unavailable' };
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
