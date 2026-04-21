# Используем официальный образ Python 3.12
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /TGBot

# Устанавливаем системные зависимости для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта в контейнер
COPY . .

# Команда по умолчанию (для сервиса web). Для бота команду переопределим в docker-compose
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]