/**
 * React Query hooks for Firmware Management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  firmwareVersionsService,
  firmwareFilesService,
  campaignsService,
  deviceFirmwareService,
} from '@/api/services/firmware.service';
import type {
  FirmwareVersion,
  FirmwareUpdateCampaign,
  DeviceFirmwareStatus,
  CreateFirmwareVersionRequest,
  CreateCampaignRequest,
} from '@/types/firmware';
import { toast } from 'sonner';

// Query keys
export const firmwareKeys = {
  all: ['admin', 'firmware'] as const,
  versions: () => [...firmwareKeys.all, 'versions'] as const,
  version: (id: string) => [...firmwareKeys.versions(), id] as const,
  files: (versionId: string) => [...firmwareKeys.version(versionId), 'files'] as const,
  campaigns: () => [...firmwareKeys.all, 'campaigns'] as const,
  campaign: (id: string) => [...firmwareKeys.campaigns(), id] as const,
  campaignStatus: (id: string) => [...firmwareKeys.campaign(id), 'status'] as const,
  deviceStatuses: (filters?: any) => [...firmwareKeys.all, 'device-statuses', filters] as const,
};

// Firmware Versions
export function useFirmwareVersions() {
  return useQuery({
    queryKey: firmwareKeys.versions(),
    queryFn: () => firmwareVersionsService.list(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

export function useFirmwareVersion(id: string) {
  return useQuery({
    queryKey: firmwareKeys.version(id),
    queryFn: () => firmwareVersionsService.getById(id),
    enabled: !!id,
  });
}

export function useCreateFirmwareVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateFirmwareVersionRequest) => firmwareVersionsService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.versions() });
      toast.success('Firmware version created successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create firmware version');
    },
  });
}

export function useUpdateFirmwareVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FirmwareVersion> }) =>
      firmwareVersionsService.update(id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.versions() });
      queryClient.setQueryData(firmwareKeys.version(updated.id), updated);
      toast.success('Firmware version updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update firmware version');
    },
  });
}

export function useDeleteFirmwareVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => firmwareVersionsService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.versions() });
      toast.success('Firmware version deleted successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete firmware version');
    },
  });
}

export function useToggleFirmwareVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => firmwareVersionsService.toggleActive(id),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.versions() });
      queryClient.setQueryData(firmwareKeys.version(updated.id), updated);
      toast.success(`Version ${updated.isActive ? 'activated' : 'deactivated'} successfully`);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to toggle firmware version');
    },
  });
}

// Firmware Files
export function useFirmwareFiles(versionId: string) {
  return useQuery({
    queryKey: firmwareKeys.files(versionId),
    queryFn: () => firmwareFilesService.list(versionId),
    enabled: !!versionId,
  });
}

export function useUploadFirmwareFiles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      versionId,
      files,
      onProgress,
    }: {
      versionId: string;
      files: File[];
      onProgress?: (fileIndex: number, progress: number) => void;
    }) => firmwareFilesService.uploadMultiple(versionId, files, onProgress),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.files(variables.versionId) });
      queryClient.invalidateQueries({ queryKey: firmwareKeys.versions() });
      toast.success('Files uploaded successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to upload files');
    },
  });
}

// Campaigns
export function useCampaigns() {
  return useQuery({
    queryKey: firmwareKeys.campaigns(),
    queryFn: () => campaignsService.list(),
    staleTime: 1 * 60 * 1000, // 1 minute
    refetchInterval: 30000, // Refetch every 30 seconds for active campaigns
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: firmwareKeys.campaign(id),
    queryFn: () => campaignsService.getById(id),
    enabled: !!id,
  });
}

export function useCampaignStatus(id: string) {
  return useQuery({
    queryKey: firmwareKeys.campaignStatus(id),
    queryFn: () => campaignsService.getStatus(id),
    enabled: !!id,
    refetchInterval: 10000, // Refetch every 10 seconds
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCampaignRequest) => campaignsService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.campaigns() });
      toast.success('Campaign created successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create campaign');
    },
  });
}

export function useUpdateCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FirmwareUpdateCampaign> }) =>
      campaignsService.update(id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.campaigns() });
      queryClient.setQueryData(firmwareKeys.campaign(updated.id), updated);
      toast.success('Campaign updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update campaign');
    },
  });
}

export function useActivateCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => campaignsService.activate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.campaigns() });
      toast.success('Campaign activated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to activate campaign');
    },
  });
}

export function usePauseCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => campaignsService.pause(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.campaigns() });
      toast.success('Campaign paused successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to pause campaign');
    },
  });
}

export function useResumeCampaign() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => campaignsService.resume(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: firmwareKeys.campaigns() });
      toast.success('Campaign resumed successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to resume campaign');
    },
  });
}

// Device Firmware Status
export function useDeviceFirmwareStatuses(filters?: { campaignId?: string; status?: string }) {
  return useQuery({
    queryKey: firmwareKeys.deviceStatuses(filters),
    queryFn: () => deviceFirmwareService.list(filters),
    staleTime: 30000, // 30 seconds
    refetchInterval: 15000, // Refetch every 15 seconds
  });
}

export function useDeviceFirmwareStatus(serial: string) {
  return useQuery({
    queryKey: [...firmwareKeys.deviceStatuses(), serial],
    queryFn: () => deviceFirmwareService.getBySerial(serial),
    enabled: !!serial,
  });
}
