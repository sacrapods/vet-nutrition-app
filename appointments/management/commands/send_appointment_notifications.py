from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import Appointment
from appointments.services.notifications import (
    send_appointment_reminder_email,
    send_whatsapp_notification,
)


class Command(BaseCommand):
    help = 'Send appointment reminder notifications (24h and 1h placeholders).'

    def handle(self, *args, **options):
        now = timezone.now()

        self.send_24h_reminders(now)
        self.send_1h_reminders(now)

    def send_24h_reminders(self, now):
        window_start = now + timedelta(hours=24) - timedelta(minutes=10)
        window_end = now + timedelta(hours=24) + timedelta(minutes=10)

        qs = Appointment.objects.filter(
            start_at__gte=window_start,
            start_at__lte=window_end,
            status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
            reminder_24h_sent_at__isnull=True,
        )

        for appointment in qs:
            send_appointment_reminder_email(appointment, reminder_type='24h')
            send_whatsapp_notification(appointment, event='reminder_24h')
            appointment.reminder_24h_sent_at = now
            appointment.save(update_fields=['reminder_24h_sent_at'])
            self.stdout.write(self.style.SUCCESS(f'24h reminder marked for appointment {appointment.id}'))

    def send_1h_reminders(self, now):
        window_start = now + timedelta(hours=1) - timedelta(minutes=10)
        window_end = now + timedelta(hours=1) + timedelta(minutes=10)

        qs = Appointment.objects.filter(
            start_at__gte=window_start,
            start_at__lte=window_end,
            status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
            reminder_1h_sent_at__isnull=True,
        )

        for appointment in qs:
            send_appointment_reminder_email(appointment, reminder_type='1h')
            send_whatsapp_notification(appointment, event='reminder_1h')
            appointment.reminder_1h_sent_at = now
            appointment.save(update_fields=['reminder_1h_sent_at'])
            self.stdout.write(self.style.SUCCESS(f'1h reminder marked for appointment {appointment.id}'))
