"""Create tables for User, Game, PlayerGame, and Group

Revision ID: e3ae9e0a2fa2
Revises: None
Create Date: 2025-04-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "e3ae9e0a2fa2"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('telegram_id', sa.BigInteger, nullable=False, unique=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Index('ix_users_id', 'id')
    )

    # Create game table
    op.create_table(
        'game',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('time_slot', sa.String, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('group_id', sa.BigInteger, nullable=False),
        sa.Index('ix_game_id', 'id')
    )

    # Create groups table
    op.create_table(
        'groups',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('title', sa.String, nullable=False)
    )

    # Create player_games table
    op.create_table(
        'player_games',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('player_id', sa.BigInteger, sa.ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('game_id', sa.Integer, sa.ForeignKey('game.id', ondelete='CASCADE'), nullable=False),
        sa.Index('ix_player_games_id', 'id')
    )

def downgrade():
    op.drop_table('player_games')
    op.drop_table('groups')
    op.drop_table('game')
    op.drop_table('users')