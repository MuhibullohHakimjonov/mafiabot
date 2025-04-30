import signal
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from handlers import router
from config import BOT_TOKEN, ADMIN_ID, DATABASE_URL
from keyboard import admin_decision_keyboard
from db_middleware import DbSessionMiddleware

# Logging
logging.basicConfig(level=logging.INFO)

# DB setup
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Scheduler job
async def ask_admin(bot: Bot):
    try:
        logging.info("Sending message to admin")
        await bot.send_message(
            ADMIN_ID,
            "Are we gonna play mafia today?",
            reply_markup=admin_decision_keyboard()
        )
    except Exception as e:
        logging.error(f"Failed to send message: {e}", exc_info=True)


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware(session_factory=async_session_factory))
    dp.include_router(router)


    await bot.set_my_commands([BotCommand(command="start", description="Start the bot")])

    scheduler = AsyncIOScheduler()
    scheduler.add_job(ask_admin, "interval", minutes=240, args=[bot])
    scheduler.start()

    stop_event = asyncio.Event()

    def _handle_signal():
        logging.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except asyncio.CancelledError:
        logging.info("Polling cancelled")
    finally:
        await stop_event.wait()
        await shutdown(bot, scheduler)

async def shutdown(bot: Bot, scheduler: AsyncIOScheduler):
    logging.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await bot.session.close()
    logging.info("Shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped manually")
