"""
Plan model — subscription plan management.
"""

from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase


class Plan:
    """Represents a subscription plan."""

    def __init__(
        self,
        id: int,
        name: str,
        crypto_price_usd: float,
        credits: int,
        is_active: bool,
        created_at: datetime,
    ):
        self.id = id
        self.name = name
        self.crypto_price_usd = crypto_price_usd
        self.credits = credits
        self.is_active = is_active
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "crypto_price_usd": float(self.crypto_price_usd),
            "credits": self.credits,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls(
            id=data["id"],
            name=data["name"],
            crypto_price_usd=float(data["crypto_price_usd"]),
            credits=data["credits"],
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def get_all() -> list["Plan"]:
        """Fetch all plans."""
        sb = get_supabase()
        response = sb.table("plans").select("*").order("credits").execute()
        return [Plan.from_dict(row) for row in response.data]

    @staticmethod
    def get_active() -> list["Plan"]:
        """Fetch only active plans."""
        sb = get_supabase()
        response = sb.table("plans").select("*").eq("is_active", True).order("credits").execute()
        return [Plan.from_dict(row) for row in response.data]

    @staticmethod
    def get_by_id(plan_id: int) -> Optional["Plan"]:
        """Fetch a plan by its ID."""
        sb = get_supabase()
        response = sb.table("plans").select("*").eq("id", plan_id).execute()
        if response.data:
            return Plan.from_dict(response.data[0])
        return None

    @staticmethod
    def get_by_name(name: str) -> Optional["Plan"]:
        """Fetch a plan by its name (case-insensitive)."""
        sb = get_supabase()
        response = sb.table("plans").select("*").ilike("name", name).execute()
        if response.data:
            return Plan.from_dict(response.data[0])
        return None

    @staticmethod
    def create(name: str, crypto_price_usd: float, credits: int, is_active: bool = True) -> "Plan":
        """Create a new subscription plan."""
        sb = get_supabase()
        response = sb.table("plans").insert({
            "name": name,
            "crypto_price_usd": crypto_price_usd,
            "credits": credits,
            "is_active": is_active,
        }).execute()
        return Plan.from_dict(response.data[0])

    def toggle_active(self) -> None:
        """Toggle the plan's active status."""
        sb = get_supabase()
        sb.table("plans").update({"is_active": not self.is_active}).eq("id", self.id).execute()
        self.is_active = not self.is_active

    def update(self, name: str = None, crypto_price_usd: float = None, credits: int = None, is_active: bool = None) -> None:
        """Update plan fields. Only provided fields will be updated."""
        sb = get_supabase()
        update_data = {}
        if name is not None:
            update_data["name"] = name
            self.name = name
        if crypto_price_usd is not None:
            update_data["crypto_price_usd"] = crypto_price_usd
            self.crypto_price_usd = crypto_price_usd
        if credits is not None:
            update_data["credits"] = credits
            self.credits = credits
        if is_active is not None:
            update_data["is_active"] = is_active
            self.is_active = is_active
        
        if update_data:
            sb.table("plans").update(update_data).eq("id", self.id).execute()

    def deactivate(self) -> None:
        """Deactivate the plan."""
        sb = get_supabase()
        sb.table("plans").update({"is_active": False}).eq("id", self.id).execute()
        self.is_active = False

    @staticmethod
    def delete(plan_id: int) -> bool:
        """Delete a plan by ID. Returns True if deleted, False if not found."""
        sb = get_supabase()
        response = sb.table("plans").delete().eq("id", plan_id).execute()
        return len(response.data) > 0
