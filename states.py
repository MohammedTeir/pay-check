"""Aiogram FSM states for the bot."""

from aiogram.fsm.state import State, StatesGroup


class CardValidationState(StatesGroup):
    """User is in card input mode."""
    waiting_for_card = State()
    pending_choice = State()  # waiting for user to choose validation mode
