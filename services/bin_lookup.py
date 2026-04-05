"""
BIN Lookup service — identifies card brand, bank, and card type from the BIN.
Uses a dual-API fallback chain for maximum reliability:

  1. Local hardcoded DB (instant, covers Stripe test cards)
  2. binlist.net (free, no key required, 5 req/hr limit)
  3. binsearchlookup.com (requires API key, 20 req/min free tier)
  4. Brand-only fallback (first digit detection)
"""

import logging
from typing import Optional

import httpx

from config import config

logger = logging.getLogger(__name__)

# ── Local BIN database (Stripe test cards + common BINs) ──────────────────

_BIN_DATABASE: dict[str, tuple[str, str, str, str]] = {
    # Visa
    "424242": ("Visa", "Stripe Test", "Credit", "US"),
    "400000": ("Visa", "Stripe Test", "Credit", "US"),
    "411111": ("Visa", "Stripe Test", "Credit", "US"),
    "401288": ("Visa", "Stripe Test", "Credit", "US"),
    # Mastercard
    "555555": ("Mastercard", "Stripe Test", "Credit", "US"),
    "520082": ("Mastercard", "Stripe Test", "Credit", "US"),
    "510510": ("Mastercard", "Stripe Test", "Credit", "US"),
    # Amex
    "378282": ("Amex", "Stripe Test", "Credit", "US"),
    "371449": ("Amex", "Stripe Test", "Credit", "US"),
    # Discover
    "601111": ("Discover", "Stripe Test", "Credit", "US"),
    "601100": ("Discover", "Stripe Test", "Credit", "US"),
    # JCB
    "353011": ("JCB", "Stripe Test", "Credit", "US"),
    "356600": ("JCB", "Stripe Test", "Credit", "US"),
    # Diners Club
    "305693": ("Diners Club", "Stripe Test", "Credit", "US"),
    "362272": ("Diners Club", "Stripe Test", "Credit", "US"),
}

# ── Brand detection by first digit ────────────────────────────────────────

_BRAND_MAP = {
    "4": "Visa",
    "5": "Mastercard",
    "3": "Amex/Diners",
    "6": "Discover",
    "2": "Mastercard/Mir",
    "9": "UnionPay",
    "1": "UPI",
    "0": "Unknown",
}

# ── Unknown result sentinel ───────────────────────────────────────────────

_UNKNOWN_RESULT = {
    "brand": "Unknown",
    "bank": "Unknown Bank",
    "type": "Unknown",
    "country": "Unknown",
}


# ── Local lookup ──────────────────────────────────────────────────────────

def _lookup_local(bin_code: str) -> Optional[dict]:
    """Check the local hardcoded database."""
    bin_6 = bin_code[:6]
    if bin_6 in _BIN_DATABASE:
        brand, bank, card_type, country = _BIN_DATABASE[bin_6]
        return {"brand": brand, "bank": bank, "type": card_type, "country": country}
    return None


# ── binlist.net lookup ───────────────────────────────────────────────────

async def _lookup_binlist(bin_code: str) -> Optional[dict]:
    """
    Query binlist.net (free tier, no API key needed).
    Rate limit: 5 req/hr. Returns None on 404, 429, or network error.
    """
    url = f"https://lookup.binlist.net/{bin_code[:8]}"
    headers = {"Accept-Version": "3"}

    api_key = config.bin_lookup_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.RequestError as e:
        logger.warning(f"binlist.net request failed: {e}")
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        logger.warning("binlist.net rate limit exceeded (5/hr). Falling back.")
        return None
    if resp.status_code != 200:
        logger.warning(f"binlist.net returned status {resp.status_code}")
        return None

    try:
        data = resp.json()
    except ValueError:
        return None

    brand = data.get("scheme") or data.get("brand", "")
    bank = (data.get("bank") or {}).get("name", "")
    card_type = data.get("type", "")
    country = (data.get("country") or {}).get("name", "")

    return {
        "brand": brand.title() if brand else "Unknown",
        "bank": bank or "Unknown Bank",
        "type": card_type.title() if card_type else "Unknown",
        "country": country or "Unknown",
    }


# ── binsearchlookup.com lookup ───────────────────────────────────────────

async def _lookup_binsearch(bin_code: str) -> Optional[dict]:
    """
    Query binsearchlookup.com (requires API key + user ID).
    Free tier: 20 req/min, 500 req/month.
    """
    api_key = config.binsearch_api_key
    user_id = config.binsearch_user_id
    if not api_key or not user_id:
        return None

    url = "https://api.binsearchlookup.com/lookup"
    params = {"bin": bin_code[:8]}
    headers = {
        "X-API-Key": api_key,
        "X-User-ID": user_id,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as e:
        logger.warning(f"binsearchlookup.com request failed: {e}")
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        logger.warning("binsearchlookup.com rate limit exceeded. Falling back.")
        return None
    if resp.status_code != 200:
        logger.warning(f"binsearchlookup.com returned status {resp.status_code}")
        return None

    try:
        body = resp.json()
    except ValueError:
        return None

    if not body.get("success") or "data" not in body:
        return None

    data = body["data"]
    brand = data.get("Brand", "")
    bank = data.get("Issuer", "")
    card_type = data.get("Type", "")
    country = data.get("CountryName", "")

    return {
        "brand": brand if brand else "Unknown",
        "bank": bank or "Unknown Bank",
        "type": card_type if card_type else "Unknown",
        "country": country or "Unknown",
    }


# ── Brand-only fallback ──────────────────────────────────────────────────

def _fallback_brand(bin_code: str) -> dict:
    """Detect brand from the first digit only."""
    first = bin_code[0] if bin_code else ""
    brand = _BRAND_MAP.get(first, "Unknown")
    return {"brand": brand, "bank": "Unknown Bank", "type": "Unknown", "country": "Unknown"}


# ── Public API ────────────────────────────────────────────────────────────

async def lookup_bin(bin_code: str) -> dict:
    """
    Look up card information from its first 6-8 digits (BIN/IIN).

    Chain:
      1. Local hardcoded database (instant)
      2. binlist.net (free, no key)
      3. binsearchlookup.com (if configured)

    Returns None if no data found — caller should fallback to AI or show Unknown.
    """
    bin_code = bin_code.strip()
    if len(bin_code) < 6:
        return None

    # 1. Local database (covers Stripe test cards instantly)
    local = _lookup_local(bin_code)
    if local:
        return local

    # 2. binlist.net (free, no auth needed)
    result = await _lookup_binlist(bin_code)
    if result and result.get('brand', 'Unknown') != 'Unknown':
        return result

    # 3. binsearchlookup.com (if API key configured)
    result = await _lookup_binsearch(bin_code)
    if result and result.get('brand', 'Unknown') != 'Unknown':
        return result

    return None  # No data found
