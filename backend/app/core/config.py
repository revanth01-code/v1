from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PORT: int = 4000
    ENV: str = "development"

    SUPABASE_URL: str = "https://test.supabase.co"
    SUPABASE_ANON_KEY: str = "test-anon-key"
    SUPABASE_SERVICE_ROLE_KEY: str = "test-service-key"

    GROQ_API_KEY: str = ""
    NOTIFICATION_API_KEY: str = ""  # Server-to-server key for n8n notification endpoint
    SENTRY_DSN: str = ""

    # Admin API key for protected universe refresh endpoints
    ADMIN_API_KEY: str = "dev-admin-secret-key-123"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # AMFI client configurations
    AMFI_TIMEOUT_SECONDS: float = 30.0
    AMFI_MAX_RETRIES: int = 3
    AMFI_RETRY_BACKOFF_FACTOR: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()