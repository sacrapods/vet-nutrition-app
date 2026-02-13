from django.urls import path
from . import views

urlpatterns = [
    path('', views.intake_form_view, name='intake_form'),
    path('success/', views.success_view, name='success'),
]