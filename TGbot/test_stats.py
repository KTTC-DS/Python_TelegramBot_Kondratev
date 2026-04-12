# test_stats.py
import os
import django
from datetime import datetime

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TGbot.settings")
django.setup()

# Импортируем функцию
from app.statistics import update_statistics  # ← замените 'app' на имя вашего приложения

print("Запуск теста статистики...")

# Увеличиваем счётчики
update_statistics('user_count')
print("✅ user_count увеличен")

update_statistics('event_count')
print("✅ event_count увеличен")

update_statistics('edited_events')
print("✅ edited_events увеличен")

update_statistics('cancelled_events')
print("✅ cancelled_events увеличен")

# Проверим, что данные записаны
from app.models import BotStatistics  # ← тоже замените 'app'

today = datetime.now().date()
stat = BotStatistics.objects.get(date=today)

print(f"\n📊 Текущая статистика за {today}:")
print(f"Новые пользователи: {stat.user_count}")
print(f"Создано событий: {stat.event_count}")
print(f"Отредактировано: {stat.edited_events}")
print(f"Отменено: {stat.cancelled_events}")