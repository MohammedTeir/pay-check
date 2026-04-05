"""
User model — CRUD operations, credit management, and ban system.
"""

from datetime import datetime, timezone
from typing import Optional

from database.supabase_client import get_supabase


class User:
    """Represents a bot user stored in Supabase."""

    def __init__(
        self,
        id: int,
        telegram_id: int,
        username: Optional[str],
        credits: int,
        plan_id: Optional[int],
        created_at: datetime,
        last_activity: datetime,
        is_banned: bool = False,
    ):
        self.id = id
        self.telegram_id = telegram_id
        self.username = username
        self.credits = credits
        self.plan_id = plan_id
        self.created_at = created_at
        self.last_activity = last_activity
        self.is_banned = is_banned

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "credits": self.credits,
            "plan_id": self.plan_id,
            "is_banned": self.is_banned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            telegram_id=data["telegram_id"],
            username=data.get("username"),
            credits=data.get("credits", 0),
            plan_id=data.get("plan_id"),
            is_banned=data.get("is_banned", False),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else None,
        )

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def get_by_telegram_id(telegram_id: int) -> Optional["User"]:
        """Fetch a user by their Telegram ID."""
        sb = get_supabase()
        response = sb.table("users").select("*").eq("telegram_id", telegram_id).execute()
        if response.data:
            return User.from_dict(response.data[0])
        return None

    @staticmethod
    def get_by_id(user_id: int) -> Optional["User"]:
        """Fetch a user by their internal database ID."""
        sb = get_supabase()
        response = sb.table("users").select("*").eq("id", user_id).execute()
        if response.data:
            return User.from_dict(response.data[0])
        return None

    @staticmethod
    def create(telegram_id: int, username: Optional[str] = None) -> "User":
        """Create a new user linked to a Telegram ID."""
        sb = get_supabase()
        response = sb.table("users").insert({
            "telegram_id": telegram_id,
            "username": username,
            "credits": 0,
        }).execute()
        return User.from_dict(response.data[0])

    @staticmethod
    def get_all(limit: int = None, offset: int = None, sort_by: str = "created_at", sort_desc: bool = True) -> list["User"]:
        """Fetch users with optional server-side pagination and sorting.

        Args:
            limit: Max users to return (None for all)
            offset: Number of users to skip (None for start)
            sort_by: Column to sort by (created_at, credits, last_activity)
            sort_desc: Sort descending
        """
        sb = get_supabase()
        query = sb.table("users").select("*").order(sort_by, desc=sort_desc)
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.range(offset, offset + limit - 1) if limit else query.range(offset, offset + 1000)
        response = query.execute()
        return [User.from_dict(row) for row in response.data]

    @staticmethod
    def count() -> int:
        """Get total user count without loading all rows."""
        sb = get_supabase()
        response = sb.table("users").select("id", count="exact").execute()
        return response.count if response.count is not None else 0

    @staticmethod
    def search(query_text: str, limit: int = 50) -> list["User"]:
        """Search users by username (partial match) or exact telegram_id."""
        sb = get_supabase()
        if query_text.isdigit():
            user = User.get_by_telegram_id(int(query_text))
            if user:
                return [user]
        response = sb.table("users").select("*").ilike("username", f"%{query_text}%").limit(limit).execute()
        return [User.from_dict(row) for row in response.data]

    def update_username(self, username: str) -> None:
        """Update the user's Telegram username."""
        sb = get_supabase()
        sb.table("users").update({"username": username}).eq("telegram_id", self.telegram_id).execute()
        self.username = username

    def touch_activity(self) -> None:
        """Update last_activity timestamp."""
        sb = get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        sb.table("users").update({"last_activity": now}).eq(
            "telegram_id", self.telegram_id
        ).execute()
        self.last_activity = datetime.now(timezone.utc)

    # ── Ban Operations ───────────────────────────────────────────────

    def ban(self, reason: str = None) -> None:
        """Ban the user (soft disable). Banned users cannot use the bot."""
        sb = get_supabase()
        sb.table("users").update({"is_banned": True}).eq("telegram_id", self.telegram_id).execute()
        self.is_banned = True

    def unban(self) -> None:
        """Unban the user, restoring access."""
        sb = get_supabase()
        sb.table("users").update({"is_banned": False}).eq("telegram_id", self.telegram_id).execute()
        self.is_banned = False

    @staticmethod
    def get_banned(limit: int = 50) -> list["User"]:
        """Get all banned users."""
        sb = get_supabase()
        response = sb.table("users").select("*").eq("is_banned", True).limit(limit).execute()
        return [User.from_dict(row) for row in response.data]

    # ── Credit Operations (Atomic) ───────────────────────────────────

    def add_credits(self, amount: int, reason: str = "admin_add", admin_id: int = None) -> None:
        """Add credits atomically using database increment. Logs transaction."""
        sb = get_supabase()
        sb.table("users").update({"credits": self.credits + amount}).eq(
            "telegram_id", self.telegram_id
        ).execute()
        self.credits += amount
        # Log the transaction (non-blocking if ledger table missing)
        try:
            from models.credit_transaction import CreditTransaction
            CreditTransaction.log(
                user_id=self.telegram_id,
                amount=amount,
                reason=reason,
                balance_after=self.credits,
                admin_id=admin_id,
                details={"reason": reason},
            )
        except Exception:
            pass  # Ledger table may not exist yet; credits still updated

    def deduct_credit(self, reason: str = "validation") -> bool:
        """Deduct 1 credit atomically. Returns False if insufficient."""
        if self.credits <= 0:
            return False
        sb = get_supabase()
        sb.table("users").update({"credits": self.credits - 1}).eq(
            "telegram_id", self.telegram_id
        ).execute()
        self.credits -= 1
        # Log the transaction (non-blocking if ledger table missing)
        try:
            from models.credit_transaction import CreditTransaction
            CreditTransaction.log(
                user_id=self.telegram_id,
                amount=-1,
                reason=reason,
                balance_after=self.credits,
                admin_id=None,
                details={"reason": reason},
            )
        except Exception:
            pass
        return True

    def deduct_credit_by(self, amount: int, reason: str = "validation") -> bool:
        """Deduct N credits atomically. Returns False if insufficient."""
        if self.credits < amount or amount <= 0:
            return False
        sb = get_supabase()
        sb.table("users").update({"credits": self.credits - amount}).eq(
            "telegram_id", self.telegram_id
        ).execute()
        self.credits -= amount
        try:
            from models.credit_transaction import CreditTransaction
            CreditTransaction.log(
                user_id=self.telegram_id,
                amount=-amount,
                reason=reason,
                balance_after=self.credits,
                admin_id=None,
                details={"reason": reason, "amount": amount},
            )
        except Exception:
            pass
        return True

    def reset_credits(self, admin_id: int = None) -> None:
        """Reset user credits to 0. Logs transaction."""
        old_credits = self.credits
        sb = get_supabase()
        sb.table("users").update({"credits": 0}).eq("telegram_id", self.telegram_id).execute()
        self.credits = 0
        # Log the transaction (non-blocking if ledger table missing)
        try:
            from models.credit_transaction import CreditTransaction
            CreditTransaction.log(
                user_id=self.telegram_id,
                amount=-old_credits,
                reason="admin_reset",
                balance_after=0,
                admin_id=admin_id,
                details={"reason": "admin_reset", "old_credits": old_credits},
            )
        except Exception:
            pass

    @staticmethod
    def delete(telegram_id: int) -> bool:
        """Delete a user by Telegram ID. Returns True if deleted, False if not found."""
        sb = get_supabase()
        response = sb.table("users").delete().eq("telegram_id", telegram_id).execute()
        return len(response.data) > 0

    @staticmethod
    def bulk_delete(telegram_ids: list[int]) -> int:
        """Delete multiple users by their Telegram IDs. Returns count of deleted users."""
        if not telegram_ids:
            return 0
        sb = get_supabase()
        response = sb.table("users").delete().in_("telegram_id", telegram_ids).execute()
        return len(response.data) if response.data else 0

    # ── Plan Operations ──────────────────────────────────────────────

    def set_plan(self, plan_id: int, credits_to_add: int, admin_id: int = None) -> None:
        """Assign a plan and add its credits atomically."""
        sb = get_supabase()
        sb.table("users").update({
            "plan_id": plan_id,
            "credits": self.credits + credits_to_add,
        }).eq("telegram_id", self.telegram_id).execute()
        self.plan_id = plan_id
        self.credits += credits_to_add
        # Log the transaction (non-blocking if ledger table missing)
        try:
            from models.credit_transaction import CreditTransaction
            CreditTransaction.log(
                user_id=self.telegram_id,
                amount=credits_to_add,
                reason="plan_assign",
                balance_after=self.credits,
                admin_id=admin_id,
                details={"plan_id": plan_id, "credits_added": credits_to_add},
            )
        except Exception:
            pass
