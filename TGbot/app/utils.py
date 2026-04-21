from django.contrib.auth.models import User
from .models import Appointment, Event
from datetime import date, time
from .statistics import update_statistics

def get_user_busy_slots(user):
    """
    Возвращает список занятых временных слотов для пользователя.
    Только активные (не отменённые) встречи.
    """
    appointments = Appointment.objects.filter(
        user=user,
        status='scheduled'  # можно добавить 'completed', если нужно
    ).order_by('date', 'time')

    return [
        {
            'date': str(appointment.date),
            'time': appointment.time.strftime('%H:%M'),
        }
        for appointment in appointments
    ]


def invite_user_to_event(user: User, event: Event, date, time, details: str = ""):
    """
    Приглашает пользователя на событие.
    Проверяет, свободен ли он в это время.
    Если свободен — создаёт встречу со статусом 'pending'.
    Обновляет статистику (event_count += 1).

    Возвращает словарь с результатом:
    {
        'success': True/False,
        'message': '...',
    }
    """
    # 1. Проверяем, не занято ли у пользователя это время
    if Appointment.objects.filter(
            user=user,
            date=date,
            time=time,
            status__in=['scheduled', 'pending']  # считаем и запланированные, и ожидание
    ).exists():
        return {
            'success': False,
            'message': f"Пользователь {user.username} уже занят {date} в {time}."
        }
    # 2. Создаём приглашение
    try:
        Appointment.objects.create(
            user=user,
            event=event,
            date=date,
            time=time,
            details=details,
            status='pending'
        )

        # 3. Обновляем статистику: +1 к созданным событиям
        update_statistics('event_count')

        return {
            'success': True,
            'message': f"Пользователь {user.username} приглашён на событие '{event.name}'. Ожидание подтверждения."
        }

    except Exception as e:
        return {
            'success': False,
            'message': f"Ошибка при создании приглашения: {str(e)}"
        }