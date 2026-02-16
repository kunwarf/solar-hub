import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useProviders, useCreateProvider, useUpdateProvider, useDeleteProvider } from './useProviders';
import { providersService } from '@/api/services/admin.service';
import type { ElectricityProvider } from '@/types/admin';

// Mock the service
vi.mock('@/api/services/admin.service', () => ({
  providersService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useProviders hooks', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe('useProviders', () => {
    it('should fetch providers successfully', async () => {
      const mockProviders: ElectricityProvider[] = [
        {
          id: 'p1',
          name: 'LESCO',
          shortName: 'LESCO',
          region: 'Punjab',
          status: 'active',
          tariffCount: 5,
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        },
      ];

      vi.mocked(providersService.list).mockResolvedValue(mockProviders);

      const { result } = renderHook(() => useProviders(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockProviders);
      expect(providersService.list).toHaveBeenCalledTimes(1);
    });

    it('should handle fetch error', async () => {
      vi.mocked(providersService.list).mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useProviders(), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });

    it('should cache providers data', async () => {
      const mockProviders: ElectricityProvider[] = [
        {
          id: 'p1',
          name: 'LESCO',
          shortName: 'LESCO',
          region: 'Punjab',
          status: 'active',
          tariffCount: 5,
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        },
      ];

      vi.mocked(providersService.list).mockResolvedValue(mockProviders);

      const { result: result1 } = renderHook(() => useProviders(), { wrapper });
      await waitFor(() => expect(result1.current.isSuccess).toBe(true));

      const { result: result2 } = renderHook(() => useProviders(), { wrapper });
      await waitFor(() => expect(result2.current.isSuccess).toBe(true));

      // Should only call API once due to caching
      expect(providersService.list).toHaveBeenCalledTimes(1);
    });
  });

  describe('useCreateProvider', () => {
    it('should create provider successfully', async () => {
      const newProvider = {
        name: 'GEPCO',
        shortName: 'GEPCO',
        region: 'Punjab',
        status: 'active' as const,
      };

      const createdProvider: ElectricityProvider = {
        id: 'p2',
        ...newProvider,
        tariffCount: 0,
        createdAt: '2024-01-02T00:00:00Z',
        updatedAt: '2024-01-02T00:00:00Z',
      };

      vi.mocked(providersService.create).mockResolvedValue(createdProvider);

      const { result } = renderHook(() => useCreateProvider(), { wrapper });

      result.current.mutate(newProvider);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(createdProvider);
      expect(providersService.create).toHaveBeenCalledWith(newProvider);
    });

    it('should handle create error', async () => {
      const newProvider = {
        name: 'GEPCO',
        shortName: 'GEPCO',
        region: 'Punjab',
        status: 'active' as const,
      };

      vi.mocked(providersService.create).mockRejectedValue({
        message: 'Failed to create provider',
      });

      const { result } = renderHook(() => useCreateProvider(), { wrapper });

      result.current.mutate(newProvider);

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useUpdateProvider', () => {
    it('should update provider successfully', async () => {
      const updateData = {
        id: 'p1',
        data: { status: 'inactive' as const },
      };

      const updatedProvider: ElectricityProvider = {
        id: 'p1',
        name: 'LESCO',
        shortName: 'LESCO',
        region: 'Punjab',
        status: 'inactive',
        tariffCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-02T00:00:00Z',
      };

      vi.mocked(providersService.update).mockResolvedValue(updatedProvider);

      const { result } = renderHook(() => useUpdateProvider(), { wrapper });

      result.current.mutate(updateData);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(updatedProvider);
      expect(providersService.update).toHaveBeenCalledWith('p1', updateData.data);
    });
  });

  describe('useDeleteProvider', () => {
    it('should delete provider successfully', async () => {
      vi.mocked(providersService.delete).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteProvider(), { wrapper });

      result.current.mutate('p1');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(providersService.delete).toHaveBeenCalledWith('p1');
    });

    it('should handle delete error', async () => {
      vi.mocked(providersService.delete).mockRejectedValue({
        message: 'Cannot delete provider with active tariffs',
      });

      const { result } = renderHook(() => useDeleteProvider(), { wrapper });

      result.current.mutate('p1');

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });
});
