# Domain Value Objects - Immutable objects defined by their attributes

from .email import Email
from .phone import PhoneNumber, PhoneType
from .address import Address, GeoLocation
from .money import Money, Currency
from .energy import (
    EnergyReading,
    EnergyUnit,
    PowerReading,
    PowerUnit,
    SolarIrradiance,
)
from .time_range import (
    TimeRange,
    DateRange,
    TimeGranularity,
)

__all__ = [
    # Email
    'Email',
    # Phone
    'PhoneNumber',
    'PhoneType',
    # Address
    'Address',
    'GeoLocation',
    # Money
    'Money',
    'Currency',
    # Energy
    'EnergyReading',
    'EnergyUnit',
    'PowerReading',
    'PowerUnit',
    'SolarIrradiance',
    # Time
    'TimeRange',
    'DateRange',
    'TimeGranularity',
]
