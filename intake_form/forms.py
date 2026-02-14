from django import forms
from django.forms import inlineformset_factory
from .models import (
    Pet, CommercialDietHistory, HomemadeDietHistory,
    CommercialTreatHistory, HomemadeTreatHistory, Supplement,
    RecentDietChange, FoodStorage, ActivityDetail,
    AdverseReaction, BrandToAvoid
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
