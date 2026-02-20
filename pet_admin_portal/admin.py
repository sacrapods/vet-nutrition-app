from django.contrib import admin

from .models import (
    Attachment,
    AuditLog,
    InventoryItem,
    InventoryTransaction,
    MedicalNote,
    Memo,
    NutritionRecord,
    PetPortalMeta,
    Prescription,
    Reminder,
    VitalsExam,
)


@admin.register(PetPortalMeta)
class PetPortalMetaAdmin(admin.ModelAdmin):
    list_display = ("pet", "behavior_badge", "status", "updated_at")
    list_filter = ("behavior_badge", "status")
    search_fields = ("pet__name", "pet__owner__name", "pet__owner__case_id")


@admin.register(VitalsExam)
class VitalsExamAdmin(admin.ModelAdmin):
    list_display = ("pet", "exam_at", "weight_kg", "temperature_c", "heart_rate_bpm", "recorded_by")
    list_filter = ("exam_type", "exam_at")
    search_fields = ("pet__name", "pet_parent__name", "pet_parent__case_id")


@admin.register(NutritionRecord)
class NutritionRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "measured_at", "bcs", "mcs", "wtr", "body_fat_percent", "bfi")
    list_filter = ("measured_at",)


@admin.register(MedicalNote)
class MedicalNoteAdmin(admin.ModelAdmin):
    list_display = ("pet", "created_by", "created_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")


@admin.register(Memo)
class MemoAdmin(admin.ModelAdmin):
    list_display = ("pet_parent", "source", "message_type", "action_required", "display_in_bulletins", "created_at")
    list_filter = ("source", "message_type", "action_required", "display_in_bulletins")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("pet", "medication_name", "dosage", "frequency", "start_date", "end_date")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("pet", "title", "uploaded_by", "created_at", "is_deleted")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("pet", "reminder_type", "due_date", "recurrence_rule", "email_notification", "is_completed")
    list_filter = ("email_notification", "is_completed")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "stock_quantity", "unit", "low_stock_threshold", "is_deleted")
    list_filter = ("category", "is_deleted")


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ("inventory_item", "transaction_type", "quantity", "created_by", "created_at")
    list_filter = ("transaction_type",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "model_label", "object_pk", "action", "actor")
    list_filter = ("action", "model_label")
    search_fields = ("model_label", "object_pk", "object_repr")
    readonly_fields = ("created_at",)
