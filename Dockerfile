FROM node:22-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    AI_DRAMA_DATA_FILE=/data/app_state.json

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY --from=frontend-build /build/frontend/dist ./web

RUN pip install --no-cache-dir .
RUN mkdir -p /data

EXPOSE 8765
VOLUME ["/data"]

CMD ["python", "-m", "ai_drama_agent.web", "--host", "0.0.0.0", "--port", "8765"]
