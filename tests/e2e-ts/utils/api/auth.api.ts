import { APIRequestContext, Page } from '@playwright/test';

/**
 * Login credentials interface
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Authentication tokens interface
 */
export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in?: number;
}

/**
 * API response interface
 */
interface LoginResponse {
  tokens?: AuthTokens;
  token?: string;
  access_token?: string;
  refresh_token?: string;
}

/**
 * Login via API and return tokens
 * Fastest authentication method (50ms vs 5s UI login)
 */
export async function loginViaAPI(
  request: APIRequestContext,
  credentials: LoginCredentials
): Promise<AuthTokens> {
  const apiURL = process.env.API_SYSTEM_A_URL || 'http://localhost:8000';

  const response = await request.post(`${apiURL}/api/v1/auth/login`, {
    data: credentials,
  });

  if (!response.ok()) {
    const errorText = await response.text();
    throw new Error(`API login failed: ${response.status()} - ${errorText}`);
  }

  const data: LoginResponse = await response.json();

  // Handle different response formats
  if (data.tokens) {
    return data.tokens;
  } else if (data.access_token) {
    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: 'Bearer',
    };
  } else if (data.token) {
    return {
      access_token: data.token,
      token_type: 'Bearer',
    };
  } else {
    throw new Error('Unexpected login response format');
  }
}

/**
 * Set authentication tokens in browser storage
 */
export async function setAuthTokens(page: Page, tokens: AuthTokens): Promise<void> {
  // Need to be on the domain to set localStorage
  await page.goto('/');

  await page.evaluate((tokens) => {
    localStorage.setItem('token', tokens.access_token);
    if (tokens.refresh_token) {
      localStorage.setItem('refresh_token', tokens.refresh_token);
    }
    localStorage.setItem('token_type', tokens.token_type);
  }, tokens);
}

/**
 * Full API login flow: login + set tokens
 * Use this for fast test setup
 */
export async function authenticateViaAPI(
  page: Page,
  credentials: LoginCredentials
): Promise<void> {
  const tokens = await loginViaAPI(page.request, credentials);
  await setAuthTokens(page, tokens);
}

/**
 * Logout via API
 */
export async function logoutViaAPI(request: APIRequestContext, token: string): Promise<void> {
  const apiURL = process.env.API_SYSTEM_A_URL || 'http://localhost:8000';

  await request.post(`${apiURL}/api/v1/auth/logout`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Refresh auth token
 */
export async function refreshToken(
  request: APIRequestContext,
  refreshToken: string
): Promise<AuthTokens> {
  const apiURL = process.env.API_SYSTEM_A_URL || 'http://localhost:8000';

  const response = await request.post(`${apiURL}/api/v1/auth/refresh`, {
    data: { refresh_token: refreshToken },
  });

  if (!response.ok()) {
    throw new Error(`Token refresh failed: ${response.status()}`);
  }

  const data: LoginResponse = await response.json();

  if (data.tokens) {
    return data.tokens;
  } else if (data.access_token) {
    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_type: 'Bearer',
    };
  } else {
    throw new Error('Unexpected refresh token response format');
  }
}

/**
 * Get user credentials from environment
 */
export function getCredentials(role: 'owner' | 'admin' | 'viewer' | 'installer'): LoginCredentials {
  const roleUpper = role.toUpperCase();

  return {
    email: process.env[`${roleUpper}_EMAIL`] || `${role}@solarhub.com`,
    password: process.env[`${roleUpper}_PASSWORD`] || `${role.charAt(0).toUpperCase() + role.slice(1)}123!@#`,
  };
}
