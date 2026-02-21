from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from intake_form.models import PreConsultSubmission
from intake_form.services.onboarding_notifications import send_access_granted_email


@receiver(pre_save, sender=PreConsultSubmission)
def _cache_previous_payment_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_payment_status = None
        return

    try:
        old = PreConsultSubmission.objects.get(pk=instance.pk)
        instance._previous_payment_status = old.payment_status
    except PreConsultSubmission.DoesNotExist:
        instance._previous_payment_status = None


@receiver(post_save, sender=PreConsultSubmission)
def _send_access_email_when_granted(sender, instance, created, **kwargs):
    prev = getattr(instance, '_previous_payment_status', None)
    eligible_statuses = {'paid', 'access_granted'}
    transitioned = (
        instance.payment_status in eligible_statuses
        and (created or prev not in eligible_statuses)
    )

    if not transitioned:
        return

    if instance.linked_user_id:
        return

    send_access_granted_email(instance)
    instance.invite_sent_at = timezone.now()
    instance.save(update_fields=['invite_sent_at'])
