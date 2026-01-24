"""
User registration service with organization, site, and device setup.
"""
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ..interfaces.repositories import UserRepository
from ..interfaces.services import PasswordHasher, TokenService, EventPublisher
from ..interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserStatus, UserRole, UserPreferences
from ...domain.entities.organization import Organization
from ...domain.entities.site import Site, SiteType, SiteStatus
from ...domain.value_objects.address import Address
from ...domain.events.user_events import UserCreated
from ...infrastructure.external.system_b_client import (
    SystemBClient,
    DeviceInfo,
    DeviceNotFoundError,
    DeviceAlreadyClaimedError,
    SystemBClientError,
)

logger = logging.getLogger(__name__)


@dataclass
class RegistrationRequest:
    """User registration request data."""
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    device_serial: Optional[str] = None


@dataclass
class SiteInfo:
    """Site information in registration response."""
    id: UUID
    name: str
    is_default: bool = True


@dataclass
class DeviceClaimInfo:
    """Device claim information in registration response."""
    id: UUID
    serial_number: str
    device_type: str
    manufacturer: Optional[str] = None
    status: str = "claimed"


@dataclass
class RegistrationResult:
    """Result of user registration."""
    success: bool
    user: Optional[User] = None
    organization_id: Optional[UUID] = None
    site: Optional[SiteInfo] = None
    device: Optional[DeviceClaimInfo] = None
    error: Optional[str] = None
    device_error: Optional[str] = None


class RegistrationService:
    """
    Service for handling user registration with full setup.

    Orchestrates:
    1. User account creation
    2. Default organization creation
    3. Default site ("My Home") creation
    4. Device claiming (if device_serial provided)
    """

    DEFAULT_SITE_NAME = "My Home"
    DEFAULT_ORG_NAME_TEMPLATE = "{first_name}'s Organization"

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        system_b_client: SystemBClient,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._system_b_client = system_b_client
        self._event_publisher = event_publisher

    async def register(
        self,
        request: RegistrationRequest,
        uow: UnitOfWork,
    ) -> RegistrationResult:
        """
        Register a new user with full setup.

        Steps:
        1. Validate email is not taken
        2. If device_serial provided, verify device exists and is orphan
        3. Create user account
        4. Create default organization
        5. Create default site
        6. Claim device if provided
        7. Publish events

        Args:
            request: Registration data
            uow: Unit of work for transaction management

        Returns:
            RegistrationResult with user, site, and optionally device info
        """
        # 1. Check if email already exists
        existing = await self._user_repository.get_by_email(request.email.lower().strip())
        if existing:
            return RegistrationResult(
                success=False,
                error="Email address is already registered"
            )

        # 2. If device_serial provided, verify device exists in System B
        device_info: Optional[DeviceInfo] = None
        device_error: Optional[str] = None

        if request.device_serial:
            try:
                device_info = await self._system_b_client.get_device_by_serial(request.device_serial)
                if device_info is None:
                    # Device not found - we'll continue registration but warn user
                    device_error = f"Device with serial '{request.device_serial}' not found. You can add it later."
                    logger.warning("Device not found during registration: %s", request.device_serial)
                elif device_info.is_claimed:
                    # Device already claimed
                    device_error = f"Device '{request.device_serial}' is already claimed by another user."
                    device_info = None
                    logger.warning("Device already claimed during registration: %s", request.device_serial)
            except SystemBClientError as e:
                # System B connection error - continue registration but warn
                device_error = "Could not verify device. You can add it later."
                device_info = None
                logger.error("System B error during registration: %s", e)

        # 3. Hash password and create user
        password_hash = self._password_hasher.hash(request.password)

        user = User(
            email=request.email.lower().strip(),
            phone=request.phone,
            password_hash=password_hash,
            first_name=request.first_name.strip(),
            last_name=request.last_name.strip(),
            status=UserStatus.PENDING_VERIFICATION,
            role=UserRole.OWNER,  # First user becomes owner
            preferences=UserPreferences(),
        )

        user.add_domain_event(UserCreated(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        ))

        saved_user = await uow.users.add(user)

        # 4. Create default organization
        org_name = self.DEFAULT_ORG_NAME_TEMPLATE.format(first_name=request.first_name.strip())
        organization = Organization.create(
            name=org_name,
            owner_id=saved_user.id,
            description=f"Personal organization for {saved_user.first_name} {saved_user.last_name}",
        )

        saved_org = await uow.organizations.add(organization)

        # 5. Create default site
        default_address = Address(
            street_address="To be updated",
            city="Lahore",  # Default city
            province="Punjab",
            country="Pakistan",
        )

        site = Site.create(
            organization_id=saved_org.id,
            name=self.DEFAULT_SITE_NAME,
            address=default_address,
            site_type=SiteType.RESIDENTIAL,
            timezone="Asia/Karachi",
        )
        # Set site status to pending_setup
        site.status = SiteStatus.PENDING_SETUP

        saved_site = await uow.sites.add(site)

        # Commit the transaction for user, org, and site
        await uow.commit()

        # 6. Claim device if valid device_info was found
        claimed_device: Optional[DeviceClaimInfo] = None

        if device_info and not device_info.is_claimed:
            try:
                claimed_device_info = await self._system_b_client.claim_device(
                    device_id=device_info.id,
                    owner_id=saved_user.id,
                    site_id=saved_site.id,
                    organization_id=saved_org.id,
                )
                claimed_device = DeviceClaimInfo(
                    id=claimed_device_info.id,
                    serial_number=claimed_device_info.serial_number,
                    device_type=claimed_device_info.device_type,
                    manufacturer=claimed_device_info.manufacturer,
                    status="claimed",
                )
                logger.info(
                    "Device claimed during registration: serial=%s, user=%s",
                    request.device_serial,
                    saved_user.email
                )
            except DeviceAlreadyClaimedError:
                device_error = f"Device '{request.device_serial}' was claimed by another user just now."
                logger.warning("Race condition: device claimed during registration: %s", request.device_serial)
            except SystemBClientError as e:
                device_error = "Could not claim device. You can try again later."
                logger.error("Failed to claim device during registration: %s", e)

        # 7. Publish events
        if self._event_publisher:
            for event in saved_user.clear_domain_events():
                await self._event_publisher.publish(event)
            for event in saved_org.clear_domain_events():
                await self._event_publisher.publish(event)
            for event in saved_site.clear_domain_events():
                await self._event_publisher.publish(event)

        return RegistrationResult(
            success=True,
            user=saved_user,
            organization_id=saved_org.id,
            site=SiteInfo(
                id=saved_site.id,
                name=saved_site.name,
                is_default=True,
            ),
            device=claimed_device,
            device_error=device_error,
        )

    async def claim_device_for_user(
        self,
        user_id: UUID,
        site_id: UUID,
        organization_id: UUID,
        device_serial: str,
    ) -> tuple[Optional[DeviceClaimInfo], Optional[str]]:
        """
        Claim a device for an existing user.

        Args:
            user_id: User UUID
            site_id: Site UUID to attach device to
            organization_id: Organization UUID
            device_serial: Device serial number

        Returns:
            Tuple of (DeviceClaimInfo, error_message)
        """
        try:
            # Get device by serial
            device_info = await self._system_b_client.get_device_by_serial(device_serial)

            if device_info is None:
                return None, f"Device with serial '{device_serial}' not found"

            if device_info.is_claimed:
                return None, f"Device '{device_serial}' is already claimed"

            # Claim the device
            claimed_info = await self._system_b_client.claim_device(
                device_id=device_info.id,
                owner_id=user_id,
                site_id=site_id,
                organization_id=organization_id,
            )

            return DeviceClaimInfo(
                id=claimed_info.id,
                serial_number=claimed_info.serial_number,
                device_type=claimed_info.device_type,
                manufacturer=claimed_info.manufacturer,
                status="claimed",
            ), None

        except DeviceNotFoundError:
            return None, f"Device with serial '{device_serial}' not found"
        except DeviceAlreadyClaimedError:
            return None, f"Device '{device_serial}' is already claimed"
        except SystemBClientError as e:
            logger.error("Failed to claim device: %s", e)
            return None, "Could not claim device. Please try again later."

    async def get_orphan_devices(self) -> list[DeviceClaimInfo]:
        """
        Get all orphan devices available for claiming.

        Returns:
            List of DeviceClaimInfo for orphan devices
        """
        try:
            devices = await self._system_b_client.get_orphan_devices()
            return [
                DeviceClaimInfo(
                    id=d.id,
                    serial_number=d.serial_number,
                    device_type=d.device_type,
                    manufacturer=d.manufacturer,
                    status="orphan",
                )
                for d in devices
            ]
        except SystemBClientError as e:
            logger.error("Failed to get orphan devices: %s", e)
            return []
