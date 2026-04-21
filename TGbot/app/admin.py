from django.contrib import admin
from .models import UserProfile, Event, Appointment

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'telegram_id', 'events_created', 'events_edited', 'events_cancelled')
    list_filter = ('events_created', 'events_edited', 'events_cancelled')
    search_fields = ('user__username', 'telegram_id')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'time', 'is_public')
    list_filter = ('date', 'is_public')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status', 'date', 'time')
    list_filter = ('status', 'event')
    search_fields = ('user__username', 'event__name')