"""
OTA Firmware Management CLI Tool.

Utility script for managing firmware updates from command line.

Usage:
    python -m system_b.scripts.ota_manager upload --version 1.2.0 --files main.py,config.py
    python -m system_b.scripts.ota_manager deploy --version 1.2.0 --devices all
    python -m system_b.scripts.ota_manager status --campaign <campaign-id>
"""
import asyncio
import argparse
import sys
from pathlib import Path
from typing import List
import hashlib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from system_b.app.infrastructure.database.session import get_db_context
from system_b.app.infrastructure.database.models.firmware import (
    FirmwareVersion, FirmwareFile, DeviceFirmwareStatus, FirmwareUpdateCampaign
)
from sqlalchemy import select


async def create_firmware_version(version: str, description: str = None):
    """Create a new firmware version."""
    async with get_db_context() as db:
        # Check if exists
        result = await db.execute(
            select(FirmwareVersion).where(FirmwareVersion.version == version)
        )
        if result.scalar_one_or_none():
            print(f"❌ Version {version} already exists")
            return None

        # Create
        firmware = FirmwareVersion(
            version=version,
            description=description,
            device_type="datalogger"
        )
        db.add(firmware)
        await db.commit()
        await db.refresh(firmware)

        print(f"✅ Created firmware version: {version} (ID: {firmware.id})")
        return firmware.id


async def upload_files(version_id: str, file_paths: List[str]):
    """Upload files to firmware version."""
    async with get_db_context() as db:
        # Verify version exists
        result = await db.execute(
            select(FirmwareVersion).where(FirmwareVersion.id == version_id)
        )
        firmware = result.scalar_one_or_none()
        if not firmware:
            print(f"❌ Firmware version {version_id} not found")
            return False

        print(f"\\nUploading files to version {firmware.version}...")

        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            if not file_path.exists():
                print(f"⚠️  Skipping {file_path.name} - not found")
                continue

            # Read file
            content = file_path.read_text()
            checksum = hashlib.sha256(content.encode()).hexdigest()

            # Determine file type
            if file_path.suffix == ".py":
                file_type = "python"
            elif file_path.suffix == ".json":
                file_type = "config"
            else:
                file_type = "text"

            # Create file record
            firmware_file = FirmwareFile(
                firmware_version_id=firmware.id,
                filename=file_path.name,
                content=content,
                file_size=len(content),
                checksum=checksum,
                file_type=file_type,
                is_required=True
            )
            db.add(firmware_file)

            print(f"  ✅ {file_path.name} ({len(content)} bytes, {checksum[:8]}...)")

        await db.commit()
        print(f"\\n✅ Uploaded {len(file_paths)} files")
        return True


async def create_campaign(name: str, version: str, devices: List[str] = None, rollout_percentage: int = 100):
    """Create an update campaign."""
    async with get_db_context() as db:
        # Find firmware version
        result = await db.execute(
            select(FirmwareVersion).where(FirmwareVersion.version == version)
        )
        firmware = result.scalar_one_or_none()
        if not firmware:
            print(f"❌ Firmware version {version} not found")
            return None

        # Create campaign
        campaign = FirmwareUpdateCampaign(
            name=name,
            firmware_version_id=firmware.id,
            target_devices=devices if devices and devices != ["all"] else None,
            rollout_strategy="immediate" if rollout_percentage == 100 else "staged",
            rollout_percentage=rollout_percentage
        )
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)

        print(f"✅ Created campaign: {name} (ID: {campaign.id})")
        print(f"   Version: {version}")
        print(f"   Rollout: {rollout_percentage}%")
        return campaign.id


async def activate_campaign(campaign_id: str):
    """Activate a campaign to start rollout."""
    async with get_db_context() as db:
        # Get campaign
        result = await db.execute(
            select(FirmwareUpdateCampaign).where(FirmwareUpdateCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            print(f"❌ Campaign {campaign_id} not found")
            return False

        # Find target devices
        target_devices = []

        if campaign.target_devices:
            target_devices = campaign.target_devices
        else:
            # Get all devices
            result = await db.execute(select(DeviceFirmwareStatus))
            devices = result.scalars().all()
            target_devices = [d.device_serial for d in devices]

        # Apply rollout percentage
        if campaign.rollout_percentage < 100:
            import random
            count = int(len(target_devices) * campaign.rollout_percentage / 100)
            target_devices = random.sample(target_devices, count)

        # Assign to devices
        for device_serial in target_devices:
            result = await db.execute(
                select(DeviceFirmwareStatus).where(DeviceFirmwareStatus.device_serial == device_serial)
            )
            status = result.scalar_one_or_none()

            if status:
                status.target_version_id = campaign.firmware_version_id
                status.update_status = "pending"
                status.update_progress = 0
            else:
                status = DeviceFirmwareStatus(
                    device_serial=device_serial,
                    target_version_id=campaign.firmware_version_id,
                    update_status="pending"
                )
                db.add(status)

        # Activate campaign
        from datetime import datetime, timezone
        campaign.status = "active"
        campaign.started_at = datetime.now(timezone.utc)

        await db.commit()

        print(f"✅ Campaign activated!")
        print(f"   Target devices: {len(target_devices)}")
        print(f"   Devices: {', '.join(target_devices[:5])}{'...' if len(target_devices) > 5 else ''}")
        return True


async def show_campaign_status(campaign_id: str):
    """Show campaign status."""
    async with get_db_context() as db:
        # Get campaign
        result = await db.execute(
            select(FirmwareUpdateCampaign).where(FirmwareUpdateCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            print(f"❌ Campaign {campaign_id} not found")
            return

        # Get firmware version
        result = await db.execute(
            select(FirmwareVersion).where(FirmwareVersion.id == campaign.firmware_version_id)
        )
        firmware = result.scalar_one_or_none()

        print(f"\\n📊 Campaign: {campaign.name}")
        print(f"   ID: {campaign.id}")
        print(f"   Status: {campaign.status}")
        print(f"   Version: {firmware.version if firmware else 'Unknown'}")
        print(f"   Created: {campaign.created_at}")

        # Get device statuses
        result = await db.execute(
            select(DeviceFirmwareStatus).where(DeviceFirmwareStatus.target_version_id == campaign.firmware_version_id)
        )
        devices = result.scalars().all()

        # Count by status
        status_counts = {}
        for device in devices:
            status_counts[device.update_status] = status_counts.get(device.update_status, 0) + 1

        print(f"\\n   Total devices: {len(devices)}")
        for status, count in status_counts.items():
            print(f"   - {status}: {count}")

        print(f"\\n   Device Details:")
        for device in devices[:10]:  # Show first 10
            print(f"   - {device.device_serial}: {device.update_status} ({device.update_progress}%)")
            if device.error_message:
                print(f"     Error: {device.error_message}")

        if len(devices) > 10:
            print(f"   ... and {len(devices) - 10} more")


async def list_versions():
    """List all firmware versions."""
    async with get_db_context() as db:
        result = await db.execute(
            select(FirmwareVersion).order_by(FirmwareVersion.created_at.desc())
        )
        versions = result.scalars().all()

        print(f"\\n📦 Firmware Versions ({len(versions)}):")
        for v in versions:
            print(f"\\n   Version: {v.version} {'✅' if v.is_active else '❌'}")
            print(f"   ID: {v.id}")
            print(f"   Files: {len(v.files)}")
            print(f"   Created: {v.created_at}")
            if v.description:
                print(f"   Description: {v.description}")


async def list_devices():
    """List all device firmware statuses."""
    async with get_db_context() as db:
        result = await db.execute(select(DeviceFirmwareStatus))
        devices = result.scalars().all()

        print(f"\\n📱 Device Firmware Status ({len(devices)}):")
        for d in devices:
            print(f"\\n   Serial: {d.device_serial}")
            print(f"   Version: {d.current_version or 'Unknown'}")
            print(f"   Status: {d.update_status}")
            if d.last_check_at:
                print(f"   Last Check: {d.last_check_at}")
            if d.error_message:
                print(f"   Error: {d.error_message}")


def main():
    parser = argparse.ArgumentParser(description="OTA Firmware Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload firmware files")
    upload_parser.add_argument("--version", required=True, help="Version string")
    upload_parser.add_argument("--description", help="Version description")
    upload_parser.add_argument("--files", required=True, help="Comma-separated file paths")

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy firmware update")
    deploy_parser.add_argument("--version", required=True, help="Version to deploy")
    deploy_parser.add_argument("--name", required=True, help="Campaign name")
    deploy_parser.add_argument("--devices", help="Comma-separated device serials, or 'all'")
    deploy_parser.add_argument("--rollout", type=int, default=100, help="Rollout percentage (1-100)")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show campaign status")
    status_parser.add_argument("--campaign", required=True, help="Campaign ID")

    # List command
    list_parser = subparsers.add_parser("list", help="List versions or devices")
    list_parser.add_argument("type", choices=["versions", "devices"], help="What to list")

    args = parser.parse_args()

    if args.command == "upload":
        # Create version and upload files
        version_id = asyncio.run(create_firmware_version(args.version, args.description))
        if version_id:
            file_paths = args.files.split(",")
            asyncio.run(upload_files(str(version_id), file_paths))

    elif args.command == "deploy":
        # Create and activate campaign
        devices = args.devices.split(",") if args.devices else ["all"]
        campaign_id = asyncio.run(create_campaign(args.name, args.version, devices, args.rollout))
        if campaign_id:
            asyncio.run(activate_campaign(str(campaign_id)))

    elif args.command == "status":
        asyncio.run(show_campaign_status(args.campaign))

    elif args.command == "list":
        if args.type == "versions":
            asyncio.run(list_versions())
        elif args.type == "devices":
            asyncio.run(list_devices())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
