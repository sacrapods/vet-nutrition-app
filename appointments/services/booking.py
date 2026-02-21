from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.models import (
    Appointment,
    AppointmentConfig,
    BlockedDate,
    BlockedTimeSlot,
    SlotLock,
)
from appointments.services.notifications import (
    send_appointment_confirmation_email,
    send_whatsapp_notification,
)

IST = ZoneInfo('Asia/Kolkata')
APPOINTMENT_DURATION_MINUTES = 60  # fallback constant; prefer config.appointment_duration_minutes at runtime
BLOCKING_STATUSES = [
    Appointment.STATUS_PENDING,
    Appointment.STATUS_CONFIRMED,
    Appointment.STATUS_COMPLETED,
    Appointment.STATUS_NO_SHOW,
]


def get_config():
    return AppointmentConfig.get_solo()


def cleanup_expired_locks():
    SlotLock.objects.filter(expires_at__lt=timezone.now()).delete()


def to_utc_from_ist(local_date, local_time):
    local_dt = datetime.combine(local_date, local_time).replace(tzinfo=IST)
    return local_dt.astimezone(dt_timezone.utc)


def to_ist(dt):
    return timezone.localtime(dt, IST)


def _is_weekend(local_date):
    return local_date.weekday() >= 5


def _slot_interval(slot_start_utc, duration_minutes=None):
    config = get_config()
    dur = duration_minutes if duration_minutes is not None else config.appointment_duration_minutes
    duration = timedelta(minutes=dur)
    start_with_buffer = slot_start_utc - timedelta(minutes=config.buffer_minutes)
    end_utc = slot_start_utc + duration
    end_with_buffer = end_utc + timedelta(minutes=config.buffer_minutes)
    return end_utc, start_with_buffer, end_with_buffer


def _daily_count(local_date, exclude_appointment_id=None):
    start_local = datetime.combine(local_date, datetime.min.time()).replace(tzinfo=IST)
    end_local = start_local + timedelta(days=1)
    qs = Appointment.objects.filter(
        start_at__gte=start_local.astimezone(dt_timezone.utc),
        start_at__lt=end_local.astimezone(dt_timezone.utc),
    ).exclude(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_RESCHEDULED])
    if exclude_appointment_id:
        qs = qs.exclude(id=exclude_appointment_id)
    return qs.count()


def validate_slot_rules(slot_start_utc, exclude_appointment_id=None,
                        duration_minutes=None, allow_subhour=False):
    """
    Validate that a slot is bookable.

    Parameters
    ----------
    slot_start_utc       : UTC datetime of the slot start
    exclude_appointment_id : appointment to exclude from overlap checks (reschedule)
    duration_minutes     : override duration (staff booking); None → use config value
    allow_subhour        : if True, skip the full-hour-only restriction (staff booking)
    """
    config = get_config()
    slot_local = to_ist(slot_start_utc)
    dur = duration_minutes if duration_minutes is not None else config.appointment_duration_minutes

    if _is_weekend(slot_local.date()):
        raise ValidationError('Appointments are available Monday to Friday only.')

    # Pet-parent bookings must be on the hour; staff bookings with custom duration may be sub-hour
    if not allow_subhour and (slot_local.minute != 0 or slot_local.second != 0):
        raise ValidationError('Only full-hour slots are allowed.')

    if slot_local.hour < config.start_hour_ist:
        raise ValidationError('This slot is outside booking hours.')

    # Check the appointment END fits within end_hour
    slot_end_local = slot_local + timedelta(minutes=dur)
    if slot_end_local.hour > config.end_hour_ist or (
        slot_end_local.hour == config.end_hour_ist and slot_end_local.minute > 0
    ):
        raise ValidationError('This slot is outside booking hours.')

    if BlockedDate.objects.filter(date=slot_local.date()).exists():
        raise ValidationError('This date is blocked.')

    if BlockedTimeSlot.objects.filter(start_at=slot_start_utc).exists():
        raise ValidationError('This time slot is blocked.')

    if _daily_count(slot_local.date(), exclude_appointment_id=exclude_appointment_id) >= config.daily_appointment_limit:
        raise ValidationError('Daily appointment limit reached for this date.')

    end_utc, start_with_buffer, end_with_buffer = _slot_interval(slot_start_utc, duration_minutes=dur)
    overlapping = Appointment.objects.filter(
        status__in=BLOCKING_STATUSES,
        start_at__lt=end_with_buffer,
        end_at__gt=start_with_buffer,
    )
    if exclude_appointment_id:
        overlapping = overlapping.exclude(id=exclude_appointment_id)

    if overlapping.exists():
        raise ValidationError('This slot is not available due to buffer/overlap rules.')


@transaction.atomic
def acquire_slot_lock(user, local_date, local_time):
    cleanup_expired_locks()
    slot_start_utc = to_utc_from_ist(local_date, local_time)
    validate_slot_rules(slot_start_utc)

    lock = SlotLock.objects.select_for_update().filter(slot_start_at=slot_start_utc).first()
    if lock and lock.expires_at > timezone.now() and lock.user_id != user.id:
        raise ValidationError('This slot is temporarily locked by another user. Please try again.')

    if lock and lock.user_id == user.id:
        lock.expires_at = SlotLock.build_expiry()
        lock.save(update_fields=['expires_at'])
        return lock

    if lock and lock.expires_at <= timezone.now():
        lock.delete()

    return SlotLock.objects.create(
        user=user,
        slot_start_at=slot_start_utc,
        expires_at=SlotLock.build_expiry(),
    )


@transaction.atomic
def create_appointment_from_lock(user, pet, lock_token, payment_reference=''):
    cleanup_expired_locks()
    try:
        lock = SlotLock.objects.select_for_update().get(lock_token=lock_token, user=user)
    except SlotLock.DoesNotExist as exc:
        raise ValidationError('Invalid or expired slot lock token.') from exc

    if lock.expires_at < timezone.now():
        lock.delete()
        raise ValidationError('Your lock expired. Please select the slot again.')

    config = get_config()
    dur = config.appointment_duration_minutes
    validate_slot_rules(lock.slot_start_at, duration_minutes=dur)
    end_at = lock.slot_start_at + timedelta(minutes=dur)

    try:
        appointment = Appointment.objects.create(
            user=user,
            pet=pet,
            start_at=lock.slot_start_at,
            end_at=end_at,
            status=Appointment.STATUS_PENDING,
            payment_status=Appointment.PAYMENT_PENDING,
            payment_reference=payment_reference,
        )
    except IntegrityError as exc:
        raise ValidationError('This slot was just booked. Please choose another slot.') from exc

    lock.delete()

    send_appointment_confirmation_email(appointment)
    send_whatsapp_notification(appointment, event='booking_created')
    return appointment


@transaction.atomic
def reschedule_appointment(user, appointment, local_date, local_time):
    if appointment.user_id != user.id:
        raise ValidationError('You are not allowed to reschedule this appointment.')

    if appointment.reschedule_count >= 1:
        raise ValidationError('You can reschedule only once.')

    if appointment.start_at - timezone.now() < timedelta(hours=12):
        raise ValidationError('Reschedule is allowed only up to 12 hours before appointment time.')

    new_start_utc = to_utc_from_ist(local_date, local_time)
    config = get_config()
    dur = config.appointment_duration_minutes
    validate_slot_rules(new_start_utc, exclude_appointment_id=appointment.id, duration_minutes=dur)

    appointment.status = Appointment.STATUS_RESCHEDULED
    appointment.save(update_fields=['status', 'updated_at'])

    new_end = new_start_utc + timedelta(minutes=dur)
    new_appointment = Appointment.objects.create(
        user=user,
        pet=appointment.pet,
        start_at=new_start_utc,
        end_at=new_end,
        status=Appointment.STATUS_PENDING,
        payment_status=appointment.payment_status,
        payment_reference=appointment.payment_reference,
        reschedule_count=appointment.reschedule_count + 1,
        follow_up_of=appointment.follow_up_of,
        is_follow_up=appointment.is_follow_up,
    )

    send_appointment_confirmation_email(new_appointment)
    send_whatsapp_notification(new_appointment, event='booking_rescheduled')
    return new_appointment


@transaction.atomic
def reschedule_appointment_from_lock(user, appointment, lock_token):
    if appointment.user_id != user.id:
        raise ValidationError('You are not allowed to reschedule this appointment.')

    if appointment.reschedule_count >= 1:
        raise ValidationError('You can reschedule only once.')

    if appointment.start_at - timezone.now() < timedelta(hours=12):
        raise ValidationError('Reschedule is allowed only up to 12 hours before appointment time.')

    cleanup_expired_locks()
    try:
        lock = SlotLock.objects.select_for_update().get(lock_token=lock_token, user=user)
    except SlotLock.DoesNotExist as exc:
        raise ValidationError('Invalid or expired slot lock token.') from exc

    if lock.expires_at < timezone.now():
        lock.delete()
        raise ValidationError('Your slot lock expired. Please select the slot again.')

    config = get_config()
    dur = config.appointment_duration_minutes
    validate_slot_rules(lock.slot_start_at, exclude_appointment_id=appointment.id, duration_minutes=dur)

    appointment.status = Appointment.STATUS_RESCHEDULED
    appointment.save(update_fields=['status', 'updated_at'])

    new_appointment = Appointment.objects.create(
        user=user,
        pet=appointment.pet,
        start_at=lock.slot_start_at,
        end_at=lock.slot_start_at + timedelta(minutes=dur),
        status=Appointment.STATUS_PENDING,
        payment_status=appointment.payment_status,
        payment_reference=appointment.payment_reference,
        reschedule_count=appointment.reschedule_count + 1,
        follow_up_of=appointment.follow_up_of,
        is_follow_up=appointment.is_follow_up,
    )
    lock.delete()

    send_appointment_confirmation_email(new_appointment)
    send_whatsapp_notification(new_appointment, event='booking_rescheduled')
    return new_appointment


def get_daily_slots(local_date, user=None, duration_minutes=None, allow_subhour=False):
    """
    Return a list of available slots for local_date.

    Parameters
    ----------
    local_date       : date in IST
    user             : optional User – used to skip that user's own lock
    duration_minutes : override slot duration; None → use config value (pet-parent path)
    allow_subhour    : if True, generate sub-hour slots (staff path)
    """
    config = get_config()
    dur = duration_minutes if duration_minutes is not None else config.appointment_duration_minutes
    slots = []
    cleanup_expired_locks()

    start_minute = config.start_hour_ist * 60        # e.g. 540 for 09:00
    end_minute   = config.end_hour_ist   * 60        # e.g. 1020 for 17:00

    # Step: for pet parents always 60-min steps (full-hour); for staff use dur
    step = dur if allow_subhour else 60

    cursor_minute = start_minute
    while cursor_minute + dur <= end_minute:
        h, m = divmod(cursor_minute, 60)
        local_dt = (
            datetime.combine(local_date, datetime.min.time()).replace(tzinfo=IST)
            + timedelta(hours=h, minutes=m)
        )
        slot_start_utc = local_dt.astimezone(dt_timezone.utc)

        slot_data = {
            'hour': h,
            'minute': m,
            'label': local_dt.strftime('%I:%M %p'),
            'available': True,
            'reason': '',
        }

        try:
            validate_slot_rules(
                slot_start_utc,
                duration_minutes=dur,
                allow_subhour=allow_subhour,
            )
        except ValidationError as exc:
            slot_data['available'] = False
            slot_data['reason'] = exc.messages[0]

        active_lock = SlotLock.objects.filter(slot_start_at=slot_start_utc, expires_at__gt=timezone.now()).first()
        if active_lock and (not user or active_lock.user_id != user.id):
            slot_data['available'] = False
            slot_data['reason'] = 'Temporarily locked'

        slots.append(slot_data)
        cursor_minute += step

    remaining = sum(1 for s in slots if s['available'])
    return slots, remaining
