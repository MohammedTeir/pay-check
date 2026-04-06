"""
Stripe Account model — multi-account management with encryption.
"""

from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase


class StripeAccount:
    """Represents a Stripe account with encrypted secret key."""

    def __init__(
        self,
        id: int,
        label: str,
        secret_key_encrypted: str,
        is_active: bool,
        daily_count: int,
        daily_reset_at: datetime,
        created_at: datetime,
    ):
        self.id = id
        self.label = label
        self._secret_key_encrypted = secret_key_encrypted
        self.is_active = is_active
        self.daily_count = daily_count
        self.daily_reset_at = daily_reset_at
        self.created_at = created_at

    @property
    def secret_key_encrypted(self) -> str:
        """Return the encrypted secret key."""
        return self._secret_key_encrypted

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "is_active": self.is_active,
            "daily_count": self.daily_count,
            "daily_reset_at": self.daily_reset_at.isoformat() if self.daily_reset_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StripeAccount":
        return cls(
            id=data["id"],
            label=data["label"],
            secret_key_encrypted=data["secret_key_encrypted"],
            is_active=data.get("is_active", False),
            daily_count=data.get("daily_count", 0),
            daily_reset_at=datetime.fromisoformat(data["daily_reset_at"]) if data.get("daily_reset_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def get_all() -> list["StripeAccount"]:
        """Fetch all Stripe accounts."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").select("*").order("created_at").execute()
        return [StripeAccount.from_dict(row) for row in response.data]

    @staticmethod
    def get_by_id(account_id: int) -> Optional["StripeAccount"]:
        """Fetch a Stripe account by its ID."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").select("*").eq("id", account_id).execute()
        if response.data:
            return StripeAccount.from_dict(response.data[0])
        return None

    @staticmethod
    def get_by_label(label: str) -> Optional["StripeAccount"]:
        """Fetch a Stripe account by its label."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").select("*").eq("label", label).execute()
        if response.data:
            return StripeAccount.from_dict(response.data[0])
        return None

    @staticmethod
    def get_active() -> Optional["StripeAccount"]:
        """Fetch the currently active Stripe account."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").select("*").eq("is_active", True).execute()
        if response.data:
            return StripeAccount.from_dict(response.data[0])
        return None

    @staticmethod
    def create(label: str, secret_key_encrypted: str, is_active: bool = False) -> "StripeAccount":
        """Add a new Stripe account with encrypted key."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").insert({
            "label": label,
            "secret_key_encrypted": secret_key_encrypted,
            "is_active": is_active,
            "daily_count": 0,
        }).execute()
        return StripeAccount.from_dict(response.data[0])

    def activate(self) -> None:
        """Set this account as active and deactivate all others."""
        sb = get_supabase()
        # Deactivate all first
        sb.table("stripe_accounts").update({"is_active": False}).neq("id", self.id).execute()
        # Activate this one
        sb.table("stripe_accounts").update({"is_active": True}).eq("id", self.id).execute()
        self.is_active = True

    def increment_daily_count(self) -> int:
        """Increment the daily usage counter and return new value."""
        sb = get_supabase()
        sb.table("stripe_accounts").update({"daily_count": self.daily_count + 1}).eq(
            "id", self.id
        ).execute()
        self.daily_count += 1
        return self.daily_count

    def reset_daily_count(self) -> None:
        """Reset the daily counter."""
        sb = get_supabase()
        sb.table("stripe_accounts").update({
            "daily_count": 0,
            "daily_reset_at": datetime.utcnow().isoformat(),
        }).eq("id", self.id).execute()
        self.daily_count = 0
        self.daily_reset_at = datetime.utcnow()

    def update_label(self, new_label: str) -> None:
        """Update the account label."""
        sb = get_supabase()
        sb.table("stripe_accounts").update({"label": new_label}).eq("id", self.id).execute()
        self.label = new_label

    @staticmethod
    def delete(account_id: int) -> bool:
        """Delete a Stripe account by ID. Returns True if deleted, False if not found."""
        sb = get_supabase()
        response = sb.table("stripe_accounts").delete().eq("id", account_id).execute()
        return len(response.data) > 0
