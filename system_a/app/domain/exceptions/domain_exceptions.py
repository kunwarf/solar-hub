"""
Domain Exceptions - Custom exceptions for domain-specific errors.
"""
from typing import Any, Dict, Optional
from uuid import UUID


class DomainException(Exception):
    """
    Base exception for all domain-related errors.

    All domain exceptions should inherit from this class to allow
    for consistent error handling across the application.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.code,
            'message': self.message,
            'details': self.details
        }


class EntityNotFoundException(DomainException):
    """Raised when a requested entity cannot be found."""

    def __init__(
        self,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        message: Optional[str] = None
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        msg = message or f"{entity_type} not found"
        if entity_id:
            msg = f"{entity_type} with id '{entity_id}' not found"
        super().__init__(
            message=msg,
            code='ENTITY_NOT_FOUND',
            details={'entity_type': entity_type, 'entity_id': str(entity_id) if entity_id else None}
        )


class ValidationException(DomainException):
    """
    Raised when domain validation fails.

    Can contain multiple validation errors for different fields.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[Dict[str, list]] = None
    ):
        self.errors = errors or {}
        super().__init__(
            message=message,
            code='VALIDATION_ERROR',
            details={'validation_errors': self.errors}
        )

    def add_error(self, field: str, error: str) -> None:
        """Add a validation error for a specific field."""
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(error)
        self.details['validation_errors'] = self.errors


class AuthorizationException(DomainException):
    """Raised when user lacks permission for an operation."""

    def __init__(
        self,
        message: str = "Not authorized to perform this action",
        required_permission: Optional[str] = None,
        resource: Optional[str] = None
    ):
        details = {}
        if required_permission:
            details['required_permission'] = required_permission
        if resource:
            details['resource'] = resource
        super().__init__(
            message=message,
            code='NOT_AUTHORIZED',
            details=details
        )


class BusinessRuleViolationException(DomainException):
    """
    Raised when a business rule is violated.

    Used for domain invariant violations that are not simple validations.
    """

    def __init__(
        self,
        rule: str,
        message: Optional[str] = None
    ):
        self.rule = rule
        super().__init__(
            message=message or f"Business rule violated: {rule}",
            code='BUSINESS_RULE_VIOLATION',
            details={'rule': rule}
        )


class ConcurrencyException(DomainException):
    """Raised when optimistic locking fails due to concurrent modifications."""

    def __init__(
        self,
        entity_type: str,
        entity_id: UUID,
        expected_version: int,
        actual_version: int
    ):
        super().__init__(
            message=f"Concurrent modification detected for {entity_type} '{entity_id}'",
            code='CONCURRENCY_ERROR',
            details={
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'expected_version': expected_version,
                'actual_version': actual_version
            }
        )


class DuplicateEntityException(DomainException):
    """Raised when attempting to create an entity that already exists."""

    def __init__(
        self,
        entity_type: str,
        field: str,
        value: Any
    ):
        super().__init__(
            message=f"{entity_type} with {field}='{value}' already exists",
            code='DUPLICATE_ENTITY',
            details={
                'entity_type': entity_type,
                'field': field,
                'value': str(value)
            }
        )


class InvalidStateTransitionException(DomainException):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        entity_type: str,
        current_state: str,
        target_state: str,
        message: Optional[str] = None
    ):
        msg = message or f"Cannot transition {entity_type} from '{current_state}' to '{target_state}'"
        super().__init__(
            message=msg,
            code='INVALID_STATE_TRANSITION',
            details={
                'entity_type': entity_type,
                'current_state': current_state,
                'target_state': target_state
            }
        )


class QuotaExceededException(DomainException):
    """Raised when a resource quota is exceeded."""

    def __init__(
        self,
        resource: str,
        limit: int,
        current: int,
        message: Optional[str] = None
    ):
        msg = message or f"{resource} quota exceeded (limit: {limit}, current: {current})"
        super().__init__(
            message=msg,
            code='QUOTA_EXCEEDED',
            details={
                'resource': resource,
                'limit': limit,
                'current': current
            }
        )


class ExternalServiceException(DomainException):
    """Raised when an external service call fails."""

    def __init__(
        self,
        service: str,
        message: str,
        original_error: Optional[str] = None
    ):
        super().__init__(
            message=f"External service error ({service}): {message}",
            code='EXTERNAL_SERVICE_ERROR',
            details={
                'service': service,
                'original_error': original_error
            }
        )
