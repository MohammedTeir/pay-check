"""
Admin model — dynamic admin management from database.
Pure DB-based — no .env fallback.
"""

from typing import Optional
from database.supabase_client import get_supabase


class Admin:
    """Admin user stored in database."""

    def __init__(self, telegram_id: int, username: str, role: str = "admin"):
        self.telegram_id = telegram_id
        self.username = username
        self.role = role

    # ── Queries ──────────────────────────────────────────────────────

    @staticmethod
    def is_admin(telegram_id: int) -> bool:
        """Check if user is an admin (any role)."""
        try:
            sb = get_supabase()
            resp = sb.table("admins").select("id").eq("telegram_id", telegram_id).execute()
            return len(resp.data) > 0
        except Exception:
            return False

    @staticmethod
    def is_super_admin(telegram_id: int) -> bool:
        """Check if user is a super admin."""
        try:
            sb = get_supabase()
            resp = sb.table("admins").select("role").eq("telegram_id", telegram_id).execute()
            if resp.data:
                return resp.data[0].get("role") == "super_admin"
        except Exception:
            pass
        
        return False

    @staticmethod
    def get_all() -> list["Admin"]:
        """Get all admins."""
        sb = get_supabase()
        resp = sb.table("admins").select("*").order("created_at").execute()
        return [
            Admin(
                telegram_id=r["telegram_id"],
                username=r.get("username", ""),
                role=r.get("role", "admin"),
            )
            for r in resp.data
        ]

    @staticmethod
    def get_by_id(telegram_id: int) -> Optional["Admin"]:
        """Get admin by telegram ID."""
        sb = get_supabase()
        resp = sb.table("admins").select("*").eq("telegram_id", telegram_id).execute()
        if resp.data:
            r = resp.data[0]
            return Admin(
                telegram_id=r["telegram_id"],
                username=r.get("username", ""),
                role=r.get("role", "admin"),
            )
        return None

    # ── Mutations ─────────────────────────────────────────────────────

    @staticmethod
    def add(telegram_id: int, username: str = "",
            role: str = "admin", added_by: int = 0) -> Optional["Admin"]:
        """Add a new admin. Returns the new admin or None if exists."""
        existing = Admin.get_by_id(telegram_id)
        if existing:
            return existing

        sb = get_supabase()
        resp = sb.table("admins").insert({
            "telegram_id": telegram_id,
            "username": username,
            "role": role,
            "added_by": added_by,
        }).execute()
        if resp.data:
            return Admin(
                telegram_id=telegram_id,
                username=username,
                role=role,
            )
        return None

    @staticmethod
    def remove(telegram_id: int) -> bool:
        """Remove an admin. Returns True if removed."""
        sb = get_supabase()
        resp = sb.table("admins").delete().eq("telegram_id", telegram_id).execute()
        return len(resp.data) > 0

    @staticmethod
    def set_role(telegram_id: int, role: str) -> bool:
        """Change admin role (admin or super_admin)."""
        sb = get_supabase()
        resp = sb.table("admins").update({"role": role}).eq("telegram_id", telegram_id).execute()
        return len(resp.data) > 0
