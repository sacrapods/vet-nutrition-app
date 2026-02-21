import logging

logger = logging.getLogger(__name__)


def send_appointment_confirmation_email(appointment):
    logger.info('Placeholder: send confirmation email for appointment %s', appointment.id)


def send_appointment_reminder_email(appointment, reminder_type):
    logger.info('Placeholder: send %s reminder email for appointment %s', reminder_type, appointment.id)


def send_whatsapp_notification(appointment, event):
    logger.info('Placeholder: send whatsapp notification %s for appointment %s', event, appointment.id)
