from datetime import date
from decimal import Decimal
from uuid import UUID

from app.transactions.service import compute_dedup_hash

USER = UUID("00000000-0000-0000-0000-000000000001")


def test_dedup_uses_approval_when_present():
    h1 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    h2 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 2),  # 다른 fallback
                            fallback_amount=Decimal("999"),
                            fallback_merchant="Y")
    assert h1 == h2  # approval_no가 있으면 fallback 무관


def test_dedup_falls_back_when_no_approval():
    h = compute_dedup_hash(USER, "samsung_card_xlsx", None,
                           fallback_date=date(2026, 4, 1),
                           fallback_amount=Decimal("100"),
                           fallback_merchant="X")
    assert isinstance(h, str)
    assert len(h) == 64  # sha256 hex


def test_dedup_different_users_get_different_hashes():
    other = UUID("00000000-0000-0000-0000-000000000002")
    h1 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    h2 = compute_dedup_hash(other, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    assert h1 != h2
