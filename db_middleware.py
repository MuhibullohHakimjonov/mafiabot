import logging
from aiogram.types import Update
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO)


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(self, handler, event: Update, data: dict):
        try:
            async with self.session_factory() as session:
                data["session"] = session
                return await handler(event, data)
        except asyncio.CancelledError:
            logging.warning("Middleware task was cancelled")
            raise  # Re-raise to allow proper shutdown
        except Exception as e:
            logging.exception("Unhandled exception in middleware")
            raise
