from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PORT: int = 4000
    ENV: str = "development"

    # Sensible test-friendly defaults so pytest can import the app without
    # a real .env present. A real .env always overrides these.
    SUPABASE_URL: str = "https://test.supabase.co"
    SUPABASE_ANON_KEY: str = "test-anon-key"
    SUPABASE_SERVICE_ROLE_KEY: str = "test-service-key"
    GROQ_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()