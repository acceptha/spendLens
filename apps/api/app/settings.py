from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    admin_email: str
    admin_password_hash: str
    jwt_secret: str
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    web_origin: str = "http://localhost:5173"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_monthly_budget_usd: float = 5.0
    anthropic_api_key: str = "sk-ant-test-placeholder"
    log_level: str = "INFO"

    @property
    def llm_enabled(self) -> bool:
        """ANTHROPIC_API_KEY가 실제 키로 설정됐는지(placeholder/빈 값 아님).

        False면 인사이트는 룰 기반 폴백을 쓰고 LLM 분류는 건너뛴다.
        """
        return self.anthropic_api_key not in ("", "sk-ant-test-placeholder")


settings = Settings()
