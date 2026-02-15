# --- Stage 1: Build Frontend (Node.js) ---
FROM node:18-alpine as frontend-builder

WORKDIR /app/frontend

# パッケージ定義をコピーしてインストール (キャッシュ活用)
COPY src/web/frontend/package.json src/web/frontend/package-lock.json* ./
RUN npm ci

# ソースコードをコピーしてビルド
COPY src/web/frontend/ ./
RUN npm run build
# -> /app/frontend/dist に成果物が生成される

# --- Stage 2: Setup Python Bot (Production) ---
FROM python:3.11-slim

WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコード一式をコピー
COPY . .

# Stage 1で作ったReactのビルド成果物を、Pythonが参照する場所にコピー
COPY --from=frontend-builder /app/frontend/dist /app/src/web/frontend/dist

# 環境変数の設定 (ログ出力の即時表示など)
ENV PYTHONUNBUFFERED=1

# 実行コマンド
CMD ["python", "-m", "src.main"]
