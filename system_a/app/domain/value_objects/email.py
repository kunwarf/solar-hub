"""
Email value object with validation.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict

from ..exceptions import ValidationException


@dataclass(frozen=True)
class Email:
    """
    Email address value object.

    Immutable and validated on construction.
    """
    value: str

    # RFC 5322 compliant email regex (simplified but practical)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    def __post_init__(self) -> None:
        """Validate email format on construction."""
        if not self.value:
            raise ValidationException(
                message="Email cannot be empty",
                errors={'email': ['Email address is required']}
            )

        # Normalize email (lowercase)
        object.__setattr__(self, 'value', self.value.lower().strip())

        if not self.EMAIL_REGEX.match(self.value):
            raise ValidationException(
                message="Invalid email format",
                errors={'email': [f"'{self.value}' is not a valid email address"]}
            )

        if len(self.value) > 254:
            raise ValidationException(
                message="Email too long",
                errors={'email': ['Email address cannot exceed 254 characters']}
            )

    @property
    def domain(self) -> str:
        """Extract domain from email."""
        return self.value.split('@')[1]

    @property
    def local_part(self) -> str:
        """Extract local part (before @) from email."""
        return self.value.split('@')[0]

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Email('{self.value}')"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {'email': self.value}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Email':
        """Create from dictionary."""
        return cls(value=data.get('email', ''))
