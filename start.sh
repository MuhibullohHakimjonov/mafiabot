#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 2
done

echo "PostgreSQL is ready. Running migrations..."

# Run Alembic migrations
alembic upgrade head

echo "Starting the bot..."

# Start the bot
python main.py
