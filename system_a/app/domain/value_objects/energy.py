"""
Energy measurement value objects for solar system metrics.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, Optional, Union

from ..exceptions import ValidationException


class EnergyUnit(str, Enum):
    """Energy measurement units."""
    WH = "Wh"      # Watt-hour
    KWH = "kWh"    # Kilowatt-hour
    MWH = "MWh"    # Megawatt-hour


class PowerUnit(str, Enum):
    """Power measurement units."""
    W = "W"        # Watt
    KW = "kW"      # Kilowatt
    MW = "MW"      # Megawatt


@dataclass(frozen=True)
class EnergyReading:
    """
    Energy measurement value object.

    Represents energy consumed or produced over time.
    """
    value: Decimal
    unit: EnergyUnit = EnergyUnit.KWH

    # Conversion factors to kWh
    TO_KWH = {
        EnergyUnit.WH: Decimal('0.001'),
        EnergyUnit.KWH: Decimal('1'),
        EnergyUnit.MWH: Decimal('1000'),
    }

    def __post_init__(self) -> None:
        """Validate energy reading."""
        if not isinstance(self.value, Decimal):
            try:
                object.__setattr__(self, 'value', Decimal(str(self.value)))
            except Exception:
                raise ValidationException(
                    message="Invalid energy value",
                    errors={'value': ['Energy value must be a valid number']}
                )

        # Round to 3 decimal places
        rounded = self.value.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'value', rounded)

    def to_kwh(self) -> 'EnergyReading':
        """Convert to kilowatt-hours."""
        factor = self.TO_KWH[self.unit]
        return EnergyReading(self.value * factor, EnergyUnit.KWH)

    def to_wh(self) -> 'EnergyReading':
        """Convert to watt-hours."""
        kwh = self.to_kwh()
        return EnergyReading(kwh.value * Decimal('1000'), EnergyUnit.WH)

    def to_mwh(self) -> 'EnergyReading':
        """Convert to megawatt-hours."""
        kwh = self.to_kwh()
        return EnergyReading(kwh.value / Decimal('1000'), EnergyUnit.MWH)

    def __add__(self, other: 'EnergyReading') -> 'EnergyReading':
        """Add energy readings."""
        if not isinstance(other, EnergyReading):
            raise TypeError(f"Cannot add EnergyReading to {type(other)}")
        # Convert both to kWh, add, then return in original unit
        self_kwh = self.to_kwh()
        other_kwh = other.to_kwh()
        return EnergyReading(self_kwh.value + other_kwh.value, EnergyUnit.KWH)

    def __sub__(self, other: 'EnergyReading') -> 'EnergyReading':
        """Subtract energy readings."""
        if not isinstance(other, EnergyReading):
            raise TypeError(f"Cannot subtract {type(other)} from EnergyReading")
        self_kwh = self.to_kwh()
        other_kwh = other.to_kwh()
        return EnergyReading(self_kwh.value - other_kwh.value, EnergyUnit.KWH)

    def __mul__(self, factor: Union[int, float, Decimal]) -> 'EnergyReading':
        """Multiply energy by a factor."""
        return EnergyReading(self.value * Decimal(str(factor)), self.unit)

    def __lt__(self, other: 'EnergyReading') -> bool:
        return self.to_kwh().value < other.to_kwh().value

    def __le__(self, other: 'EnergyReading') -> bool:
        return self.to_kwh().value <= other.to_kwh().value

    def __gt__(self, other: 'EnergyReading') -> bool:
        return self.to_kwh().value > other.to_kwh().value

    def __ge__(self, other: 'EnergyReading') -> bool:
        return self.to_kwh().value >= other.to_kwh().value

    @property
    def formatted(self) -> str:
        """Return formatted string with unit."""
        return f"{self.value:,.3f} {self.unit.value}"

    def __str__(self) -> str:
        return self.formatted

    def __repr__(self) -> str:
        return f"EnergyReading({self.value}, {self.unit.value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'value': str(self.value),
            'unit': self.unit.value,
            'kwh': str(self.to_kwh().value)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnergyReading':
        """Create from dictionary."""
        return cls(
            value=Decimal(str(data.get('value', 0))),
            unit=EnergyUnit(data.get('unit', 'kWh'))
        )

    @classmethod
    def kwh(cls, value: Union[int, float, Decimal, str]) -> 'EnergyReading':
        """Convenience constructor for kWh."""
        return cls(value=Decimal(str(value)), unit=EnergyUnit.KWH)

    @classmethod
    def zero(cls, unit: EnergyUnit = EnergyUnit.KWH) -> 'EnergyReading':
        """Create zero energy reading."""
        return cls(value=Decimal('0'), unit=unit)


@dataclass(frozen=True)
class PowerReading:
    """
    Power measurement value object.

    Represents instantaneous power (energy per unit time).
    """
    value: Decimal
    unit: PowerUnit = PowerUnit.KW

    # Conversion factors to kW
    TO_KW = {
        PowerUnit.W: Decimal('0.001'),
        PowerUnit.KW: Decimal('1'),
        PowerUnit.MW: Decimal('1000'),
    }

    def __post_init__(self) -> None:
        """Validate power reading."""
        if not isinstance(self.value, Decimal):
            try:
                object.__setattr__(self, 'value', Decimal(str(self.value)))
            except Exception:
                raise ValidationException(
                    message="Invalid power value",
                    errors={'value': ['Power value must be a valid number']}
                )

        # Round to 3 decimal places
        rounded = self.value.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'value', rounded)

    def to_kw(self) -> 'PowerReading':
        """Convert to kilowatts."""
        factor = self.TO_KW[self.unit]
        return PowerReading(self.value * factor, PowerUnit.KW)

    def to_w(self) -> 'PowerReading':
        """Convert to watts."""
        kw = self.to_kw()
        return PowerReading(kw.value * Decimal('1000'), PowerUnit.W)

    def to_mw(self) -> 'PowerReading':
        """Convert to megawatts."""
        kw = self.to_kw()
        return PowerReading(kw.value / Decimal('1000'), PowerUnit.MW)

    def energy_over_hours(self, hours: Union[int, float, Decimal]) -> EnergyReading:
        """
        Calculate energy produced/consumed over given hours.

        Energy = Power * Time
        """
        kw = self.to_kw()
        kwh = kw.value * Decimal(str(hours))
        return EnergyReading(kwh, EnergyUnit.KWH)

    def __add__(self, other: 'PowerReading') -> 'PowerReading':
        """Add power readings."""
        if not isinstance(other, PowerReading):
            raise TypeError(f"Cannot add PowerReading to {type(other)}")
        self_kw = self.to_kw()
        other_kw = other.to_kw()
        return PowerReading(self_kw.value + other_kw.value, PowerUnit.KW)

    def __sub__(self, other: 'PowerReading') -> 'PowerReading':
        """Subtract power readings."""
        if not isinstance(other, PowerReading):
            raise TypeError(f"Cannot subtract {type(other)} from PowerReading")
        self_kw = self.to_kw()
        other_kw = other.to_kw()
        return PowerReading(self_kw.value - other_kw.value, PowerUnit.KW)

    def __mul__(self, factor: Union[int, float, Decimal]) -> 'PowerReading':
        """Multiply power by a factor."""
        return PowerReading(self.value * Decimal(str(factor)), self.unit)

    def __lt__(self, other: 'PowerReading') -> bool:
        return self.to_kw().value < other.to_kw().value

    def __le__(self, other: 'PowerReading') -> bool:
        return self.to_kw().value <= other.to_kw().value

    def __gt__(self, other: 'PowerReading') -> bool:
        return self.to_kw().value > other.to_kw().value

    def __ge__(self, other: 'PowerReading') -> bool:
        return self.to_kw().value >= other.to_kw().value

    @property
    def formatted(self) -> str:
        """Return formatted string with unit."""
        return f"{self.value:,.3f} {self.unit.value}"

    def __str__(self) -> str:
        return self.formatted

    def __repr__(self) -> str:
        return f"PowerReading({self.value}, {self.unit.value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'value': str(self.value),
            'unit': self.unit.value,
            'kw': str(self.to_kw().value)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PowerReading':
        """Create from dictionary."""
        return cls(
            value=Decimal(str(data.get('value', 0))),
            unit=PowerUnit(data.get('unit', 'kW'))
        )

    @classmethod
    def kw(cls, value: Union[int, float, Decimal, str]) -> 'PowerReading':
        """Convenience constructor for kW."""
        return cls(value=Decimal(str(value)), unit=PowerUnit.KW)

    @classmethod
    def zero(cls, unit: PowerUnit = PowerUnit.KW) -> 'PowerReading':
        """Create zero power reading."""
        return cls(value=Decimal('0'), unit=unit)


@dataclass(frozen=True)
class SolarIrradiance:
    """
    Solar irradiance value object (W/m²).

    Represents the power per unit area received from the sun.
    """
    value: Decimal  # W/m²

    def __post_init__(self) -> None:
        """Validate irradiance value."""
        if not isinstance(self.value, Decimal):
            try:
                object.__setattr__(self, 'value', Decimal(str(self.value)))
            except Exception:
                raise ValidationException(
                    message="Invalid irradiance value",
                    errors={'value': ['Irradiance value must be a valid number']}
                )

        if self.value < 0:
            raise ValidationException(
                message="Invalid irradiance",
                errors={'value': ['Irradiance cannot be negative']}
            )

        # Round to 1 decimal place
        rounded = self.value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'value', rounded)

    @property
    def is_peak_sun(self) -> bool:
        """Check if this is peak sun hours equivalent (>= 1000 W/m²)."""
        return self.value >= Decimal('1000')

    @property
    def condition(self) -> str:
        """Return weather condition description based on irradiance."""
        if self.value >= Decimal('800'):
            return "Sunny"
        elif self.value >= Decimal('400'):
            return "Partly Cloudy"
        elif self.value >= Decimal('100'):
            return "Cloudy"
        else:
            return "Low Light"

    def __str__(self) -> str:
        return f"{self.value} W/m²"

    def __repr__(self) -> str:
        return f"SolarIrradiance({self.value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'value': str(self.value),
            'unit': 'W/m²',
            'condition': self.condition
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SolarIrradiance':
        """Create from dictionary."""
        return cls(value=Decimal(str(data.get('value', 0))))
