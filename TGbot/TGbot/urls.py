"""
URL configuration for TGbot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('export/events/', views.export_events, name='export_events'),
    # API endpoints
    path('api/public-events/', views.public_events_list, name='api_public_events'),
    path('api/user-events/<str:telegram_id>/', views.user_events_by_telegram, name='api_user_events'),
    path('api/appointments/', views.appointments_list, name='api_appointments'),
    path('api/events/<int:pk>/', views.event_detail, name='api_event_detail'),
]
