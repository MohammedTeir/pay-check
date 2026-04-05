"""
Session timeout middleware — auto-clear FSM states after inactivity.
"""

import logging
import time
from typing import Any, Dict, Optional
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State

logger = logging.getLogger(__name__)


class SessionTimeoutMiddleware(BaseMiddleware):
    """
    Middleware that automatically clears FSM state after inactivity.
    
    Prevents users from being stuck in a state if they abandon the conversation.
    """
    
    def __init__(
        self,
        timeout_seconds: int = 900,  # 15 minutes default
        warning_seconds: int = 600,  # Warn at 10 minutes
    ):
        super().__init__()
        self.timeout_seconds = timeout_seconds
        self.warning_seconds = warning_seconds
        # In-memory session tracking
        self._sessions: Dict[int, Dict[str, Any]] = {}
    
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        # Get user ID
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
        
        state = data.get("state")
        if not state:
            return await handler(event, data)
        
        current_time = time.time()
        current_state = await state.get_state()
        
        # Check session data
        session = self._sessions.get(user_id)
        
        if session and current_state:
            last_activity = session.get("last_activity", 0)
            elapsed = current_time - last_activity
            
            # Check if session has timed out
            if elapsed > self.timeout_seconds:
                logger.info(
                    f"Session timeout for user {user_id}: "
                    f"{elapsed:.0f}s > {self.timeout_seconds}s. Clearing state."
                )
                
                # Clear state
                await state.clear()
                
                # Notify user
                try:
                    if isinstance(event, Message):
                        await event.answer(
                            "⏱️ *Session Timeout*\n\n"
                            "Your previous session has expired due to inactivity.\n"
                            "Please start over with /menu",
                            parse_mode="MarkdownV2"
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            "⏱️ Session expired. Please start over.",
                            show_alert=True
                        )
                except Exception as e:
                    logger.error(f"Failed to send timeout notification: {e}")
                
                # Remove from tracking
                del self._sessions[user_id]
                
                # Don't continue to handler if state was cleared
                if isinstance(event, CallbackQuery):
                    await event.answer()
                return
            
            # Warn user if approaching timeout (only once)
            elif elapsed > self.warning_seconds and not session.get("warned", False):
                session["warned"] = True
                remaining = self.timeout_seconds - elapsed
                minutes = int(remaining // 60)
                
                try:
                    if isinstance(event, Message):
                        await event.answer(
                            f"⚠️ *Session Expiring Soon*\n\n"
                            f"Your session will expire in `{minutes}` minutes "
                            f"due to inactivity.\n\n"
                            f"Please continue or use /menu to cancel.",
                            parse_mode="MarkdownV2"
                        )
                except Exception as e:
                    logger.error(f"Failed to send warning notification: {e}")
        
        # Update session activity
        if current_state:
            self._sessions[user_id] = {
                "last_activity": current_time,
                "state": current_state,
                "warned": session.get("warned", False) if session else False,
            }
        
        # Call handler
        result = await handler(event, data)
        
        # Update last activity after handler execution
        if current_state:
            self._sessions.setdefault(user_id, {})["last_activity"] = current_time
        
        return result
    
    def clear_session(self, user_id: int) -> None:
        """Manually clear a user's session tracking."""
        self._sessions.pop(user_id, None)
    
    def get_session_info(self, user_id: int) -> Optional[Dict]:
        """Get session info for a user (for debugging/admin)."""
        session = self._sessions.get(user_id)
        if not session:
            return None
        
        elapsed = time.time() - session["last_activity"]
        return {
            "state": session.get("state"),
            "elapsed_seconds": int(elapsed),
            "timeout_in": max(0, int(self.timeout_seconds - elapsed)),
            "warned": session.get("warned", False),
        }
    
    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns count of cleaned sessions."""
        current_time = time.time()
        expired = [
            uid for uid, session in self._sessions.items()
            if current_time - session["last_activity"] > self.timeout_seconds
        ]
        
        for uid in expired:
            del self._sessions[uid]
        
        return len(expired)
