import psycopg2, os
from dotenv import load_dotenv

load_dotenv('settings/.env')

conn = psycopg2.connect(
    host='localhost',
    database='db_tg_bot_calendar',
    user='ktts_ds',
    password=os.getenv('DB_PASSWORD')
)