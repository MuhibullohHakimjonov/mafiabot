from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton


def admin_decision_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Yes", callback_data="admin_yes"))
    builder.add(InlineKeyboardButton(text="No", callback_data="admin_no"))
    return builder.as_markup()


def game_time_keyboard():
    builder = InlineKeyboardBuilder()
    times = ["19:00-19:30", "19:30-20:00"]
    for t in times:
        builder.add(InlineKeyboardButton(text=t, callback_data=f"time_{t}"))
    return builder.as_markup()


def user_response_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Yes", callback_data="join_game"))
    builder.add(InlineKeyboardButton(text="No", callback_data="decline_game"))
    return builder.as_markup()


def join_game_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Join Game", callback_data="register"))
    return builder.as_markup()
