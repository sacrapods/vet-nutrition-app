from datetime import timedelta

from django.db import IntegrityError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from appointments.models import Appointment, AppointmentConfig
from appointments.services.notifications import send_whatsapp_notification


@receiver(pre_save, sender=Appointment)
def cache_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        old = Appointment.objects.get(pk=instance.pk)
        instance._previous_status = old.status
    except Appointment.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Appointment)
def create_follow_up_on_completion(sender, instance, created, **kwargs):
    if created:
        return

    previous = getattr(instance, '_previous_status', None)
    if instance.status != Appointment.STATUS_COMPLETED or previous == Appointment.STATUS_COMPLETED:
        return

    if instance.is_follow_up:
        return

    config = AppointmentConfig.get_solo()
    if not config.follow_up_enabled:
        return

    if Appointment.objects.filter(follow_up_of=instance).exists():
        return

    follow_up_start = instance.start_at + timedelta(days=config.follow_up_days)
    follow_up_end = instance.end_at + timedelta(days=config.follow_up_days)

    try:
        follow_up = Appointment.objects.create(
            user=instance.user,
            pet=instance.pet,
            start_at=follow_up_start,
            end_at=follow_up_end,
            status=Appointment.STATUS_PENDING,
            payment_status=Appointment.PAYMENT_PENDING,
            is_follow_up=True,
            follow_up_of=instance,
        )
    except IntegrityError:
        return

    send_whatsapp_notification(follow_up, event='follow_up_created')
