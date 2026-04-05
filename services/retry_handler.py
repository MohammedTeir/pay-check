"""
Retry handler — exponential backoff retry logic for transient failures.
"""

import asyncio
import functools
import logging
from typing import Callable, Optional, Type, Tuple, Any

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Exception indicating a transient error that should be retried."""
    pass


class RetryExhaustedError(Exception):
    """Exception indicating all retry attempts were exhausted."""
    def __init__(self, message: str, last_error: Exception):
        super().__init__(message)
        self.last_error = last_error


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator for async functions with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types that should trigger retry
                             (default: all exceptions)
        on_retry: Optional callback(attempt, error, delay) for logging/monitoring
    
    Usage:
        @retry_async(max_retries=3, base_delay=1.0)
        async def stripe_operation():
            ...
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    
                    if attempt == max_retries:
                        # All retries exhausted
                        logger.error(
                            f"{func.__name__}: All {max_retries} retries exhausted. "
                            f"Last error: {e}"
                        )
                        raise RetryExhaustedError(
                            f"{func.__name__} failed after {max_retries} retries: {e}",
                            last_error
                        )
                    
                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    # Add jitter (±25%)
                    import random
                    jitter = delay * 0.25 * (2 * random.random() - 1)
                    delay_with_jitter = delay + jitter
                    
                    logger.warning(
                        f"{func.__name__}: Attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay_with_jitter:.2f}s..."
                    )
                    
                    if on_retry:
                        on_retry(attempt + 1, e, delay_with_jitter)
                    
                    await asyncio.sleep(delay_with_jitter)
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"{func.__name__}: Non-retryable error: {e}")
                    raise
            
            raise RuntimeError("Should not reach here")
        
        return wrapper
    return decorator


async def retry_with_callback(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff (programmatic API).
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum retry attempts
        base_delay: Initial delay (seconds)
        max_delay: Maximum delay (seconds)
        retryable_exceptions: Exceptions that trigger retry
        on_retry: Callback for retry events
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of func(*args, **kwargs)
    
    Raises:
        RetryExhaustedError: If all retries fail
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_error = e
            
            if attempt == max_retries:
                logger.error(
                    f"{func.__name__}: All {max_retries} retries exhausted. "
                    f"Last error: {e}"
                )
                raise RetryExhaustedError(
                    f"{func.__name__} failed after {max_retries} retries: {e}",
                    last_error
                )
            
            delay = min(base_delay * (2.0 ** attempt), max_delay)
            import random
            jitter = delay * 0.25 * (2 * random.random() - 1)
            delay_with_jitter = delay + jitter
            
            logger.warning(
                f"{func.__name__}: Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay_with_jitter:.2f}s..."
            )
            
            if on_retry:
                on_retry(attempt + 1, e, delay_with_jitter)
            
            await asyncio.sleep(delay_with_jitter)
        except Exception as e:
            logger.error(f"{func.__name__}: Non-retryable error: {e}")
            raise
    
    raise RuntimeError("Should not reach here")


def is_stripe_retryable_error(error: Exception) -> bool:
    """Check if a Stripe error is transient and should be retried."""
    import stripe
    
    # Network errors
    if isinstance(error, stripe.error.APIConnectionError):
        return True
    
    # Rate limits
    if isinstance(error, stripe.error.RateLimitError):
        return True
    
    # Temporary server errors
    if isinstance(error, stripe.error.APIError):
        return True
    
    # Timeout errors
    if isinstance(error, asyncio.TimeoutError):
        return True
    
    return False


def retry_stripe(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
):
    """Decorator specifically for Stripe API calls with smart retry logic."""
    import stripe
    
    return retry_async(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=(
            stripe.error.APIConnectionError,
            stripe.error.RateLimitError,
            stripe.error.APIError,
            asyncio.TimeoutError,
        ),
        on_retry=lambda attempt, error, delay: logger.warning(
            f"Stripe API retry {attempt}/{max_retries}: {error}"
        ),
    )
