from rest_framework import serializers
from .models import Event, Appointment, UserProfile
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'telegram_id', 'events_created', 'events_edited', 'events_cancelled']

class EventSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source='organizer.username', read_only=True)
    class Meta:
        model = Event
        fields = ['id', 'name', 'date', 'time', 'description', 'organizer', 'organizer_name', 'is_public']

class AppointmentSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Appointment
        fields = ['id', 'event', 'event_name', 'user', 'username', 'date', 'time', 'details', 'status']