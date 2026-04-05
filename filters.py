"""Bot-level filters."""

from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import config


class AdminFilter(BaseFilter):
    """Check if the user is an admin."""

    async def __call__(self, message: Message) -> bool:
        return is_admin(message.from_user.id)


def is_admin(user_id: int) -> bool:
    """Check if user is an admin — purely database-driven."""
    try:
        from models.admin_model import Admin
        return Admin.is_admin(user_id)
    except Exception:
        return False
