"""
Settings model — bot-wide configurable settings stored in DB.
Admins can change these from the bot without editing .env.
"""

from typing import Optional

from database.supabase_client import get_supabase


class Settings:
    """Bot-wide settings stored in the settings table."""

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def get(key: str) -> Optional[str]:
        """Get a setting value by key."""
        sb = get_supabase()
        response = sb.table("settings").select("value").eq("key", key).execute()
        if response.data:
            return response.data[0]["value"]
        return None

    @staticmethod
    def set(key: str, value: str) -> None:
        """Set a setting value. Creates or updates."""
        sb = get_supabase()
        # Try update first
        resp = sb.table("settings").update({"value": value}).eq("key", key).execute()
        if not resp.data:
            # Insert if doesn't exist
            sb.table("settings").insert({"key": key, "value": value}).execute()

    @staticmethod
    def get_all() -> dict:
        """Get all settings as a dict."""
        sb = get_supabase()
        response = sb.table("settings").select("key, value").execute()
        return {row["key"]: row["value"] for row in response.data}

    @staticmethod
    def get_crypto_addresses() -> dict:
        """Get crypto payment addresses."""
        all_settings = Settings.get_all()
        return {
            "usdt": all_settings.get("crypto_address_usdt", ""),
            "btc": all_settings.get("crypto_address_btc", ""),
            "admin_contact": all_settings.get("admin_contact", "@admin"),
        }
