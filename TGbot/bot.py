import os
import django
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

load_dotenv('../settings/.env', encoding='utf-8')

token = os.getenv('API_TOKEN')
if not token:
    raise ValueError("API_TOKEN не найден в .env файле")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TGbot.settings')
django.setup()

from app.bot_handlers import start, create_event, invite, button_callback
from app.models import UserProfile, Event, Appointment

def main():
    token = os.getenv('API_TOKEN')
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create_event", create_event))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()