"""
Password hashing implementation using bcrypt.
"""
import bcrypt

from ...application.interfaces.services import PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    """Bcrypt implementation of password hasher."""

    def __init__(self, rounds: int = 12):
        """
        Initialize hasher with work factor.

        Args:
            rounds: Number of bcrypt rounds (default 12, good balance of security/speed)
        """
        self._rounds = rounds

    def hash(self, password: str) -> str:
        """Hash a password using bcrypt."""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=self._rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def verify(self, password: str, hashed: str) -> bool:
        """Verify a password against a hash."""
        try:
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except (ValueError, TypeError):
            return False
