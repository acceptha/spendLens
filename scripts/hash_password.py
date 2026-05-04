"""Generate an argon2id hash for ADMIN_PASSWORD_HASH env.

Usage:
    cd apps/api && uv run python ../../scripts/hash_password.py
"""
import getpass
import sys

# 동일 venv에서 실행되어야 argon2-cffi 사용 가능 (apps/api에서 uv run)
from argon2 import PasswordHasher


def main() -> int:
    pwd = getpass.getpass("Enter password: ")
    confirm = getpass.getpass("Confirm:        ")
    if pwd != confirm:
        print("Mismatch.", file=sys.stderr)
        return 1
    h = PasswordHasher().hash(pwd)
    print()
    print(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
