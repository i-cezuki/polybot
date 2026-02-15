# Stage 1: フロントエンドビルド
FROM node:20-slim AS frontend-build

WORKDIR /frontend
COPY src/web/frontend/package.json src/web/frontend/package-lock.json* ./
RUN npm install
COPY src/web/frontend/ ./
RUN npm run build

# Stage 2: Python アプリケーション
FROM python:3.11-slim

WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python依存パッケージ
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY . .

# ビルド済みフロントエンドをコピー
COPY --from=frontend-build /frontend/dist /app/src/web/frontend/dist

CMD ["python", "src/main.py"]
