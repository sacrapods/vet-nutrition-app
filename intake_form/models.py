from django.db import models
from django.utils import timezone
import random
import string
import os

# ═══════════════════════════════════════════════════════
# CORE MODELS: Pet Parent & Pet
# ═══════════════════════════════════════════════════════

class PetParent(models.Model):
    """Pet owner/guardian information"""
    # Unique identifiers
    case_id = models.CharField(max_length=20, unique=True, editable=False)
    email = models.EmailField(unique=True)
    
    # Contact information
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    location_primary_vet = models.CharField(max_length=300, blank=True)
    
    # Edit access
    edit_token = models.CharField(max_length=64, blank=True)
    edit_token_expiry = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Auto-generate case ID if not exists
        if not self.case_id:
            year = timezone.now().year
            random_num = ''.join(random.choices(string.digits, k=4))
            self.case_id = f"PNV-{year}-{random_num}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.case_id})"
    
    class Meta:
        verbose_name = "Pet Parent"
        verbose_name_plural = "Pet Parents"
        ordering = ['-created_at']


class Pet(models.Model):
    """Individual pet information"""
    SPECIES_CHOICES = [
        ('dog', 'Dog'),
        ('cat', 'Cat'),
        ('other', 'Other'),
    ]
    
    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    
    BODY_CONDITION_CHOICES = [
        ('ideal', 'Ideal'),
        ('underweight', 'Underweight'),
        ('overweight', 'Overweight'),
    ]
    
    owner = models.ForeignKey(PetParent, on_delete=models.CASCADE, related_name='pets')
    
    # Basic information
    name = models.CharField(max_length=100)
    dob_age = models.CharField(max_length=100, verbose_name="Date of Birth / Age")
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=100)
    colour = models.CharField(max_length=50, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    neutered = models.BooleanField(default=False, verbose_name="Neutered/Spayed")
    
    # Physical attributes
    current_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Current Weight (kg)")
    body_condition = models.CharField(max_length=20, choices=BODY_CONDITION_CHOICES)
    
    # Consultation details
    consultation_goals = models.TextField(verbose_name="Reasons and goals for this consultation")
    
    def __str__(self):
        return f"{self.name} ({self.species}) - {self.owner.name}"
    
    class Meta:
        ordering = ['name']


# ═══════════════════════════════════════════════════════
# HOUSEHOLD & FEEDING
# ═══════════════════════════════════════════════════════

class HouseholdDetails(models.Model):
    """Household and living situation"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='household')
    
    food_ingredients_to_avoid = models.TextField(blank=True, verbose_name="Food ingredients to avoid in household")
    can_arrange_special_food = models.CharField(max_length=20, choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('will_try', 'I will try my best'),
    ])
    
    who_feeds = models.CharField(max_length=20, choices=[
        ('one_person', 'Only one person'),
        ('varies', 'Varies from day-to-day'),
    ])
    feeder_name = models.CharField(max_length=200, blank=True)
    
    other_pets = models.BooleanField(default=False)
    other_pets_details = models.TextField(blank=True)
    
    pet_housed = models.CharField(max_length=20, choices=[
        ('indoors', 'Indoors'),
        ('outdoors', 'Outdoors'),
        ('both', 'Both'),
    ])
    
    def __str__(self):
        return f"Household - {self.pet.name}"


class FeedingBehavior(models.Model):
    """Feeding management and eating behavior"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='feeding')
    
    # Food availability
    food_availability = models.CharField(max_length=20, choices=[
        ('always', 'Always available during the day'),
        ('certain_times', 'Only at certain times'),
    ])
    food_availability_times = models.CharField(max_length=200, blank=True)
    meals_per_day = models.IntegerField(null=True, blank=True)
    
    # Eating behavior (stored as JSON string)
    eating_behaviors = models.TextField(blank=True, help_text="Comma-separated: eats_immediately, nibbles, returns_later, hand_fed, begs, table_scraps")
    
    # Attitude changes
    attitude_changed = models.BooleanField(default=False)
    attitude_change_details = models.TextField(blank=True)
    
    # Unmonitored food access
    unmonitored_food_access = models.BooleanField(default=False)
    unmonitored_sources = models.TextField(blank=True, help_text="Comma-separated sources")
    
    # Bowl types
    bowl_type = models.CharField(max_length=100, blank=True)
    bowl_material = models.CharField(max_length=100, blank=True)
    water_bowl_type = models.CharField(max_length=100, blank=True)
    water_bowl_material = models.CharField(max_length=100, blank=True)
    
    # Appetite
    good_appetite = models.CharField(max_length=20, choices=[
        ('yes', 'Yes'),
        ('sometimes', 'Sometimes'),
        ('no', 'No'),
    ], blank=True)
    
    appetite_recently = models.CharField(max_length=20, choices=[
        ('increased', 'Increased'),
        ('same', 'Stayed the same'),
        ('decreased', 'Decreased'),
    ], blank=True)
    
    recent_diet_change = models.BooleanField(default=False)
    recent_diet_change_details = models.TextField(blank=True)
    # Bowl types
    # Bowl types (now storing multiple selections)
    bowl_type = models.TextField(blank=True, help_text="Comma-separated bowl types")
    bowl_type_other = models.CharField(max_length=200, blank=True)
    bowl_material = models.TextField(blank=True, help_text="Comma-separated materials")
    bowl_material_other = models.CharField(max_length=100, blank=True)
    
    water_bowl_type = models.TextField(blank=True, help_text="Comma-separated water bowl types")
    water_bowl_material = models.TextField(blank=True, help_text="Comma-separated water bowl materials")
    water_bowl_material_other = models.CharField(max_length=100, blank=True)
    
    # Recent changes (4 weeks)
    recent_change_4_weeks = models.BooleanField(default=False)
    recent_change_4_weeks_details = models.TextField(blank=True)
    
    def __str__(self):
        return f"Feeding - {self.pet.name}"


class FoodPreferences(models.Model):
    """Pet food and treat preferences"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='food_preferences')
    
    # Stored as comma-separated values
    current_food_preferences = models.TextField(blank=True, help_text="e.g., canned, dry, homecooked, raw")
    current_treat_preferences = models.TextField(blank=True)
    
    refuses_food = models.BooleanField(default=False)
    refused_food_details = models.TextField(blank=True)
    
    preferred_treats_in_plan = models.TextField(blank=True)
    food_brands_to_avoid = models.TextField(blank=True)
    important_food_factors = models.TextField(blank=True, help_text="e.g., price, quality, skin/coat, dental")
    brands_to_avoid_detailed = models.TextField(blank=True, verbose_name="Brands to avoid with reasons")
    
    def __str__(self):
        return f"Food Preferences - {self.pet.name}"


# ═══════════════════════════════════════════════════════
# DIET HISTORY TABLES (Dynamic/Multiple Rows)
# ═══════════════════════════════════════════════════════

class CommercialDietHistory(models.Model):
    """Commercial pet food currently being fed"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='commercial_diet')
    
    DIET_TYPE_CHOICES = [
        ('dry_kibble', 'Dry Kibble'),
        ('wet_canned', 'Wet/Canned'),
        ('raw', 'Raw'),
        ('dehydrated', 'Dehydrated'),
        ('fresh_frozen', 'Fresh/Freeze-dried'),
    ]
    
    diet_type = models.CharField(max_length=50, choices=DIET_TYPE_CHOICES)
    brand = models.CharField(max_length=100)
    product_details = models.CharField(max_length=200)
    amount_per_day = models.CharField(max_length=50, verbose_name="Amount fed per day (gm/ml)")
    food_topper_details = models.CharField(max_length=200, blank=True)
    topper_amount_per_meal = models.CharField(max_length=50, blank=True)
    meals_per_day = models.IntegerField()
    fed_since = models.CharField(max_length=100)
    reason_stopped = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.brand} - {self.pet.name}"
    
    class Meta:
        verbose_name = "Commercial Diet History"
        verbose_name_plural = "Commercial Diet History"


class HomemadeDietHistory(models.Model):
    """Homemade food currently being fed"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='homemade_diet')
    
    ingredient_food_item = models.CharField(max_length=200)
    raw_quantity_per_day = models.CharField(max_length=50, verbose_name="Weight of raw quantity fed per day (gm/ml)")
    preparation_method = models.CharField(max_length=100)
    feed_frequency_per_day = models.IntegerField()
    fed_since = models.CharField(max_length=100)
    reason_stopped = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.ingredient_food_item} - {self.pet.name}"
    
    class Meta:
        verbose_name = "Homemade Diet History"
        verbose_name_plural = "Homemade Diet History"


class CommercialTreatHistory(models.Model):
    """Commercial treats being fed"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='commercial_treats')
    
    treat_type = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    product_details = models.CharField(max_length=200)
    quantity_per_day = models.CharField(max_length=50)
    fed_since = models.CharField(max_length=100)
    reason_stopped = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.brand} treat - {self.pet.name}"
    
    class Meta:
        verbose_name = "Commercial Treat History"
        verbose_name_plural = "Commercial Treat History"


class HomemadeTreatHistory(models.Model):
    """Homemade/human food treats"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='homemade_treats')
    
    treat_type_form = models.CharField(max_length=100)
    ingredient = models.CharField(max_length=200)
    preparation_method = models.CharField(max_length=100)
    quantity_per_day = models.CharField(max_length=50)
    fed_since = models.CharField(max_length=100)
    reason_stopped = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.ingredient} treat - {self.pet.name}"
    
    class Meta:
        verbose_name = "Homemade Treat History"
        verbose_name_plural = "Homemade Treat History"


class Supplement(models.Model):
    """Dietary supplements"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='supplements')
    
    brand_name = models.CharField(max_length=100)
    form = models.CharField(max_length=100, help_text="e.g., tablet, powder, liquid")
    amount = models.CharField(max_length=50)
    per_day = models.IntegerField()
    fed_since = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.brand_name} - {self.pet.name}"
    
    class Meta:
        verbose_name = "Supplement"
        verbose_name_plural = "Supplements"


class RecentDietChange(models.Model):
    """Diet changes in last 2-3 months"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='recent_diet_changes')
    
    brand = models.CharField(max_length=100, blank=True)
    product_food_ingredient = models.CharField(max_length=200)
    form_type = models.CharField(max_length=100)
    amount_per_day = models.CharField(max_length=50)
    meals_per_day = models.IntegerField()
    start_date = models.CharField(max_length=100)
    stop_date = models.CharField(max_length=100, blank=True)
    reason_stopped = models.CharField(max_length=200)
    
    def __str__(self):
        return f"Diet change - {self.pet.name}"
    
    class Meta:
        verbose_name = "Recent Diet Change"
        verbose_name_plural = "Recent Diet Changes"


class FoodStorage(models.Model):
    """How pet food is stored"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='food_storage')
    
    FOOD_TYPE_CHOICES = [
        ('dry', 'Dry Food'),
        ('wet', 'Wet food/canned'),
        ('raw', 'Raw food'),
        ('homecooked', 'Fresh home cooked'),
        ('dehydrated', 'Dehydrated food'),
    ]
    
    food_type = models.CharField(max_length=50, choices=FOOD_TYPE_CHOICES)
    storage_location = models.CharField(max_length=200)
    time_period = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.food_type} storage - {self.pet.name}"
    
    class Meta:
        verbose_name = "Food Storage"
        verbose_name_plural = "Food Storage"


# ═══════════════════════════════════════════════════════
# FITNESS & ACTIVITY
# ═══════════════════════════════════════════════════════

class FitnessActivity(models.Model):
    """Overall fitness and activity level"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='fitness')
    
    ACTIVITY_LEVEL_CHOICES = [
        ('very_active', 'Very active/athlete'),
        ('high', 'High'),
        ('moderate', 'Moderate'),
        ('average', 'Average'),
        ('hardly_moves', 'Hardly moves'),
    ]
    
    activity_level = models.CharField(max_length=50, choices=ACTIVITY_LEVEL_CHOICES)
    exercise_duration = models.CharField(max_length=50, blank=True)
    leash_walk_frequency = models.CharField(max_length=50, blank=True)
    
    fenced_yard_access = models.BooleanField(default=False)
    urban_rural = models.CharField(max_length=20, choices=[
        ('urban', 'Urban'),
        ('rural', 'Rural'),
        ('both', 'Mix of both'),
    ], blank=True)
    
    travel_buddy = models.CharField(max_length=20, choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('sometimes', 'Sometimes'),
    ], blank=True)
    travel_modes = models.CharField(max_length=200, blank=True)
    
    exercise_types = models.TextField(blank=True, help_text="Comma-separated: run, walk, fetch, pulling, agility, swimming")
    
    training_show_dog = models.BooleanField(default=False)
    training_details = models.TextField(blank=True)
    
    recent_activity_changes = models.BooleanField(default=False)
    activity_change_details = models.TextField(blank=True)
    
    increase_exercise_feasible = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Fitness - {self.pet.name}"


class ActivityDetail(models.Model):
    """Specific activity details"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='activity_details')
    
    ACTIVITY_TYPE_CHOICES = [
        ('run', 'Run'),
        ('walk', 'Walk'),
        ('fetch', 'Fetch'),
        ('pulling', 'Pulling/Tugging'),
        ('agility', 'Agility'),
        ('swimming', 'Swimming'),
    ]
    
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)
    duration_distance = models.CharField(max_length=100, verbose_name="Time period (mins) / Distance")
    frequency_per_week = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.activity_type} - {self.pet.name}"


class RehabilitationTherapy(models.Model):
    """Physical rehabilitation therapy"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='rehabilitation')
    
    receives_therapy = models.BooleanField(default=False)
    therapy_types = models.TextField(blank=True, help_text="Comma-separated therapy types")
    
    def __str__(self):
        return f"Rehab - {self.pet.name}"


# ═══════════════════════════════════════════════════════
# MEDICAL HISTORY
# ═══════════════════════════════════════════════════════

class MedicalHistory(models.Model):
    """General medical history and symptoms"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='medical_history')
    
    # Weight changes
    weight_change = models.BooleanField(default=False)
    weight_change_type = models.CharField(max_length=20, choices=[
        ('gain', 'Weight gain'),
        ('loss', 'Weight loss'),
    ], blank=True)
    weight_change_amount_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weight_change_period = models.CharField(max_length=100, blank=True)
    
    # Symptoms
    difficulty_chewing = models.BooleanField(default=False)
    difficulty_swallowing = models.BooleanField(default=False)
    excessive_salivation = models.BooleanField(default=False)
    symptom_details = models.TextField(blank=True)
    
    # Vomiting
    vomiting_per_day = models.IntegerField(null=True, blank=True)
    vomiting_per_week = models.IntegerField(null=True, blank=True)
    vomiting_colour = models.CharField(max_length=100, blank=True)
    vomiting_since = models.CharField(max_length=100, blank=True)
    
    # Urination/Drinking
    urination_changed = models.BooleanField(default=False)
    urination_direction = models.CharField(max_length=20, choices=[
        ('increased', 'Increased'),
        ('decreased', 'Decreased'),
    ], blank=True)
    urine_colour = models.CharField(max_length=100, blank=True)
    urine_change_since = models.CharField(max_length=100, blank=True)
    
    drinking_changed = models.BooleanField(default=False)
    drinking_direction = models.CharField(max_length=20, choices=[
        ('increased', 'Increased'),
        ('decreased', 'Decreased'),
    ], blank=True)
    drinking_change_since = models.CharField(max_length=100, blank=True)
    
    # Defecation
    stool_quality_changed = models.BooleanField(default=False)
    stool_colour = models.CharField(max_length=100, blank=True)
    poops_per_day = models.IntegerField(null=True, blank=True)
    stool_types = models.TextField(blank=True, help_text="Comma-separated: hard, soft, loose, blood")
    stool_change_since = models.CharField(max_length=100, blank=True)
    
    # Medication administration
    medication_admin_method = models.TextField(blank=True)
    
    def __str__(self):
        return f"Medical History - {self.pet.name}"


class AdverseReaction(models.Model):
    """Adverse reactions to foods/medications"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='adverse_reactions')
    
    brand = models.CharField(max_length=100, blank=True)
    product_ingredient_medication = models.CharField(max_length=200)
    form_type = models.CharField(max_length=100)
    fed_since = models.CharField(max_length=100)
    reaction_symptoms = models.TextField()
    
    def __str__(self):
        return f"Adverse Reaction - {self.pet.name}"


class VaccinationStatus(models.Model):
    """Vaccination and prevention status"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='vaccination_status')
    
    yearly_vaccinations = models.BooleanField(default=False)
    deworming = models.BooleanField(default=False)
    
    topical_tick_flea = models.CharField(max_length=20, choices=[
        ('monthly', 'Every month'),
        ('3monthly', 'Every 3 months'),
        ('no', 'No'),
    ], blank=True)
    
    oral_tick_flea = models.CharField(max_length=20, choices=[
        ('monthly', 'Every month'),
        ('6monthly', 'Every 6 months'),
        ('no', 'No'),
    ], blank=True)
    
    def __str__(self):
        return f"Vaccination Status - {self.pet.name}"


class PrimaryVetInfo(models.Model):
    """Primary veterinarian contact information"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='primary_vet')
    
    vet_name = models.CharField(max_length=200)
    practice_name_location = models.CharField(max_length=300)
    clinic_phone = models.CharField(max_length=20)
    email = models.EmailField()
    
    def __str__(self):
        return f"Primary Vet - {self.pet.name}"


# ═══════════════════════════════════════════════════════
# CLINICAL HISTORY (Filled by Referring Vet)
# ═══════════════════════════════════════════════════════

class ClinicalHistory(models.Model):
    """Clinical history filled by referring veterinarian"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='clinical_history')
    
    additional_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Clinical History - {self.pet.name}"


class ClinicalCondition(models.Model):
    """Medical conditions being treated"""
    clinical_history = models.ForeignKey(ClinicalHistory, on_delete=models.CASCADE, related_name='conditions')
    
    condition_disease = models.CharField(max_length=200)
    clinical_symptoms = models.TextField()
    medication_name = models.CharField(max_length=200)
    dose_frequency = models.CharField(max_length=200)
    treatment_length = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.condition_disease} - {self.clinical_history.pet.name}"


class LongTermMedication(models.Model):
    """Long-term medications"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='long_term_medications')
    
    medication_name = models.CharField(max_length=200)
    dose = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.medication_name} - {self.pet.name}"


class SurgicalHistory(models.Model):
    """Surgical procedures"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='surgical_history')
    
    surgery_name = models.CharField(max_length=200)
    date_performed = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.surgery_name} - {self.pet.name}"


class DiagnosticImaging(models.Model):
    """Diagnostic imaging procedures"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='diagnostic_imaging')
    
    imaging_type = models.CharField(max_length=200)
    date_performed = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.imaging_type} - {self.pet.name}"


class VetUpload(models.Model):
    """File uploads from the vet clinical form (lab reports, imaging reports)"""
    CATEGORY_CHOICES = [
        ('blood_work', 'Blood Work / Lab Reports'),
        ('diagnostic_imaging', 'Diagnostic Imaging Reports'),
    ]

    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='vet_uploads')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to='vet_uploads/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_category_display()} - {self.original_filename} ({self.pet.name})"

    @property
    def is_image(self):
        ext = os.path.splitext(self.original_filename)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']

    def delete(self, *args, **kwargs):
        if self.file:
            storage = self.file.storage
            if storage.exists(self.file.name):
                storage.delete(self.file.name)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Vet Upload"
        verbose_name_plural = "Vet Uploads"
        ordering = ['category', '-uploaded_at']


# ═══════════════════════════════════════════════════════
# CONSENT & PREFERENCES
# ═══════════════════════════════════════════════════════

class ConsentForm(models.Model):
    """Consultation consent"""
    pet_parent = models.OneToOneField(PetParent, on_delete=models.CASCADE, related_name='consent')

    agreed = models.BooleanField(default=False)
    date_signed = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consent - {self.pet_parent.name}"


class DietPlanPreferences(models.Model):
    """Preferred diet plan type"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='diet_preferences')

    preferences = models.TextField(blank=True, help_text="Comma-separated: dry_kibble, wet_only, combination, homecooked, etc.")

    def __str__(self):
        return f"Diet Preferences - {self.pet.name}"


class AdviceSource(models.Model):
    """Q20 - Who is your go-to source of advice for pet care"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='advice_source')

    sources = models.TextField(blank=True, help_text="Comma-separated: veterinarian, breeder, pet_store, friend_family, book_magazine, internet")
    other_source = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Advice Source - {self.pet.name}"


class ChronicCondition(models.Model):
    """Q43 - Chronic conditions diagnosed"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='chronic_condition')

    has_chronic = models.BooleanField(default=False)
    details = models.TextField(blank=True)

    def __str__(self):
        return f"Chronic Condition - {self.pet.name}"


class BrandToAvoid(models.Model):
    """Q17 - Pet food brands to avoid (dynamic table)"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='brands_to_avoid')

    brand_name = models.CharField(max_length=200)
    reason = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.brand_name} - {self.pet.name}"

    class Meta:
        verbose_name = "Brand To Avoid"
        verbose_name_plural = "Brands To Avoid"


class TreatPreferenceInPlan(models.Model):
    """Q16 - Treats preferred in diet plan"""
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, related_name='treat_plan_preferences')

    preferences = models.TextField(blank=True, help_text="Comma-separated: commercial_store, dehydrated, raw_bone, homemade_cooked")

    def __str__(self):
        return f"Treat Plan Preferences - {self.pet.name}"


# ═══════════════════════════════════════════════════════
# DOCTOR NOTES
# ═══════════════════════════════════════════════════════

class DoctorNote(models.Model):
    """Doctor's clinical notes"""
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='doctor_notes')
    
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Note for {self.pet.name} - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-created_at']


class HomemadeDietQuestionnaire(models.Model):
    """Standalone homemade diet questionnaire submissions."""

    owner_name = models.CharField(max_length=200)
    owner_email = models.EmailField(blank=True)
    owner_phone = models.CharField(max_length=20, blank=True)

    pet_name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=Pet.SPECIES_CHOICES)
    breed = models.CharField(max_length=100, blank=True)
    age = models.CharField(max_length=100, blank=True)
    current_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    current_diet_description = models.TextField(blank=True)
    homemade_meals_per_day = models.IntegerField(null=True, blank=True)
    recipe_ingredients = models.TextField(blank=True, help_text="Main ingredients currently fed")
    recipe_preparation = models.TextField(blank=True)
    supplements_medications = models.TextField(blank=True)
    concerns_or_goals = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Homemade Diet - {self.pet_name} ({self.owner_name})"

    class Meta:
        ordering = ['-created_at']
