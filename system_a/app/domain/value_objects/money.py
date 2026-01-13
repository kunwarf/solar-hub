"""
Money and Currency value objects for financial calculations.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, Union

from ..exceptions import ValidationException


class Currency(str, Enum):
    """Supported currencies."""
    PKR = "PKR"  # Pakistani Rupee (primary)
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro


@dataclass(frozen=True)
class Money:
    """
    Money value object with currency support.

    Uses Decimal for precise financial calculations.
    Primary currency is PKR (Pakistani Rupee).
    """
    amount: Decimal
    currency: Currency = Currency.PKR

    # Decimal places for each currency
    DECIMAL_PLACES = {
        Currency.PKR: 2,
        Currency.USD: 2,
        Currency.EUR: 2,
    }

    def __post_init__(self) -> None:
        """Validate and normalize money value."""
        # Convert to Decimal if needed
        if not isinstance(self.amount, Decimal):
            try:
                object.__setattr__(self, 'amount', Decimal(str(self.amount)))
            except Exception:
                raise ValidationException(
                    message="Invalid amount",
                    errors={'amount': ['Amount must be a valid number']}
                )

        # Round to appropriate decimal places
        places = self.DECIMAL_PLACES.get(self.currency, 2)
        quantize_str = '0.' + '0' * places
        rounded = self.amount.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'amount', rounded)

    def __add__(self, other: 'Money') -> 'Money':
        """Add two money values."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money to {type(other)}")
        if self.currency != other.currency:
            raise ValidationException(
                message="Currency mismatch",
                errors={'currency': [f"Cannot add {self.currency.value} to {other.currency.value}"]}
            )
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        """Subtract money values."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other)} from Money")
        if self.currency != other.currency:
            raise ValidationException(
                message="Currency mismatch",
                errors={'currency': [f"Cannot subtract {other.currency.value} from {self.currency.value}"]}
            )
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Union[int, float, Decimal]) -> 'Money':
        """Multiply money by a factor."""
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def __truediv__(self, divisor: Union[int, float, Decimal]) -> 'Money':
        """Divide money by a factor."""
        if divisor == 0:
            raise ValidationException(
                message="Division by zero",
                errors={'divisor': ['Cannot divide by zero']}
            )
        return Money(self.amount / Decimal(str(divisor)), self.currency)

    def __lt__(self, other: 'Money') -> bool:
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: 'Money') -> bool:
        self._check_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: 'Money') -> bool:
        self._check_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: 'Money') -> bool:
        self._check_currency(other)
        return self.amount >= other.amount

    def _check_currency(self, other: 'Money') -> None:
        """Ensure same currency for comparison."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money to {type(other)}")
        if self.currency != other.currency:
            raise ValidationException(
                message="Currency mismatch",
                errors={'currency': ['Cannot compare different currencies']}
            )

    @property
    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == Decimal('0')

    @property
    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > Decimal('0')

    @property
    def is_negative(self) -> bool:
        """Check if amount is negative."""
        return self.amount < Decimal('0')

    def abs(self) -> 'Money':
        """Return absolute value."""
        return Money(abs(self.amount), self.currency)

    def negate(self) -> 'Money':
        """Return negated value."""
        return Money(-self.amount, self.currency)

    @property
    def formatted(self) -> str:
        """
        Return formatted string with currency symbol.

        PKR: Rs. 1,234.56
        USD: $1,234.56
        EUR: €1,234.56
        """
        symbols = {
            Currency.PKR: 'Rs.',
            Currency.USD: '$',
            Currency.EUR: '€',
        }
        symbol = symbols.get(self.currency, self.currency.value)

        # Format with thousand separators
        formatted_amount = f"{self.amount:,.2f}"

        if self.currency == Currency.PKR:
            return f"{symbol} {formatted_amount}"
        return f"{symbol}{formatted_amount}"

    def __str__(self) -> str:
        return self.formatted

    def __repr__(self) -> str:
        return f"Money({self.amount}, {self.currency.value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'amount': str(self.amount),
            'currency': self.currency.value,
            'formatted': self.formatted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Money':
        """Create from dictionary."""
        return cls(
            amount=Decimal(str(data.get('amount', 0))),
            currency=Currency(data.get('currency', 'PKR'))
        )

    @classmethod
    def pkr(cls, amount: Union[int, float, Decimal, str]) -> 'Money':
        """Convenience constructor for Pakistani Rupees."""
        return cls(amount=Decimal(str(amount)), currency=Currency.PKR)

    @classmethod
    def zero(cls, currency: Currency = Currency.PKR) -> 'Money':
        """Create a zero money value."""
        return cls(amount=Decimal('0'), currency=currency)
