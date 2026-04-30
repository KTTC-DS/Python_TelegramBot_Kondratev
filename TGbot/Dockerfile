# Используем официальный образ Python 3.12
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
# Должна совпадать с путём монтирования в docker-compose.yml (./:/app)
WORKDIR /app

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

# Копируем скрипт entrypoint и делаем его исполняемым
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Указываем entrypoint (выполняется при запуске контейнера)
ENTRYPOINT ["/entrypoint.sh"]