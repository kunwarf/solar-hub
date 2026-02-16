/**
 * Firmware API Service (System B)
 *
 * Handles all OTA firmware management API calls
 * - Firmware versions
 * - Firmware files
 * - Update campaigns
 * - Device firmware status
 */

import axios from 'axios';
import { SYSTEM_B_CONFIG } from '../config';
import { tokenStorage } from '../client';
import type {
  FirmwareVersion,
  FirmwareFile,
  FirmwareUpdateCampaign,
  DeviceFirmwareStatus,
  FirmwareUpdateHistory,
  CreateFirmwareVersionRequest,
  CreateCampaignRequest,
  CampaignStatusResponse,
} from '@/types/firmware';

// Create System B client
const systemBClient = axios.create({
  baseURL: SYSTEM_B_CONFIG.baseUrl,
  timeout: 60000, // 60s for file uploads
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to System B requests
systemBClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Firmware Versions
export const firmwareVersionsService = {
  list: async (): Promise<FirmwareVersion[]> => {
    const response = await systemBClient.get('/firmware/versions');
    return response.data;
  },

  getById: async (id: string): Promise<FirmwareVersion> => {
    const response = await systemBClient.get(`/firmware/versions/${id}`);
    return response.data;
  },

  create: async (data: CreateFirmwareVersionRequest): Promise<FirmwareVersion> => {
    const response = await systemBClient.post('/firmware/versions', data);
    return response.data;
  },

  update: async (id: string, data: Partial<FirmwareVersion>): Promise<FirmwareVersion> => {
    const response = await systemBClient.put(`/firmware/versions/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await systemBClient.delete(`/firmware/versions/${id}`);
  },

  toggleActive: async (id: string): Promise<FirmwareVersion> => {
    const response = await systemBClient.post(`/firmware/versions/${id}/toggle`);
    return response.data;
  },
};

// Firmware Files
export const firmwareFilesService = {
  list: async (versionId: string): Promise<FirmwareFile[]> => {
    const response = await systemBClient.get(`/firmware/versions/${versionId}/files`);
    return response.data;
  },

  getById: async (versionId: string, fileId: string): Promise<FirmwareFile> => {
    const response = await systemBClient.get(`/firmware/versions/${versionId}/files/${fileId}`);
    return response.data;
  },

  upload: async (versionId: string, file: File, onProgress?: (progress: number) => void): Promise<FirmwareFile> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await systemBClient.post(
      `/firmware/versions/${versionId}/files`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(progress);
          }
        },
      }
    );
    return response.data;
  },

  uploadMultiple: async (
    versionId: string,
    files: File[],
    onProgress?: (fileIndex: number, progress: number) => void
  ): Promise<FirmwareFile[]> => {
    const uploadedFiles: FirmwareFile[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const uploadedFile = await firmwareFilesService.upload(
        versionId,
        file,
        (progress) => onProgress?.(i, progress)
      );
      uploadedFiles.push(uploadedFile);
    }

    return uploadedFiles;
  },

  download: async (versionId: string, fileId: string): Promise<Blob> => {
    const response = await systemBClient.get(
      `/firmware/versions/${versionId}/files/${fileId}/download`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  delete: async (versionId: string, fileId: string): Promise<void> => {
    await systemBClient.delete(`/firmware/versions/${versionId}/files/${fileId}`);
  },
};

// Update Campaigns
export const campaignsService = {
  list: async (): Promise<FirmwareUpdateCampaign[]> => {
    const response = await systemBClient.get('/firmware/campaigns');
    return response.data;
  },

  getById: async (id: string): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.get(`/firmware/campaigns/${id}`);
    return response.data;
  },

  create: async (data: CreateCampaignRequest): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.post('/firmware/campaigns', data);
    return response.data;
  },

  update: async (id: string, data: Partial<FirmwareUpdateCampaign>): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.put(`/firmware/campaigns/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await systemBClient.delete(`/firmware/campaigns/${id}`);
  },

  activate: async (id: string): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.post(`/firmware/campaigns/${id}/activate`);
    return response.data;
  },

  pause: async (id: string): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.post(`/firmware/campaigns/${id}/pause`);
    return response.data;
  },

  resume: async (id: string): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.post(`/firmware/campaigns/${id}/resume`);
    return response.data;
  },

  cancel: async (id: string): Promise<FirmwareUpdateCampaign> => {
    const response = await systemBClient.post(`/firmware/campaigns/${id}/cancel`);
    return response.data;
  },

  getStatus: async (id: string): Promise<CampaignStatusResponse> => {
    const response = await systemBClient.get(`/firmware/campaigns/${id}/status`);
    return response.data;
  },
};

// Device Firmware Status
export const deviceFirmwareService = {
  list: async (params?: {
    campaignId?: string;
    status?: string;
  }): Promise<DeviceFirmwareStatus[]> => {
    const response = await systemBClient.get('/firmware/devices/status', { params });
    return response.data;
  },

  getBySerial: async (serial: string): Promise<DeviceFirmwareStatus> => {
    const response = await systemBClient.get(`/firmware/devices/${serial}/status`);
    return response.data;
  },

  updateStatus: async (
    serial: string,
    data: Partial<DeviceFirmwareStatus>
  ): Promise<DeviceFirmwareStatus> => {
    const response = await systemBClient.put(`/firmware/devices/${serial}/status`, data);
    return response.data;
  },
};

// Firmware Update History
export const firmwareHistoryService = {
  list: async (params?: {
    deviceSerial?: string;
    campaignId?: string;
    status?: string;
  }): Promise<FirmwareUpdateHistory[]> => {
    const response = await systemBClient.get('/firmware/history', { params });
    return response.data;
  },

  getById: async (id: string): Promise<FirmwareUpdateHistory> => {
    const response = await systemBClient.get(`/firmware/history/${id}`);
    return response.data;
  },
};

export default {
  versions: firmwareVersionsService,
  files: firmwareFilesService,
  campaigns: campaignsService,
  deviceStatus: deviceFirmwareService,
  history: firmwareHistoryService,
};
