from django.contrib import admin
from .models import (
    PetParent, Pet, HouseholdDetails, FeedingBehavior, FoodPreferences,
    CommercialDietHistory, HomemadeDietHistory, CommercialTreatHistory,
    HomemadeTreatHistory, Supplement, RecentDietChange, FoodStorage,
    FitnessActivity, ActivityDetail, RehabilitationTherapy,
    MedicalHistory, AdverseReaction, VaccinationStatus, PrimaryVetInfo,
    ClinicalHistory, ClinicalCondition, LongTermMedication,
    SurgicalHistory, DiagnosticImaging, ConsentForm,
    DietPlanPreferences, DoctorNote
)

# Register all models in admin
admin.site.register(PetParent)
admin.site.register(Pet)
admin.site.register(HouseholdDetails)
admin.site.register(FeedingBehavior)
admin.site.register(FoodPreferences)
admin.site.register(CommercialDietHistory)
admin.site.register(HomemadeDietHistory)
admin.site.register(CommercialTreatHistory)
admin.site.register(HomemadeTreatHistory)
admin.site.register(Supplement)
admin.site.register(RecentDietChange)
admin.site.register(FoodStorage)
admin.site.register(FitnessActivity)
admin.site.register(ActivityDetail)
admin.site.register(RehabilitationTherapy)
admin.site.register(MedicalHistory)
admin.site.register(AdverseReaction)
admin.site.register(VaccinationStatus)
admin.site.register(PrimaryVetInfo)
admin.site.register(ClinicalHistory)
admin.site.register(ClinicalCondition)
admin.site.register(LongTermMedication)
admin.site.register(SurgicalHistory)
admin.site.register(DiagnosticImaging)
admin.site.register(ConsentForm)
admin.site.register(DietPlanPreferences)
admin.site.register(DoctorNote)