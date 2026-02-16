/**
 * React Query hooks for Electricity Providers
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { providersService } from '@/api/services/admin.service';
import type { ElectricityProvider } from '@/types/admin';
import { toast } from 'sonner';

// Query keys
export const providerKeys = {
  all: ['admin', 'providers'] as const,
  lists: () => [...providerKeys.all, 'list'] as const,
  list: (filters?: any) => [...providerKeys.lists(), filters] as const,
  details: () => [...providerKeys.all, 'detail'] as const,
  detail: (id: string) => [...providerKeys.details(), id] as const,
};

// List providers
export function useProviders() {
  return useQuery({
    queryKey: providerKeys.list(),
    queryFn: () => providersService.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Get provider by ID
export function useProvider(id: string) {
  return useQuery({
    queryKey: providerKeys.detail(id),
    queryFn: () => providersService.getById(id),
    enabled: !!id,
  });
}

// Create provider
export function useCreateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<ElectricityProvider, 'id' | 'tariffCount' | 'createdAt' | 'updatedAt'>) =>
      providersService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: providerKeys.lists() });
      toast.success('Provider created successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create provider');
    },
  });
}

// Update provider
export function useUpdateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ElectricityProvider> }) =>
      providersService.update(id, data),
    onSuccess: (updatedProvider) => {
      queryClient.invalidateQueries({ queryKey: providerKeys.lists() });
      queryClient.setQueryData(providerKeys.detail(updatedProvider.id), updatedProvider);
      toast.success('Provider updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update provider');
    },
  });
}

// Delete provider
export function useDeleteProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => providersService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: providerKeys.lists() });
      toast.success('Provider deleted successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete provider');
    },
  });
}
