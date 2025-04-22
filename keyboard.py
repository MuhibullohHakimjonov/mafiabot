from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup


def admin_decision_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Yes", callback_data="admin_yes"))
    builder.add(InlineKeyboardButton(text="No", callback_data="admin_no"))
    return builder.as_markup()


def game_time_keyboard():
    builder = InlineKeyboardBuilder()
    times = ["19:00-19:30", "19:30-20:00", "20:00-20:30", "20:30-21:00"]
    for t in times:
        builder.add(InlineKeyboardButton(text=t, callback_data=f"time_{t}"))
    return builder.as_markup()


def join_game_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Join Game", callback_data="register"))
    return builder.as_markup()


def admin_panel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 View Groups")],
            [KeyboardButton(text="📌 Active Games")]
        ],
        resize_keyboard=True
    )


def time_selection_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="19:00", callback_data="game_time_19:00")
    builder.button(text="20:00", callback_data="game_time_20:00")
    builder.button(text="20:30", callback_data="game_time_20:30")
    builder.button(text="21:00", callback_data="game_time_21:00")
    builder.adjust(2)
    return builder.as_markup()


def add_bot_to_group_button(bot_username: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Add Bot as Admin",
        url=f"https://t.me/{bot_username}?startgroup&admin=1"
    )
    return builder.as_markup()
