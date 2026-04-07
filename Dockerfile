# Берём лёгкий бетон
FROM python:3.12-slim

# Ставим скоростной бур (uv) напрямую из их репозитория
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Размечаем площадку
WORKDIR /app

# Заливаем зависимости
COPY pyproject.toml .

# Ставим пакеты системно, виртуальная среда внутри контейнера не нужна
RUN uv pip install --system .

# Завозим код
COPY src/ src/

# Команда на старт двигателя
CMD ["python", "src/main.py"]
