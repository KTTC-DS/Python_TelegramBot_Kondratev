import os
import django
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

load_dotenv('.env', encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TGbot.settings')
django.setup()

from app.bot_handlers import (
    start, create_event, invite, button_callback,
    calendar_cmd, my_events_cmd, edit_event, delete_event,
    share_event, unshare_event, public_events_cmd, export_events_cmd
)

async def error_handler(update, context):
    print(f"Ошибка: {context.error}")

def main():
    token = os.getenv('API_TOKEN')
    # Устанавливаем таймауты (без сложного HTTPX)
    app = (ApplicationBuilder()
           .token(token)
           .connect_timeout(30.0)
           .read_timeout(30.0)
           .build())

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calendar", calendar_cmd))
    app.add_handler(CommandHandler("my_events", my_events_cmd))
    app.add_handler(CommandHandler("create_event", create_event))
    app.add_handler(CommandHandler("edit_event", edit_event))
    app.add_handler(CommandHandler("delete_event", delete_event))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("share_event", share_event))
    app.add_handler(CommandHandler("unshare_event", unshare_event))
    app.add_handler(CommandHandler("public_events", public_events_cmd))
    app.add_handler(CommandHandler("export_events", export_events_cmd))
    app.add_error_handler(error_handler)
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()