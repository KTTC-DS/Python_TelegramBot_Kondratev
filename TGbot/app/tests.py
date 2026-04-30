# app/tests.py
import csv
import io
import hmac
import hashlib
from datetime import date, time
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from .models import UserProfile, Event, Appointment, BotStatistics
from .utils import get_user_busy_slots, invite_user_to_event
from .statistics import update_statistics
from .bot_handlers import (
    _get_or_create_user_profile,
    _get_event_by_id,
    _create_appointment,
    _update_appointment_status,
    _get_appointment_by_id,
    _get_user_by_telegram_id,
    _get_user_appointments,
    _get_user_events,
    find_date_index,
)

# ==================== ТЕСТЫ МОДЕЛЕЙ ====================
class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.profile = UserProfile.objects.create(user=self.user, telegram_id="123456789")
        self.event = Event.objects.create(
            name="Тестовое событие",
            date=date(2025, 12, 31),
            time=time(15, 0),
            description="Описание",
            organizer=self.user,
            is_public=False
        )

    def test_user_profile_creation(self):
        self.assertEqual(self.profile.telegram_id, "123456789")
        self.assertEqual(self.profile.user.username, "testuser")

    def test_event_creation(self):
        self.assertEqual(self.event.name, "Тестовое событие")
        self.assertEqual(self.event.organizer, self.user)
        self.assertFalse(self.event.is_public)

    def test_appointment_creation(self):
        appointment = Appointment.objects.create(
            user=self.user,
            event=self.event,
            date=date(2025, 12, 31),
            time=time(15, 0),
            details="Детали",
            status='pending'
        )
        self.assertEqual(appointment.status, 'pending')
        self.assertEqual(appointment.user, self.user)


# ==================== ТЕСТЫ ВСПОМОГАТЕЛЬНЫХ ФУНКЦИЙ ====================
class HelperFunctionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.profile = UserProfile.objects.create(user=self.user, telegram_id="999")

    def test_get_or_create_user_profile_existing(self):
        profile = _get_or_create_user_profile("999", "t", "f", "l")
        self.assertEqual(profile, self.profile)

    def test_get_or_create_user_profile_new(self):
        profile = _get_or_create_user_profile("888", "new", "New", "User")
        self.assertEqual(profile.telegram_id, "888")
        self.assertTrue(User.objects.filter(username="tg_888").exists())

    def test_get_event_by_id(self):
        event = Event.objects.create(name="Test", date=date(2025,1,1), time=time(12,0))
        self.assertEqual(_get_event_by_id(event.id), event)
        self.assertIsNone(_get_event_by_id(999))

    def test_create_appointment(self):
        event = Event.objects.create(name="Meeting", date=date(2025,1,1), time=time(12,0))
        app = _create_appointment(event, self.user.id)
        self.assertEqual(app.user_id, self.user.id)
        self.assertEqual(app.event, event)
        self.assertEqual(app.status, 'pending')

    def test_update_appointment_status(self):
        event = Event.objects.create(name="Meeting", date=date(2025,1,1), time=time(12,0))
        app = Appointment.objects.create(user=self.user, event=event, date=event.date, time=event.time, status='pending')
        self.assertTrue(_update_appointment_status(app.id, 'confirmed'))
        app.refresh_from_db()
        self.assertEqual(app.status, 'confirmed')
        self.assertFalse(_update_appointment_status(999, 'confirmed'))

    def test_get_appointment_by_id(self):
        event = Event.objects.create(name="Meeting", date=date(2025,1,1), time=time(12,0))
        app = Appointment.objects.create(user=self.user, event=event, date=event.date, time=event.time, status='pending')
        self.assertEqual(_get_appointment_by_id(app.id), app)
        self.assertIsNone(_get_appointment_by_id(999))

    def test_find_date_index(self):
        args = ["event", "name", "2025-12-31", "15:00", "desc"]
        self.assertEqual(find_date_index(args), 2)
        args_no_date = ["event", "name", "desc"]
        self.assertIsNone(find_date_index(args_no_date))
        args_multi = ["2025-01-01", "10:00"]
        self.assertEqual(find_date_index(args_multi), 0)


# ==================== ТЕСТЫ БИЗНЕС-ЛОГИКИ ====================
class BusinessLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.profile = UserProfile.objects.create(user=self.user, telegram_id="111")
        self.event = Event.objects.create(
            name="Event", date=date(2025,1,1), time=time(10,0), organizer=self.user
        )

    def test_get_user_busy_slots(self):
        Appointment.objects.create(
            user=self.user, event=self.event, date=date(2025,1,1), time=time(10,0), status='scheduled'
        )
        busy = get_user_busy_slots(self.user)
        self.assertEqual(len(busy), 1)
        self.assertEqual(busy[0]['date'], '2025-01-01')

    def test_invite_user_to_event_free(self):
        target_user = User.objects.create_user(username="target")
        result = invite_user_to_event(target_user, self.event, date(2025,2,2), time(14,0), "details")
        self.assertTrue(result['success'])
        self.assertTrue(Appointment.objects.filter(user=target_user, event=self.event).exists())

    def test_invite_user_to_event_busy(self):
        target_user = User.objects.create_user(username="target")
        Appointment.objects.create(
            user=target_user, event=self.event, date=date(2025,2,2), time=time(14,0), status='scheduled'
        )
        result = invite_user_to_event(target_user, self.event, date(2025,2,2), time(14,0), "details")
        self.assertFalse(result['success'])
        self.assertIn("уже занят", result['message'])


# ==================== ТЕСТЫ СТАТИСТИКИ ====================
class StatisticsTests(TestCase):
    def test_update_statistics_atomic(self):
        today = timezone.now().date()
        # Первое обновление – создаёт запись со значением 1
        update_statistics('user_count')
        stat = BotStatistics.objects.get(date=today)
        self.assertEqual(stat.user_count, 1)

        # Второе обновление – атомарно увеличивает
        update_statistics('user_count')
        stat.refresh_from_db()
        self.assertEqual(stat.user_count, 2)

        # Другое поле
        update_statistics('event_count')
        stat.refresh_from_db()
        self.assertEqual(stat.event_count, 1)

        # Несуществующее поле
        with self.assertRaises(ValueError):
            update_statistics('fake_field')

    def test_statistics_multiple_updates(self):
        today = timezone.now().date()
        update_statistics('user_count')
        update_statistics('user_count')
        update_statistics('event_count')
        stat = BotStatistics.objects.get(date=today)
        self.assertEqual(stat.user_count, 2)
        self.assertEqual(stat.event_count, 1)


# ==================== ТЕСТЫ API ====================
class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="apiuser", password="pass")
        self.profile = UserProfile.objects.create(user=self.user, telegram_id="222")
        self.public_event = Event.objects.create(
            name="Public", date=date(2025,1,1), time=time(12,0), is_public=True, organizer=self.user
        )
        self.private_event = Event.objects.create(
            name="Private", date=date(2025,1,2), time=time(13,0), is_public=False, organizer=self.user
        )

    def test_public_events_list(self):
        url = reverse('api_public_events')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Public")

    def test_user_events_by_telegram_public_only(self):
        url = reverse('api_user_events', kwargs={'telegram_id': '222'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Должно быть только публичное событие (is_public=True)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Public")

    def test_user_events_not_found(self):
        url = reverse('api_user_events', kwargs={'telegram_id': '999'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_event_detail(self):
        url = reverse('api_event_detail', kwargs={'pk': self.public_event.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], "Public")


# ==================== ТЕСТЫ ЭКСПОРТА CSV ====================
class ExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exporter", password="pass")
        self.profile = UserProfile.objects.create(user=self.user, telegram_id="333")
        self.event = Event.objects.create(
            name="Export event", date=date(2025,1,1), time=time(10,0), organizer=self.user
        )

    def test_export_events_view(self):
        from django.conf import settings
        secret = settings.SECRET_KEY.encode()
        user_id = str(self.user.id)
        signature = hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()
        url = f"/export/events/?user_id={user_id}&signature={signature}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        self.assertEqual(rows[0][1], "Название")
        self.assertEqual(rows[1][1], "Export event")

    def test_export_events_invalid_signature(self):
        url = "/export/events/?user_id=1&signature=wrong"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)