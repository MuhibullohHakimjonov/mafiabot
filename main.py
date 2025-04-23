from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from handlers import router
from config import BOT_TOKEN, ADMIN_ID, DATABASE_URL
from keyboard import admin_decision_keyboard
from db_middleware import DbSessionMiddleware

import asyncio
import logging

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

scheduler = AsyncIOScheduler()


async def ask_admin(bot: Bot):
    try:
        await bot.send_message(
            ADMIN_ID,
            "Are we gonna play mafia today?",
            reply_markup=admin_decision_keyboard()
        )
    except Exception as e:
        logging.error(f"Error sending message to admin: {e}")


def setup_scheduler(bot: Bot):
    scheduler.add_job(ask_admin, "interval", minutes=1, args=[bot])
    scheduler.start()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(session_factory=async_session_factory))
    dp.include_router(router)
    setup_scheduler(bot)

    await bot.set_my_commands([BotCommand(command="start", description="Start the bot")])
    await dp.start_polling(bot, allowed_updates=["message", "chat_member", "my_chat_member", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
