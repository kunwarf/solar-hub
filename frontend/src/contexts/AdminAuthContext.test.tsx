import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { AdminAuthProvider, useAdminAuth } from './AdminAuthContext';

describe('AdminAuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('should provide initial unauthenticated state', () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.adminUser).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('should login with valid credentials', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    let success = false;
    await act(async () => {
      success = await result.current.login('admin@solarhub.com', 'admin123');
    });

    expect(success).toBe(true);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.adminUser).toMatchObject({
      email: 'admin@solarhub.com',
      role: 'super_admin',
    });
  });

  it('should fail login with invalid credentials', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    let success = false;
    await act(async () => {
      success = await result.current.login('wrong@example.com', 'wrongpass');
    });

    expect(success).toBe(false);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.adminUser).toBeNull();
  });

  it('should logout and clear session', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    // Login first
    await act(async () => {
      await result.current.login('admin@solarhub.com', 'admin123');
    });

    expect(result.current.isAuthenticated).toBe(true);

    // Logout
    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.adminUser).toBeNull();
    expect(localStorage.getItem('admin_token')).toBeNull();
  });

  it('should check permissions correctly', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    // Login as super_admin
    await act(async () => {
      await result.current.login('admin@solarhub.com', 'admin123');
    });

    expect(result.current.hasPermission('manage_providers')).toBe(true);
    expect(result.current.hasPermission('manage_tariffs')).toBe(true);
    expect(result.current.hasPermission('manage_firmware')).toBe(true);
  });

  it('should check ops_admin permissions', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    // Login as ops_admin
    await act(async () => {
      await result.current.login('ops@solarhub.com', 'ops123');
    });

    expect(result.current.hasPermission('manage_providers')).toBe(true);
    expect(result.current.hasPermission('manage_tariffs')).toBe(true);
    expect(result.current.hasPermission('manage_firmware')).toBe(false);
  });

  it('should check any permission correctly', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    await act(async () => {
      await result.current.login('ops@solarhub.com', 'ops123');
    });

    expect(
      result.current.hasAnyPermission(['manage_providers', 'manage_firmware'])
    ).toBe(true);
    expect(
      result.current.hasAnyPermission(['manage_firmware', 'manage_campaigns'])
    ).toBe(false);
  });

  it('should check role correctly', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    await act(async () => {
      await result.current.login('admin@solarhub.com', 'admin123');
    });

    expect(result.current.hasRole('super_admin')).toBe(true);
    expect(result.current.hasRole('ops_admin')).toBe(false);
  });

  it('should add audit entries', async () => {
    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    await act(async () => {
      await result.current.login('admin@solarhub.com', 'admin123');
    });

    act(() => {
      result.current.addAuditEntry({
        action: 'create',
        entity: 'provider',
        entityId: 'p1',
        details: {
          after: { name: 'Test Provider' },
        },
      });
    });

    expect(result.current.auditLog).toHaveLength(2); // Login + Create
    expect(result.current.auditLog[0].action).toBe('create');
    expect(result.current.auditLog[0].entity).toBe('provider');
    expect(result.current.auditLog[0].actor).toBe('admin@solarhub.com');
  });

  it('should restore session from localStorage', () => {
    const mockUser = {
      id: 'admin-1',
      email: 'admin@solarhub.com',
      firstName: 'Super',
      lastName: 'Admin',
      role: 'super_admin' as const,
      status: 'active' as const,
      createdAt: new Date().toISOString(),
    };

    localStorage.setItem('admin_token', 'mock_token');
    localStorage.setItem('admin_user', JSON.stringify(mockUser));

    const { result } = renderHook(() => useAdminAuth(), {
      wrapper: AdminAuthProvider,
    });

    waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.adminUser).toMatchObject(mockUser);
    });
  });
});
