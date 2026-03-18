from telegram.ext import Application, CommandHandler
import os, logging
from dotenv import load_dotenv
import psycopg2
from db_conn import conn
from note_calendar import Calendar

calendar = Calendar(conn)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update, context):
    await update.message.reply_text('Привет! Я бот для работы с календарём событий.')


load_dotenv('settings/.env')
token = os.getenv('API_TOKEN')


def main():
    # Инициализация приложения через builder
    application = (
        Application.builder()
        .token(token)
        .build()
    )

    # Регистрация основных команд
    application.add_handler(CommandHandler("start", start))

    # Регистрация обработчиков из отдельного файла
    from handlers import register_handlers
    register_handlers(application, calendar)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()