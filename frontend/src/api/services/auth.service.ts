/**
 * Authentication Service
 *
 * Handles all authentication-related API calls.
 * Falls back to mock data when API is unavailable.
 */

import apiClient, { tokenStorage, checkApiHealth } from '../client';
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

// Mock data for development/offline mode
const mockUsers: Map<string, { password: string; user: User }> = new Map([
  [
    'demo@example.com',
    {
      password: 'Password123!',
      user: {
        id: 'mock-user-1',
        email: 'demo@example.com',
        first_name: 'John',
        last_name: 'Doe',
        phone: '+92-300-1234567',
        role: 'owner' as const,
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
        updated_at: '2024-01-01T00:00:00Z',
      },
    },
  ],
  [
    'admin@solarhub.pk',
    {
      password: 'Admin123!',
      user: {
        id: 'mock-user-2',
        email: 'admin@solarhub.pk',
        first_name: 'Admin',
        last_name: 'User',
        phone: '+92-300-9876543',
        role: 'admin' as const,
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
        updated_at: '2024-01-01T00:00:00Z',
      },
    },
  ],
]);

class AuthService {
  private apiAvailable: boolean | null = null;

  /**
   * Check if the API is available
   */
  private async isApiAvailable(): Promise<boolean> {
    if (this.apiAvailable !== null) {
      return this.apiAvailable;
    }
    this.apiAvailable = await checkApiHealth();
    // Recheck every 30 seconds
    setTimeout(() => {
      this.apiAvailable = null;
    }, 30000);
    return this.apiAvailable;
  }

  /**
   * Login user
   */
  async login(credentials: LoginRequest): Promise<{ success: boolean; user?: User; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return this.mockLogin(credentials);
    }

    return { success: false, error: 'API unavailable and mock mode disabled' };
  }

  /**
   * Mock login for development
   */
  private async mockLogin(
    credentials: LoginRequest
  ): Promise<{ success: boolean; user?: User; error?: string }> {
    await new Promise((resolve) => setTimeout(resolve, 500)); // Simulate network delay

    const mockData = mockUsers.get(credentials.email.toLowerCase());
    if (mockData && mockData.password === credentials.password) {
      const mockTokens = {
        access_token: `mock-access-token-${Date.now()}`,
        refresh_token: `mock-refresh-token-${Date.now()}`,
        token_type: 'bearer',
        expires_in: 900,
      };

      tokenStorage.setTokens(mockTokens);
      localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(mockData.user));

      return { success: true, user: mockData.user };
    }

    return { success: false, error: 'Invalid email or password' };
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
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback
    if (API_CONFIG.useMockFallback) {
      return this.mockRegister(data);
    }

    return { success: false, error: 'API unavailable and mock mode disabled' };
  }

  /**
   * Mock registration
   */
  private async mockRegister(
    data: RegisterRequest
  ): Promise<{
    success: boolean;
    message?: string;
    user?: User;
    site?: SiteInfo;
    device?: DeviceClaimInfo;
    error?: string;
  }> {
    await new Promise((resolve) => setTimeout(resolve, 500));

    if (mockUsers.has(data.email.toLowerCase())) {
      return { success: false, error: 'An account with this email already exists' };
    }

    const newUser: User = {
      id: `mock-user-${Date.now()}`,
      email: data.email,
      first_name: data.first_name,
      last_name: data.last_name,
      phone: data.phone,
      role: 'owner' as const,
      status: 'pending' as const,
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
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    mockUsers.set(data.email.toLowerCase(), { password: data.password, user: newUser });

    // Create mock site
    const mockSite: SiteInfo = {
      id: `mock-site-${Date.now()}`,
      name: 'My Home',
      is_default: true,
    };

    // Create mock device if serial was provided
    let mockDevice: DeviceClaimInfo | undefined;
    if (data.device_serial) {
      mockDevice = {
        id: `mock-device-${Date.now()}`,
        serial_number: data.device_serial,
        device_type: 'inverter',
        manufacturer: 'Mock Manufacturer',
        status: 'claimed',
      };
    }

    return {
      success: true,
      message: 'Account created successfully. Please check your email to verify your account.',
      user: newUser,
      site: mockSite,
      device: mockDevice,
    };
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.post(API_ENDPOINTS.auth.logout);
      } catch {
        // Ignore logout errors - just clear local storage
      }
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

    const apiAvailable = await this.isApiAvailable();
    if (apiAvailable && tokenStorage.hasValidToken()) {
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
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    // Mock fallback - just update local storage
    if (API_CONFIG.useMockFallback) {
      const user = await this.getCurrentUser();
      if (user) {
        user.preferences = { ...user.preferences, ...preferences };
        localStorage.setItem(API_CONFIG.tokenKeys.user, JSON.stringify(user));
        return { success: true };
      }
    }

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Change password
   */
  async changePassword(
    currentPassword: string,
    newPassword: string
  ): Promise<{ success: boolean; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
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

    return { success: false, error: 'API unavailable' };
  }

  /**
   * Request password reset
   */
  async forgotPassword(email: string): Promise<{ success: boolean; message?: string; error?: string }> {
    const apiAvailable = await this.isApiAvailable();

    if (apiAvailable) {
      try {
        await apiClient.post(API_ENDPOINTS.auth.forgotPassword, { email });
        return { success: true, message: 'Password reset email sent' };
      } catch (error: unknown) {
        const apiError = error as { message?: string };
        return { success: false, error: apiError.message || 'Failed to send reset email' };
      }
    }

    // Mock - always succeed
    if (API_CONFIG.useMockFallback) {
      return { success: true, message: 'Password reset email sent (mock)' };
    }

    return { success: false, error: 'API unavailable' };
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
