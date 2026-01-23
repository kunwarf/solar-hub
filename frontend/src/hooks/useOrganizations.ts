/**
 * Organizations Hooks
 *
 * Custom React hooks for managing organization data and operations.
 */

import { useState, useEffect, useCallback, useRef, createContext, useContext, type ReactNode } from 'react';
import {
  organizationsService,
  type OrganizationFilters,
  type InviteRequest,
} from '@/api/services/organizations.service';
import type { Organization, OrganizationMember, UserRole, PaginationParams } from '@/api/types';

export interface UseOrganizationsOptions {
  filters?: OrganizationFilters;
  pagination?: PaginationParams;
}

export interface UseOrganizationsReturn {
  organizations: Organization[];
  total: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createOrganization: (data: { name: string; description?: string }) => Promise<Organization>;
  updateOrganization: (
    orgId: string,
    updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>
  ) => Promise<Organization>;
  deleteOrganization: (orgId: string) => Promise<void>;
}

/**
 * Hook for listing and managing organizations
 */
export function useOrganizations(options: UseOrganizationsOptions = {}): UseOrganizationsReturn {
  const { filters, pagination } = options;

  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchOrganizations = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await organizationsService.listOrganizations(filters, pagination);
      if (mountedRef.current) {
        setOrganizations(response.items);
        setTotal(response.total);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch organizations');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [filters, pagination]);

  const createOrganization = useCallback(
    async (data: { name: string; description?: string }) => {
      const newOrg = await organizationsService.createOrganization(data);
      setOrganizations(prev => [...prev, newOrg]);
      setTotal(prev => prev + 1);
      return newOrg;
    },
    []
  );

  const updateOrganization = useCallback(
    async (
      orgId: string,
      updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>
    ) => {
      const updatedOrg = await organizationsService.updateOrganization(orgId, updates);
      setOrganizations(prev =>
        prev.map(org => (org.id === orgId ? updatedOrg : org))
      );
      return updatedOrg;
    },
    []
  );

  const deleteOrganization = useCallback(async (orgId: string) => {
    await organizationsService.deleteOrganization(orgId);
    setOrganizations(prev => prev.filter(org => org.id !== orgId));
    setTotal(prev => prev - 1);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchOrganizations();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchOrganizations]);

  return {
    organizations,
    total,
    isLoading,
    error,
    refresh: fetchOrganizations,
    createOrganization,
    updateOrganization,
    deleteOrganization,
  };
}

export interface UseOrganizationReturn {
  organization: Organization | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  update: (updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>) => Promise<void>;
}

/**
 * Hook for fetching a single organization
 */
export function useOrganization(orgId: string | null): UseOrganizationReturn {
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchOrganization = useCallback(async () => {
    if (!orgId) {
      setOrganization(null);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const data = await organizationsService.getOrganization(orgId);
      if (mountedRef.current) {
        setOrganization(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch organization');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [orgId]);

  const update = useCallback(
    async (updates: Partial<Pick<Organization, 'name' | 'description' | 'settings'>>) => {
      if (!orgId) return;
      const updatedOrg = await organizationsService.updateOrganization(orgId, updates);
      setOrganization(updatedOrg);
    },
    [orgId]
  );

  useEffect(() => {
    mountedRef.current = true;
    fetchOrganization();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchOrganization]);

  return {
    organization,
    isLoading,
    error,
    refresh: fetchOrganization,
    update,
  };
}

export interface UseOrganizationMembersReturn {
  members: OrganizationMember[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  inviteMember: (invite: InviteRequest) => Promise<{ success: boolean; message: string }>;
  updateMemberRole: (userId: string, role: UserRole) => Promise<void>;
  removeMember: (userId: string) => Promise<void>;
}

/**
 * Hook for managing organization members
 */
export function useOrganizationMembers(orgId: string | null): UseOrganizationMembersReturn {
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchMembers = useCallback(async () => {
    if (!orgId) {
      setMembers([]);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const data = await organizationsService.getMembers(orgId);
      if (mountedRef.current) {
        setMembers(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch members');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [orgId]);

  const inviteMember = useCallback(
    async (invite: InviteRequest) => {
      if (!orgId) throw new Error('No organization selected');
      return await organizationsService.inviteMember(orgId, invite);
    },
    [orgId]
  );

  const updateMemberRole = useCallback(
    async (userId: string, role: UserRole) => {
      if (!orgId) return;
      const updatedMember = await organizationsService.updateMemberRole(orgId, userId, role);
      setMembers(prev =>
        prev.map(member => (member.user_id === userId ? updatedMember : member))
      );
    },
    [orgId]
  );

  const removeMember = useCallback(
    async (userId: string) => {
      if (!orgId) return;
      await organizationsService.removeMember(orgId, userId);
      setMembers(prev => prev.filter(member => member.user_id !== userId));
    },
    [orgId]
  );

  useEffect(() => {
    mountedRef.current = true;
    fetchMembers();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchMembers]);

  return {
    members,
    isLoading,
    error,
    refresh: fetchMembers,
    inviteMember,
    updateMemberRole,
    removeMember,
  };
}

// Organization Context for app-wide current organization
interface OrganizationContextType {
  currentOrganization: Organization | null;
  setCurrentOrganization: (org: Organization | null) => void;
  isLoading: boolean;
}

const OrganizationContext = createContext<OrganizationContextType | null>(null);

interface OrganizationProviderProps {
  children: ReactNode;
  defaultOrgId?: string;
}

/**
 * Provider for current organization context
 */
export function OrganizationProvider({ children, defaultOrgId }: OrganizationProviderProps) {
  const [currentOrganization, setCurrentOrganization] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(!!defaultOrgId);

  useEffect(() => {
    if (defaultOrgId) {
      setIsLoading(true);
      organizationsService
        .getOrganization(defaultOrgId)
        .then(setCurrentOrganization)
        .catch(console.error)
        .finally(() => setIsLoading(false));
    }
  }, [defaultOrgId]);

  return (
    <OrganizationContext.Provider
      value={{ currentOrganization, setCurrentOrganization, isLoading }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}

/**
 * Hook to access current organization context
 */
export function useCurrentOrganization() {
  const context = useContext(OrganizationContext);
  if (!context) {
    throw new Error('useCurrentOrganization must be used within an OrganizationProvider');
  }
  return context;
}
