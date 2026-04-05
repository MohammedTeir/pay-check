"""
Credit Transaction model — audit ledger for all credit changes.
"""

from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase


class CreditTransaction:
    """Represents a single credit change entry in the audit ledger."""

    # Reason codes
    VALIDATION = "validation"
    ADMIN_ADD = "admin_add"
    ADMIN_RESET = "admin_reset"
    PLAN_ASSIGN = "plan_assign"
    ADMIN_GRANT = "admin_grant"

    def __init__(
        self,
        id: int,
        user_id: int,
        amount: int,
        reason: str,
        balance_after: int,
        admin_id: Optional[int],
        details: Optional[dict],
        created_at: datetime,
    ):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.reason = reason
        self.balance_after = balance_after
        self.admin_id = admin_id
        self.details = details
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "reason": self.reason,
            "balance_after": self.balance_after,
            "admin_id": self.admin_id,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreditTransaction":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            amount=data["amount"],
            reason=data["reason"],
            balance_after=data["balance_after"],
            admin_id=data.get("admin_id"),
            details=data.get("details"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    # ── Ledger Operations ──────────────────────────────────────────────

    @staticmethod
    def log(
        user_id: int,
        amount: int,
        reason: str,
        balance_after: int,
        admin_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> "CreditTransaction":
        """Record a credit change in the ledger."""
        sb = get_supabase()
        response = sb.table("credit_transactions").insert({
            "user_id": user_id,
            "amount": amount,
            "reason": reason,
            "balance_after": balance_after,
            "admin_id": admin_id,
            "details": details or {},
        }).execute()
        return CreditTransaction.from_dict(response.data[0])

    @staticmethod
    def get_by_user(telegram_id: int, limit: int = 50) -> list["CreditTransaction"]:
        """Get credit transaction history for a user."""
        sb = get_supabase()
        response = (
            sb.table("credit_transactions")
            .select("*")
            .eq("user_id", telegram_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [CreditTransaction.from_dict(row) for row in response.data]

    @staticmethod
    def get_summary(telegram_id: int) -> dict:
        """Get credit summary for a user: total added, total deducted, net."""
        sb = get_supabase()
        response = (
            sb.table("credit_transactions")
            .select("amount")
            .eq("user_id", telegram_id)
            .execute()
        )
        total_added = sum(r["amount"] for r in response.data if r["amount"] > 0)
        total_deducted = abs(sum(r["amount"] for r in response.data if r["amount"] < 0))
        return {
            "total_added": total_added,
            "total_deducted": total_deducted,
            "net": total_added - total_deducted,
            "transaction_count": len(response.data),
        }
