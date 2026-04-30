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
from datetime import datetime
from .statistics import update_statistics


logger = logging.getLogger(__name__)

def find_date_index(args):
    """Ищет индекс аргумента, соответствующего формату ГГГГ-ММ-ДД."""
    for i, arg in enumerate(args):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', arg):
            return i
    return None


# ---------- Синхронные функции для безопасного вызова через sync_to_async ----------
def _get_user_by_telegram_id(telegram_id):
    try:
        return User.objects.get(userprofile__telegram_id=str(telegram_id))
    except User.DoesNotExist:
        # Не создаём пользователя, просто пробрасываем исключение дальше
        raise


def _get_user_appointments(user):
    """Возвращает список встреч пользователя с предзагруженными событиями."""
    return list(Appointment.objects.filter(user=user).select_related('event').order_by('date', 'time'))


def _get_user_events(user):
    """Возвращает список событий, где пользователь является организатором."""
    return list(Event.objects.filter(organizer=user).order_by('date', 'time'))


def _get_or_create_user_profile(telegram_id, username, first_name, last_name):
    """Создаёт или возвращает существующий профиль пользователя по Telegram ID."""
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
    """Возвращает событие по ID или None."""
    try:
        return Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return None


def _create_appointment(event, user_id):
    """Создаёт приглашение (Appointment) для пользователя на событие."""
    return Appointment.objects.create(
        event=event,
        user_id=user_id,
        date=event.date,
        time=event.time,
        details=event.description,
        status='pending'
    )


def _update_appointment_status(appointment_id, new_status):
    """Обновляет статус приглашения (Appointment) в базе данных."""
    try:
        app = Appointment.objects.get(id=appointment_id)
        print(f"Updating appointment {appointment_id} from {app.status} to {new_status}", flush=True)
        app.status = new_status
        app.save()
        print("Saved successfully", flush=True)
        return True
    except Appointment.DoesNotExist:
        print(f"Appointment {appointment_id} not found", flush=True)
        return False
    except Exception as e:
        print(f"Error updating appointment: {e}", flush=True)
        return False


def _get_appointment_by_id(appointment_id):
    """Возвращает приглашение по ID или None."""
    try:
        return Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        return None


# ---------- Асинхронные утилиты ----------
async def _get_user_profile_from_update(update: Update) -> UserProfile:
    """Извлекает профиль пользователя из Telegram-обновления."""
    telegram_id = update.effective_user.id
    return await sync_to_async(UserProfile.objects.get)(telegram_id=str(telegram_id))


async def _get_event_and_check_owner(event_id: int, user_profile: UserProfile):
    """Возвращает событие и флаг, является ли пользователь его организатором."""
    event = await sync_to_async(_get_event_by_id)(event_id)
    if not event:
        return None, False
    return event, (event.organizer_id == user_profile.user_id)


# ---------- Команда /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрирует пользователя (создаёт профиль) и показывает список доступных команд."""
    user = update.effective_user
    await sync_to_async(_get_or_create_user_profile)(
        user.id, user.username, user.first_name, user.last_name
    )
    await sync_to_async(update_statistics)('user_count')
    await update.message.reply_text(
        "✅ Вы зарегистрированы!\n\n"
        "📌 /create_event – создать событие\n"
        "📅 /calendar – мои встречи\n"
        "📋 /my_events – мои созданные события\n"
        "✏️ /edit_event <id> Новое_название ГГГГ-ММ-ДД ЧЧ:ММ [Описание] – редактировать\n"
        "🗑 /delete_event <id> – удалить событие\n"
        "📨 /invite <event_id> <telegram_id> – пригласить участника (только организатор)\n"
        "🌍 /share_event <id> - Делает событие публичным (доступным для просмотра всем пользователям)\n"
        "🔒 /unshare_event <id> - Делает событие приватным (недоступным для просмотра всем пользователям)\n"
        "📥 /export_events – выгрузить свои события в CSV"
    )


# ---------- Команда /calendar ----------
async def calendar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список встреч, где пользователь является участником."""
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
    """Показывает список событий, созданных пользователем (организатором)."""
    telegram_id = update.effective_user.id
    try:
        user = await sync_to_async(_get_user_by_telegram_id)(telegram_id)
    except User.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы. Напишите /start.")
        return
    events = await sync_to_async(_get_user_events)(user)
    if not events:
        await update.message.reply_text("Вы ещё не создали ни одного события.")
        return
    text = "📌 Созданные вами события:\n\n"
    for ev in events:
        text += f"ID {ev.id}: {ev.name} – {ev.date} {ev.time}\n"
    await update.message.reply_text(text)

# ---------- Команда /create_event ----------
async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создает новое событие."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование: /create_event Название события ГГГГ-ММ-ДД ЧЧ:ММ [Описание]\n"
        )
        return

    # Ищем индекс даты (первый аргумент, похожий на ГГГГ-ММ-ДД)
    date_idx = find_date_index(args)
    if date_idx is None or date_idx + 1 >= len(args):
        await update.message.reply_text("Не указана дата и время. Укажите дату в формате ГГГГ-ММ-ДД и время ЧЧ:ММ.")
        return

    # Название – всё, что до даты
    name = " ".join(args[:date_idx])
    date_str = args[date_idx]
    time_str = args[date_idx + 1] if date_idx + 1 < len(args) else None
    description = " ".join(args[date_idx + 2:]) if date_idx + 2 < len(args) else ""

    if not time_str:
        await update.message.reply_text("Не указано время. Укажите время в формате ЧЧ:ММ.")
        return

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        await update.message.reply_text("Неверный формат даты или времени. Используйте ГГГГ-ММ-ДД и ЧЧ:ММ")
        return

    try:
        profile = await _get_user_profile_from_update(update)
        event = await sync_to_async(Event.objects.create)(
            name=name,
            date=date_obj,
            time=time_obj,
            description=description,
            organizer_id=profile.user_id
        )
        profile.events_created += 1
        await sync_to_async(profile.save)()
        await sync_to_async(update_statistics)('event_count')
        await update.message.reply_text(f"✅ Событие '{name}' создано с ID {event.id}")
    except Exception as e:
        logger.exception("Ошибка при создании события")
        await update.message.reply_text("❌ Произошла ошибка при создании события.")


# ---------- Команда /edit_event ----------
async def edit_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирует созданное ранее событие."""
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Использование: /edit_event <id> <новое_название> <ГГГГ-ММ-ДД> <ЧЧ:ММ> [новое_описание]\n"
            "Название может содержать пробелы."
        )
        return

    try:
        event_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    # Ищем индекс даты среди аргументов после id
    date_idx = find_date_index(args[1:])
    if date_idx is None:
        await update.message.reply_text("Не указана новая дата в формате ГГГГ-ММ-ДД.")
        return
    date_idx += 1  # смещение из-за id

    # Название – всё, что между id и датой
    new_name = " ".join(args[1:date_idx])
    new_date_str = args[date_idx]
    if date_idx + 1 >= len(args):
        await update.message.reply_text("Не указано новое время.")
        return
    new_time_str = args[date_idx + 1]
    new_description = " ".join(args[date_idx + 2:]) if date_idx + 2 < len(args) else ""

    try:
        new_date_obj = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        new_time_obj = datetime.strptime(new_time_str, '%H:%M').time()
    except ValueError:
        await update.message.reply_text("Неверный формат даты или времени. Используйте ГГГГ-ММ-ДД и ЧЧ:ММ")
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
    event.date = new_date_obj
    event.time = new_time_obj
    if new_description:
        event.description = new_description

    await sync_to_async(event.save)()
    profile.events_edited += 1
    await sync_to_async(profile.save)()
    await sync_to_async(update_statistics)('edited_events')
    await update.message.reply_text(f"✅ Событие {event_id} обновлено.")


# ---------- Команда /delete_event ----------
async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет событие (только свои)."""
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
    await sync_to_async(update_statistics)('cancelled_events')
    await sync_to_async(event.delete)()
    await update.message.reply_text(f"✅ Событие {event_id} удалено.")


# ---------- Команда /invite ----------
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приглашает другого пользователя на событие. Только организатор."""
    args = context.args
    print(f"📨 INVITE called with args: {args}", flush=True)
    if len(args) != 2:
        await update.message.reply_text("Использование: /invite <event_id> <telegram_id_участника>")
        return
    try:
        event_id = int(args[0])
        target_tg_id = int(args[1])
    except ValueError:
        await update.message.reply_text("ID события и Telegram ID должны быть числами")
        return

    profile = await _get_user_profile_from_update(update)
    event, is_owner = await _get_event_and_check_owner(event_id, profile)
    if not event:
        await update.message.reply_text(f"Событие с ID {event_id} не найдено.")
        return
    if not is_owner:
        await update.message.reply_text("❌ Только организатор может приглашать на событие.")
        return

    target_profile = await sync_to_async(_get_or_create_user_profile)(target_tg_id, None, None, None)
    appointment = await sync_to_async(_create_appointment)(event, target_profile.user_id)

    keyboard = [[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{appointment.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{appointment.id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📅 Приглашение на встречу\n\n"
        f"Событие: {event.name}\n"
        f"Дата: {event.date}\n"
        f"Время: {event.time}\n"
        f"Описание: {event.description or '—'}\n\n"
        "Нажмите кнопку, чтобы подтвердить или отклонить."
    )

    try:
        await context.bot.send_message(
            chat_id=target_tg_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=None   # отключаем Markdown, чтобы не было ошибок
        )
        await update.message.reply_text(f"✅ Приглашение отправлено пользователю {target_tg_id}")
    except Exception as e:
        logger.exception("Ошибка при отправке приглашения")
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")


# ---------- Команда /share_event ----------
async def share_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Делает событие публичным (доступным для просмотра всем пользователям)."""
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
    """Делает публичное событие приватным (скрывает из общего списка)."""
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
    """Показывает список всех публичных событий (общий календарь)."""
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
    telegram_id = update.effective_user.id
    print(f"🔘 Callback received: {data} from {telegram_id}", flush=True)

    try:
        app_id = int(data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Некорректные данные.")
        return

    # Получаем приглашение
    appointment = await sync_to_async(_get_appointment_by_id)(app_id)
    if not appointment:
        await query.edit_message_text("❌ Приглашение не найдено.")
        return

    # Получаем профиль нажавшего
    user_profile = await sync_to_async(_get_or_create_user_profile)(telegram_id, None, None, None)

    # Сравниваем user_id (а не объекты)
    if appointment.user_id != user_profile.user_id:
        await query.edit_message_text("❌ Вы не можете подтвердить чужое приглашение.")
        return

    if data.startswith("confirm_"):
        success = await sync_to_async(_update_appointment_status)(app_id, 'confirmed')
        if success:
            await query.edit_message_text("✅ Вы подтвердили участие во встрече.")
        else:
            await query.edit_message_text("❌ Ошибка: не удалось подтвердить.")
    elif data.startswith("decline_"):
        success = await sync_to_async(_update_appointment_status)(app_id, 'cancelled')
        if success:
            await query.edit_message_text("❌ Вы отклонили приглашение.")
        else:
            await query.edit_message_text("❌ Ошибка: не удалось отклонить.")


# ---------- Команда /export_events ----------
async def export_events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует события пользователя в CSV-файл и отправляет его в чат."""
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