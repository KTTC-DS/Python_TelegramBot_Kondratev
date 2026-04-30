import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BotStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True, verbose_name='Дата')),
                ('user_count', models.PositiveIntegerField(default=0, verbose_name='Новые пользователи')),
                ('event_count', models.PositiveIntegerField(default=0, verbose_name='Создано событий')),
                ('edited_events', models.PositiveIntegerField(default=0, verbose_name='Отредактировано событий')),
                ('cancelled_events', models.PositiveIntegerField(default=0, verbose_name='Отменено событий')),
            ],
            options={
                'verbose_name': 'Статистика бота',
                'verbose_name_plural': 'Статистика бота',
            },
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('date', models.DateField()),
                ('time', models.TimeField()),
                ('description', models.TextField(blank=True)),
                ('is_public', models.BooleanField(default=False, verbose_name='Публичное событие')),
                ('organizer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Событие',
                'verbose_name_plural': 'События',
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_id', models.CharField(max_length=15, unique=True)),
                ('events_created', models.PositiveIntegerField(default=0)),
                ('events_edited', models.PositiveIntegerField(default=0)),
                ('events_cancelled', models.PositiveIntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Профиль пользователя',
                'verbose_name_plural': 'Профили пользователей',
            },
        ),
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('time', models.TimeField()),
                ('details', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('scheduled', 'Запланировано'), ('pending', 'Ожидание подтверждения'), ('cancelled', 'Отменено'), ('completed', 'Завершено')], default='pending', max_length=40)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.event')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Встреча',
                'verbose_name_plural': 'Встречи',
            },
        ),
    ]