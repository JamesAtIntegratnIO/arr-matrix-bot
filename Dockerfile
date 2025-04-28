# ============================
# Stage 1: Builder
# ============================
FROM python:3.13-alpine AS builder

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    python3-dev

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# ============================
# Stage 2: Runtime
# ============================
FROM python:3.13-alpine

RUN apk add --no-cache \
    libstdc++ \
    libffi \
    openssl

WORKDIR /app

COPY --from=builder /install /usr/local

# This copies everything inside local matrix_bot/ (including config.py)
# into /app/matrix_bot/ inside the container
COPY matrix_bot/ /app/matrix_bot/

# Ensure config.json is handled (either copied here or mounted via volume)
# If mounting via volume, this line is not needed.
# COPY config.json /app/config.json

CMD ["python", "-m", "matrix_bot"]