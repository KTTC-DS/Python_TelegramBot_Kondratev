import csv
import hmac
import hashlib
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Event, Appointment
from .serializers import EventSerializer, AppointmentSerializer



def export_events(request):
    # Получаем параметры
    user_id = request.GET.get('user_id')
    signature = request.GET.get('signature')

    if not user_id or not signature:
        return HttpResponseForbidden("Missing parameters")

    # Проверка подписи (секретный ключ из настроек, например SECRET_KEY)
    from django.conf import settings
    secret = settings.SECRET_KEY.encode()
    expected = hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return HttpResponseForbidden("Invalid signature")

    # Получаем пользователя
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseForbidden("User not found")

    # Извлекаем события пользователя (где он организатор)
    events = Event.objects.filter(organizer=user).order_by('date', 'time')

    # Создаём CSV-ответ
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="events_{user.username}.csv"'

    writer = csv.writer(response)
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

    return response


# 1. Список всех публичных событий (доступно без авторизации)
@api_view(['GET'])
@permission_classes([AllowAny])
def public_events_list(request):
    events = Event.objects.filter(is_public=True).order_by('date', 'time')
    serializer = EventSerializer(events, many=True)
    return Response(serializer.data)

# 2. Получить события конкретного пользователя по его telegram_id (требуется аутентификация?)
# Для простоты сделаем доступ без токена, но можно добавить ключ.
@api_view(['GET'])
def user_events_by_telegram(request, telegram_id):
    try:
        from .models import UserProfile
        profile = UserProfile.objects.get(telegram_id=str(telegram_id))
        events = Event.objects.filter(organizer=profile.user, is_public=True).order_by('date', 'time')
        serializer = EventSerializer(events, many=True)
        return Response(serializer.data)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# 3. Список всех встреч (Appointment) – пример для администратора
@api_view(['GET'])
def appointments_list(request):
    appointments = Appointment.objects.all().order_by('date', 'time')
    serializer = AppointmentSerializer(appointments, many=True)
    return Response(serializer.data)

# 4. Детальная информация о событии по ID
@api_view(['GET'])
def event_detail(request, pk):
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = EventSerializer(event)
    return Response(serializer.data)
