from django.db.models import F
from django.utils import timezone
from .models import BotStatistics

# Допустимые поля (безопасный список)
ALLOWED_STATISTICS_FIELDS = {'user_count', 'event_count', 'edited_events', 'cancelled_events'}

def update_statistics(field_name):
    """
    Атомарно увеличивает указанное поле в статистике за текущий день.
    Допустимые имена полей: user_count, event_count, edited_events, cancelled_events.
    """
    if field_name not in ALLOWED_STATISTICS_FIELDS:
        raise ValueError(f"Поле '{field_name}' не существует в BotStatistics")

    today = timezone.now().date()
    stat, created = BotStatistics.objects.get_or_create(date=today)
    if created:
        setattr(stat, field_name, 1)
        stat.save()
    else:
        BotStatistics.objects.filter(date=today).update(**{field_name: F(field_name) + 1})