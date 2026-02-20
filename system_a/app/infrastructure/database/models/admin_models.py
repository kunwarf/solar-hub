"""
SQLAlchemy models for admin portal entities.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from .base import BaseModel
from ....domain.entities.admin import (
    AdminAuditLog,
    ElectricityProvider,
    ElectricityTariff,
    LoadSheddingSchedule,
    ProviderStatus,
    TariffCategory,
    TariffStatus,
    TariffType,
)


class ElectricityProviderModel(BaseModel):
    """SQLAlchemy model for electricity_providers table."""

    __tablename__ = "electricity_providers"

    name = Column(String(200), nullable=False)
    short_name = Column(String(20), nullable=False, index=True)
    region = Column(String(100), nullable=False, index=True)
    status = Column(
        Enum(ProviderStatus, name="provider_status", values_callable=lambda e: [x.value for x in e]),
        default=ProviderStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    tariff_count = Column(Float, default=0, nullable=False)

    def to_domain(self) -> ElectricityProvider:
        provider = ElectricityProvider(
            id=self.id,
            name=self.name,
            short_name=self.short_name,
            region=self.region,
            status=self.status,
            tariff_count=int(self.tariff_count or 0),
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )
        provider._domain_events = []
        return provider

    @classmethod
    def from_domain(cls, provider: ElectricityProvider) -> "ElectricityProviderModel":
        return cls(
            id=provider.id,
            name=provider.name,
            short_name=provider.short_name,
            region=provider.region,
            status=provider.status,
            tariff_count=provider.tariff_count,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            version=provider.version,
        )

    def update_from_domain(self, provider: ElectricityProvider) -> None:
        self.name = provider.name
        self.short_name = provider.short_name
        self.region = provider.region
        self.status = provider.status
        self.tariff_count = provider.tariff_count
        self.updated_at = provider.updated_at
        self.version = provider.version


class ElectricityTariffModel(BaseModel):
    """SQLAlchemy model for electricity_tariffs table."""

    __tablename__ = "electricity_tariffs"

    provider_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("electricity_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    category = Column(
        Enum(TariffCategory, name="tariff_category", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        index=True,
    )
    type = Column(
        Enum(TariffType, name="tariff_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    rates = Column(JSONB, nullable=False)
    fixed_charges = Column(Float, default=0.0, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    status = Column(
        Enum(TariffStatus, name="tariff_status", values_callable=lambda e: [x.value for x in e]),
        default=TariffStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=True)

    def to_domain(self) -> ElectricityTariff:
        tariff = ElectricityTariff(
            id=self.id,
            provider_id=self.provider_id,
            name=self.name,
            category=self.category,
            type=self.type,
            rates=self.rates or {},
            fixed_charges=float(self.fixed_charges or 0.0),
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            status=self.status,
            description=self.description,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )
        tariff._domain_events = []
        return tariff

    @classmethod
    def from_domain(cls, tariff: ElectricityTariff) -> "ElectricityTariffModel":
        return cls(
            id=tariff.id,
            provider_id=tariff.provider_id,
            name=tariff.name,
            category=tariff.category,
            type=tariff.type,
            rates=tariff.rates,
            fixed_charges=tariff.fixed_charges,
            effective_from=tariff.effective_from,
            effective_to=tariff.effective_to,
            status=tariff.status,
            description=tariff.description,
            created_at=tariff.created_at,
            updated_at=tariff.updated_at,
            version=tariff.version,
        )

    def update_from_domain(self, tariff: ElectricityTariff) -> None:
        self.name = tariff.name
        self.category = tariff.category
        self.type = tariff.type
        self.rates = tariff.rates
        self.fixed_charges = tariff.fixed_charges
        self.effective_from = tariff.effective_from
        self.effective_to = tariff.effective_to
        self.status = tariff.status
        self.description = tariff.description
        self.updated_at = tariff.updated_at
        self.version = tariff.version


class LoadSheddingScheduleModel(BaseModel):
    """SQLAlchemy model for load_shedding_schedules table."""

    __tablename__ = "load_shedding_schedules"

    area_name = Column(String(200), nullable=False)
    region = Column(String(100), nullable=False, index=True)
    feeder_code = Column(String(50), nullable=True, index=True)
    schedule = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)

    def to_domain(self) -> LoadSheddingSchedule:
        sched = LoadSheddingSchedule(
            id=self.id,
            area_name=self.area_name,
            region=self.region,
            feeder_code=self.feeder_code,
            schedule=self.schedule or {},
            is_active=self.is_active,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )
        sched._domain_events = []
        return sched

    @classmethod
    def from_domain(cls, sched: LoadSheddingSchedule) -> "LoadSheddingScheduleModel":
        return cls(
            id=sched.id,
            area_name=sched.area_name,
            region=sched.region,
            feeder_code=sched.feeder_code,
            schedule=sched.schedule,
            is_active=sched.is_active,
            effective_from=sched.effective_from,
            effective_to=sched.effective_to,
            created_at=sched.created_at,
            updated_at=sched.updated_at,
            version=sched.version,
        )

    def update_from_domain(self, sched: LoadSheddingSchedule) -> None:
        self.area_name = sched.area_name
        self.region = sched.region
        self.feeder_code = sched.feeder_code
        self.schedule = sched.schedule
        self.is_active = sched.is_active
        self.effective_from = sched.effective_from
        self.effective_to = sched.effective_to
        self.updated_at = sched.updated_at
        self.version = sched.version


class AdminAuditLogModel(BaseModel):
    """SQLAlchemy model for admin_audit_logs table."""

    __tablename__ = "admin_audit_logs"

    admin_user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    admin_email = Column(String(254), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)   # max IPv6 length
    user_agent = Column(Text, nullable=True)

    def to_domain(self) -> AdminAuditLog:
        log = AdminAuditLog(
            id=self.id,
            admin_user_id=self.admin_user_id,
            admin_email=self.admin_email,
            action=self.action,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            old_values=self.old_values,
            new_values=self.new_values,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )
        log._domain_events = []
        return log

    @classmethod
    def from_domain(cls, log: AdminAuditLog) -> "AdminAuditLogModel":
        return cls(
            id=log.id,
            admin_user_id=log.admin_user_id,
            admin_email=log.admin_email,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            old_values=log.old_values,
            new_values=log.new_values,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at,
            version=log.version,
        )
