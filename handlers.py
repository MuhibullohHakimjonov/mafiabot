import aiogram
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery

from keyboard import admin_decision_keyboard, game_time_keyboard, user_response_keyboard, join_game_keyboard
from config import ADMIN_ID
from models import User, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = Router()
players_today = set()


async def get_user(telegram_id: int, session: AsyncSession):
    """Fetches user from database by telegram_id."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()


@router.message(Command("start"))
async def start(message: types.Message):
    """Handles start command. Different messages for admin and users."""
    if message.from_user.id == ADMIN_ID:
        await message.answer("Hello, Admin! Do we play Mafia today?", reply_markup=admin_decision_keyboard())
    else:
        async with AsyncSessionLocal() as session:
            user = await get_user(message.from_user.id, session)
            if user:
                await message.answer("You are already registered!")
            else:
                await message.answer("Click below to join the game!", reply_markup=join_game_keyboard())


@router.callback_query(F.data == "admin_yes")
async def admin_yes(callback: types.CallbackQuery):
    """Handles admin clicking 'Yes' and asks for time slot."""
    await callback.message.edit_text("Select a time slot:", reply_markup=game_time_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_no")
async def admin_no(callback: types.CallbackQuery):
    """Handles admin clicking 'No'."""
    await callback.message.edit_text("Okay, no game today!")
    await callback.answer()


@router.callback_query(F.data.startswith("time_"))
async def set_game_time(callback: types.CallbackQuery):
    """Handles time slot selection and asks users if they want to play."""
    time_slot = callback.data.split("_")[1]
    await callback.message.answer(f"Game scheduled at {time_slot}!")

    async with AsyncSessionLocal() as session:
        # Fetch registered users from database
        result = await session.execute(select(User.telegram_id))
        users = result.scalars().all()

    for user_id in users:
        try:
            await callback.bot.send_message(
                user_id,
                f"Mafia game at {time_slot}! Will you join?",
                reply_markup=user_response_keyboard()
            )
            print(f"✅ Sent game invite to {user_id}")
        except Exception as e:
            print(f"❌ Failed to send message to {user_id}: {e}")

    await callback.answer()


@router.callback_query(F.data == "register")
async def register(callback: CallbackQuery):
    """Handles user clicking 'Join Game' button for registration."""
    async with AsyncSessionLocal() as session:
        user = await get_user(callback.from_user.id, session)
        if user:
            await callback.message.answer("You have already joined!")
        else:
            new_user = User(telegram_id=callback.from_user.id, name=callback.from_user.full_name)
            session.add(new_user)
            await session.commit()
            await callback.message.answer("You have successfully joined the game! ✅")
    await callback.answer()


@router.callback_query(F.data.in_(["join_game", "decline_game"]))
async def handle_user_decision(callback: CallbackQuery):
    """Handles user decision for today's game."""
    user_choice = callback.data

    async with AsyncSessionLocal() as session:
        user = await get_user(callback.from_user.id, session)

    if not user:
        await callback.message.answer("You are not registered! Click /start to join the game.")
        return

    if user_choice == "join_game":
        if user.telegram_id in players_today:
            await callback.message.answer("You have already joined today's game!")
        else:
            players_today.add(user.telegram_id)
            await callback.message.answer("Okay, you joined! 🎉")
            try:
                await callback.bot.send_message(ADMIN_ID, f"✅ {user.name} is joining the game!")
            except Exception as e:
                print(f"❌ Failed to notify admin: {e}")

    elif user_choice == "decline_game":
        await callback.message.answer("Maybe next time! 🙂")
        await callback.bot.send_message(ADMIN_ID, f"❌ {user.name} is not joining the game!")

    await callback.answer()
