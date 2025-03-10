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
        logging.info(f"Middleware processing event: {event}")
        async with self.session_factory() as session:
            data["session"] = session
            result = await handler(event, data)
            logging.info(f"Middleware finished processing event: {event}")
            return result
