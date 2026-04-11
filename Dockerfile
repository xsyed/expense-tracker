FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN chmod +x entrypoint.sh

ARG STATIC_VERSION=0
ENV STATIC_VERSION=${STATIC_VERSION}

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
