"""
Configuration loader — reads environment variables and provides typed access.
"""

import os
from dataclasses import dataclass, field
from typing import Set, Literal

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded from environment variables."""

    # Application Environment
    app_env: Literal["development", "production"] = field(
        default_factory=lambda: os.getenv("APP_ENV", "development").lower()
    )

    # Telegram
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )

    # Supabase
    supabase_url: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", "")
    )
    supabase_service_role_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    # Encryption
    encryption_key: str = field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", "")
    )

    # Admin IDs (optional — admins can also be managed via database)
    admin_ids: Set[int] = field(default_factory=lambda: frozenset(
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip()
    ))

    # Crypto addresses
    crypto_address_usdt: str = field(
        default_factory=lambda: os.getenv("CRYPTO_ADDRESS_USDT", "")
    )
    crypto_address_btc: str = field(
        default_factory=lambda: os.getenv("CRYPTO_ADDRESS_BTC", "")
    )
    admin_contact: str = field(
        default_factory=lambda: os.getenv("ADMIN_CONTACT", "@admin")
    )

    # Stripe
    stripe_amount_cents: int = field(
        default_factory=lambda: int(os.getenv("STRIPE_AMOUNT_CENTS", "50"))
    )
    stripe_publishable_key: str = field(
        default_factory=lambda: os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    )

    # Webapp (for Stripe Elements automation)
    webapp_port: int = field(
        default_factory=lambda: int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "5000")))
    )
    webapp_url: str = field(
        default_factory=lambda: os.getenv(
            "WEBAPP_URL",
            f"http://127.0.0.1:{os.getenv('PORT', os.getenv('WEBAPP_PORT', '5000'))}"
        )
    )

    # Rate limiting
    rate_limit_per_hour: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_HOUR", "5"))
    )
    rate_limit_per_day: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_DAY", "20"))
    )
    stripe_account_daily_limit: int = field(
        default_factory=lambda: int(os.getenv("STRIPE_ACCOUNT_DAILY_LIMIT", "200"))
    )

    # Card cooldown
    card_cooldown_hours: int = field(
        default_factory=lambda: int(os.getenv("CARD_COOLDOWN_HOURS", "24"))
    )

    # BIN Lookup
    bin_lookup_api_key: str = field(
        default_factory=lambda: os.getenv("BIN_LOOKUP_API_KEY", "")
    )
    binsearch_api_key: str = field(
        default_factory=lambda: os.getenv("BINSEARCH_API_KEY", "")
    )
    binsearch_user_id: str = field(
        default_factory=lambda: os.getenv("BINSEARCH_USER_ID", "")
    )

    # OpenRouter AI
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )

    # Webhook (optional — defaults to polling if not set)
    webhook_url: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_URL", "")
    )
    webhook_path: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_PATH", "/webhook")
    )
    webhook_secret: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "")
    )
    webhook_port: int = field(
        default_factory=lambda: int(os.getenv("WEBHOOK_PORT", "8080"))
    )
    webhook_host: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_HOST", "0.0.0.0")
    )

    @property
    def use_webhook(self) -> bool:
        """Return True if webhook mode is enabled based on environment.
        
        In production mode, webhook is required (WEBHOOK_URL must be set).
        In development mode, defaults to polling unless WEBHOOK_URL is explicitly set.
        """
        if self.app_env == "production":
            # Production always requires webhook
            return bool(self.webhook_url and self.webhook_secret)
        else:
            # Development can use webhook if explicitly configured
            return bool(self.webhook_url and self.webhook_secret)
    
    @property
    def use_polling(self) -> bool:
        """Return True if polling mode should be used."""
        return not self.use_webhook

    def validate(self) -> None:
        """Raise ValueError if required configuration is missing."""
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.encryption_key:
            missing.append("ENCRYPTION_KEY")

        # Validate environment-specific requirements
        if self.app_env == "production" and not self.use_webhook:
            missing.append("WEBHOOK_URL (required for production mode)")
            missing.append("WEBHOOK_SECRET (required for production mode)")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        
        # Validate app_env value
        if self.app_env not in ("development", "production"):
            raise ValueError(
                f"Invalid APP_ENV value: '{self.app_env}'. Must be 'development' or 'production'"
            )


# Singleton config instance
config = Config()
