from django.conf import settings
from django.db import models
from django.utils import timezone

from intake_form.models import Pet, PetParent


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class TimeStampedSoftDeleteModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_deleted",
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])


class PetPortalMeta(TimeStampedSoftDeleteModel):
    BEHAVIOR_FRIENDLY = "friendly"
    BEHAVIOR_AGGRESSIVE = "aggressive"
    BEHAVIOR_NERVOUS = "nervous"
    BEHAVIOR_CHOICES = [
        (BEHAVIOR_FRIENDLY, "Friendly"),
        (BEHAVIOR_AGGRESSIVE, "Aggressive"),
        (BEHAVIOR_NERVOUS, "Nervous"),
    ]

    STATUS_ALIVE = "alive"
    STATUS_DECEASED = "deceased"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ALIVE, "Alive"),
        (STATUS_DECEASED, "Deceased"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name="portal_meta")
    photo = models.FileField(upload_to="portal_pet_photos/%Y/%m/", null=True, blank=True)
    behavior_badge = models.CharField(max_length=20, choices=BEHAVIOR_CHOICES, default=BEHAVIOR_FRIENDLY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ALIVE)

    def __str__(self):
        return f"Portal Meta - {self.pet.name}"


class VitalsExam(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="portal_vitals_exams")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="vitals_exams")
    exam_type = models.CharField(max_length=60, default="Vitals Exam")
    exam_at = models.DateTimeField(default=timezone.now)

    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    heart_rate_bpm = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate_bpm = models.PositiveIntegerField(null=True, blank=True)
    capillary_refill_time = models.CharField(max_length=40, blank=True)
    mucous_membrane = models.CharField(max_length=100, blank=True)
    blood_pressure_systolic = models.PositiveIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveIntegerField(null=True, blank=True)
    hydration = models.CharField(max_length=100, blank=True)
    pain_score = models.PositiveSmallIntegerField(null=True, blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_vitals_exams",
    )

    class Meta:
        ordering = ["-exam_at", "-created_at"]

    def __str__(self):
        return f"Vitals - {self.pet.name} @ {self.exam_at:%Y-%m-%d %H:%M}"


class NutritionRecord(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="nutrition_records")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="nutrition_records")
    measured_at = models.DateTimeField(default=timezone.now)

    bcs = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    mcs = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    wtr = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    body_fat_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bfi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_nutrition_records",
    )

    class Meta:
        ordering = ["-measured_at", "-created_at"]


class MedicalNote(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="medical_notes")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="medical_notes")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    subjective = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class Memo(TimeStampedSoftDeleteModel):
    SOURCE_INTERNAL = "internal"
    SOURCE_CLIENT_CALL = "client_call"
    SOURCE_REQUEST = "request"
    SOURCE_MESSAGE = "message"
    SOURCE_OTHER = "other"
    SOURCE_CHOICES = [
        (SOURCE_INTERNAL, "Internal"),
        (SOURCE_CLIENT_CALL, "Client Call"),
        (SOURCE_REQUEST, "Request"),
        (SOURCE_MESSAGE, "Message"),
        (SOURCE_OTHER, "Other"),
    ]

    TYPE_NORMAL = "normal"
    TYPE_URGENT = "urgent"
    TYPE_EXTREME = "extremely_urgent"
    MESSAGE_TYPE_CHOICES = [
        (TYPE_NORMAL, "Normal"),
        (TYPE_URGENT, "Urgent"),
        (TYPE_EXTREME, "Extremely Urgent"),
    ]

    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="memos")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="memos", null=True, blank=True)

    source = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_INTERNAL)
    body = models.TextField()
    message_type = models.CharField(max_length=32, choices=MESSAGE_TYPE_CHOICES, default=TYPE_NORMAL)
    display_in_bulletins = models.BooleanField(default=False)
    action_required = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_portal_memos",
    )
    assigned_to = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assigned_portal_memos")

    class Meta:
        ordering = ["-created_at"]


class Prescription(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="portal_prescriptions")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="portal_prescriptions")

    medication_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=120)
    frequency = models.CharField(max_length=120)
    duration = models.CharField(max_length=120)
    instructions = models.TextField(blank=True)

    prescribing_vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescribed_portal_prescriptions",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Attachment(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="portal_attachments")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="portal_attachments")

    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to="portal_attachments/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_portal_attachments",
    )

    class Meta:
        ordering = ["-created_at"]

    @property
    def extension(self):
        name = (self.file.name or "").lower()
        return name.rsplit(".", 1)[-1] if "." in name else ""


class Reminder(TimeStampedSoftDeleteModel):
    pet_parent = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name="portal_reminders")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="portal_reminders")

    reminder_type = models.CharField(max_length=120)
    message = models.TextField()
    due_date = models.DateField()
    recurrence_rule = models.CharField(max_length=120, blank=True, help_text="e.g. weekly, monthly")
    email_notification = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date", "-created_at"]


class InventoryItem(TimeStampedSoftDeleteModel):
    CATEGORY_FOOD = "food"
    CATEGORY_MEDICINE = "medicine"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_FOOD, "Food"),
        (CATEGORY_MEDICINE, "Medicine"),
        (CATEGORY_OTHER, "Other"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    sku = models.CharField(max_length=120, blank=True)
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, default="units")
    low_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return self.name


class InventoryTransaction(TimeStampedSoftDeleteModel):
    TYPE_PURCHASE = "purchase"
    TYPE_CONSUMPTION = "consumption"
    TYPE_ADJUSTMENT = "adjustment"
    TYPE_CHOICES = [
        (TYPE_PURCHASE, "Purchase"),
        (TYPE_CONSUMPTION, "Consumption"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    ]

    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True)

    pet_parent = models.ForeignKey(PetParent, null=True, blank=True, on_delete=models.SET_NULL)
    pet = models.ForeignKey(Pet, null=True, blank=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_transactions_created",
    )

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_SOFT_DELETE = "soft_delete"
    ACTION_RESTORE = "restore"
    ACTION_UNDO = "undo"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_SOFT_DELETE, "Soft Delete"),
        (ACTION_RESTORE, "Restore"),
        (ACTION_UNDO, "Undo"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pet_admin_portal_audit_events",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    model_label = models.CharField(max_length=120)
    object_pk = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pet_admin_portal_undo_events",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model_label}#{self.object_pk} {self.action}"
