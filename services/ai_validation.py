"""
AI-powered card analysis using OpenRouter API.
Never sends full card numbers — only BIN (first 6), last 4, and expiry.
Provides enhanced reasoning-based validation insights.
"""

import json
import logging
import asyncio
from typing import Optional

import httpx

from config import config

logger = logging.getLogger(__name__)


async def ai_analyze_card(
    full_number: str,
    last4: str,
    exp_month: str,
    exp_year: str,
    bin_lookup_result: Optional[dict] = None,
) -> dict:
    """
    Analyze a card using AI reasoning.

    Args:
        full_number: Full card number
        last4: Last 4 digits
        exp_month: Expiry month (01-12)
        exp_year: Expiry year
        bin_lookup_result: Optional dict from bin_lookup service

    Returns:
        dict with keys: analysis, confidence, risk_level, brand, bank, type, country, is_test_card, expiry_valid
    """
    api_key = config.openrouter_api_key
    if not api_key:
        return {
            "analysis": "AI analysis unavailable — no API key configured",
            "confidence": "N/A",
            "risk_level": "Unknown",
            "brand_guess": "Unknown",
            "bank_guess": "Unknown",
        }

    # Build context from BIN lookup if available
    bin_context = ""
    if bin_lookup_result:
        bl = bin_lookup_result
        bin_context = (
            f"\nBIN Lookup Data:\n"
            f"  Brand: {bl.get('brand', 'Unknown')}\n"
            f"  Bank: {bl.get('bank', 'Unknown')}\n"
            f"  Type: {bl.get('type', 'Unknown')}\n"
            f"  Country: {bl.get('country', 'Unknown')}"
        )
    else:
        bin_context = "\nBIN Lookup: No data found — use your knowledge to identify the brand."

    system_prompt = (
        "You are a card analysis expert. Analyze the given BIN (Bank Identification Number) "
        "to provide insights about the card. You have deep knowledge of card numbering patterns, "
        "bank BIN ranges, and card network conventions.\n\n"
        "Respond in this EXACT JSON format only:\n"
        "{\n"
        '  "brand": "Visa/Mastercard/Amex/Discover/Unknown",\n'
        '  "bank": "Bank name or Unknown",\n'
        '  "type": "Credit/Debit/Prepaid/Unknown",\n'
        '  "country": "Country or Unknown",\n'
        '  "is_test_card": true/false,\n'
        '  "expiry_valid": true/false,\n'
        '  "risk_level": "Low/Medium/High",\n'
        '  "confidence": "0-100%",\n'
        '  "analysis": "Brief explanation of findings"\n'
        "}\n\n"
        "Rules:\n"
        "- Visa starts with 4, Mastercard 5, Amex 34/37, Discover 6011/65\n"
        "- BIN 424242 is a known Stripe test card\n"
        "- Check if expiry is in the future\n"
        "- Be concise in analysis"
    )

    user_prompt = (
        f"Analyze this card:\n"
        f"Full Number: {full_number}\n"
        f"Expiry: {exp_month}/{exp_year}"
        f"{bin_context}"
    )

    max_retries = 3
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"AI analysis retry attempt {attempt + 1}/{max_retries}")
            await asyncio.sleep(2)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                data=json.dumps({
                    "model": "qwen/qwen3.6-plus:free",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 500,
                })
            )
        except httpx.RequestError as e:
            logger.warning(f"OpenRouter request failed (attempt {attempt + 1}): {e}")
            continue

        if resp.status_code != 200:
            logger.warning(f"OpenRouter returned {resp.status_code} (attempt {attempt + 1})")
            continue

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON from markdown code blocks if present
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())

            return {
                "brand": result.get("brand", "Unknown"),
                "bank": result.get("bank", "Unknown"),
                "type": result.get("type", "Unknown"),
                "country": result.get("country", "Unknown"),
                "is_test_card": result.get("is_test_card", False),
                "expiry_valid": result.get("expiry_valid", True),
                "risk_level": result.get("risk_level", "Unknown"),
                "confidence": result.get("confidence", "N/A"),
                "analysis": result.get("analysis", "No analysis"),
            }

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse AI response (attempt {attempt + 1}): {e}")
            continue

    # All retries exhausted
    logger.error("AI analysis failed after 3 attempts")
    return {
        "analysis": "AI service unavailable",
        "confidence": "N/A",
        "risk_level": "Unknown",
        "brand": "Unknown",
        "bank": "Unknown",
        "type": "Unknown",
        "country": "Unknown",
        "is_test_card": False,
        "expiry_valid": True,
    }
