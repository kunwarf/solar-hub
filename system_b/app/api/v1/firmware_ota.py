"""
OTA Firmware Management API endpoints.

Provides endpoints for:
- Uploading firmware versions
- Managing update campaigns
- Device update checks
- Monitoring update status
"""
from datetime import datetime, timezone as dt_timezone
from typing import List, Optional
from uuid import UUID
import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from pydantic import BaseModel, Field

# NOTE: uvicorn runs with `WorkingDirectory=/opt/solarhub/app/solar-hub/system_b`
# and launches `app.main:app`, so the module namespace starts at `app.*` —
# there is NO `system_b` package on the path.  Every other v1 router uses
# relative imports (see devices.py:14, telemetry.py, commands.py); this
# file must match that convention or FastAPI fails to import the whole
# api_router at startup and every worker crashes on boot (no port bind).
from ...infrastructure.database.timescale_connection import get_db
from ...infrastructure.database.models.firmware import (
    FirmwareVersion, FirmwareFile, DeviceFirmwareStatus,
    FirmwareUpdateCampaign, FirmwareUpdateHistory
)


router = APIRouter(prefix="/firmware", tags=["OTA Firmware Management"])


# ============================================================================
# Pydantic Models
# ============================================================================

class FirmwareVersionCreate(BaseModel):
    """Request model for creating firmware version."""
    version: str = Field(..., description="Version string (e.g., '1.2.0')")
    description: Optional[str] = Field(None, description="Version description")
    device_type: str = Field("datalogger", description="Device type")
    created_by: Optional[str] = None


class FirmwareFileUpload(BaseModel):
    """Request model for uploading firmware file."""
    filename: str = Field(..., description="File name")
    content: str = Field(..., description="File content (text or base64)")
    file_type: str = Field("python", description="File type: python, config, binary")
    is_required: bool = Field(True, description="Is this file required?")


class DeviceUpdateCheck(BaseModel):
    """Request model for device checking for updates."""
    device_serial: str = Field(..., description="Device serial number")
    current_version: Optional[str] = Field(None, description="Current firmware version")
    device_info: Optional[dict] = Field(None, description="Device metadata (memory, uptime, etc.)")


class DeviceUpdateStatus(BaseModel):
    """Request model for device reporting update status."""
    device_serial: str
    update_status: str  # downloading, applying, success, failed
    progress: int = Field(0, ge=0, le=100)
    error_message: Optional[str] = None


class CampaignCreate(BaseModel):
    """Request model for creating update campaign."""
    name: str = Field(..., description="Campaign name")
    firmware_version_id: UUID = Field(..., description="Firmware version to deploy")
    target_devices: Optional[List[str]] = Field(None, description="Specific device serials")
    target_filter: Optional[dict] = Field(None, description="Filter criteria (e.g., {'current_version': '1.0.0'})")
    rollout_strategy: str = Field("immediate", description="Rollout strategy")
    rollout_percentage: int = Field(100, ge=1, le=100, description="Rollout percentage")
    created_by: Optional[str] = None


# ============================================================================
# Firmware Version Management
# ============================================================================

@router.post("/versions", response_model=dict)
async def create_firmware_version(
    version_data: FirmwareVersionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new firmware version."""
    # Check if version already exists
    result = await db.execute(
        select(FirmwareVersion).where(FirmwareVersion.version == version_data.version)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Version {version_data.version} already exists")

    # Create version
    firmware = FirmwareVersion(
        version=version_data.version,
        description=version_data.description,
        device_type=version_data.device_type,
        created_by=version_data.created_by
    )
    db.add(firmware)
    await db.commit()
    await db.refresh(firmware)

    return {
        "id": str(firmware.id),
        "version": firmware.version,
        "created_at": firmware.created_at.isoformat()
    }


@router.post("/versions/{version_id}/files", response_model=dict)
async def upload_firmware_file(
    version_id: UUID,
    file_data: FirmwareFileUpload,
    db: AsyncSession = Depends(get_db)
):
    """Upload a file to a firmware version."""
    # Verify firmware version exists
    result = await db.execute(
        select(FirmwareVersion).where(FirmwareVersion.id == version_id)
    )
    firmware = result.scalar_one_or_none()
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware version not found")

    # Calculate checksum
    checksum = hashlib.sha256(file_data.content.encode()).hexdigest()

    # Create file record
    firmware_file = FirmwareFile(
        firmware_version_id=version_id,
        filename=file_data.filename,
        content=file_data.content,
        file_size=len(file_data.content),
        checksum=checksum,
        file_type=file_data.file_type,
        is_required=file_data.is_required
    )
    db.add(firmware_file)
    await db.commit()
    await db.refresh(firmware_file)

    return {
        "id": str(firmware_file.id),
        "filename": firmware_file.filename,
        "size": firmware_file.file_size,
        "checksum": checksum
    }


@router.get("/versions", response_model=List[dict])
async def list_firmware_versions(
    device_type: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """List all firmware versions."""
    query = select(FirmwareVersion)

    if device_type:
        query = query.where(FirmwareVersion.device_type == device_type)
    if active_only:
        query = query.where(FirmwareVersion.is_active == True)

    query = query.order_by(FirmwareVersion.created_at.desc())

    result = await db.execute(query)
    versions = result.scalars().all()

    return [
        {
            "id": str(v.id),
            "version": v.version,
            "description": v.description,
            "device_type": v.device_type,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat(),
            "file_count": len(v.files)
        }
        for v in versions
    ]


@router.get("/versions/{version_id}/files", response_model=List[dict])
async def get_firmware_files(
    version_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all files for a firmware version."""
    result = await db.execute(
        select(FirmwareFile).where(FirmwareFile.firmware_version_id == version_id)
    )
    files = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "filename": f.filename,
            "size": f.file_size,
            "checksum": f.checksum,
            "file_type": f.file_type,
            "is_required": f.is_required,
            "content": f.content  # Include content for download
        }
        for f in files
    ]


# ============================================================================
# Device Update Check (Called by ESP32)
# ============================================================================

@router.post("/check-update", response_model=dict)
async def check_for_update(
    check_data: DeviceUpdateCheck,
    db: AsyncSession = Depends(get_db)
):
    """
    Device checks if an update is available.
    Called periodically by ESP32.
    """
    # Update last check time
    result = await db.execute(
        select(DeviceFirmwareStatus).where(
            DeviceFirmwareStatus.device_serial == check_data.device_serial
        )
    )
    status = result.scalar_one_or_none()

    if not status:
        # First time this device is checking - create status record.
        # NOTE: `metadata_` is the Python attribute name; it maps to the
        # `metadata` DB column.  See firmware.py model for the rename
        # rationale (SQLAlchemy reserves `metadata` on Declarative Base).
        status = DeviceFirmwareStatus(
            device_serial=check_data.device_serial,
            current_version=check_data.current_version,
            last_check_at=datetime.now(dt_timezone.utc),
            metadata_=check_data.device_info,
        )
        db.add(status)
    else:
        # Update existing status
        status.current_version = check_data.current_version
        status.last_check_at = datetime.now(dt_timezone.utc)
        if check_data.device_info:
            status.metadata_ = check_data.device_info

    await db.commit()
    await db.refresh(status)

    # Check if update is available
    if status.target_version_id and status.update_status in ["pending", "failed"]:
        # Fetch target version details
        result = await db.execute(
            select(FirmwareVersion).where(FirmwareVersion.id == status.target_version_id)
        )
        target_version = result.scalar_one_or_none()

        if target_version and target_version.version != check_data.current_version:
            # Update available!
            return {
                "update_available": True,
                "target_version": target_version.version,
                "version_id": str(target_version.id),
                "description": target_version.description,
                "files_url": f"/api/v1/firmware/versions/{target_version.id}/files"
            }

    return {"update_available": False}


@router.post("/update-status", response_model=dict)
async def report_update_status(
    status_data: DeviceUpdateStatus,
    db: AsyncSession = Depends(get_db)
):
    """
    Device reports update status progress.
    Called by ESP32 during update process.
    """
    result = await db.execute(
        select(DeviceFirmwareStatus).where(
            DeviceFirmwareStatus.device_serial == status_data.device_serial
        )
    )
    status = result.scalar_one_or_none()

    if not status:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update status
    old_status = status.update_status
    status.update_status = status_data.update_status
    status.update_progress = status_data.progress
    status.updated_at = datetime.now(dt_timezone.utc)

    if status_data.error_message:
        status.error_message = status_data.error_message

    # Track status transitions
    if old_status != "downloading" and status_data.update_status == "downloading":
        status.update_started_at = datetime.now(dt_timezone.utc)

    if status_data.update_status in ["success", "failed"]:
        status.update_completed_at = datetime.now(dt_timezone.utc)

        # If successful, update current version
        if status_data.update_status == "success" and status.target_version_id:
            result = await db.execute(
                select(FirmwareVersion).where(FirmwareVersion.id == status.target_version_id)
            )
            target_version = result.scalar_one_or_none()
            if target_version:
                old_version = status.current_version
                status.current_version = target_version.version
                status.update_status = "up_to_date"
                status.target_version_id = None

                # Create history record
                history = FirmwareUpdateHistory(
                    device_serial=status_data.device_serial,
                    from_version=old_version,
                    to_version=target_version.version,
                    status="success",
                    started_at=status.update_started_at,
                    completed_at=status.update_completed_at
                )
                db.add(history)

    await db.commit()

    return {"success": True}


# ============================================================================
# Update Campaign Management
# ============================================================================

@router.post("/campaigns", response_model=dict)
async def create_update_campaign(
    campaign_data: CampaignCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a firmware update campaign."""
    # Verify firmware version exists
    result = await db.execute(
        select(FirmwareVersion).where(FirmwareVersion.id == campaign_data.firmware_version_id)
    )
    firmware = result.scalar_one_or_none()
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware version not found")

    # Create campaign
    campaign = FirmwareUpdateCampaign(
        name=campaign_data.name,
        firmware_version_id=campaign_data.firmware_version_id,
        target_devices=campaign_data.target_devices,
        target_filter=campaign_data.target_filter,
        rollout_strategy=campaign_data.rollout_strategy,
        rollout_percentage=campaign_data.rollout_percentage,
        created_by=campaign_data.created_by
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat()
    }


@router.post("/campaigns/{campaign_id}/activate", response_model=dict)
async def activate_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Activate a campaign to start rolling out updates."""
    result = await db.execute(
        select(FirmwareUpdateCampaign).where(FirmwareUpdateCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns can be activated")

    # Determine target devices
    target_devices = []

    if campaign.target_devices:
        # Specific devices specified
        target_devices = campaign.target_devices
    elif campaign.target_filter:
        # Apply filter to find devices
        query = select(DeviceFirmwareStatus)

        if "current_version" in campaign.target_filter:
            query = query.where(DeviceFirmwareStatus.current_version == campaign.target_filter["current_version"])

        result = await db.execute(query)
        devices = result.scalars().all()
        target_devices = [d.device_serial for d in devices]

    # Apply rollout percentage (staged rollout)
    if campaign.rollout_percentage < 100:
        import random
        count = int(len(target_devices) * campaign.rollout_percentage / 100)
        target_devices = random.sample(target_devices, count)

    # Assign target version to devices
    for device_serial in target_devices:
        result = await db.execute(
            select(DeviceFirmwareStatus).where(DeviceFirmwareStatus.device_serial == device_serial)
        )
        status = result.scalar_one_or_none()

        if status:
            status.target_version_id = campaign.firmware_version_id
            status.update_status = "pending"
            status.update_progress = 0
            status.error_message = None
        else:
            # Create new status for device
            status = DeviceFirmwareStatus(
                device_serial=device_serial,
                target_version_id=campaign.firmware_version_id,
                update_status="pending"
            )
            db.add(status)

    # Update campaign status
    campaign.status = "active"
    campaign.started_at = datetime.now(dt_timezone.utc)

    await db.commit()

    return {
        "success": True,
        "target_device_count": len(target_devices),
        "target_devices": target_devices
    }


@router.get("/campaigns/{campaign_id}/status", response_model=dict)
async def get_campaign_status(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get campaign rollout status."""
    # Get campaign
    result = await db.execute(
        select(FirmwareUpdateCampaign).where(FirmwareUpdateCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get device statuses
    result = await db.execute(
        select(DeviceFirmwareStatus).where(DeviceFirmwareStatus.target_version_id == campaign.firmware_version_id)
    )
    devices = result.scalars().all()

    # Count by status
    status_counts = {}
    for device in devices:
        status_counts[device.update_status] = status_counts.get(device.update_status, 0) + 1

    return {
        "campaign_id": str(campaign.id),
        "name": campaign.name,
        "status": campaign.status,
        "total_devices": len(devices),
        "status_breakdown": status_counts,
        "devices": [
            {
                "serial": d.device_serial,
                "current_version": d.current_version,
                "status": d.update_status,
                "progress": d.update_progress,
                "last_check": d.last_check_at.isoformat() if d.last_check_at else None,
                "error": d.error_message
            }
            for d in devices
        ]
    }


@router.get("/devices/status", response_model=List[dict])
async def list_device_firmware_status(
    update_status: Optional[str] = None,
    current_version: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List firmware status of all devices."""
    query = select(DeviceFirmwareStatus)

    if update_status:
        query = query.where(DeviceFirmwareStatus.update_status == update_status)
    if current_version:
        query = query.where(DeviceFirmwareStatus.current_version == current_version)

    result = await db.execute(query)
    devices = result.scalars().all()

    return [
        {
            "device_serial": d.device_serial,
            "current_version": d.current_version,
            "update_status": d.update_status,
            "update_progress": d.update_progress,
            "last_check_at": d.last_check_at.isoformat() if d.last_check_at else None,
            "error_message": d.error_message
        }
        for d in devices
    ]
