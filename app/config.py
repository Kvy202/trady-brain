from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "trady-brain"
    version: str = "0.3.0"

    # JWT
    jwt_secret: str = Field(default="trady-dev-secret-CHANGE-IN-PRODUCTION")
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./trady.db")

    # FCM
    fcm_enabled: bool = Field(default=False)

    # ── Phase 3: Trading Bot Brain ────────────────────────────────────────────
    # TRADING_BOT_MODE=mock  → use built-in mock responses
    # TRADING_BOT_MODE=real  → proxy to external bot API
    trading_bot_mode: str = Field(default="mock")

    trading_bot_base_url: str = Field(default="http://localhost:9000")
    trading_bot_api_key: str = Field(default="")
    trading_bot_hmac_secret: str = Field(default="trady-bot-hmac-secret-CHANGE-IN-PRODUCTION")
    trading_bot_timeout_seconds: int = Field(default=5)

    # Comma-separated lists parsed into sets by properties below
    trading_bot_allowed_commands: str = Field(
        default="pause_bot,reduce_risk,conservative_mode,bot_status,get_metrics,get_positions,get_logs"
    )
    trading_bot_require_approval_commands: str = Field(
        default=(
            "resume_bot,emergency_stop,flatten_positions,increase_risk,"
            "change_strategy,add_symbol,disable_stop_loss,disable_drawdown_limit"
        )
    )

    # Pending approval TTL in seconds
    approval_ttl_seconds: int = Field(default=300)

    # Webhook
    trading_bot_webhook_secret: str = Field(default="trady-webhook-secret-CHANGE-IN-PRODUCTION")
    # Max age for incoming webhook timestamps
    webhook_max_age_seconds: int = Field(default=60)

    # Rate limiting: N trading commands per device per minute
    trading_rate_limit: str = Field(default="20/minute")

    @property
    def allowed_commands_set(self) -> set:
        return {c.strip() for c in self.trading_bot_allowed_commands.split(",") if c.strip()}

    @property
    def approval_commands_set(self) -> set:
        return {c.strip() for c in self.trading_bot_require_approval_commands.split(",") if c.strip()}

    @property
    def blocked_commands_set(self) -> set:
        return {
            "withdraw_funds",
            "transfer_funds",
            "reveal_api_keys",
            "disable_all_safety",
            "set_unlimited_leverage",
        }


settings = Settings()
