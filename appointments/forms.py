from django import forms
from django.contrib.auth import get_user_model

from intake_form.decorators import VET_GROUP, ADMIN_GROUP
from intake_form.models import Pet, PetParent

from .models import (
    Appointment,
    AppointmentConfig,
    ConsultationNote,
    AdminSLAConfig,
    NoteTemplate,
    ProviderCapacity,
)

User = get_user_model()


class AppointmentBookingForm(forms.Form):
    pet = forms.ModelChoiceField(queryset=None, empty_label='Select pet', required=True)
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    appointment_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), required=True)
    lock_token = forms.UUIDField(required=False, widget=forms.HiddenInput())
    payment_reference = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = user.pet_parent_submissions.prefetch_related('pets').values_list('pets__id', flat=True) if user else []
        self.fields['pet'].queryset = Pet.objects.filter(id__in=qs).order_by('name')
        self.fields['pet'].widget.attrs.update(
            {
                'class': 'pet-select',
                'data-placeholder': 'Choose a pet profile',
            }
        )


class AppointmentRescheduleForm(forms.Form):
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    appointment_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), required=True)
    lock_token = forms.UUIDField(required=False, widget=forms.HiddenInput())


class AppointmentStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['status', 'payment_status', 'payment_reference', 'assigned_provider']


class ConsultationNoteForm(forms.ModelForm):
    class Meta:
        model = ConsultationNote
        fields = ['notes', 'prescription_pdf', 'diet_plan_pdf']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 6}),
        }


class AppointmentConfigForm(forms.ModelForm):
    class Meta:
        model = AppointmentConfig
        fields = [
            'start_hour_ist',
            'end_hour_ist',
            'buffer_minutes',
            'daily_appointment_limit',
            'follow_up_enabled',
            'follow_up_days',
            'slot_lock_minutes',
            'upi_id',
        ]


class AdminSLAConfigForm(forms.ModelForm):
    class Meta:
        model = AdminSLAConfig
        fields = [
            'reschedule_response_hours',
            'note_completion_hours',
            'overdue_warning_hours',
        ]


class NoteTemplateForm(forms.ModelForm):
    class Meta:
        model = NoteTemplate
        fields = ['title', 'body', 'active']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 5}),
        }


class ProviderCapacityForm(forms.ModelForm):
    class Meta:
        model = ProviderCapacity
        fields = ['provider', 'daily_limit', 'active']


class StaffAppointmentForm(forms.Form):
    """Form for staff-driven manual appointment creation."""

    # ── Step 1: Who ──────────────────────────────────────────────
    pet_parent = forms.ModelChoiceField(
        queryset=PetParent.objects.select_related('user').order_by('name'),
        empty_label='Search or select pet parent…',
        required=True,
        label='Pet Parent',
    )
    pet = forms.ModelChoiceField(
        queryset=Pet.objects.none(),
        empty_label='Select pet…',
        required=True,
        label='Pet',
    )

    # ── Step 2: When ─────────────────────────────────────────────
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        label='Date',
    )
    # "slot" time (selected from available slots) OR custom override
    appointment_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'step': '900'}),
        required=True,
        label='Time',
    )
    override_slot_rules = forms.BooleanField(
        required=False,
        label='Override slot restrictions',
        help_text='Tick to bypass weekend/hours/capacity checks (use with caution).',
    )
    duration_minutes = forms.ChoiceField(
        choices=[
            (15,  '15 min'),
            (30,  '30 min'),
            (45,  '45 min'),
            (60,  '60 min (1 hr)'),
            (90,  '90 min (1.5 hr)'),
            (120, '120 min (2 hr)'),
        ],
        initial=60,
        required=True,
        label='Duration',
    )

    # ── Step 3: What ─────────────────────────────────────────────
    appt_type = forms.ChoiceField(
        choices=[('', 'Select type…')] + Appointment.APPT_TYPE_CHOICES,
        required=False,
        label='Appointment Type',
    )
    assigned_provider = forms.ModelChoiceField(
        queryset=User.objects.none(),
        empty_label='Unassigned',
        required=False,
        label='Assigned Vet / Provider',
    )
    staff_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Reason for visit, clinical notes, special instructions…'}),
        required=False,
        label='Reason / Notes',
    )

    # ── Step 4: Status ───────────────────────────────────────────
    status = forms.ChoiceField(
        choices=Appointment.STATUS_CHOICES,
        initial=Appointment.STATUS_CONFIRMED,
        required=True,
        label='Initial Status',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import Group
        try:
            vet_group = Group.objects.get(name=VET_GROUP)
            admin_group = Group.objects.get(name=ADMIN_GROUP)
            provider_qs = User.objects.filter(
                groups__in=[vet_group, admin_group]
            ).distinct().order_by('first_name', 'last_name', 'email')
        except Exception:
            provider_qs = User.objects.filter(is_staff=True).order_by('first_name', 'last_name', 'email')
        self.fields['assigned_provider'].queryset = provider_qs

        # If pet_parent is already bound (POST), pre-filter pets
        if self.data.get('pet_parent'):
            try:
                parent_id = int(self.data['pet_parent'])
                self.fields['pet'].queryset = Pet.objects.filter(
                    owner_id=parent_id
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.initial.get('pet_parent'):
            try:
                parent_id = int(self.initial['pet_parent'])
                self.fields['pet'].queryset = Pet.objects.filter(
                    owner_id=parent_id
                ).order_by('name')
            except (ValueError, TypeError):
                pass
