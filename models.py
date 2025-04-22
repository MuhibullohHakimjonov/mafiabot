from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String, nullable=False)
    player_games = relationship("PlayerGame", back_populates="player")


class Game(Base):
    __tablename__ = "game"

    id = Column(Integer, primary_key=True, index=True)
    time_slot = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    player_games = relationship(
        "PlayerGame",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    group_id = Column(BigInteger, nullable=False)


class PlayerGame(Base):
    __tablename__ = "player_games"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"),
                       nullable=False)
    status = Column(String, nullable=False)
    game_id = Column(Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False)
    player = relationship("User", back_populates="player_games")
    game = relationship("Game", back_populates="player_games")


class Group(Base):
    __tablename__ = "groups"

    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
