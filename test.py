import sys
sys.path.append('.')  # если нужно

# Загружаем .env вручную
from dotenv import load_dotenv
load_dotenv('settings/.env', encoding='utf-8')

from db_conn import conn

cursor = conn.cursor()
cursor.execute("SELECT current_user, current_database();")
print("Подключён как:", cursor.fetchone())
cursor.close()