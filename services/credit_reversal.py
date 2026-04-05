"""
Credit reversal service — safe reversal of accidental credit additions.
"""

import logging
from typing import Optional
from models.credit_transaction import CreditTransaction
from models.user import User
from models.admin_log import AdminLog

logger = logging.getLogger(__name__)


class ReversalError(Exception):
    """Raised when a credit reversal fails."""
    pass


def can_reverse_transaction(tx_id: int) -> tuple[bool, str]:
    """
    Check if a transaction can be reversed.
    
    Returns:
        (can_reverse, reason)
    """
    sb = __import__('database.supabase_client', fromlist=['get_supabase']).get_supabase()
    
    # Get the transaction
    result = sb.table("credit_transactions").select("*").eq("id", tx_id).execute()
    if not result.data:
        return False, "Transaction not found"
    
    tx = result.data[0]
    
    # Check if already reversed
    if tx.get("reversed", False):
        return False, "Transaction already reversed"
    
    # Check if it's a positive transaction (can only reverse additions)
    if tx["amount"] <= 0:
        return False, "Can only reverse credit additions"
    
    # Check if user has enough credits to reverse
    user = User.get_by_telegram_id(tx["user_id"])
    if not user:
        return False, "User not found"
    
    if user.credits < tx["amount"]:
        return False, f"User has insufficient credits ({user.credits} < {tx['amount']})"
    
    return True, "Can reverse"


def reverse_credit_transaction(
    tx_id: int,
    reversed_by: int,
    reason: str = "Manual reversal",
) -> dict:
    """
    Reverse a credit transaction.
    
    Args:
        tx_id: Transaction ID to reverse
        reversed_by: Admin Telegram ID performing the reversal
        reason: Reason for reversal
    
    Returns:
        Dict with reversal details
    
    Raises:
        ReversalError: If reversal fails
    """
    # Check if can reverse
    can_reverse, reason_msg = can_reverse_transaction(tx_id)
    if not can_reverse:
        raise ReversalError(f"Cannot reverse transaction: {reason_msg}")
    
    sb = __import__('database.supabase_client', fromlist=['get_supabase']).get_supabase()
    
    # Get the transaction
    result = sb.table("credit_transactions").select("*").eq("id", tx_id).execute()
    tx = result.data[0]
    
    # Get user
    user = User.get_by_telegram_id(tx["user_id"])
    if not user:
        raise ReversalError("User not found")
    
    old_balance = user.credits
    
    # Deduct credits
    new_balance = user.credits - tx["amount"]
    if new_balance < 0:
        raise ReversalError("Reversal would result in negative balance")
    
    # Update user credits
    sb.table("users").update({"credits": new_balance}).eq("telegram_id", user.telegram_id).execute()
    
    # Mark transaction as reversed
    sb.table("credit_transactions").update({
        "reversed": True,
        "reversed_by": reversed_by,
        "reversal_reason": reason,
        "reversed_at": __import__('datetime').datetime.utcnow().isoformat(),
    }).eq("id", tx_id).execute()
    
    # Create reversal transaction record
    CreditTransaction.log(
        user_id=tx["user_id"],
        amount=-tx["amount"],
        reason="reversal",
        balance_after=new_balance,
        admin_id=reversed_by,
        details={
            "reversed_tx_id": tx_id,
            "reason": reason,
            "old_balance": old_balance,
        }
    )
    
    # Log in admin log
    try:
        admin_log_entry = AdminLog(
            admin_id=reversed_by,
            admin_username=None,  # Will be populated by caller
            action="reverse_credits",
            details={
                "tx_id": tx_id,
                "user_id": tx["user_id"],
                "amount": tx["amount"],
                "reason": reason,
                "old_balance": old_balance,
                "new_balance": new_balance,
            }
        )
        admin_log_entry.log()
    except Exception as e:
        logger.warning(f"Failed to log reversal in admin log: {e}")
    
    return {
        "success": True,
        "tx_id": tx_id,
        "user_id": tx["user_id"],
        "amount_reversed": tx["amount"],
        "old_balance": old_balance,
        "new_balance": new_balance,
        "reversed_by": reversed_by,
        "reason": reason,
    }


def get_reversible_transactions(
    user_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get list of transactions that can be reversed.
    
    Args:
        user_id: Filter by user (optional)
        limit: Max results
    
    Returns:
        List of reversible transactions
    """
    sb = __import__('database.supabase_client', fromlist=['get_supabase']).get_supabase()
    
    query = sb.table("credit_transactions").select("*")
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    # Only positive transactions that aren't reversed
    query = query.gt("amount", 0).eq("reversed", False)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    
    reversible = []
    for tx in result.data:
        can_rev, _ = can_reverse_transaction(tx["id"])
        if can_rev:
            reversible.append(tx)
    
    return reversible
