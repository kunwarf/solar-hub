/**
 * Users Service
 *
 * Handles all user management API calls (profile updates, user listing, etc.)
 */

import apiClient from '../client';
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

class UsersService {
  /**
   * Get current user profile
   */
  async getProfile(): Promise<User> {
    const response = await apiClient.get<User>(API_ENDPOINTS.users.me);
    return response.data;
  }

  /**
   * Update user profile
   */
  async updateProfile(updates: Partial<Pick<User, 'first_name' | 'last_name' | 'phone'>>): Promise<User> {
    const response = await apiClient.patch<User>(API_ENDPOINTS.users.me, updates);
    // Update local cache
    localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(response.data));
    return response.data;
  }

  /**
   * Update user preferences
   */
  async updatePreferences(preferences: Partial<UserPreferences>): Promise<User> {
    const response = await apiClient.put<User>(API_ENDPOINTS.users.preferences, preferences);
    // Update local cache
    localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(response.data));
    return response.data;
  }

  /**
   * List all users (admin only)
   */
  async listUsers(
    filters?: UserFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<User>> {
    const response = await apiClient.get<PaginatedResponse<User>>(
      API_ENDPOINTS.users.list,
      { params: { ...filters, ...pagination } }
    );
    return response.data;
  }

  /**
   * Get user by ID (admin only)
   */
  async getUser(userId: string): Promise<User> {
    const response = await apiClient.get<User>(API_ENDPOINTS.users.byId(userId));
    return response.data;
  }

  /**
   * Update user role (admin only)
   */
  async updateUserRole(userId: string, role: UserRole): Promise<User> {
    const response = await apiClient.put<User>(
      API_ENDPOINTS.users.role(userId),
      { role }
    );
    return response.data;
  }

  /**
   * Update user status (admin only)
   */
  async updateUserStatus(userId: string, status: UserStatus): Promise<User> {
    const response = await apiClient.put<User>(
      API_ENDPOINTS.users.status(userId),
      { status }
    );
    return response.data;
  }
}

export const usersService = new UsersService();
export default usersService;
