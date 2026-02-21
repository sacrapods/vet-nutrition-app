from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re
from .models import (
    Pet, CommercialDietHistory, HomemadeDietHistory,
    CommercialTreatHistory, HomemadeTreatHistory, Supplement,
    RecentDietChange, FoodStorage, ActivityDetail,
    AdverseReaction, BrandToAvoid, PreConsultSubmission
)

User = get_user_model()


class PetParentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=False, max_length=150)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email",
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "placeholder": "name@example.com",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )


class PostPaymentActivationForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="Registered Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@example.com"}),
    )
    phone = forms.CharField(
        required=True,
        max_length=20,
        label="Registered Mobile Number",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "e.g. 9876543210"}),
    )
    password1 = forms.CharField(
        min_length=8,
        label="Create Password",
        help_text="Use 8+ characters with uppercase, lowercase, number, and symbol.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Create a strong password"}),
    )
    password2 = forms.CharField(
        min_length=8,
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Re-enter password"}),
    )

    def clean_password1(self):
        password = self.cleaned_data.get("password1", "")
        validate_password(password)
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must include at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must include at least one lowercase letter.")
        if not re.search(r"\d", password):
            raise ValidationError("Password must include at least one number.")
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError("Password must include at least one symbol (e.g. @, #, !, %).")
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise ValidationError('Passwords do not match.')
        return cleaned

    def get_eligible_submission(self):
        email = self.cleaned_data['email'].strip().lower()
        phone = self.cleaned_data['phone'].strip()
        return (
            PreConsultSubmission.objects
            .filter(
                parent_email__iexact=email,
                parent_phone=phone,
                payment_status__in=['paid', 'access_granted'],
                linked_user__isnull=True,
            )
            .order_by('-created_at')
            .first()
        )


class CommercialDietForm(forms.ModelForm):
    class Meta:
        model = CommercialDietHistory
        exclude = ['pet']


class HomemadeDietForm(forms.ModelForm):
    class Meta:
        model = HomemadeDietHistory
        exclude = ['pet']


class CommercialTreatForm(forms.ModelForm):
    class Meta:
        model = CommercialTreatHistory
        exclude = ['pet']


class HomemadeTreatForm(forms.ModelForm):
    class Meta:
        model = HomemadeTreatHistory
        exclude = ['pet']


class SupplementForm(forms.ModelForm):
    class Meta:
        model = Supplement
        exclude = ['pet']


class RecentDietChangeForm(forms.ModelForm):
    class Meta:
        model = RecentDietChange
        exclude = ['pet']


class FoodStorageForm(forms.ModelForm):
    class Meta:
        model = FoodStorage
        exclude = ['pet']


class ActivityDetailForm(forms.ModelForm):
    class Meta:
        model = ActivityDetail
        exclude = ['pet']


class AdverseReactionForm(forms.ModelForm):
    class Meta:
        model = AdverseReaction
        exclude = ['pet']


class BrandToAvoidForm(forms.ModelForm):
    class Meta:
        model = BrandToAvoid
        exclude = ['pet']


# Formsets
CommercialDietFormSet = inlineformset_factory(
    Pet, CommercialDietHistory,
    form=CommercialDietForm,
    extra=1, can_delete=True
)

HomemadeDietFormSet = inlineformset_factory(
    Pet, HomemadeDietHistory,
    form=HomemadeDietForm,
    extra=1, can_delete=True
)

CommercialTreatFormSet = inlineformset_factory(
    Pet, CommercialTreatHistory,
    form=CommercialTreatForm,
    extra=1, can_delete=True
)

HomemadeTreatFormSet = inlineformset_factory(
    Pet, HomemadeTreatHistory,
    form=HomemadeTreatForm,
    extra=1, can_delete=True
)

SupplementFormSet = inlineformset_factory(
    Pet, Supplement,
    form=SupplementForm,
    extra=1, can_delete=True
)

RecentDietChangeFormSet = inlineformset_factory(
    Pet, RecentDietChange,
    form=RecentDietChangeForm,
    extra=1, can_delete=True
)

ActivityDetailFormSet = inlineformset_factory(
    Pet, ActivityDetail,
    form=ActivityDetailForm,
    extra=1, can_delete=True
)

AdverseReactionFormSet = inlineformset_factory(
    Pet, AdverseReaction,
    form=AdverseReactionForm,
    extra=1, can_delete=True
)

BrandToAvoidFormSet = inlineformset_factory(
    Pet, BrandToAvoid,
    form=BrandToAvoidForm,
    extra=1, can_delete=True
)
