"""
Phone number value object with Pakistan-specific validation support.
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from ..exceptions import ValidationException


class PhoneType(str, Enum):
    """Types of phone numbers."""
    MOBILE = "mobile"
    LANDLINE = "landline"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PhoneNumber:
    """
    Phone number value object with Pakistan-specific support.

    Supports Pakistani mobile formats:
    - 03XX-XXXXXXX (local format)
    - +923XX-XXXXXXX (international format)
    - 923XX-XXXXXXX (without plus)
    """
    number: str
    country_code: str = "+92"  # Default to Pakistan

    # Pakistani mobile number patterns
    PK_MOBILE_REGEX = re.compile(r'^(?:\+?92|0)?3[0-9]{9}$')

    # Generic international format
    INTERNATIONAL_REGEX = re.compile(r'^\+?[1-9]\d{6,14}$')

    def __post_init__(self) -> None:
        """Validate and normalize phone number."""
        if not self.number:
            raise ValidationException(
                message="Phone number cannot be empty",
                errors={'phone': ['Phone number is required']}
            )

        # Remove spaces, dashes, and parentheses
        cleaned = re.sub(r'[\s\-\(\)]+', '', self.number)
        object.__setattr__(self, 'number', cleaned)

        # Validate format
        if not self._is_valid():
            raise ValidationException(
                message="Invalid phone number format",
                errors={'phone': [f"'{self.number}' is not a valid phone number"]}
            )

    def _is_valid(self) -> bool:
        """Check if phone number is valid."""
        # Check Pakistani mobile format first
        if self.country_code == "+92":
            return bool(self.PK_MOBILE_REGEX.match(self.number))
        # Fall back to generic international format
        return bool(self.INTERNATIONAL_REGEX.match(self.number))

    @property
    def normalized(self) -> str:
        """
        Return fully normalized international format.

        For Pakistani numbers: +923XXXXXXXXX
        """
        number = self.number

        # Handle Pakistani numbers
        if self.country_code == "+92":
            # Remove leading 0 if present
            if number.startswith('0'):
                number = number[1:]
            # Remove +92 or 92 prefix if present
            if number.startswith('+92'):
                number = number[3:]
            elif number.startswith('92'):
                number = number[2:]

            return f"+92{number}"

        # For other countries, ensure + prefix
        if not number.startswith('+'):
            return f"+{number}"
        return number

    @property
    def phone_type(self) -> PhoneType:
        """Determine phone type (mobile/landline)."""
        normalized = self.normalized

        # Pakistani mobile numbers start with +923
        if normalized.startswith('+923'):
            return PhoneType.MOBILE

        # Pakistani landline patterns (simplified)
        if normalized.startswith('+9221') or normalized.startswith('+9242'):
            return PhoneType.LANDLINE

        return PhoneType.UNKNOWN

    @property
    def display_format(self) -> str:
        """
        Return human-readable format.

        For Pakistani: 03XX-XXX-XXXX
        """
        normalized = self.normalized

        if normalized.startswith('+92') and len(normalized) == 13:
            # Pakistani format: 03XX-XXX-XXXX
            local = '0' + normalized[3:]
            return f"{local[:4]}-{local[4:7]}-{local[7:]}"

        return normalized

    def __str__(self) -> str:
        return self.normalized

    def __repr__(self) -> str:
        return f"PhoneNumber('{self.normalized}')"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'number': self.normalized,
            'country_code': self.country_code,
            'phone_type': self.phone_type.value,
            'display': self.display_format
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhoneNumber':
        """Create from dictionary."""
        return cls(
            number=data.get('number', ''),
            country_code=data.get('country_code', '+92')
        )

    @classmethod
    def pakistan(cls, number: str) -> 'PhoneNumber':
        """Convenience constructor for Pakistani numbers."""
        return cls(number=number, country_code="+92")
