/**
 * React Query hooks for Tariff Plans
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tariffsService } from '@/api/services/admin.service';
import type { TariffPlan } from '@/types/admin';
import { toast } from 'sonner';

// Query keys
export const tariffKeys = {
  all: ['admin', 'tariffs'] as const,
  lists: () => [...tariffKeys.all, 'list'] as const,
  list: (filters?: { providerId?: string }) => [...tariffKeys.lists(), filters] as const,
  details: () => [...tariffKeys.all, 'detail'] as const,
  detail: (id: string) => [...tariffKeys.details(), id] as const,
};

// List tariffs
export function useTariffs(filters?: { providerId?: string }) {
  return useQuery({
    queryKey: tariffKeys.list(filters),
    queryFn: () => tariffsService.list(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Get tariff by ID
export function useTariff(id: string) {
  return useQuery({
    queryKey: tariffKeys.detail(id),
    queryFn: () => tariffsService.getById(id),
    enabled: !!id,
  });
}

// Create tariff
export function useCreateTariff() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<TariffPlan, 'id'>) => tariffsService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tariffKeys.lists() });
      toast.success('Tariff plan created successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create tariff plan');
    },
  });
}

// Update tariff
export function useUpdateTariff() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<TariffPlan> }) =>
      tariffsService.update(id, data),
    onSuccess: (updatedTariff) => {
      queryClient.invalidateQueries({ queryKey: tariffKeys.lists() });
      queryClient.setQueryData(tariffKeys.detail(updatedTariff.id), updatedTariff);
      toast.success('Tariff plan updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update tariff plan');
    },
  });
}

// Delete tariff
export function useDeleteTariff() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => tariffsService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tariffKeys.lists() });
      toast.success('Tariff plan deleted successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete tariff plan');
    },
  });
}
