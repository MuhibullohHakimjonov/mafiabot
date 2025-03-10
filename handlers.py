import asyncio

from aiogram import Router, types, F, Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, ChatMemberUpdated
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete
from sqlalchemy.orm import joinedload

from config import ADMIN_ID, BOT_USERNAME
from keyboard import time_selection_keyboard, game_time_keyboard, admin_panel_keyboard, \
    user_menu_keyboard
from models import User, AsyncSessionLocal, Game, PlayerGame, Group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db

router = Router()
players_today = {}


class RegisterState(StatesGroup):
    waiting_for_name = State()
    waiting_for_time = State()


async def get_user(telegram_id: int, session: AsyncSession):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()


def add_bot_to_group_button(bot_username: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Add Bot as Admin",
        url=f"https://t.me/{bot_username}?startgroup&admin=1"
    )
    return builder.as_markup()


@router.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "Hello, Admin! Choose an option:",
            reply_markup=admin_panel_keyboard()
        )
    else:
        if message.chat.type == "private":
            await message.answer(
                "To use this bot, add it to a group **with admin permissions**:",
                reply_markup=add_bot_to_group_button(BOT_USERNAME)
            )
        await message.answer("Select Menu", reply_markup=user_menu_keyboard()
                             )


# 🤖 BOT handlers ------------------------------------------------------

@router.my_chat_member()
async def on_bot_status_update(event: ChatMemberUpdated, bot: Bot, session: AsyncSession):
    """Handles when the bot is added or removed from a group."""
    chat_id = event.chat.id

    if event.new_chat_member.status in ["administrator", "creator"]:
        await bot.send_message(chat_id, "✅ Bot is ready! You can now start a game.")

        # Store the group in the database
        title = event.chat.title
        result = await session.execute(select(Group).where(Group.id == chat_id))
        existing_group = result.scalars().first()

        if not existing_group:
            session.add(Group(id=chat_id, title=title))
            await session.commit()

    elif event.new_chat_member.status in ["kicked", "left"]:
        # Bot was removed from the group → Delete from database
        print(f"🚨 Bot was removed from group {chat_id}, deleting from database.")
        await session.execute(delete(Group).where(Group.id == chat_id))
        await session.commit()

    else:
        # If bot was added but not as an admin, inform users and delete the message after a delay
        warning_msg = await bot.send_message(chat_id, "⚠️ Please promote me to admin to start a game!")
        await asyncio.sleep(10)
        await bot.delete_message(chat_id, warning_msg.message_id)


async def is_bot_admin(chat_id: int, bot: Bot) -> bool:
    """Check if the bot is an admin in the given chat."""
    bot_member = await bot.get_chat_member(chat_id, bot.id)
    return bot_member.status in ["administrator", "creator"]


# 🎮 Game Handlers--------------------------------------------
@router.message(Command("start_game"))
async def start_game(message: types.Message, bot: Bot):
    """Start a game only if the bot has admin rights."""
    if not await is_bot_admin(message.chat.id, bot):
        await message.answer("⚠️ Please promote me to admin first!")
        return

    await message.answer("🎭 The Mafia game is starting!")


@router.message(F.text == "Register")
async def register(message: types.Message, state: FSMContext):
    # Prompt the user to type their name
    await message.answer("Please type your name:")
    await state.set_state(RegisterState.waiting_for_name)


@router.message(RegisterState.waiting_for_name)
async def save_name(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    name = message.text

    async with get_db() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        existing_user = result.scalars().first()

        if existing_user:
            await message.answer("You are already registered!")
        else:
            # Save the new user
            new_user = User(telegram_id=telegram_id, name=name)
            db.add(new_user)
            await db.commit()
            await message.answer(f"Thank you, {name}! You have been registered.")
    await state.clear()


@router.callback_query(F.data == "admin_yes")
async def admin_yes(callback: types.CallbackQuery):
    await callback.message.edit_text("Select a time slot:", reply_markup=game_time_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_no")
async def admin_no(callback: types.CallbackQuery):
    await callback.message.edit_text("Okay, no game today!")
    await callback.answer()


@router.callback_query(F.data.startswith("time_"))
async def set_game_time(callback: types.CallbackQuery):
    """Handles game time selection, saves the game, and notifies users."""
    time_slot = callback.data.split("_")[1]

    async with AsyncSessionLocal() as session:
        # Save the new game
        new_game = Game(time_slot=time_slot)
        session.add(new_game)
        await session.commit()  # Commit to generate game ID

        # Fetch groups to notify
        group_result = await session.execute(select(Group))
        groups = group_result.scalars().all()

    # Notify all groups
    for group in groups:
        try:
            await callback.bot.send_message(
                group.id,
                f"📢 A new Mafia game is scheduled at {time_slot}! Join using the bot. @hwhambot"
            )
        except Exception as e:
            print(f"❌ Failed to send message to group {group.id}: {e}")

    await callback.message.answer(f"✅ Game scheduled at {time_slot}!")
    await callback.answer()


@router.message(F.text == "📜 View Players")
async def select_game(message: types.Message):
    """Admin selects a game to view participants."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game).where(Game.is_active == True))
        active_games = result.scalars().all()

    if not active_games:
        await message.answer("❌ No active games available.")
        return

    keyboard = InlineKeyboardBuilder()
    for game in active_games:
        keyboard.add(InlineKeyboardButton(text=f"🎲 {game.time_slot}", callback_data=f"view_game_{game.id}"))

    await message.answer("📌 Select a game to view participants:", reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("view_game_"))
async def show_game_players(callback: types.CallbackQuery):
    """Displays players who joined a specific game."""
    game_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        # Fetch game with players
        result = await session.execute(
            select(Game)
            .options(joinedload(Game.player_games).joinedload(PlayerGame.player))
            .where(Game.id == game_id)
        )
        game = result.scalars().first()

        if not game:
            await callback.message.answer("❌ Game not found.")
            return

        players = [pg.player for pg in game.player_games]

    if not players:
        await callback.message.answer(f"⚠️ No players joined the {game.time_slot} game.")
        return

    player_details = "\n".join([f"👤 {player.name}" for player in players])

    await callback.message.answer(f"📜 **Players for {game.time_slot}:**\n{player_details}")
    await callback.answer()


@router.message(F.text == "📌 Active Games")
async def show_active_games(message: types.Message):
    """Shows all active games and allows the admin to delete them."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game).where(Game.is_active == True))
        active_games = result.scalars().all()

    if not active_games:
        await message.answer("❌ No active games at the moment.")
        return

    # Create an inline keyboard with delete options
    keyboard = InlineKeyboardBuilder()
    for game in active_games:
        keyboard.add(InlineKeyboardButton(
            text=f"🗑 Delete {game.time_slot}",
            callback_data=f"delete_game_{game.id}"
        ))

    await message.answer("📌 **Active Games:**\nSelect a game to delete:", reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("delete_game_"))
async def delete_game(callback: types.CallbackQuery):
    """Deletes a selected game from the database."""
    game_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        game = await session.get(Game, game_id)
        if not game:
            await callback.message.answer("❌ Game not found.")
            return

        # Manually delete associated PlayerGame entries
        await session.execute(delete(PlayerGame).where(PlayerGame.game_id == game_id))
        await session.commit()  # Commit before deleting Game

        # Now delete the game itself
        await session.delete(game)
        await session.commit()

    await callback.message.answer(f"✅ Game at {game.time_slot} has been deleted.")
    await callback.answer()


# 📌 USER REGISTRATION & GAME PARTICIPATION ----------------------------------------


@router.message(F.text == "Games")
async def show_games(message: types.Message):
    async with AsyncSessionLocal() as session:
        # Fetch active games
        result = await session.execute(select(Game).where(Game.is_active == True))
        active_games = result.scalars().all()

    if not active_games:
        await message.answer("No active games available.")
        return

    # Create a keyboard with available games
    builder = InlineKeyboardBuilder()
    for game in active_games:
        builder.button(text=f"Game at {game.time_slot}", callback_data=f"select_game_{game.id}")
    builder.adjust(1)  # Arrange buttons in one column

    await message.answer("Select a game:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("select_game_"))
async def handle_game_selection(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        # Fetch the selected game
        game = await session.get(Game, game_id)
        if not game:
            await callback.message.answer("Game not found.")
            return

        # Prompt the user to choose a time slot
        await callback.message.answer(
            f"Select a time slot for the game at {game.time_slot}:",
            reply_markup=time_selection_keyboard()
        )
        await callback.answer()


@router.callback_query(F.data.startswith("game_time_"))
async def handle_game_time_selection(callback: types.CallbackQuery):
    time_slot = callback.data.split("_")[2]
    telegram_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        # Fetch the user
        user = await get_user(telegram_id, session)
        if not user:
            await callback.message.answer("You are not registered! Click /start to join the game.")
            return

        # Fetch the active game
        active_game = await session.execute(select(Game).where(Game.is_active == True))
        active_game = active_game.scalars().first()

        if active_game:
            player_game = PlayerGame(player_id=telegram_id, game_id=active_game.id)
            session.add(player_game)
            await session.commit()

        # Notify the admin
        await callback.bot.send_message(
            ADMIN_ID,
            f"✅ {user.name} will participate in the game at {time_slot}!"
        )

        await callback.message.answer(f"✅ You have joined the game at {time_slot}!")
        await callback.answer()
