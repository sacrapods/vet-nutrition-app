from django.urls import path

from . import views

app_name = 'appointments'

urlpatterns = [
    path('', views.pet_parent_dashboard_view, name='pet_dashboard'),
    path('book/', views.book_appointment_view, name='book'),
    path('book/success/<int:appointment_id>/', views.booking_success_view, name='booking_success'),
    path('api/slots/', views.available_slots_api, name='available_slots_api'),
    path('api/lock-slot/', views.lock_slot_api, name='lock_slot_api'),
    path('<int:appointment_id>/', views.appointment_detail_view, name='detail'),
    path('<int:appointment_id>/reschedule/', views.reschedule_appointment_view, name='reschedule'),

    path('admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/calendar/', views.admin_calendar_view, name='admin_calendar'),
    path('admin/pets/', views.admin_pets_view, name='admin_pets'),
    path('admin/appointments/', views.admin_appointments_view, name='admin_appointments'),
    path('admin/appointments/<int:appointment_id>/', views.admin_appointment_detail_view, name='admin_appointment_detail'),
    path('admin/reschedule-requests/', views.admin_reschedule_requests_view, name='admin_reschedule_requests'),
    path('admin/blocked-dates/', views.admin_blocked_dates_view, name='admin_blocked_dates'),
    path('admin/blocked-slots/', views.admin_blocked_slots_view, name='admin_blocked_slots'),
    path('admin/notes/', views.admin_notes_view, name='admin_notes'),
    path('admin/workload/', views.admin_workload_view, name='admin_workload'),
    path('admin/audit-history/', views.admin_audit_history_view, name='admin_audit_history'),
    path('admin/settings/', views.admin_settings_view, name='admin_settings'),
    path('admin/book/', views.admin_book_appointment_view, name='admin_book_appointment'),
    path('admin/api/pets-by-parent/', views.admin_pets_by_parent_api, name='admin_pets_by_parent_api'),
    path('admin/api/slots/', views.admin_slots_api, name='admin_slots_api'),
]
