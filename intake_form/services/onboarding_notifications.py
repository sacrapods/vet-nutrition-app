import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_access_granted_email(submission):
    activation_url = f"{settings.SITE_BASE_URL}{reverse('activate_account')}"
    subject = 'Poshtik NutriVet: Payment received, activate your account'
    message = (
        f"Hello {submission.parent_name},\n\n"
        "Your payment has been confirmed.\n"
        "You can now activate your account and create your password using:\n"
        f"{activation_url}\n\n"
        f"Use this email as username: {submission.parent_email}\n"
        "and your registered phone number for verification.\n\n"
        "Regards,\nPoshtik NutriVet"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[submission.parent_email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed sending access granted email for pre-consult submission %s', submission.id)
