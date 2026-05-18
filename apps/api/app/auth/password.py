from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


class PasswordPolicyError(ValueError):
    """비밀번호 정책 위반."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise PasswordPolicyError("MIN_LENGTH")
    if not any(ch.isalpha() for ch in password):
        raise PasswordPolicyError("MISSING_LETTER")
    if not any(ch.isdigit() for ch in password):
        raise PasswordPolicyError("MISSING_DIGIT")
