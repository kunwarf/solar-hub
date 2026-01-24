/**
 * API Module Index
 *
 * Main entry point for all API-related functionality.
 */

// Configuration
export { API_CONFIG, API_ENDPOINTS, SYSTEM_B_CONFIG, SYSTEM_B_ENDPOINTS } from './config';

// Client
export { default as apiClient, tokenStorage, checkApiHealth } from './client';

// Services
export * from './services';

// Types
export * from './types';
