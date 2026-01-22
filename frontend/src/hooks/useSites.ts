/**
 * useSites Hook
 *
 * Provides site data from the API with loading and error states.
 * Falls back to mock data when API is unavailable.
 */

import { useState, useEffect, useCallback, createContext, useContext, ReactNode, useMemo } from 'react';
import { sitesService } from '@/api';
import type { Site, SiteStatus, PaginationParams } from '@/api/types';

interface SiteFilters {
  status?: SiteStatus;
  search?: string;
}

interface UseSitesOptions {
  filters?: SiteFilters;
  pagination?: PaginationParams;
}

interface UseSitesReturn {
  sites: Site[];
  total: number;
  page: number;
  pages: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setFilters: (filters: SiteFilters) => void;
  setPage: (page: number) => void;
}

export function useSites(options: UseSitesOptions = {}): UseSitesReturn {
  const {
    filters: initialFilters = {},
    pagination: initialPagination = { page: 1, page_size: 20 },
  } = options;

  const [sites, setSites] = useState<Site[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPageState] = useState(initialPagination.page || 1);
  const [pages, setPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<SiteFilters>(initialFilters);

  const fetchSites = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await sitesService.listSites(filters, {
        page,
        page_size: initialPagination.page_size || 20,
      });

      setSites(response.items);
      setTotal(response.total);
      setPages(response.pages);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch sites';
      setError(message);
      console.error('useSites error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filters, page, initialPagination.page_size]);

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  const setFilters = useCallback((newFilters: SiteFilters) => {
    setFiltersState(newFilters);
    setPageState(1);
  }, []);

  const setPage = useCallback((newPage: number) => {
    setPageState(newPage);
  }, []);

  return {
    sites,
    total,
    page,
    pages,
    isLoading,
    error,
    refresh: fetchSites,
    setFilters,
    setPage,
  };
}

/**
 * Hook to get a single site by ID
 */
export function useSite(siteId: string | null) {
  const [site, setSite] = useState<Site | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSite = useCallback(async () => {
    if (!siteId) {
      setSite(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await sitesService.getSite(siteId);
      setSite(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch site';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [siteId]);

  useEffect(() => {
    fetchSite();
  }, [fetchSite]);

  return { site, isLoading, error, refresh: fetchSite };
}

// ============= Site Context =============
// Provides the currently selected site throughout the app

interface SiteContextType {
  currentSite: Site | null;
  isLoading: boolean;
  error: string | null;
  setCurrentSite: (site: Site | null) => void;
  selectSiteById: (siteId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const SiteContext = createContext<SiteContextType | undefined>(undefined);

interface SiteProviderProps {
  children: ReactNode;
  defaultSiteId?: string;
}

export function SiteProvider({ children, defaultSiteId }: SiteProviderProps) {
  const [currentSite, setCurrentSite] = useState<Site | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDefaultSite = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      if (defaultSiteId) {
        const site = await sitesService.getSite(defaultSiteId);
        setCurrentSite(site);
      } else {
        const site = await sitesService.getDefaultSite();
        setCurrentSite(site);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch site';
      setError(message);
      console.error('SiteProvider error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [defaultSiteId]);

  useEffect(() => {
    fetchDefaultSite();
  }, [fetchDefaultSite]);

  const selectSiteById = useCallback(async (siteId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const site = await sitesService.getSite(siteId);
      setCurrentSite(site);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch site';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      currentSite,
      isLoading,
      error,
      setCurrentSite,
      selectSiteById,
      refresh: fetchDefaultSite,
    }),
    [currentSite, isLoading, error, selectSiteById, fetchDefaultSite]
  );

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useCurrentSite() {
  const context = useContext(SiteContext);
  if (!context) {
    throw new Error('useCurrentSite must be used within a SiteProvider');
  }
  return context;
}
