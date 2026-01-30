"""
Register management system.

Provides register metadata, categorization, validation, and management
for device configuration registers.
"""
from .register_metadata import (
    RegisterGroup,
    RegisterCriticality,
    RegisterValidation,
    RegisterMetadata,
    RegisterMetadataRegistry,
    get_register_metadata_registry,
)

__all__ = [
    "RegisterGroup",
    "RegisterCriticality",
    "RegisterValidation",
    "RegisterMetadata",
    "RegisterMetadataRegistry",
    "get_register_metadata_registry",
]
