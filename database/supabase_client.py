"""
Supabase client singleton — uses service role key for full DB access.
"""

from supabase import create_client, Client
from config import config

_supabase: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client instance."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(config.supabase_url, config.supabase_service_role_key)
    return _supabase
