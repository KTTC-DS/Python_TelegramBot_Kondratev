import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from .models import UserProfile, Event, Appointment

# ---------- Вспомогательные функции (синхронные) ----------
def get_or_create_user_profile(telegram_id, username, first_name, last_name):
    """Возвращает UserProfile, создаёт User и Profile при необходимости"""
    try:
        profile = UserProfile.objects.get(telegram_id=str(telegram_id))
        return profile
    except UserProfile.DoesNotExist:
        # Создаём пользователя Django
        user = User.objects.create_user(
            username=f"tg_{telegram_id}",
            first_name=first_name or "",
            last_name=last_name or ""
        )
        profile = UserProfile.objects.create(user=user, telegram_id=str(telegram_id))
        return profile

def get_event_by_id(event_id):
    try:
        return Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return None

def create_appointment(event, user_profile):
    appointment = Appointment.objects.create(
        event=event,
        user=user_profile.user,
        status='pending'
    )
    return appointment

def update_appointment_status(appointment_id, new_status):
    try:
        app = Appointment.objects.get(id=appointment_id)
        app.status = new_status
        app.save()
        return True
    except Appointment.DoesNotExist:
        return False

# ---------- Асинхронные обработчики ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для встреч.\n"
                                    "/create_event — создать событие\n"
                                    "/invite <event_id> <telegram_id> — пригласить участника")

async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Простой диалог: название, дата, время, описание"""
    # Для простоты сделаем через аргументы команды: /create_event Название ГГГГ-ММ-ДД ЧЧ:ММ Описание
    args = context.args
    if len(args) < 4:
        await update.message.reply_text("Использование: /create_event Название ГГГГ-ММ-ДД ЧЧ:ММ Описание")
        return
    name = args[0]
    date = args[1]
    time = args[2]
    description = " ".join(args[3:])

    # Валидация даты и времени
    if not re.match(r'\d{4}-\d{2}-\d{2}', date):
        await update.message.reply_text("Дата должна быть в формате ГГГГ-ММ-ДД")
        return
    if not re.match(r'\d{2}:\d{2}', time):
        await update.message.reply_text("Время должно быть в формате ЧЧ:ММ")
        return

    # Создаём событие в БД
    event = await sync_to_async(Event.objects.create)(
        name=name, date=date, time=time, description=description
    )
    await update.message.reply_text(f"Событие '{name}' создано с ID {event.id}")

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приглашает пользователя по его telegram_id на событие"""
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /invite <event_id> <telegram_id_участника>")
        return
    try:
        event_id = int(args[0])
        target_tg_id = int(args[1])
    except ValueError:
        await update.message.reply_text("ID события и Telegram ID должны быть числами")
        return

    # Получаем событие
    event = await sync_to_async(get_event_by_id)(event_id)
    if not event:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено")
        return

    # Получаем профиль приглашаемого
    target_profile = await sync_to_async(get_or_create_user_profile)(target_tg_id, None, None, None)

    # Создаём приглашение
    appointment = await sync_to_async(create_appointment)(event, target_profile)

    # Готовим inline-кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{appointment.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{appointment.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Текст уведомления
    text = (
        f"📅 *Приглашение на встречу*\n\n"
        f"Событие: {event.name}\n"
        f"Дата: {event.date}\n"
        f"Время: {event.time}\n"
        f"Описание: {event.description or '—'}\n\n"
        f"Нажмите кнопку, чтобы подтвердить или отклонить."
    )

    try:
        await context.bot.send_message(
            chat_id=target_tg_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await update.message.reply_text(f"Приглашение отправлено пользователю {target_tg_id}")
    except Exception as e:
        await update.message.reply_text(f"Не удалось отправить сообщение: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # всегда отвечаем, чтобы убрать состояние загрузки

    data = query.data
    if data.startswith("confirm_"):
        app_id = int(data.split("_")[1])
        success = await sync_to_async(update_appointment_status)(app_id, 'confirmed')
        if success:
            await query.edit_message_text("✅ Вы подтвердили участие во встрече.")
        else:
            await query.edit_message_text("❌ Ошибка: приглашение не найдено.")
    elif data.startswith("decline_"):
        app_id = int(data.split("_")[1])
        success = await sync_to_async(update_appointment_status)(app_id, 'cancelled')
        if success:
            await query.edit_message_text("❌ Вы отклонили приглашение.")
        else:
            await query.edit_message_text("❌ Ошибка: приглашение не найдено.")