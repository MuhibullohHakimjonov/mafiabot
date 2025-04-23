#!/bin/bash
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if pg_isready -h db -p 5432 -U ${POSTGRES_USER} -d ${POSTGRES_DB}; then
        echo "PostgreSQL is ready!"
        break
    fi
    echo "Waiting for PostgreSQL ($i/30)..."
    sleep 1
done

echo "Running migrations..."
alembic upgrade head
echo "Starting bot..."
python main.py
