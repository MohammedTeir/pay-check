"""
Card hash utility — SHA-256 salted hashing for duplicate card detection.
Never stores full card numbers; only irreversible hashes.
"""

import hashlib
import os
import time

from config import config


def hash_card_number(card_number: str) -> str:
    """
    Create a salted SHA-256 hash of a card number.
    Uses a deterministic salt derived from ENCRYPTION_KEY so the same card
    always produces the same hash for duplicate detection.
    """
    # Deterministic salt: first 16 bytes of SHA-256 of encryption key
    salt = hashlib.sha256(config.encryption_key.encode()).hexdigest()[:32]
    return hashlib.sha256(f"{card_number}{salt}".encode()).hexdigest()


def is_card_on_cooldown(card_hash: str) -> bool:
    """
    Check if a card hash is still within the cooldown period.
    Returns True if the card was validated within the last N hours.
    """
    from database.supabase_client import get_supabase

    sb = get_supabase()
    response = (
        sb.table("card_cooldowns")
        .select("expires_at")
        .eq("card_hash", card_hash)
        .gte("expires_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        .execute()
    )
    return len(response.data) > 0


def set_card_cooldown(card_hash: str) -> None:
    """
    Record a card hash with an expiry time.
    Prevents the same card from being validated again within the cooldown window.
    """
    from datetime import datetime, timedelta

    from database.supabase_client import get_supabase

    now = datetime.utcnow()
    expires = now + timedelta(hours=config.card_cooldown_hours)

    sb = get_supabase()
    sb.table("card_cooldowns").insert({
        "card_hash": card_hash,
        "validated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }).execute()
