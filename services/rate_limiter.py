"""
Rate limiter — in-memory sliding window rate limiting.
Tracks per-user and per-Stripe-account limits.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Tuple

from config import config


class RateLimiter:
    """
    Sliding window rate limiter.
    - Per user: max N attempts per hour, M per day
    - Per Stripe account: max K attempts per day
    """

    def __init__(
        self,
        max_per_hour: int = config.rate_limit_per_hour,
        max_per_day: int = config.rate_limit_per_day,
        max_stripe_daily: int = config.stripe_account_daily_limit,
    ):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.max_stripe_daily = max_stripe_daily

        # user_id -> list of timestamps
        self._user_attempts: dict[int, list[float]] = defaultdict(list)
        # stripe_account_id -> list of timestamps
        self._stripe_attempts: dict[int, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup(self, timestamps: list[float], window: float) -> list[float]:
        """Remove timestamps outside the current window."""
        cutoff = time.time() - window
        return [t for t in timestamps if t > cutoff]

    def check_user(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if a user is within rate limits.
        Returns (allowed, reason).
        """
        now = time.time()
        one_hour = 3600
        one_day = 86400

        with self._lock:
            # Clean up old entries
            self._user_attempts[user_id] = self._cleanup(
                self._user_attempts[user_id], one_day
            )
            attempts = self._user_attempts[user_id]

            # Check hourly limit
            recent_hour = [t for t in attempts if t > now - one_hour]
            if len(recent_hour) >= self.max_per_hour:
                return False, f"Hourly rate limit exceeded ({self.max_per_hour}/hour)"

            # Check daily limit
            if len(attempts) >= self.max_per_day:
                return False, f"Daily rate limit exceeded ({self.max_per_day}/day)"

            # Record this attempt
            attempts.append(now)
            return True, ""

    def check_stripe_account(self, account_id: int) -> Tuple[bool, str]:
        """
        Check if a Stripe account is within its daily limit.
        Returns (allowed, reason).
        """
        one_day = 86400

        with self._lock:
            self._stripe_attempts[account_id] = self._cleanup(
                self._stripe_attempts[account_id], one_day
            )
            attempts = self._stripe_attempts[account_id]

            if len(attempts) >= self.max_stripe_daily:
                return False, f"Stripe account daily limit reached ({self.max_stripe_daily}/day)"

            attempts.append(time.time())
            return True, ""

    def get_user_stats(self, user_id: int) -> dict:
        """Get current rate limit stats for a user."""
        now = time.time()
        one_hour = 3600
        one_day = 86400

        with self._lock:
            attempts = self._user_attempts.get(user_id, [])
            hour_count = len([t for t in attempts if t > now - one_hour])
            day_count = len([t for t in attempts if t > now - one_day])

        return {
            "attempts_this_hour": hour_count,
            "attempts_today": day_count,
            "hourly_limit": self.max_per_hour,
            "daily_limit": self.max_per_day,
            "hourly_remaining": max(0, self.max_per_hour - hour_count),
            "daily_remaining": max(0, self.max_per_day - day_count),
        }

    def reset_user(self, user_id: int) -> None:
        """Clear rate limit history for a user."""
        with self._lock:
            self._user_attempts.pop(user_id, None)

    def reset_all(self) -> None:
        """Clear all rate limit data (useful for testing)."""
        with self._lock:
            self._user_attempts.clear()
            self._stripe_attempts.clear()


# Singleton instance
rate_limiter = RateLimiter()
