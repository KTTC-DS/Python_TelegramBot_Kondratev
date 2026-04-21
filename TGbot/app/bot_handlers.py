import re
import hashlib
import csv
import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile, Event, Appointment

logger = logging.getLogger(__name__)

# ---------- Синхронные функции для безопасного вызова через sync_to_async ----------
def _get_user_by_telegram_id(telegram_id):
    return User.objects.get(userprofile__telegram_id=str(telegram_id))

def _get_user_appointments(user):
    return list(Appointment.objects.filter(user=user).select_related('event').order_by('date', 'time'))

def _get_user_events(user):
    return list(Event.objects.filter(organizer=user).order_by('date', 'time'))

def _get_or_create_user_profile(telegram_id, username, first_name, last_name):
    try:
        return UserProfile.objects.get(telegram_id=str(telegram_id))
    except UserProfile.DoesNotExist:
        user = User.objects.create_user(
            username=f"tg_{telegram_id}",
            first_name=first_name or "",
            last_name=last_name or ""
        )
        return UserProfile.objects.create(user=user, telegram_id=str(telegram_id))

def _get_event_by_id(event_id):
    try:
        return Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return None

def _create_appointment(event, user_id):
    return Appointment.objects.create(
        event=event,
        user_id=user_id,
        date=event.date,
        time=event.time,
        details=event.description,
        status='pending'
    )

def _update_appointment_status(appointment_id, new_status):
    try:
        app = Appointment.objects.get(id=appointment_id)
        app.status = new_status
        app.save()
        return True
    except Appointment.DoesNotExist:
        return False

# ---------- Асинхронные утилиты ----------
async def _get_user_profile_from_update(update: Update) -> UserProfile:
    telegram_id = update.effective_user.id
    return await sync_to_async(UserProfile.objects.get)(telegram_id=str(telegram_id))

async def _get_event_and_check_owner(event_id: int, user_profile: UserProfile):
    event = await sync_to_async(_get_event_by_id)(event_id)
    if not event:
        return None, False
    return event, (event.organizer_id == user_profile.user_id)

# ---------- Команда /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await sync_to_async(_get_or_create_user_profile)(
        user.id, user.username, user.first_name, user.last_name
    )
    await update.message.reply_text(
        "✅ Вы зарегистрированы!\n\n"
        "📌 /create_event – создать событие\n"
        "📅 /calendar – мои встречи\n"
        "📋 /my_events – мои созданные события\n"
        "✏️ /edit_event <id> <название> <ГГГГ-ММ-ДД> <ЧЧ:ММ> [новое_описание]\n"
        "🗑 /delete_event <id> – удалить событие\n"
        "📨 /invite <event_id> <telegram_id> – пригласить участника (только организатор)\n"
        "📥 /export_events – выгрузить свои события в CSV"
    )

# ---------- Команда /calendar ----------
async def calendar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = await sync_to_async(_get_user_by_telegram_id)(telegram_id)
    appointments = await sync_to_async(_get_user_appointments)(user)

    if not appointments:
        await update.message.reply_text("У вас нет предстоящих встреч.")
        return

    text = "📅 *Ваши встречи:*\n\n"
    for app in appointments:
        status_icon = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌',
            'scheduled': '📌'
        }.get(app.status, '❓')
        text += f"{status_icon} *{app.event.name}* – {app.date} {app.time}\n"
        text += f"   Статус: {app.get_status_display()}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ---------- Команда /my_events ----------
async def my_events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = await sync_to_async(_get_user_by_telegram_id)(telegram_id)
    events = await sync_to_async(_get_user_events)(user)

    if not events:
        await update.message.reply_text("Вы ещё не создали ни одного события.")
        return

    text = "📌 *Созданные вами события:*\n\n"
    for ev in events:
        text += f"ID {ev.id}: {ev.name} – {ev.date} {ev.time}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ---------- Команда /create_event ----------
async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Использование: /create_event Название ГГГГ-ММ-ДД ЧЧ:ММ Описание"
        )
        return

    name = args[0]
    date = args[1]
    time = args[2]
    description = " ".join(args[3:])

    if not re.match(r'\d{4}-\d{2}-\d{2}', date):
        await update.message.reply_text("Дата должна быть в формате ГГГГ-ММ-ДД")
        return
    if not re.match(r'\d{2}:\d{2}', time):
        await update.message.reply_text("Время должно быть в формате ЧЧ:ММ")
        return

    try:
        profile = await _get_user_profile_from_update(update)
        event = await sync_to_async(Event.objects.create)(
            name=name, date=date, time=time, description=description,
            organizer_id=profile.user_id
        )
        profile.events_created += 1
        await sync_to_async(profile.save)()
        await update.message.reply_text(f"✅ Событие '{name}' создано с ID {event.id}")
    except Exception as e:
        logger.exception("Ошибка при создании события")
        await update.message.reply_text("❌ Произошла ошибка при создании события.")

# ---------- Команда /edit_event ----------
async def edit_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Использование: /edit_event <id> <новое_название> <ГГГГ-ММ-ДД> <ЧЧ:ММ> [новое_описание]"
        )
        return

    try:
        event_id = int(args[0])
        new_name = args[1]
        new_date = args[2]
        new_time = args[3]
        new_description = " ".join(args[4:]) if len(args) > 4 else None
    except (ValueError, IndexError):
        await update.message.reply_text("Неверный формат. ID должен быть числом.")
        return

    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Вы можете редактировать только свои события.")
        return

    event.name = new_name
    event.date = new_date
    event.time = new_time
    if new_description is not None:
        event.description = new_description

    await sync_to_async(event.save)()
    profile.events_edited += 1
    await sync_to_async(profile.save)()
    await update.message.reply_text(f"✅ Событие {event_id} обновлено.")

# ---------- Команда /delete_event ----------
async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Использование: /delete_event <id>")
        return
    try:
        event_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Вы можете удалять только свои события.")
        return

    profile.events_cancelled += 1
    await sync_to_async(profile.save)()
    await sync_to_async(event.delete)()
    await update.message.reply_text(f"✅ Событие {event_id} удалено.")

# ---------- Команда /invite ----------
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Получаем событие и проверяем права организатора
    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Только организатор может приглашать на событие.")
        return

    # Создаём или получаем профиль приглашаемого
    target_profile = await sync_to_async(_get_or_create_user_profile)(target_tg_id, None, None, None)
    appointment = await sync_to_async(_create_appointment)(event, target_profile.user_id)

    keyboard = [[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{appointment.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{appointment.id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
        await update.message.reply_text(f"✅ Приглашение отправлено пользователю {target_tg_id}")
    except Exception as e:
        logger.exception("Ошибка при отправке приглашения")
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")

# ---------- Команда /share_event ----------
async def share_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /share_event <id_события>")
        return
    try:
        event_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID события должен быть числом.")
        return

    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text("Событие не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Вы можете делиться только своими событиями.")
        return
    if event.is_public:
        await update.message.reply_text("ℹ️ Это событие уже публичное.")
        return

    event.is_public = True
    await sync_to_async(event.save)()
    await update.message.reply_text(
        f"✅ Событие *{event.name}* теперь публично. Другие пользователи могут его видеть.",
        parse_mode='Markdown'
    )

# ---------- Команда /unshare_event ----------
async def unshare_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /unshare_event <id_события>")
        return
    try:
        event_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID события должен быть числом.")
        return

    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text("Событие не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Вы можете изменять только свои события.")
        return
    if not event.is_public:
        await update.message.reply_text("ℹ️ Это событие и так непубличное.")
        return

    event.is_public = False
    await sync_to_async(event.save)()
    await update.message.reply_text(
        f"✅ Событие *{event.name}* теперь приватное (не публикуется).",
        parse_mode='Markdown'
    )

# ---------- Команда /public_events ----------
async def public_events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    public_events = await sync_to_async(list)(
        Event.objects.filter(is_public=True).select_related('organizer').order_by('date', 'time')
    )
    if not public_events:
        await update.message.reply_text("🌍 Нет публичных событий.")
        return

    telegram_id = update.effective_user.id
    current_user = await sync_to_async(_get_user_by_telegram_id)(telegram_id)

    text = "🌍 *Общие события (публичные):*\n\n"
    for ev in public_events:
        organizer_name = ev.organizer.username if ev.organizer else "Неизвестный"
        owner_mark = " *(ваше)*" if ev.organizer_id == current_user.id else ""
        text += f"• *{ev.name}*{owner_mark} – {ev.date} {ev.time}\n"
        text += f"  Организатор: {organizer_name}\n"
        text += f"  Описание: {ev.description or '—'}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ---------- Обработчик кнопок ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        if data.startswith("confirm_"):
            app_id = int(data.split("_")[1])
            success = await sync_to_async(_update_appointment_status)(app_id, 'confirmed')
            if success:
                await query.edit_message_text("✅ Вы подтвердили участие во встрече.")
            else:
                await query.edit_message_text("❌ Ошибка: приглашение не найдено.")
        elif data.startswith("decline_"):
            app_id = int(data.split("_")[1])
            success = await sync_to_async(_update_appointment_status)(app_id, 'cancelled')
            if success:
                await query.edit_message_text("❌ Вы отклонили приглашение.")
            else:
                await query.edit_message_text("❌ Ошибка: приглашение не найдено.")
    except Exception as e:
        logger.exception("Ошибка в callback-обработчике")
        await query.edit_message_text("❌ Произошла ошибка при обработке.")

# ---------- Команда /export_events ----------
async def export_events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = await sync_to_async(_get_user_by_telegram_id)(telegram_id)
    events = await sync_to_async(list)(Event.objects.filter(organizer=user).order_by('date', 'time'))

    if not events:
        await update.message.reply_text("У вас нет созданных событий для экспорта.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Название', 'Дата', 'Время', 'Описание', 'Публичное'])
    for event in events:
        writer.writerow([
            event.id,
            event.name,
            event.date,
            event.time,
            event.description,
            'Да' if event.is_public else 'Нет'
        ])

    output.seek(0)
    await update.message.reply_document(
        document=io.BytesIO(output.getvalue().encode('utf-8')),
        filename=f"events_{user.username}.csv",
        caption="📊 Ваши события"
    )