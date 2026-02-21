from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import (
    AdminAuditLog,
    AdminSLAConfig,
    Appointment,
    AppointmentConfig,
    AppointmentRescheduleRequest,
    BlockedDate,
    BlockedTimeSlot,
    ConsultationNote,
    NoteTemplate,
    ProviderCapacity,
    SlotLock,
)

IST = ZoneInfo('Asia/Kolkata')


class ConsultationNoteInline(admin.StackedInline):
    model = ConsultationNote
    extra = 0


@admin.register(AppointmentConfig)
class AppointmentConfigAdmin(admin.ModelAdmin):
    list_display = (
        'start_hour_ist',
        'end_hour_ist',
        'appointment_duration_minutes',
        'buffer_minutes',
        'daily_appointment_limit',
        'follow_up_enabled',
        'follow_up_days',
        'slot_lock_minutes',
    )
    readonly_fields = ('appointment_duration_minutes',)


@admin.register(BlockedDate)
class BlockedDateAdmin(admin.ModelAdmin):
    list_display = ('date', 'reason', 'created_at')
    search_fields = ('reason',)
    ordering = ('date',)


@admin.register(BlockedTimeSlot)
class BlockedTimeSlotAdmin(admin.ModelAdmin):
    list_display = ('start_at', 'reason', 'created_at')
    search_fields = ('reason',)


@admin.register(SlotLock)
class SlotLockAdmin(admin.ModelAdmin):
    list_display = ('slot_start_at', 'user', 'expires_at', 'created_at')
    search_fields = ('user__username',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'pet', 'user', 'start_at', 'appointment_kind', 'status', 'payment_status', 'reschedule_count'
    )
    list_filter = ('status', 'payment_status', 'is_follow_up')
    search_fields = ('pet__name', 'user__username', 'payment_reference')
    list_select_related = ('user', 'pet')
    list_editable = ('status', 'payment_status')
    inlines = [ConsultationNoteInline]
    change_list_template = 'admin/appointments/appointment/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('calendar/', self.admin_site.admin_view(self.calendar_view), name='appointments_appointment_calendar'),
            path('calendar/day/<str:date_str>/', self.admin_site.admin_view(self.calendar_day_view), name='appointments_appointment_calendar_day'),
            path('calendar/block-day/', self.admin_site.admin_view(self.block_day_view), name='appointments_appointment_block_day'),
            path('calendar/block-range/', self.admin_site.admin_view(self.block_range_view), name='appointments_appointment_block_range'),
        ]
        return custom + urls

    @admin.display(description='Type')
    def appointment_kind(self, obj):
        return obj.appointment_type_label

    def calendar_view(self, request):
        view_type = request.GET.get('view', 'month')
        try:
            anchor = datetime.strptime(request.GET.get('date', ''), '%Y-%m-%d').date()
        except ValueError:
            anchor = timezone.localdate()

        if view_type == 'week':
            start_day = anchor - timedelta(days=anchor.weekday())
            end_day = start_day + timedelta(days=7)
        else:
            start_day = anchor.replace(day=1)
            if start_day.month == 12:
                end_day = start_day.replace(year=start_day.year + 1, month=1, day=1)
            else:
                end_day = start_day.replace(month=start_day.month + 1, day=1)

        start_dt = datetime.combine(start_day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
        end_dt = datetime.combine(end_day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)

        appointments = (
            Appointment.objects.filter(start_at__gte=start_dt, start_at__lt=end_dt)
            .select_related('pet', 'user')
            .order_by('start_at')
        )

        grouped = {}
        for appointment in appointments:
            local_day = timezone.localtime(appointment.start_at, IST).date()
            grouped.setdefault(local_day, []).append(appointment)

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Appointment Calendar',
            'appointments_by_day': grouped,
            'anchor_date': anchor,
            'view_type': view_type,
            'blocked_dates': set(BlockedDate.objects.values_list('date', flat=True)),
            'summary': {
                'total': appointments.count(),
                'pending': appointments.filter(status=Appointment.STATUS_PENDING).count(),
                'no_show': appointments.filter(status=Appointment.STATUS_NO_SHOW).count(),
            },
        }
        return TemplateResponse(request, 'admin/appointments/appointment/calendar.html', context)

    def calendar_day_view(self, request, date_str):
        day = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_dt = datetime.combine(day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
        end_dt = start_dt + timedelta(days=1)

        appointments = (
            Appointment.objects.filter(start_at__gte=start_dt, start_at__lt=end_dt)
            .select_related('pet', 'user')
            .order_by('start_at')
        )

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': f'Appointments on {day}',
            'day': day,
            'appointments': appointments,
            'blocked': BlockedDate.objects.filter(date=day).exists(),
        }
        return TemplateResponse(request, 'admin/appointments/appointment/calendar_day.html', context)

    def block_day_view(self, request):
        if request.method == 'POST':
            day = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
            BlockedDate.objects.get_or_create(date=day)
            self.message_user(request, f'Day {day} blocked successfully.')
        return HttpResponseRedirect(reverse('admin:appointments_appointment_calendar'))

    def block_range_view(self, request):
        if request.method == 'POST':
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            reason = (request.POST.get('reason') or '').strip()
            if end_date < start_date:
                start_date, end_date = end_date, start_date

            cursor = start_date
            created_count = 0
            while cursor <= end_date:
                _, created = BlockedDate.objects.get_or_create(
                    date=cursor,
                    defaults={'reason': reason},
                )
                if created:
                    created_count += 1
                cursor += timedelta(days=1)
            self.message_user(
                request,
                f'Blocked {created_count} day(s) between {start_date} and {end_date}.',
            )
        return HttpResponseRedirect(reverse('admin:appointments_appointment_calendar'))


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'updated_at')
    search_fields = ('appointment__pet__name', 'appointment__user__username')


@admin.register(AppointmentRescheduleRequest)
class AppointmentRescheduleRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'appointment',
        'requested_by',
        'requested_start_at',
        'status',
        'reviewed_by',
        'reviewed_at',
    )
    list_filter = ('status', 'created_at', 'reviewed_at')
    search_fields = ('appointment__pet__name', 'requested_by__username', 'requested_by__email')


@admin.register(ProviderCapacity)
class ProviderCapacityAdmin(admin.ModelAdmin):
    list_display = ('provider', 'daily_limit', 'active', 'updated_at')
    list_filter = ('active',)
    search_fields = ('provider__email', 'provider__username')


@admin.register(AdminSLAConfig)
class AdminSLAConfigAdmin(admin.ModelAdmin):
    list_display = ('reschedule_response_hours', 'note_completion_hours', 'overdue_warning_hours', 'updated_at')


@admin.register(NoteTemplate)
class NoteTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'updated_at', 'updated_by')
    list_filter = ('active',)
    search_fields = ('title', 'body')


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'entity_type', 'entity_id', 'action', 'changed_by')
    list_filter = ('entity_type', 'action', 'created_at')
    search_fields = ('entity_id', 'action', 'summary', 'changed_by__email', 'changed_by__username')
    readonly_fields = ('entity_type', 'entity_id', 'action', 'changed_by', 'summary', 'metadata', 'created_at')
