# Build frontend and backend for production

# 1) Build the React UI
FROM node:20-alpine AS ui-builder
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ .
RUN npm run build

# 2) Build the Python backend with the compiled UI assets
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and built UI
COPY . .
COPY --from=ui-builder /app/ui/dist ./ui/dist

EXPOSE 8888
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8888"]
