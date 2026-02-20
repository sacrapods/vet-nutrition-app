from django import forms

from intake_form.models import Pet, PetParent

from .models import (
    Attachment,
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


class PetParentEditForm(forms.ModelForm):
    class Meta:
        model = PetParent
        fields = ["name", "phone", "email", "location_primary_vet"]


class PetEditForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = ["name", "species", "breed", "dob_age", "current_weight_kg"]


class PetPortalMetaForm(forms.ModelForm):
    class Meta:
        model = PetPortalMeta
        fields = ["photo", "behavior_badge", "status"]


class VitalsExamForm(forms.ModelForm):
    exam_at = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    class Meta:
        model = VitalsExam
        fields = [
            "weight_kg",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_bpm",
            "capillary_refill_time",
            "mucous_membrane",
            "blood_pressure_systolic",
            "blood_pressure_diastolic",
            "hydration",
            "pain_score",
            "exam_at",
        ]


class NutritionRecordForm(forms.ModelForm):
    measured_at = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    class Meta:
        model = NutritionRecord
        fields = ["bcs", "mcs", "wtr", "body_fat_percent", "bfi", "measured_at"]


class MedicalNoteForm(forms.ModelForm):
    class Meta:
        model = MedicalNote
        fields = ["subjective", "objective", "assessment", "plan"]


class MemoForm(forms.ModelForm):
    class Meta:
        model = Memo
        fields = [
            "source",
            "body",
            "message_type",
            "display_in_bulletins",
            "action_required",
            "assigned_to",
        ]
        widgets = {"assigned_to": forms.SelectMultiple(attrs={"size": 5})}


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = [
            "medication_name",
            "dosage",
            "frequency",
            "duration",
            "instructions",
            "start_date",
            "end_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["title", "file"]


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ["reminder_type", "message", "due_date", "recurrence_rule", "email_notification"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "category", "sku", "stock_quantity", "unit", "low_stock_threshold"]


class InventoryTransactionForm(forms.ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = ["inventory_item", "transaction_type", "quantity", "unit_cost", "note"]
