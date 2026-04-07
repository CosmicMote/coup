# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (cached layer)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build
# Output: /app/frontend/dist/


# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install Python dependencies
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

# Copy game engine and server source
COPY coup/       ./coup/
COPY server/     ./server/
COPY web_main.py ./

# Copy the built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

EXPOSE 8080

CMD ["python", "web_main.py"]
