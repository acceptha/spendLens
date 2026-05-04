from app.auth.password import hash_password, verify_password


def test_hash_password_returns_argon2_string():
    h = hash_password("hunter2")
    assert h.startswith("$argon2id$")


def test_verify_password_round_trip():
    h = hash_password("hunter2")
    assert verify_password(h, "hunter2") is True
    assert verify_password(h, "wrong") is False


def test_verify_invalid_hash_returns_false():
    assert verify_password("not-a-hash", "anything") is False
