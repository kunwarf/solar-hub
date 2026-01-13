"""
Address and GeoLocation value objects.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..exceptions import ValidationException


@dataclass(frozen=True)
class GeoLocation:
    """
    Geographic coordinates value object.

    Represents a point on Earth with latitude and longitude.
    """
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Validate coordinates."""
        if not -90 <= self.latitude <= 90:
            raise ValidationException(
                message="Invalid latitude",
                errors={'latitude': ['Latitude must be between -90 and 90 degrees']}
            )

        if not -180 <= self.longitude <= 180:
            raise ValidationException(
                message="Invalid longitude",
                errors={'longitude': ['Longitude must be between -180 and 180 degrees']}
            )

    def distance_to(self, other: 'GeoLocation') -> float:
        """
        Calculate distance to another location in kilometers.

        Uses Haversine formula for great-circle distance.
        """
        import math

        R = 6371  # Earth's radius in kilometers

        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        delta_lat = math.radians(other.latitude - self.latitude)
        delta_lon = math.radians(other.longitude - self.longitude)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def __str__(self) -> str:
        return f"{self.latitude}, {self.longitude}"

    def __repr__(self) -> str:
        return f"GeoLocation(lat={self.latitude}, lon={self.longitude})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeoLocation':
        """Create from dictionary."""
        return cls(
            latitude=float(data.get('latitude', 0)),
            longitude=float(data.get('longitude', 0))
        )


@dataclass(frozen=True)
class Address:
    """
    Physical address value object.

    Supports Pakistani address format with optional fields.
    """
    street_address: str
    city: str
    province: str  # For Pakistan: Punjab, Sindh, KPK, Balochistan, etc.
    country: str = "Pakistan"
    postal_code: Optional[str] = None
    district: Optional[str] = None
    area: Optional[str] = None  # Locality/neighborhood
    geo_location: Optional[GeoLocation] = None

    # Major Pakistani cities for validation
    PAKISTAN_CITIES = {
        'karachi', 'lahore', 'faisalabad', 'rawalpindi', 'gujranwala',
        'peshawar', 'multan', 'hyderabad', 'islamabad', 'quetta',
        'bahawalpur', 'sargodha', 'sialkot', 'sukkur', 'larkana',
        'sheikhupura', 'jhang', 'rahim yar khan', 'mardan', 'gujrat',
        'kasur', 'dera ghazi khan', 'sahiwal', 'okara', 'wah cantt'
    }

    # Pakistani provinces
    PAKISTAN_PROVINCES = {
        'punjab', 'sindh', 'khyber pakhtunkhwa', 'kpk', 'balochistan',
        'gilgit-baltistan', 'azad kashmir', 'islamabad capital territory', 'ict'
    }

    def __post_init__(self) -> None:
        """Validate address."""
        if not self.street_address or not self.street_address.strip():
            raise ValidationException(
                message="Street address is required",
                errors={'street_address': ['Street address cannot be empty']}
            )

        if not self.city or not self.city.strip():
            raise ValidationException(
                message="City is required",
                errors={'city': ['City cannot be empty']}
            )

        if not self.province or not self.province.strip():
            raise ValidationException(
                message="Province is required",
                errors={'province': ['Province cannot be empty']}
            )

    @property
    def is_pakistani_address(self) -> bool:
        """Check if this is a Pakistani address."""
        return self.country.lower() == 'pakistan'

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.street_address]

        if self.area:
            parts.append(self.area)

        parts.append(self.city)

        if self.district and self.district.lower() != self.city.lower():
            parts.append(self.district)

        parts.append(self.province)

        if self.postal_code:
            parts.append(self.postal_code)

        parts.append(self.country)

        return ', '.join(parts)

    @property
    def short_address(self) -> str:
        """Return shortened address for display."""
        return f"{self.city}, {self.province}"

    def __str__(self) -> str:
        return self.full_address

    def __repr__(self) -> str:
        return f"Address(city='{self.city}', province='{self.province}')"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            'street_address': self.street_address,
            'city': self.city,
            'province': self.province,
            'country': self.country,
        }

        if self.postal_code:
            result['postal_code'] = self.postal_code
        if self.district:
            result['district'] = self.district
        if self.area:
            result['area'] = self.area
        if self.geo_location:
            result['geo_location'] = self.geo_location.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Address':
        """Create from dictionary."""
        geo_data = data.get('geo_location')
        geo_location = GeoLocation.from_dict(geo_data) if geo_data else None

        return cls(
            street_address=data.get('street_address', ''),
            city=data.get('city', ''),
            province=data.get('province', ''),
            country=data.get('country', 'Pakistan'),
            postal_code=data.get('postal_code'),
            district=data.get('district'),
            area=data.get('area'),
            geo_location=geo_location
        )
