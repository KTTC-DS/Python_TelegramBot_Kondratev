from .models import BotStatistics
from django.utils import timezone

def update_statistics(field_name):
    """
    Увеличивает указанное поле в BotStatistics для текущей даты.
    При необходимости создаёт запись.
    Поля: 'user_count', 'event_count', 'edited_events', 'cancelled_events'
    """
    today = timezone.now().date()

    stat, created = BotStatistics.objects.get_or_create(
        date=today,
        defaults={
            'user_count': 0,
            'event_count': 0,
            'edited_events': 0,
            'cancelled_events': 0,
        }
    )

    # Увеличиваем нужное поле
    if hasattr(stat, field_name):
        value = getattr(stat, field_name)
        setattr(stat, field_name, value + 1)
        stat.save(update_fields=[field_name])  # экономим ресурсы — обновляем только одно поле
    else:
        raise ValueError(f"Поле '{field_name}' не существует в BotStatistics")