/**
 * Users Hooks
 *
 * Custom React hooks for managing user data and operations.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { usersService, type UserFilters } from '@/api/services/users.service';
import type { User, UserRole, UserStatus, UserPreferences, PaginationParams } from '@/api/types';

export interface UseUsersOptions {
  filters?: UserFilters;
  pagination?: PaginationParams;
}

export interface UseUsersReturn {
  users: User[];
  total: number;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateUserRole: (userId: string, role: UserRole) => Promise<void>;
  updateUserStatus: (userId: string, status: UserStatus) => Promise<void>;
}

/**
 * Hook for listing and managing users (admin only)
 */
export function useUsers(options: UseUsersOptions = {}): UseUsersReturn {
  const { filters, pagination } = options;

  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await usersService.listUsers(filters, pagination);
      if (mountedRef.current) {
        setUsers(response.items);
        setTotal(response.total);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch users');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [filters, pagination]);

  const updateUserRole = useCallback(async (userId: string, role: UserRole) => {
    try {
      const updatedUser = await usersService.updateUserRole(userId, role);
      setUsers(prev =>
        prev.map(user => (user.id === userId ? updatedUser : user))
      );
    } catch (err) {
      throw err;
    }
  }, []);

  const updateUserStatus = useCallback(async (userId: string, status: UserStatus) => {
    try {
      const updatedUser = await usersService.updateUserStatus(userId, status);
      setUsers(prev =>
        prev.map(user => (user.id === userId ? updatedUser : user))
      );
    } catch (err) {
      throw err;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchUsers();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchUsers]);

  return {
    users,
    total,
    isLoading,
    error,
    refresh: fetchUsers,
    updateUserRole,
    updateUserStatus,
  };
}

export interface UseUserProfileReturn {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateProfile: (updates: Partial<Pick<User, 'first_name' | 'last_name' | 'phone'>>) => Promise<void>;
  updatePreferences: (preferences: Partial<UserPreferences>) => Promise<void>;
}

/**
 * Hook for managing current user's profile
 */
export function useUserProfile(): UseUserProfileReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const profile = await usersService.getProfile();
      if (mountedRef.current) {
        setUser(profile);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch profile');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const updateProfile = useCallback(
    async (updates: Partial<Pick<User, 'first_name' | 'last_name' | 'phone'>>) => {
      try {
        const updatedUser = await usersService.updateProfile(updates);
        setUser(updatedUser);
      } catch (err) {
        throw err;
      }
    },
    []
  );

  const updatePreferences = useCallback(async (preferences: Partial<UserPreferences>) => {
    try {
      const updatedUser = await usersService.updatePreferences(preferences);
      setUser(updatedUser);
    } catch (err) {
      throw err;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchProfile();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchProfile]);

  return {
    user,
    isLoading,
    error,
    refresh: fetchProfile,
    updateProfile,
    updatePreferences,
  };
}

/**
 * Hook for fetching a single user by ID
 */
export function useUser(userId: string | null) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchUser = useCallback(async () => {
    if (!userId) {
      setUser(null);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const data = await usersService.getUser(userId);
      if (mountedRef.current) {
        setUser(data);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch user');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [userId]);

  useEffect(() => {
    mountedRef.current = true;
    fetchUser();

    return () => {
      mountedRef.current = false;
    };
  }, [fetchUser]);

  return {
    user,
    isLoading,
    error,
    refresh: fetchUser,
  };
}
