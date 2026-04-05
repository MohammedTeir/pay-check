"""
Admin Log model — audit trail for all admin actions.
"""

from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase


class AdminLog:
    """Represents an admin action audit log entry."""

    def __init__(
        self,
        id: int,
        admin_id: int,
        admin_username: Optional[str],
        action: str,
        details: Optional[dict],
        created_at: datetime,
    ):
        self.id = id
        self.admin_id = admin_id
        self.admin_username = admin_username
        self.action = action
        self.details = details
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "admin_id": self.admin_id,
            "admin_username": self.admin_username,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AdminLog":
        return cls(
            id=data["id"],
            admin_id=data["admin_id"],
            admin_username=data.get("admin_username"),
            action=data["action"],
            details=data.get("details"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

    # ── CRUD Operations ──────────────────────────────────────────────

    @staticmethod
    def log(admin_id: int, admin_username: Optional[str], action: str, details: Optional[dict] = None) -> "AdminLog":
        """Record an admin action."""
        sb = get_supabase()
        response = sb.table("admin_logs").insert({
            "admin_id": admin_id,
            "admin_username": admin_username,
            "action": action,
            "details": details or {},
        }).execute()
        return AdminLog.from_dict(response.data[0])

    @staticmethod
    def get_recent(limit: int = 50) -> list["AdminLog"]:
        """Get the most recent admin actions."""
        sb = get_supabase()
        response = (
            sb.table("admin_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AdminLog.from_dict(row) for row in response.data]

    @staticmethod
    def get_by_admin(admin_id: int, limit: int = 50) -> list["AdminLog"]:
        """Get admin actions filtered by admin ID."""
        sb = get_supabase()
        response = (
            sb.table("admin_logs")
            .select("*")
            .eq("admin_id", admin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AdminLog.from_dict(row) for row in response.data]

    @staticmethod
    def get_by_action(action: str, limit: int = 50) -> list["AdminLog"]:
        """Get admin actions filtered by action type."""
        sb = get_supabase()
        response = (
            sb.table("admin_logs")
            .select("*")
            .eq("action", action)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AdminLog.from_dict(row) for row in response.data]

    @staticmethod
    def clear_old(days_to_keep: int = 30) -> int:
        """Delete admin logs older than the specified number of days. Returns count of deleted logs."""
        from datetime import datetime, timedelta
        sb = get_supabase()
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
        response = sb.table("admin_logs").delete().lt("created_at", cutoff_date).execute()
        return len(response.data) if response.data else 0
