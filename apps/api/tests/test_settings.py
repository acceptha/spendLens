
def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("ADMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$xxx")
    monkeypatch.setenv("JWT_SECRET", "secret123")
    monkeypatch.setenv("WEB_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    from app.settings import Settings
    s = Settings()

    assert s.database_url == "postgresql://test"
    assert s.admin_email == "test@example.com"
    assert s.jwt_access_ttl_minutes == 15  # default
    assert s.jwt_refresh_ttl_days == 7     # default
    assert s.log_level == "DEBUG"          # explicitly set above
