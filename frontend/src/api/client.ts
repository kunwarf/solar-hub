/**
 * API Client
 *
 * Axios-based HTTP client with:
 * - Automatic token management
 * - Request/response interceptors
 * - Token refresh on 401
 * - Error handling
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG, API_ENDPOINTS } from './config';

// Types for API responses
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ValidationErrorDetail {
  field: string;
  message: string;
  type: string;
}

export interface ApiError {
  error: string;
  message: string;
  details?: ValidationErrorDetail[] | Record<string, unknown>;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Token management utilities
export const tokenStorage = {
  getAccessToken: (): string | null => {
    return localStorage.getItem(API_CONFIG.tokenKeys.accessToken);
  },

  getRefreshToken: (): string | null => {
    return localStorage.getItem(API_CONFIG.tokenKeys.refreshToken);
  },

  setTokens: (tokens: TokenPair): void => {
    localStorage.setItem(API_CONFIG.tokenKeys.accessToken, tokens.access_token);
    localStorage.setItem(API_CONFIG.tokenKeys.refreshToken, tokens.refresh_token);
  },

  clearTokens: (): void => {
    localStorage.removeItem(API_CONFIG.tokenKeys.accessToken);
    localStorage.removeItem(API_CONFIG.tokenKeys.refreshToken);
    localStorage.removeItem(API_CONFIG.tokenKeys.user);
  },

  hasValidToken: (): boolean => {
    return !!tokenStorage.getAccessToken();
  },
};

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_CONFIG.baseUrl,
  timeout: API_CONFIG.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: Error) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null): void => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized - attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(apiClient(originalRequest));
            },
            reject: (err: Error) => {
              reject(err);
            },
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenStorage.getRefreshToken();
      if (!refreshToken) {
        tokenStorage.clearTokens();
        window.location.href = '/auth';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post<TokenPair>(
          `${API_CONFIG.baseUrl}${API_ENDPOINTS.auth.refresh}`,
          { refresh_token: refreshToken }
        );

        const newTokens = response.data;
        tokenStorage.setTokens(newTokens);
        processQueue(null, newTokens.access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newTokens.access_token}`;
        }

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error, null);
        tokenStorage.clearTokens();
        window.location.href = '/auth';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Format error response
    const responseData = error.response?.data;
    let apiError: ApiError;

    if (responseData) {
      apiError = responseData;

      // If this is a validation error with details, format a user-friendly message
      if (responseData.error === 'VALIDATION_ERROR' && Array.isArray(responseData.details)) {
        const details = responseData.details as ValidationErrorDetail[];
        if (details.length > 0) {
          // Create a message from the first error detail for better UX
          const firstError = details[0];
          apiError.message = firstError.message;

          // If there are multiple errors, append count
          if (details.length > 1) {
            apiError.message += ` (and ${details.length - 1} more issue${details.length > 2 ? 's' : ''})`;
          }
        }
      }
    } else {
      apiError = {
        error: 'NETWORK_ERROR',
        message: error.message || 'Network error occurred',
      };
    }

    return Promise.reject(apiError);
  }
);

// Check if API is available
export const checkApiHealth = async (): Promise<boolean> => {
  try {
    await axios.get(`${API_CONFIG.baseUrl.replace('/api/v1', '')}/health`, {
      timeout: 5000,
    });
    return true;
  } catch {
    return false;
  }
};

export default apiClient;
