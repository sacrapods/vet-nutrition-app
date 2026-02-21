from django.contrib import admin
from .models import (
    PetParent, Pet, HouseholdDetails, FeedingBehavior, FoodPreferences,
    CommercialDietHistory, HomemadeDietHistory, CommercialTreatHistory,
    HomemadeTreatHistory, Supplement, RecentDietChange, FoodStorage,
    FitnessActivity, ActivityDetail, RehabilitationTherapy,
    MedicalHistory, AdverseReaction, VaccinationStatus, PrimaryVetInfo,
    ClinicalHistory, ClinicalCondition, LongTermMedication,
    SurgicalHistory, DiagnosticImaging, ConsentForm,
    DietPlanPreferences, DoctorNote,
    AdviceSource, ChronicCondition, BrandToAvoid, TreatPreferenceInPlan,
    HomemadeDietQuestionnaire, VetUpload, IntakeFormDraft,
    HomemadeQuestionnaireDraft, VetFormDraft, VetFormAccessLink,
    PreConsultSubmission
)

@admin.register(PetParent)
class PetParentAdmin(admin.ModelAdmin):
    list_display = ("case_id", "name", "email", "user", "created_at")
    search_fields = ("case_id", "name", "email", "user__username")
    list_filter = ("created_at",)


@admin.register(HomemadeDietQuestionnaire)
class HomemadeDietQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ("pet_name", "owner_name", "submitted_by", "created_at")
    search_fields = ("pet_name", "owner_name", "submitted_by__username")
    list_filter = ("species", "created_at")


@admin.register(ClinicalHistory)
class ClinicalHistoryAdmin(admin.ModelAdmin):
    list_display = ("pet", "submitted_by", "created_at")
    search_fields = ("pet__name", "pet__owner__case_id", "submitted_by__username")


@admin.register(VetUpload)
class VetUploadAdmin(admin.ModelAdmin):
    list_display = ("pet", "category", "original_filename", "uploaded_by", "uploaded_at")
    list_filter = ("category", "uploaded_at")
    search_fields = ("pet__name", "pet__owner__case_id", "original_filename", "uploaded_by__username")


@admin.register(PreConsultSubmission)
class PreConsultSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "parent_name",
        "parent_email",
        "parent_phone",
        "pet_name",
        "payment_status",
        "linked_user",
        "created_at",
        "invite_sent_at",
        "activated_at",
    )
    list_filter = ("payment_status", "created_at", "invite_sent_at", "activated_at")
    search_fields = ("parent_name", "parent_email", "parent_phone", "pet_name")
    actions = ("mark_access_granted",)

    @admin.action(description="Mark selected requests as Access Granted")
    def mark_access_granted(self, request, queryset):
        updated = 0
        for obj in queryset:
            if obj.payment_status != "access_granted":
                obj.payment_status = "access_granted"
                obj.save(update_fields=["payment_status"])
                updated += 1
        self.message_user(request, f"{updated} request(s) marked as access granted.")


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
admin.site.register(ClinicalCondition)
admin.site.register(LongTermMedication)
admin.site.register(SurgicalHistory)
admin.site.register(DiagnosticImaging)
admin.site.register(ConsentForm)
admin.site.register(DietPlanPreferences)
admin.site.register(DoctorNote)
admin.site.register(AdviceSource)
admin.site.register(ChronicCondition)
admin.site.register(BrandToAvoid)
admin.site.register(TreatPreferenceInPlan)
admin.site.register(IntakeFormDraft)
admin.site.register(HomemadeQuestionnaireDraft)
admin.site.register(VetFormDraft)
admin.site.register(VetFormAccessLink)
