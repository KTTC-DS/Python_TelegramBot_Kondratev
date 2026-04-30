from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telegram_id = models.CharField(max_length=15, unique=True)

    # поля статистики
    events_created = models.PositiveIntegerField(default=0)
    events_edited = models.PositiveIntegerField(default=0)
    events_cancelled = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f"{self.user.username} - {self.telegram_id}"


# модель событий
class Event(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    description = models.TextField(blank=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_public = models.BooleanField(default=False, verbose_name="Публичное событие")

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

    def __str__(self):
        return self.name

# модель для хранеиния статистики бота
class BotStatistics(models.Model):
    date = models.DateField("Дата", unique=True)
    user_count = models.PositiveIntegerField("Новые пользователи", default=0)
    event_count = models.PositiveIntegerField("Создано событий", default=0)
    edited_events = models.PositiveIntegerField("Отредактировано событий", default=0)
    cancelled_events = models.PositiveIntegerField("Отменено событий", default=0)

    class Meta:
        verbose_name = "Статистика бота"
        verbose_name_plural = "Статистика бота"

    def __str__(self):
        return f"Статистика за {self.date}"


# модель базы данных для встреч
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('pending', 'Ожидание подтверждения'),
        ('cancelled', 'Отменено'),
        ('completed', 'Завершено'),
        ('confirmed', 'Подтверждено'),   # добавлено новое состояние
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    details = models.TextField(blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='pending')

    class Meta:
        verbose_name = 'Встреча'
        verbose_name_plural = 'Встречи'

    def __str__(self):
        return f"{self.user.username} - {self.event.name} - {self.date} - {self.time}"