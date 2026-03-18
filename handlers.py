from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters
)
import logging
import re

logger = logging.getLogger(__name__)

_calendar = None

# Состояния для диалога создания события
(NAME, DATE, TIME, DETAILS) = range(4)

# Состояния для диалога редактирования события
(EDIT_ID, EDIT_NAME, EDIT_DATE, EDIT_TIME, EDIT_DETAILS) = range(4, 9)

# Вспомогательные функции для валидации
def is_valid_date(date_str: str) -> bool:
    """Проверяет формат ГГГГ-ММ-ДД"""
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', date_str))

def is_valid_time(time_str: str) -> bool:
    """Проверяет формат ЧЧ:ММ"""
    return bool(re.match(r'^\d{2}:\d{2}$', time_str))

async def ensure_user_registered(update: Update):
    """Гарантирует, что пользователь есть в БД (авторегистрация)"""
    user = update.effective_user
    _calendar.ensure_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

# ---------- Диалог создания события ----------
async def create_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user_registered(update)
    await update.message.reply_text("Введите название события:")
    return NAME

async def create_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_name'] = update.message.text
    await update.message.reply_text("Введите дату (ГГГГ-ММ-ДД):")
    return DATE

async def create_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    if not is_valid_date(date):
        await update.message.reply_text("Неверный формат. Введите дату в формате ГГГГ-ММ-ДД:")
        return DATE
    context.user_data['event_date'] = date
    await update.message.reply_text("Введите время (ЧЧ:ММ):")
    return TIME

async def create_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time = update.message.text
    if not is_valid_time(time):
        await update.message.reply_text("Неверный формат. Введите время в формате ЧЧ:ММ:")
        return TIME
    context.user_data['event_time'] = time
    await update.message.reply_text("Введите описание события:")
    return DETAILS

async def create_event_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text
    user_id = update.effective_user.id
    event_id = _calendar.create_event(
        user_id,
        context.user_data['event_name'],
        context.user_data['event_date'],
        context.user_data['event_time'],
        details
    )
    await update.message.reply_text(f"Событие создано с номером {event_id}.")
    context.user_data.clear()
    return ConversationHandler.END

async def create_event_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание события отменено.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- Диалог редактирования события ----------
async def edit_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user_registered(update)
    await update.message.reply_text("Введите ID события, которое хотите отредактировать:")
    return EDIT_ID

async def edit_event_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        event_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте снова:")
        return EDIT_ID
    user_id = update.effective_user.id
    # Проверим, существует ли такое событие у пользователя
    event = _calendar.read_event(user_id, event_id)
    if event is None:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено. Попробуйте другой ID или /cancel для отмены.")
        return EDIT_ID
    context.user_data['edit_event_id'] = event_id
    await update.message.reply_text("Введите новое название события:")
    return EDIT_NAME

async def edit_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['edit_name'] = update.message.text
    await update.message.reply_text("Введите новую дату (ГГГГ-ММ-ДД):")
    return EDIT_DATE

async def edit_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    if not is_valid_date(date):
        await update.message.reply_text("Неверный формат. Введите дату в формате ГГГГ-ММ-ДД:")
        return EDIT_DATE
    context.user_data['edit_date'] = date
    await update.message.reply_text("Введите новое время (ЧЧ:ММ):")
    return EDIT_TIME

async def edit_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time = update.message.text
    if not is_valid_time(time):
        await update.message.reply_text("Неверный формат. Введите время в формате ЧЧ:ММ:")
        return EDIT_TIME
    context.user_data['edit_time'] = time
    await update.message.reply_text("Введите новое описание события:")
    return EDIT_DETAILS

async def edit_event_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text
    user_id = update.effective_user.id
    success = _calendar.edit_event(
        user_id,
        context.user_data['edit_event_id'],
        new_name=context.user_data['edit_name'],
        new_date=context.user_data['edit_date'],
        new_time=context.user_data['edit_time'],
        new_details=details
    )
    if success:
        await update.message.reply_text(f"Событие {context.user_data['edit_event_id']} обновлено.")
    else:
        await update.message.reply_text("Не удалось обновить событие.")
    context.user_data.clear()
    return ConversationHandler.END

async def edit_event_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Редактирование отменено.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- Одношаговые обработчики ----------
async def event_read_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user_registered(update)
    user_id = update.effective_user.id
    try:
        if not context.args:
            await update.message.reply_text("Укажите ID события: /read_event <id>")
            return
        event_id = int(context.args[0])
        event = _calendar.read_event(user_id, event_id)
        if event is None:
            await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
        else:
            text = (
                f"ID: {event['id']}\n"
                f"Название: {event['name']}\n"
                f"Дата: {event['date']}\n"
                f"Время: {event['time']}\n"
                f"Описание: {event['details']}"
            )
            await update.message.reply_text(text)
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
    except Exception as e:
        logger.exception("Ошибка в event_read_handler")
        await update.message.reply_text("Произошла ошибка при чтении события.")

async def event_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user_registered(update)
    user_id = update.effective_user.id
    try:
        if not context.args:
            await update.message.reply_text("Укажите ID события: /delete_event <id>")
            return
        event_id = int(context.args[0])
        success = _calendar.delete_event(user_id, event_id)
        if success:
            await update.message.reply_text(f"Событие {event_id} удалено.")
        else:
            await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
    except Exception as e:
        logger.exception("Ошибка в event_delete_handler")
        await update.message.reply_text("Произошла ошибка при удалении события.")

async def event_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user_registered(update)
    user_id = update.effective_user.id
    try:
        events = _calendar.list_events(user_id)
        if not events:
            await update.message.reply_text("У вас пока нет событий.")
            return
        lines = [f"{e['id']}: {e['name']} ({e['date']} {e['time']})" for e in events]
        await update.message.reply_text("Ваши события:\n" + "\n".join(lines))
    except Exception as e:
        logger.exception("Ошибка в event_list_handler")
        await update.message.reply_text("Произошла ошибка при получении списка событий.")

async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    success = _calendar.register_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    if success:
        await update.message.reply_text(f"{user.first_name}, вы успешно зарегистрированы!")
    else:
        await update.message.reply_text("Вы уже зарегистрированы.")

# ---------- Регистрация обработчиков ----------
def register_handlers(application, calendar):
    global _calendar
    _calendar = calendar

    # Диалог создания события
    create_conv = ConversationHandler(
        entry_points=[CommandHandler('create_event', create_event_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_name)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_time)],
            DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_details)],
        },
        fallbacks=[CommandHandler('cancel', create_event_cancel)]
    )
    application.add_handler(create_conv)

    # Диалог редактирования события
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler('edit_event', edit_event_start)],
        states={
            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_get_id)],
            EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_name)],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_date)],
            EDIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_time)],
            EDIT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_details)],
        },
        fallbacks=[CommandHandler('cancel', edit_event_cancel)]
    )
    application.add_handler(edit_conv)

    # Одношаговые команды
    application.add_handler(CommandHandler('register', register_handler))
    application.add_handler(CommandHandler('read_event', event_read_handler))
    application.add_handler(CommandHandler('delete_event', event_delete_handler))
    application.add_handler(CommandHandler('list_events', event_list_handler))