import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@/test/utils';
import { AdminGuard } from './AdminGuard';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

// Mock the admin auth hook
vi.mock('@/contexts/AdminAuthContext', () => ({
  useAdminAuth: vi.fn(),
}));

// Mock router
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

describe('AdminGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show loading state while checking authentication', () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      hasPermission: () => false,
      hasAnyPermission: () => false,
    } as any);

    render(
      <AdminGuard>
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('should redirect to login when not authenticated', async () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      hasPermission: () => false,
      hasAnyPermission: () => false,
    } as any);

    render(
      <AdminGuard>
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/admin/login', { replace: true });
    });

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('should render children when authenticated', () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: () => true,
      hasAnyPermission: () => true,
    } as any);

    render(
      <AdminGuard>
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('should redirect when missing required permission', async () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: (permission: string) => permission !== 'manage_firmware',
      hasAnyPermission: () => false,
    } as any);

    render(
      <AdminGuard requiredPermission="manage_firmware">
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/admin', { replace: true });
    });
  });

  it('should render when user has required permission', () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: (permission: string) => permission === 'manage_providers',
      hasAnyPermission: () => true,
    } as any);

    render(
      <AdminGuard requiredPermission="manage_providers">
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('should check multiple required permissions', async () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: (permission: string) => permission === 'manage_providers',
      hasAnyPermission: () => false,
    } as any);

    render(
      <AdminGuard requiredPermissions={['manage_providers', 'manage_tariffs']}>
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/admin', { replace: true });
    });
  });

  it('should allow access with any permission', () => {
    vi.mocked(useAdminAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: () => false,
      hasAnyPermission: (permissions: string[]) =>
        permissions.includes('manage_providers'),
    } as any);

    render(
      <AdminGuard anyPermission={['manage_providers', 'manage_tariffs']}>
        <div>Protected Content</div>
      </AdminGuard>,
      { withRouter: false, withAdminAuth: false }
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });
});
