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

# Set up logging
logging.basicConfig(level=logging.INFO)

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


async def shutdown(bot: Bot, scheduler: AsyncIOScheduler):
    logging.info("Initiating shutdown...")
    scheduler.shutdown(wait=False)  # Stop scheduler immediately
    await bot.session.close()  # Close bot session
    await engine.dispose()  # Close database connections
    logging.info("Shutdown complete")

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(session_factory=async_session_factory))
    dp.include_router(router)
    setup_scheduler(bot)

    await bot.set_my_commands([BotCommand(command="start", description="Start the bot")])

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    tasks = []

    def handle_shutdown():
        tasks.append(loop.create_task(shutdown(bot, scheduler)))
        for task in asyncio.all_tasks(loop):
            if task is not asyncio.current_task():
                task.cancel()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "chat_member", "my_chat_member", "callback_query"])
    except asyncio.CancelledError:
        logging.info("Polling cancelled")
    finally:
        await shutdown(bot, scheduler)



if __name__ == "__main__":
    asyncio.run(main())

