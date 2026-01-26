/**
 * Authentication Service
 *
 * Handles all authentication-related API calls.
 */

import apiClient, { tokenStorage } from '../client';
import { API_CONFIG, API_ENDPOINTS } from '../config';
import type {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  UserPreferences,
  SiteInfo,
  DeviceClaimInfo,
} from '../types';

class AuthService {
  /**
   * Login user
   */
  async login(credentials: LoginRequest): Promise<{ success: boolean; user?: User; error?: string }> {
    try {
      const response = await apiClient.post<LoginResponse>(
        API_ENDPOINTS.auth.login,
        credentials
      );

      tokenStorage.setTokens({
        access_token: response.data.tokens.access_token,
        refresh_token: response.data.tokens.refresh_token,
        token_type: response.data.tokens.token_type,
        expires_in: response.data.tokens.expires_in,
      });

      localStorage.setItem(
        API_CONFIG.tokenKeys.user,
        JSON.stringify(response.data.user)
      );

      return { success: true, user: response.data.user };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Login failed' };
    }
  }

  /**
   * Register new user
   */
  async register(
    data: RegisterRequest
  ): Promise<{
    success: boolean;
    message?: string;
    user?: User;
    site?: SiteInfo;
    device?: DeviceClaimInfo;
    error?: string;
  }> {
    try {
      const response = await apiClient.post<RegisterResponse>(
        API_ENDPOINTS.auth.register,
        data
      );
      return {
        success: response.data.success,
        message: response.data.message,
        user: response.data.user,
        site: response.data.site,
        device: response.data.device,
      };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Registration failed' };
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      await apiClient.post(API_ENDPOINTS.auth.logout);
    } catch {
      // Ignore logout errors - just clear local storage
    }

    tokenStorage.clearTokens();
  }

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<User | null> {
    // First check local storage
    const storedUser = localStorage.getItem(API_CONFIG.tokenKeys.user);
    if (!storedUser) {
      return null;
    }

    if (tokenStorage.hasValidToken()) {
      try {
        const response = await apiClient.get<User>(API_ENDPOINTS.auth.me);
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(response.data));
        return response.data;
      } catch {
        // If API fails, return cached user
        return JSON.parse(storedUser);
      }
    }

    return JSON.parse(storedUser);
  }

  /**
   * Update user preferences
   */
  async updatePreferences(
    preferences: Partial<UserPreferences>
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.put(API_ENDPOINTS.users.preferences, preferences);
      // Update local storage
      const user = await this.getCurrentUser();
      if (user) {
        user.preferences = { ...user.preferences, ...preferences };
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(user));
      }
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to update preferences' };
    }
  }

  /**
   * Change password
   */
  async changePassword(
    currentPassword: string,
    newPassword: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      await apiClient.post(API_ENDPOINTS.auth.changePassword, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      return { success: true };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to change password' };
    }
  }

  /**
   * Request password reset
   */
  async forgotPassword(email: string): Promise<{ success: boolean; message?: string; error?: string }> {
    try {
      await apiClient.post(API_ENDPOINTS.auth.forgotPassword, { email });
      return { success: true, message: 'Password reset email sent' };
    } catch (error: unknown) {
      const apiError = error as { message?: string };
      return { success: false, error: apiError.message || 'Failed to send reset email' };
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return tokenStorage.hasValidToken();
  }
}

export const authService = new AuthService();
export default authService;
