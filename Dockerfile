FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

RUN dos2unix start.sh && chmod +x start.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["./start.sh"]
