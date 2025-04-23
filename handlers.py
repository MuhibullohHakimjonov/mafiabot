import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, ChatMemberUpdated, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete
from config import ADMIN_ID
from keyboard import game_time_keyboard, admin_panel_keyboard, add_bot_to_group_button
from models import User, AsyncSessionLocal, Game, PlayerGame, Group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db

router = Router()
players_today = {}


class RegisterState(StatesGroup):
    waiting_for_name = State()


@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    bot_username = (await message.bot.get_me()).username

    async with get_db() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        existing_user = result.scalars().first()

    if existing_user:
        if telegram_id == ADMIN_ID:
            await message.answer("👑 Welcome, Admin!", reply_markup=admin_panel_keyboard())
        else:
            await message.answer(
                "👋 Welcome back!",
                reply_markup=add_bot_to_group_button(bot_username)
            )
    else:
        await message.answer("👋 Welcome! Please type your name to register:")
        await state.set_state(RegisterState.waiting_for_name)


@router.message(RegisterState.waiting_for_name)
async def register_user(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    user_name = message.text.strip()

    async with get_db() as db:
        new_user = User(telegram_id=telegram_id, name=user_name)
        db.add(new_user)
        await db.commit()

    await state.clear()

    await message.answer(f"✅ Welcome, {user_name}! You are now registered.")


# 🤖 BOT handlers ------------------------------------------------------

@router.my_chat_member()
async def on_bot_status_update(event: ChatMemberUpdated, bot: Bot, session: AsyncSession):
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
        await session.execute(delete(Group).where(Group.id == chat_id))
        await session.commit()

    else:
        warning_msg = await bot.send_message(chat_id, "⚠️ Please promote me to admin to start a game!")
        await asyncio.sleep(10)
        await bot.delete_message(chat_id, warning_msg.message_id)


async def is_bot_admin(chat_id: int, bot: Bot) -> bool:
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


@router.message(RegisterState.waiting_for_name)
async def save_name(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    name = message.text.strip()

    async with get_db() as db:
        new_user = User(telegram_id=telegram_id, name=name)
        db.add(new_user)
        await db.commit()

    await message.answer(f"Thank you, {name}! You are now registered.")
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
    time_slot = callback.data.split("_")[1]

    async with AsyncSessionLocal() as session:
        group_result = await session.execute(select(Group))
        groups = group_result.scalars().all()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Join", callback_data="join_yes_{}"),
                    InlineKeyboardButton(text="❌ No", callback_data="join_no_{}"),
                ]
            ]
        )

        for group in groups:
            new_game = Game(time_slot=time_slot, group_id=group.id)
            session.add(new_game)
            await session.flush()
            game_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Join", callback_data=f"join_yes_{new_game.id}"),
                        InlineKeyboardButton(text="❌ No", callback_data=f"join_no_{new_game.id}"),
                    ]
                ]
            )

            try:
                game_message = await callback.bot.send_message(
                    chat_id=group.id,
                    text=f"📢 **A new Mafia game is scheduled at {time_slot}!** Will you join?",
                    reply_markup=game_keyboard
                )

                await callback.bot.pin_chat_message(
                    chat_id=group.id,
                    message_id=game_message.message_id,
                    disable_notification=True
                )

            except Exception as e:
                print(f"❌ Failed to send/pin message in group {group.id}: {e}")
                continue

            await asyncio.sleep(0.05)

        await session.commit()

    await callback.message.answer(f"✅ Game scheduled at {time_slot} for all groups!")
    await callback.answer()


async def refresh_game_message(callback: types.CallbackQuery, game_id: int):
    async with AsyncSessionLocal() as session:
        game = await session.execute(
            select(Game).where(Game.id == game_id, Game.group_id == callback.message.chat.id)
        )
        game = game.scalar_one_or_none()

        if not game:
            await callback.answer("❌ This game has ended or doesn't belong to this group.", show_alert=True)
            return

        result = await session.execute(
            select(User.name, PlayerGame.status)
            .join(PlayerGame, User.telegram_id == PlayerGame.player_id)
            .where(PlayerGame.game_id == game_id)
        )
        players = result.all()

    joined_players = [f"✅ {p[0]}" for p in players if p[1] == "joined"]
    declined_players = [f"❌ {p[0]}" for p in players if p[1] == "declined"]

    joined_text = "\n".join(joined_players) if joined_players else "No players joined yet."
    declined_text = "\n".join(declined_players) if declined_players else "No players declined yet."

    new_text = f"""
📢 **Mafia Game Scheduled!**  
🕒 **Time Slot:** {game.time_slot}

**Joined Players:**
{joined_text}

**Declined Players:**
{declined_text}
    """.strip()

    if callback.message.text.strip() == new_text:
        await callback.answer("ℹ️ The message is already up to date.")
        return

    await callback.message.edit_text(new_text, reply_markup=callback.message.reply_markup)

    await callback.answer()


@router.callback_query(F.data.startswith("join_yes_"))
async def join_yes(callback: types.CallbackQuery):
    """Handles when a user confirms participation."""
    game_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        # ✅ Check if the game still exists
        game = await session.get(Game, game_id)
        if not game:
            await callback.answer("❌ This game has ended.", show_alert=True)
            return

        # ✅ Check if user is registered
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalars().first()

        if not user:
            await callback.answer("⚠️ You need to register first! Use /start.", show_alert=True)
            return

        # ✅ Check if the user already responded
        result = await session.execute(
            select(PlayerGame).where(PlayerGame.game_id == game_id, PlayerGame.player_id == user_id)
        )
        existing_entry = result.scalars().first()

        if existing_entry and existing_entry.status == "joined":
            await callback.answer("ℹ️ You have already joined this game.", show_alert=True)
            return

        if not existing_entry:
            new_player = PlayerGame(game_id=game_id, player_id=user_id, status="joined")
            session.add(new_player)
        else:
            existing_entry.status = "joined"

        await session.commit()

        await callback.bot.send_message(
            ADMIN_ID, f"✅ {user.name} has joined the game at {game.time_slot}."
        )

    # ✅ Refresh game message dynamically
    await refresh_game_message(callback, game_id)
    await callback.answer("✅ You have joined the game!")


@router.callback_query(F.data.startswith("join_no_"))
async def join_no(callback: types.CallbackQuery):
    """Handles when a user declines participation."""
    game_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        # ✅ Check if the game still exists
        game = await session.get(Game, game_id)
        if not game:
            await callback.answer("❌ This game has ended.", show_alert=True)
            return

        # ✅ Check if user is registered
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalars().first()

        if not user:
            await callback.answer("⚠️ You need to register first! Use /start.", show_alert=True)
            return

        # ✅ Check if the user already responded
        result = await session.execute(
            select(PlayerGame).where(PlayerGame.game_id == game_id, PlayerGame.player_id == user_id)
        )
        existing_entry = result.scalars().first()

        if existing_entry and existing_entry.status == "declined":
            await callback.answer("ℹ️ You have already declined this game.", show_alert=True)
            return

        if not existing_entry:
            new_player = PlayerGame(game_id=game_id, player_id=user_id, status="declined")
            session.add(new_player)
        else:
            existing_entry.status = "declined"

        await session.commit()

        await callback.bot.send_message(
            ADMIN_ID, f"❌ {user.name} has declined to join the game at {game.time_slot}."
        )
    await refresh_game_message(callback, game_id)
    await callback.answer("❌ You declined the game.")


@router.message(F.text == "👥 View Groups")
async def admin_view_groups(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Group))
        groups = result.scalars().all()

    if not groups:
        await message.answer("❌ No groups found.")
        return

    keyboard = InlineKeyboardBuilder()
    for group in groups:
        keyboard.add(InlineKeyboardButton(
            text=str(group.title or group.id),
            callback_data=f"view_games_{group.id}"
        ))

    await message.answer("📋 Select a group:", reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("view_games_"))
async def admin_view_games(callback: types.CallbackQuery):
    group_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game).where(Game.group_id == group_id))
        games = result.scalars().all()

    if not games:
        await callback.message.edit_text("❌ No games in this group.")
        return

    keyboard = InlineKeyboardBuilder()
    for game in games:
        keyboard.add(InlineKeyboardButton(
            text=f"{game.time_slot}",
            callback_data=f"view_players_{game.id}"
        ))
    keyboard.adjust(2)

    await callback.message.edit_text(
        "🎮 Select a game to view players:", reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("view_players_"))
async def admin_view_players(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        game = await session.get(Game, game_id)
        if not game:
            await callback.answer("❌ Game not found.")
            return

        result = await session.execute(
            select(User.name, PlayerGame.status)
            .join(PlayerGame, User.telegram_id == PlayerGame.player_id)
            .where(PlayerGame.game_id == game_id)
        )
        players = result.all()

    joined = [f"✅ {p[0]}" for p in players if p[1] == "joined"]
    declined = [f"❌ {p[0]}" for p in players if p[1] == "declined"]

    joined_text = "\n".join(joined) or "No players joined."
    declined_text = "\n".join(declined) or "No players declined."

    await callback.message.edit_text(f"""
🎮 **Game at {game.time_slot}**

👥 **Joined:**
{joined_text}

🚫 **Declined:**
{declined_text}
    """.strip())


@router.message(F.text == "📌 Active Games")
async def show_active_games(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Game).where(Game.is_active == True))
        active_games = result.scalars().all()
        result_group = await session.execute(select(Group))
        groups = result_group.scalars().all()

    if not active_games:
        await message.answer("❌ No active games at the moment.")
        return
    keyboard = InlineKeyboardBuilder()
    for game in active_games:
        keyboard.add(InlineKeyboardButton(
            text=f"🗑 Delete {[group.title for group in groups if group.id == game.group_id]} {game.time_slot}",
            callback_data=f"delete_game_{game.id}"
        ))

    keyboard.adjust(2)
    await message.answer("📌 **Active Games:**\nSelect a game to delete:", reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("delete_game_"))
async def delete_game(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        game = await session.get(Game, game_id)
        if not game:
            await callback.message.answer("❌ Game not found.")
            return
        await session.execute(delete(PlayerGame).where(PlayerGame.game_id == game_id))
        await session.commit()
        await session.delete(game)
        await session.commit()

    await callback.message.answer(f"✅ Game at {game.time_slot} has been deleted.")
    await callback.answer()
