/**
 * Users Service
 *
 * Handles all user management API calls (profile updates, user listing, etc.)
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { checkApiHealth } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import type {
  User,
  UserRole,
  UserStatus,
  UserPreferences,
  PaginatedResponse,
  PaginationParams,
} from '../types';

// User filters for API
export interface UserFilters {
  role?: UserRole;
  status?: UserStatus;
  search?: string;
}

// Mock users data
const mockUsers: User[] = [
  {
    id: 'user-001',
    email: 'john.doe@example.com',
    first_name: 'John',
    last_name: 'Doe',
    phone: '+92-300-1234567',
    role: 'owner' as UserRole,
    status: 'active' as UserStatus,
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
  {
    id: 'user-002',
    email: 'admin@solarhub.pk',
    first_name: 'Admin',
    last_name: 'User',
    phone: '+92-300-9876543',
    role: 'admin' as UserRole,
    status: 'active' as UserStatus,
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
  {
    id: 'user-003',
    email: 'manager@solarhub.pk',
    first_name: 'Site',
    last_name: 'Manager',
    phone: '+92-321-5551234',
    role: 'manager' as UserRole,
    status: 'active' as UserStatus,
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
  {
    id: 'user-004',
    email: 'viewer@solarhub.pk',
    first_name: 'Read',
    last_name: 'Only',
    phone: '+92-333-7771234',
    role: 'viewer' as UserRole,
    status: 'active' as UserStatus,
    is_verified: true,
    preferences: {
      timezone: 'Asia/Karachi',
      language: 'en',
      currency: 'PKR',
      date_format: 'DD/MM/YYYY',
      dark_mode: false,
      notifications_enabled: false,
      email_notifications: false,
      sms_notifications: false,
    },
    created_at: '2024-01-08T00:00:00Z',
    updated_at: '2024-01-08T00:00:00Z',
  },
  {
    id: 'user-005',
    email: 'installer@solarhub.pk',
    first_name: 'Solar',
    last_name: 'Installer',
    phone: '+92-345-1112233',
    role: 'installer' as UserRole,
    status: 'active' as UserStatus,
    is_verified: true,
    preferences: {
      timezone: 'Asia/Karachi',
      language: 'en',
      currency: 'PKR',
      date_format: 'DD/MM/YYYY',
      dark_mode: true,
      notifications_enabled: true,
      email_notifications: true,
      sms_notifications: true,
    },
    created_at: '2024-01-10T00:00:00Z',
    updated_at: '2024-01-12T09:00:00Z',
  },
  {
    id: 'user-006',
    email: 'pending@solarhub.pk',
    first_name: 'Pending',
    last_name: 'User',
    phone: '+92-312-4445566',
    role: 'viewer' as UserRole,
    status: 'pending' as UserStatus,
    is_verified: false,
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
    created_at: '2024-01-14T00:00:00Z',
    updated_at: '2024-01-14T00:00:00Z',
  },
];

class UsersService {
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
   * Get current user profile
   */
  async getProfile(): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<User>(API_ENDPOINTS.users.me);
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch user profile, using cached data:', error);
      }
    }

    // Mock fallback - return first mock user as current user
    if (API_CONFIG.useMockFallback) {
      const cachedUser = localStorage.getItem(API_CONFIG.tokenKeys.user);
      if (cachedUser) {
        return JSON.parse(cachedUser);
      }
      return mockUsers[0];
    }

    throw new Error('API unavailable');
  }

  /**
   * Update user profile
   */
  async updateProfile(updates: Partial<Pick<User, 'first_name' | 'last_name' | 'phone'>>): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.patch<User>(API_ENDPOINTS.users.me, updates);
        // Update local cache
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(response.data));
        return response.data;
      } catch (error) {
        console.warn('Failed to update profile via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const cachedUser = localStorage.getItem(API_CONFIG.tokenKeys.user);
      if (cachedUser) {
        const user = JSON.parse(cachedUser);
        const updatedUser = { ...user, ...updates, updated_at: new Date().toISOString() };
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(updatedUser));
        return updatedUser;
      }
    }

    throw new Error('API unavailable');
  }

  /**
   * Update user preferences
   */
  async updatePreferences(preferences: Partial<UserPreferences>): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.put<User>(API_ENDPOINTS.users.preferences, preferences);
        // Update local cache
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(response.data));
        return response.data;
      } catch (error) {
        console.warn('Failed to update preferences via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const cachedUser = localStorage.getItem(API_CONFIG.tokenKeys.user);
      if (cachedUser) {
        const user = JSON.parse(cachedUser);
        const updatedUser = {
          ...user,
          preferences: { ...user.preferences, ...preferences },
          updated_at: new Date().toISOString(),
        };
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(updatedUser));
        return updatedUser;
      }
    }

    throw new Error('API unavailable');
  }

  /**
   * List all users (admin only)
   */
  async listUsers(
    filters?: UserFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<User>> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<PaginatedResponse<User>>(
          API_ENDPOINTS.users.list,
          { params: { ...filters, ...pagination } }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch users, using mock data:', error);
      }
    }

    // Mock fallback with filtering
    if (API_CONFIG.useMockFallback) {
      let filtered = [...mockUsers];

      if (filters?.role) {
        filtered = filtered.filter(u => u.role === filters.role);
      }
      if (filters?.status) {
        filtered = filtered.filter(u => u.status === filters.status);
      }
      if (filters?.search) {
        const search = filters.search.toLowerCase();
        filtered = filtered.filter(u =>
          u.email.toLowerCase().includes(search) ||
          u.first_name.toLowerCase().includes(search) ||
          u.last_name.toLowerCase().includes(search)
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
   * Get user by ID (admin only)
   */
  async getUser(userId: string): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.get<User>(API_ENDPOINTS.users.byId(userId));
        return response.data;
      } catch (error) {
        console.warn('Failed to fetch user, using mock data:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const user = mockUsers.find(u => u.id === userId);
      if (user) return user;
      throw new Error('User not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Update user role (admin only)
   */
  async updateUserRole(userId: string, role: UserRole): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.put<User>(
          API_ENDPOINTS.users.role(userId),
          { role }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to update user role via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const userIndex = mockUsers.findIndex(u => u.id === userId);
      if (userIndex >= 0) {
        mockUsers[userIndex] = {
          ...mockUsers[userIndex],
          role,
          updated_at: new Date().toISOString(),
        };
        return mockUsers[userIndex];
      }
      throw new Error('User not found');
    }

    throw new Error('API unavailable');
  }

  /**
   * Update user status (admin only)
   */
  async updateUserStatus(userId: string, status: UserStatus): Promise<User> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        const response = await apiClient.put<User>(
          API_ENDPOINTS.users.status(userId),
          { status }
        );
        return response.data;
      } catch (error) {
        console.warn('Failed to update user status via API:', error);
      }
    }

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      const userIndex = mockUsers.findIndex(u => u.id === userId);
      if (userIndex >= 0) {
        mockUsers[userIndex] = {
          ...mockUsers[userIndex],
          status,
          updated_at: new Date().toISOString(),
        };
        return mockUsers[userIndex];
      }
      throw new Error('User not found');
    }

    throw new Error('API unavailable');
  }
}

export const usersService = new UsersService();
export default usersService;
