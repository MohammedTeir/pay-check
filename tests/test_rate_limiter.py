"""
Tests for the sliding window rate limiter.
"""

import pytest
import time
from services.rate_limiter import RateLimiter


class TestRateLimiter:
    """Rate limiter tests."""

    def setup_method(self):
        """Create a fresh rate limiter for each test."""
        self.limiter = RateLimiter(
            max_per_hour=3,
            max_per_day=5,
            max_stripe_daily=10,
        )

    def test_user_within_limits(self):
        """User should be allowed within limits."""
        allowed, reason = self.limiter.check_user(1)
        assert allowed is True
        assert reason == ""

    def test_user_hourly_limit(self):
        """User should be blocked after exceeding hourly limit."""
        for i in range(3):
            allowed, _ = self.limiter.check_user(1)
            assert allowed is True

        # 4th attempt should be blocked
        allowed, reason = self.limiter.check_user(1)
        assert allowed is False
        assert "Hourly" in reason

    def test_user_daily_limit(self):
        """User should be blocked after exceeding daily limit."""
        # Create a limiter with very low daily limit
        limiter = RateLimiter(max_per_hour=100, max_per_day=2, max_stripe_daily=100)

        allowed, _ = limiter.check_user(1)
        assert allowed is True

        allowed, _ = limiter.check_user(1)
        assert allowed is True

        allowed, reason = limiter.check_user(1)
        assert allowed is False
        assert "Daily" in reason

    def test_different_users_independent(self):
        """Different users should have independent limits."""
        self.limiter.check_user(1)
        self.limiter.check_user(1)
        self.limiter.check_user(1)

        # User 1 should be at limit
        allowed, _ = self.limiter.check_user(1)
        assert allowed is False

        # User 2 should still be allowed
        allowed, _ = self.limiter.check_user(2)
        assert allowed is True

    def test_stripe_account_limit(self):
        """Stripe account should have its own daily limit."""
        for i in range(10):
            allowed, _ = self.limiter.check_stripe_account(1)
            assert allowed is True

        # 11th attempt should be blocked
        allowed, reason = self.limiter.check_stripe_account(1)
        assert allowed is False
        assert "daily limit" in reason.lower()

    def test_get_user_stats(self):
        """User stats should reflect current usage."""
        self.limiter.check_user(1)
        self.limiter.check_user(1)

        stats = self.limiter.get_user_stats(1)
        assert stats["attempts_this_hour"] == 2
        assert stats["hourly_limit"] == 3
        assert stats["hourly_remaining"] == 1

    def test_reset_user(self):
        """Resetting a user should clear their history."""
        self.limiter.check_user(1)
        self.limiter.check_user(1)
        self.limiter.check_user(1)

        # At limit
        allowed, _ = self.limiter.check_user(1)
        assert allowed is False

        # Reset
        self.limiter.reset_user(1)

        # Should be allowed again
        allowed, _ = self.limiter.check_user(1)
        assert allowed is True

    def test_reset_all(self):
        """Reset all should clear everything."""
        self.limiter.check_user(1)
        self.limiter.check_stripe_account(1)
        self.limiter.reset_all()

        stats = self.limiter.get_user_stats(1)
        assert stats["attempts_this_hour"] == 0
