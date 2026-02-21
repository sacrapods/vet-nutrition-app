from datetime import timedelta
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AppointmentConfig(models.Model):
    start_hour_ist = models.PositiveSmallIntegerField(default=9)
    end_hour_ist = models.PositiveSmallIntegerField(default=17)
    appointment_duration_minutes = models.PositiveSmallIntegerField(default=60)
    buffer_minutes = models.PositiveSmallIntegerField(default=15)
    daily_appointment_limit = models.PositiveSmallIntegerField(default=8)
    follow_up_enabled = models.BooleanField(default=True)
    follow_up_days = models.PositiveSmallIntegerField(default=7)
    slot_lock_minutes = models.PositiveSmallIntegerField(default=5)
    upi_id = models.CharField(max_length=200, default='your-upi-id@bank')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Appointment Configuration'

    def __str__(self):
        return 'Appointment Configuration'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BlockedDate(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'Blocked date: {self.date}'


class BlockedTimeSlot(models.Model):
    start_at = models.DateTimeField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_at']

    def __str__(self):
        return f'Blocked slot: {self.start_at}'


class Appointment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_RESCHEDULED = 'rescheduled'
    STATUS_NO_SHOW = 'no_show'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_RESCHEDULED, 'Rescheduled'),
        (STATUS_NO_SHOW, 'No Show'),
    ]

    PAYMENT_UNPAID = 'unpaid'
    PAYMENT_PAID = 'paid'
    PAYMENT_PENDING = 'pending'

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_UNPAID, 'Unpaid'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_PENDING, 'Pending'),
    ]

    # Appointment type choices (staff-facing)
    APPT_TYPE_CONSULTATION = 'consultation'
    APPT_TYPE_VACCINATION = 'vaccination'
    APPT_TYPE_SURGERY = 'surgery'
    APPT_TYPE_FOLLOW_UP = 'follow_up'
    APPT_TYPE_GROOMING = 'grooming'
    APPT_TYPE_WELLNESS = 'wellness'
    APPT_TYPE_EMERGENCY = 'emergency'
    APPT_TYPE_OTHER = 'other'

    APPT_TYPE_CHOICES = [
        (APPT_TYPE_CONSULTATION, 'Consultation'),
        (APPT_TYPE_VACCINATION, 'Vaccination'),
        (APPT_TYPE_SURGERY, 'Surgery'),
        (APPT_TYPE_FOLLOW_UP, 'Follow-up'),
        (APPT_TYPE_GROOMING, 'Grooming'),
        (APPT_TYPE_WELLNESS, 'Wellness Check'),
        (APPT_TYPE_EMERGENCY, 'Emergency'),
        (APPT_TYPE_OTHER, 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appointments')
    pet = models.ForeignKey('intake_form.Pet', on_delete=models.CASCADE, related_name='appointments')
    assigned_provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_appointments',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_modifications',
    )

    start_at = models.DateTimeField(unique=True, db_index=True)
    end_at = models.DateTimeField(db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_UNPAID)
    payment_reference = models.CharField(max_length=255, blank=True)

    appt_type = models.CharField(
        max_length=30,
        choices=APPT_TYPE_CHOICES,
        default=APPT_TYPE_CONSULTATION,
        blank=True,
        verbose_name='Appointment Type',
    )
    staff_notes = models.TextField(blank=True, verbose_name='Reason / Notes')

    reschedule_count = models.PositiveSmallIntegerField(default=0)
    is_follow_up = models.BooleanField(default=False)
    follow_up_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_ups'
    )

    reminder_24h_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_1h_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_at']
        indexes = [
            models.Index(fields=['user', 'start_at']),
            models.Index(fields=['status', 'start_at']),
        ]

    def __str__(self):
        return f'{self.pet.name} - {self.start_at}'

    @property
    def appointment_type(self):
        return self.appt_type or ('follow_up' if self.is_follow_up else 'initial')

    @property
    def appointment_type_label(self):
        if self.appt_type:
            return dict(self.APPT_TYPE_CHOICES).get(self.appt_type, self.appt_type.title())
        return 'Follow-up' if self.is_follow_up else 'Initial'


class SlotLock(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appointment_slot_locks')
    slot_start_at = models.DateTimeField(unique=True, db_index=True)
    lock_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Lock {self.slot_start_at} by {self.user}'

    @classmethod
    def build_expiry(cls):
        config = AppointmentConfig.get_solo()
        return timezone.now() + timedelta(minutes=config.slot_lock_minutes)


class ConsultationNote(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='consultation_note')
    notes = models.TextField(blank=True)
    prescription_pdf = models.FileField(upload_to='appointments/prescriptions/%Y/%m/', blank=True)
    diet_plan_pdf = models.FileField(upload_to='appointments/diet_plans/%Y/%m/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Consultation note for {self.appointment}'


class AppointmentRescheduleRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='reschedule_requests',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_reschedule_requests',
    )
    requested_start_at = models.DateTimeField(db_index=True)
    requested_end_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_appointment_reschedule_requests',
    )
    resulting_appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_reschedule_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Reschedule request #{self.id} for appointment #{self.appointment_id}'


class ProviderCapacity(models.Model):
    provider = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='provider_capacity',
    )
    daily_limit = models.PositiveSmallIntegerField(default=8)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Provider Capacity'
        verbose_name_plural = 'Provider Capacities'

    def __str__(self):
        return f'{self.provider} (limit: {self.daily_limit}/day)'


class AdminSLAConfig(models.Model):
    reschedule_response_hours = models.PositiveSmallIntegerField(default=24)
    note_completion_hours = models.PositiveSmallIntegerField(default=24)
    overdue_warning_hours = models.PositiveSmallIntegerField(default=4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admin SLA Configuration'

    def __str__(self):
        return 'Admin SLA Configuration'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NoteTemplate(models.Model):
    title = models.CharField(max_length=120)
    body = models.TextField()
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_note_templates',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_note_templates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class AdminAuditLog(models.Model):
    ENTITY_APPOINTMENT = 'appointment'
    ENTITY_RESCHEDULE = 'reschedule_request'
    ENTITY_BLOCKED_DATE = 'blocked_date'
    ENTITY_BLOCKED_SLOT = 'blocked_slot'
    ENTITY_SETTINGS = 'settings'
    ENTITY_NOTE_TEMPLATE = 'note_template'
    ENTITY_PROVIDER = 'provider'
    ENTITY_SYSTEM = 'system'

    ENTITY_CHOICES = [
        (ENTITY_APPOINTMENT, 'Appointment'),
        (ENTITY_RESCHEDULE, 'Reschedule Request'),
        (ENTITY_BLOCKED_DATE, 'Blocked Date'),
        (ENTITY_BLOCKED_SLOT, 'Blocked Slot'),
        (ENTITY_SETTINGS, 'Settings'),
        (ENTITY_NOTE_TEMPLATE, 'Note Template'),
        (ENTITY_PROVIDER, 'Provider'),
        (ENTITY_SYSTEM, 'System'),
    ]

    entity_type = models.CharField(max_length=40, choices=ENTITY_CHOICES, default=ENTITY_SYSTEM)
    entity_id = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=120)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_audit_events',
    )
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.entity_type}:{self.entity_id} {self.action}'
