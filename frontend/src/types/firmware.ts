// OTA Firmware Management Types

export interface FirmwareVersion {
  id: string;
  version: string;
  description: string;
  deviceType: string;  // "esp32_datalogger"
  isActive: boolean;
  fileCount: number;
  totalSize: number;  // bytes
  createdAt: string;
  createdBy: string;
}

export interface FirmwareFile {
  id: string;
  versionId: string;
  filename: string;
  fileType: "python" | "json" | "config";
  size: number;  // bytes
  checksum: string;  // SHA256
  createdAt: string;
}

export interface DeviceFirmwareStatus {
  deviceSerial: string;
  deviceName?: string;
  currentVersion: string;
  targetVersion?: string;
  updateStatus: "up_to_date" | "pending" | "downloading" | "applying" | "success" | "failed" | "rollback";
  progress: number;  // 0-100
  lastCheckAt?: string;
  errorMessage?: string;
  deviceInfo?: {
    freeMemory: number;
    totalMemory: number;
    uptime: number;
  };
}

export interface FirmwareUpdateCampaign {
  id: string;
  name: string;
  description?: string;
  versionId: string;
  version: string;  // Denormalized for display
  targetDevices: string[];  // Device serials or "all"
  rolloutStrategy: "immediate" | "staged" | "canary";
  rolloutPercentage: number;  // 1-100
  status: "draft" | "active" | "paused" | "completed" | "cancelled";
  startedAt?: string;
  completedAt?: string;
  statistics: {
    totalDevices: number;
    pending: number;
    downloading: number;
    applying: number;
    success: number;
    failed: number;
  };
  createdAt: string;
  createdBy: string;
}

export interface FirmwareUpdateHistory {
  id: string;
  deviceSerial: string;
  campaignId?: string;
  fromVersion: string;
  toVersion: string;
  status: "success" | "failed" | "rollback";
  startedAt: string;
  completedAt?: string;
  duration?: number;  // seconds
  errorMessage?: string;
}

// API Request/Response Types

export interface CreateFirmwareVersionRequest {
  version: string;
  description: string;
  deviceType?: string;
}

export interface UploadFirmwareFileRequest {
  versionId: string;
  file: File;
}

export interface CreateCampaignRequest {
  name: string;
  description?: string;
  versionId: string;
  targetDevices: string[];  // Device serials or ["all"]
  rolloutStrategy: "immediate" | "staged" | "canary";
  rolloutPercentage?: number;  // Required for staged/canary
}

export interface CampaignStatusResponse {
  campaign: FirmwareUpdateCampaign;
  devices: DeviceFirmwareStatus[];
}
