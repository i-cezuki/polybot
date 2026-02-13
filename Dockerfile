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

CMD ["python", "src/main.py"]
