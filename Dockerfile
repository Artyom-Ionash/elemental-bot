# Используем официальный легковесный образ Python
FROM python:3.12-slim

# Копируем бинарный файл uv напрямую из официального образа Astral
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Настройки оптимизации uv внутри контейнера
# UV_COMPILE_BYTECODE=1: компилирует python-файлы в байт-код для быстрого старта бота
# PATH: добавляет путь к локальному .venv контейнера в системный PATH
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  PATH="/app/.venv/bin:$PATH"

# Размечаем площадку
WORKDIR /app

# 1. Сначала копируем ТОЛЬКО манифесты зависимостей.
# Это позволяет Docker кэшировать установленные библиотеки.
COPY pyproject.toml uv.lock* ./

# 2. Устанавливаем зависимости строго по лок-файлу без самого кода бота
# --frozen: заставляет uv строго следовать uv.lock без его перезаписи
# --no-install-project: не ставит структуру самого проекта на этом шаге
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev

# 3. Завозим актуальный код проекта.
# Теперь изменения в src/ не будут приводить к повторному скачиванию библиотек.
COPY src/ src/

# 4. Завершаем синхронизацию (устанавливаем структуру проекта, если требуется)
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev

# Команда запуска. Благодаря настройке PATH выше,
# системный python автоматически подхватит установленный .venv
CMD ["python", "src/main.py"]
