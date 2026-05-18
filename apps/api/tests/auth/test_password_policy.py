import pytest

from app.auth.password import PasswordPolicyError, validate_password_policy


def test_strong_password_passes():
    validate_password_policy("abcd1234")  # no raise


def test_too_short_raises():
    with pytest.raises(PasswordPolicyError, match="MIN_LENGTH"):
        validate_password_policy("a1b2c3")


def test_no_letter_raises():
    with pytest.raises(PasswordPolicyError, match="MISSING_LETTER"):
        validate_password_policy("12345678")


def test_no_digit_raises():
    with pytest.raises(PasswordPolicyError, match="MISSING_DIGIT"):
        validate_password_policy("abcdefgh")


def test_long_strong_password_passes():
    validate_password_policy("MyStr0ngPassword!")
