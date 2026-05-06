from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "trady-brain"
    version: str = "0.2.0"

    # JWT
    jwt_secret: str = Field(default="trady-dev-secret-CHANGE-IN-PRODUCTION")
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    # Database — sqlite for local; swap to postgresql+asyncpg://... for prod
    database_url: str = Field(default="sqlite+aiosqlite:///./trady.db")

    # Firebase Cloud Messaging — false until Admin SDK is configured
    fcm_enabled: bool = Field(default=False)


settings = Settings()
