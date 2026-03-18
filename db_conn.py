import psycopg2
import os
import sys
from dotenv import load_dotenv

# Загружаем .env с явной кодировкой
load_dotenv('settings/.env', encoding='utf-8')

# Читаем переменные
DB_HOST = os.getenv('DB_HOST') or 'localhost'
DB_NAME = os.getenv('DB_NAME') or 'db_tg_bot_calendar'
DB_USER = os.getenv('DB_USER') or 'ktts_ds'
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Проверка пароля
if not DB_PASSWORD:
    sys.stderr.write("❌ DB_PASSWORD отсутствует!\n")
    sys.exit(1)

# Принудительное декодирование (на случай, если где-то затесались байты)
try:
    # Убедимся, что все параметры — строки в чистом UTF-8
    DB_HOST = str(DB_HOST).strip()
    DB_NAME = str(DB_NAME).strip()
    DB_USER = str(DB_USER).strip()
    DB_PASSWORD = str(DB_PASSWORD).strip()

    # Логируем без пароля
    sys.stderr.write(f"✅ Подключение: host={DB_HOST}, db={DB_NAME}, user={DB_USER}\n")

    # Подключаемся
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        client_encoding='UTF8'
    )
    sys.stderr.write("✅ Подключение к БД успешно!\n")

except UnicodeError as e:
    sys.stderr.write(f"❌ Ошибка кодировки в параметрах: {e}\n")
    raise
except Exception as e:
    sys.stderr.write(f"❌ Ошибка подключения: {e}\n")
    raise