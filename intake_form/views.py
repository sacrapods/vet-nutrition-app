from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models as db_models
from django.views.decorators.http import require_POST
from .models import (
    PetParent, Pet, HouseholdDetails, FeedingBehavior,
    FoodPreferences, CommercialDietHistory, HomemadeDietHistory,
    CommercialTreatHistory, HomemadeTreatHistory, Supplement,
    RecentDietChange, FoodStorage, FitnessActivity, ActivityDetail,
    RehabilitationTherapy, MedicalHistory, AdverseReaction,
    VaccinationStatus, PrimaryVetInfo, ConsentForm,
    DietPlanPreferences, AdviceSource, ChronicCondition,
    BrandToAvoid, TreatPreferenceInPlan,
    ClinicalHistory, ClinicalCondition, LongTermMedication,
    SurgicalHistory, DiagnosticImaging, VetUpload
)


def intake_form_view(request):
    """Display and process the intake form"""

    if request.method == 'POST':
        # ── Pet Parent ──
        pet_parent = PetParent.objects.create(
            name=request.POST.get('parent_name'),
            email=request.POST.get('parent_email'),
            phone=request.POST.get('parent_phone'),
            location_primary_vet=request.POST.get('parent_location', '')
        )

        # ── Pet ──
        pet_weight = request.POST.get('pet_weight', '')
        pet = Pet.objects.create(
            owner=pet_parent,
            name=request.POST.get('pet_name', ''),
            dob_age=request.POST.get('pet_age', ''),
            species=request.POST.get('pet_species', 'dog'),
            breed=request.POST.get('pet_breed', ''),
            colour=request.POST.get('pet_colour', ''),
            sex=request.POST.get('pet_sex', 'male'),
            neutered=request.POST.get('pet_neutered') == 'yes',
            current_weight_kg=pet_weight if pet_weight else None,
            body_condition=request.POST.get('pet_body_condition', 'ideal'),
            consultation_goals=request.POST.get('pet_consultation_goals', '')
        )

        # ── Household Details ──
        HouseholdDetails.objects.create(
            pet=pet,
            food_ingredients_to_avoid=request.POST.get('household_avoid_ingredients', ''),
            can_arrange_special_food=request.POST.get('household_arrange_food', 'no'),
            who_feeds=request.POST.get('household_who_feeds', 'varies'),
            feeder_name=request.POST.get('household_feeder_name', ''),
            other_pets=request.POST.get('household_other_pets') == 'yes',
            other_pets_details=request.POST.get('household_other_pets_details', ''),
            pet_housed=request.POST.get('household_pet_housed', 'indoors')
        )

        # ── Feeding Behavior ──
        feeding_behaviors = request.POST.getlist('feeding_behaviors')
        unmonitored_sources_list = request.POST.getlist('unmonitored_sources')
        unmonitored_other = request.POST.get('unmonitored_other', '')
        unmonitored_str = ','.join(unmonitored_sources_list)
        if unmonitored_other:
            unmonitored_str += ',' + unmonitored_other

        bowl_types_str = ','.join(request.POST.getlist('bowl_types'))
        bowl_material_str = ','.join(request.POST.getlist('bowl_material'))
        water_bowl_types_str = ','.join(request.POST.getlist('water_bowl_types'))
        water_bowl_material_str = ','.join(request.POST.getlist('water_bowl_material'))

        meals_per_day = request.POST.get('feeding_meals_per_day')

        FeedingBehavior.objects.create(
            pet=pet,
            food_availability=request.POST.get('feeding_food_availability', 'always'),
            food_availability_times=request.POST.get('feeding_food_times', ''),
            meals_per_day=int(meals_per_day) if meals_per_day else None,
            eating_behaviors=','.join(feeding_behaviors),
            attitude_changed=request.POST.get('feeding_attitude_changed') == 'yes',
            attitude_change_details=request.POST.get('feeding_attitude_details', ''),
            unmonitored_food_access=request.POST.get('feeding_unmonitored') == 'yes',
            unmonitored_sources=unmonitored_str,
            good_appetite=request.POST.get('feeding_good_appetite', ''),
            appetite_recently=request.POST.get('feeding_appetite_recently', ''),
            bowl_type=bowl_types_str,
            bowl_type_other=request.POST.get('bowl_type_other', ''),
            bowl_material=bowl_material_str,
            bowl_material_other=request.POST.get('bowl_material_other', ''),
            water_bowl_type=water_bowl_types_str,
            water_bowl_material=water_bowl_material_str,
            water_bowl_material_other=request.POST.get('water_bowl_material_other', ''),
            recent_change_4_weeks=request.POST.get('recent_diet_change_4wks') == 'yes',
            recent_change_4_weeks_details=request.POST.get('recent_change_4wks_details', '')
        )

        # ── Food Preferences ──
        food_prefs_str = ','.join(request.POST.getlist('food_preferences'))
        treat_prefs_str = ','.join(request.POST.getlist('treat_preferences'))
        food_factors_str = ','.join(request.POST.getlist('food_factors'))

        FoodPreferences.objects.create(
            pet=pet,
            current_food_preferences=food_prefs_str,
            current_treat_preferences=treat_prefs_str,
            refuses_food=request.POST.get('food_refuses') == 'yes',
            refused_food_details=request.POST.get('food_refuses_details', ''),
            preferred_treats_in_plan=request.POST.get('preferred_treats_in_plan', ''),
            food_brands_to_avoid=request.POST.get('brands_to_avoid', ''),
            important_food_factors=food_factors_str
        )

        # ── Q16: Treat Preferences in Plan (checkboxes) ──
        treat_plan_prefs = request.POST.getlist('treat_plan_preferences')
        TreatPreferenceInPlan.objects.create(
            pet=pet,
            preferences=','.join(treat_plan_prefs)
        )

        # ── Q17: Brands to Avoid (dynamic table) ──
        brand_names = request.POST.getlist('avoid_brand_name[]')
        brand_reasons = request.POST.getlist('avoid_brand_reason[]')
        for i in range(len(brand_names)):
            if brand_names[i].strip():
                BrandToAvoid.objects.create(
                    pet=pet,
                    brand_name=brand_names[i],
                    reason=brand_reasons[i] if i < len(brand_reasons) else ''
                )

        # ── Food Storage ──
        storage_types = ['dry', 'wet', 'raw', 'homecooked', 'dehydrated']
        for st in storage_types:
            loc = request.POST.get(f'storage_{st}_location', '')
            period = request.POST.get(f'storage_{st}_period', '')
            if loc or period:
                FoodStorage.objects.create(
                    pet=pet,
                    food_type=st,
                    storage_location=loc,
                    time_period=period
                )

        # ── Q20: Advice Source ──
        advice_sources = request.POST.getlist('advice_sources')
        AdviceSource.objects.create(
            pet=pet,
            sources=','.join(advice_sources),
            other_source=request.POST.get('advice_source_other', '')
        )

        # ── Commercial Diet History (dynamic table) ──
        diet_types = request.POST.getlist('diet_type[]')
        diet_brands = request.POST.getlist('diet_brand[]')
        diet_products = request.POST.getlist('diet_product[]')
        diet_amounts = request.POST.getlist('diet_amount[]')
        diet_toppers = request.POST.getlist('diet_topper[]')
        diet_topper_amts = request.POST.getlist('diet_topper_amount[]')
        diet_meals = request.POST.getlist('diet_meals[]')
        diet_since = request.POST.getlist('diet_since[]')
        diet_reason = request.POST.getlist('diet_reason_stopped[]')

        for i in range(len(diet_types)):
            if diet_types[i] and diet_brands[i]:
                CommercialDietHistory.objects.create(
                    pet=pet,
                    diet_type=diet_types[i],
                    brand=diet_brands[i],
                    product_details=diet_products[i] if i < len(diet_products) else '',
                    amount_per_day=diet_amounts[i] if i < len(diet_amounts) else '',
                    food_topper_details=diet_toppers[i] if i < len(diet_toppers) else '',
                    topper_amount_per_meal=diet_topper_amts[i] if i < len(diet_topper_amts) else '',
                    meals_per_day=int(diet_meals[i]) if i < len(diet_meals) and diet_meals[i] else 1,
                    fed_since=diet_since[i] if i < len(diet_since) else '',
                    reason_stopped=diet_reason[i] if i < len(diet_reason) else ''
                )

        # ── Homemade Diet History (dynamic table) ──
        hd_ingredients = request.POST.getlist('hd_ingredient[]')
        hd_quantities = request.POST.getlist('hd_quantity[]')
        hd_preparations = request.POST.getlist('hd_preparation[]')
        hd_frequencies = request.POST.getlist('hd_frequency[]')
        hd_since = request.POST.getlist('hd_since[]')
        hd_reason = request.POST.getlist('hd_reason_stopped[]')

        for i in range(len(hd_ingredients)):
            if hd_ingredients[i].strip():
                HomemadeDietHistory.objects.create(
                    pet=pet,
                    ingredient_food_item=hd_ingredients[i],
                    raw_quantity_per_day=hd_quantities[i] if i < len(hd_quantities) else '',
                    preparation_method=hd_preparations[i] if i < len(hd_preparations) else '',
                    feed_frequency_per_day=int(hd_frequencies[i]) if i < len(hd_frequencies) and hd_frequencies[i] else 1,
                    fed_since=hd_since[i] if i < len(hd_since) else '',
                    reason_stopped=hd_reason[i] if i < len(hd_reason) else ''
                )

        # ── Commercial Treat History (dynamic table) ──
        ct_types = request.POST.getlist('ct_type[]')
        ct_brands = request.POST.getlist('ct_brand[]')
        ct_products = request.POST.getlist('ct_product[]')
        ct_quantities = request.POST.getlist('ct_quantity[]')
        ct_since = request.POST.getlist('ct_since[]')
        ct_reason = request.POST.getlist('ct_reason_stopped[]')

        for i in range(len(ct_types)):
            if ct_types[i].strip():
                CommercialTreatHistory.objects.create(
                    pet=pet,
                    treat_type=ct_types[i],
                    brand=ct_brands[i] if i < len(ct_brands) else '',
                    product_details=ct_products[i] if i < len(ct_products) else '',
                    quantity_per_day=ct_quantities[i] if i < len(ct_quantities) else '',
                    fed_since=ct_since[i] if i < len(ct_since) else '',
                    reason_stopped=ct_reason[i] if i < len(ct_reason) else ''
                )

        # ── Homemade Treat History (dynamic table) ──
        treat_type_forms = request.POST.getlist('treat_type_form[]')
        treat_ingredients = request.POST.getlist('treat_ingredient[]')
        treat_preparations = request.POST.getlist('treat_preparation[]')
        treat_quantities = request.POST.getlist('treat_quantity[]')
        treat_since_list = request.POST.getlist('treat_since[]')
        treat_reason = request.POST.getlist('treat_reason_stopped[]')

        for i in range(len(treat_ingredients)):
            if treat_ingredients[i].strip():
                HomemadeTreatHistory.objects.create(
                    pet=pet,
                    treat_type_form=treat_type_forms[i] if i < len(treat_type_forms) else '',
                    ingredient=treat_ingredients[i],
                    preparation_method=treat_preparations[i] if i < len(treat_preparations) else '',
                    quantity_per_day=treat_quantities[i] if i < len(treat_quantities) else '',
                    fed_since=treat_since_list[i] if i < len(treat_since_list) else '',
                    reason_stopped=treat_reason[i] if i < len(treat_reason) else ''
                )

        # ── Supplements (dynamic table) ──
        supp_brands = request.POST.getlist('supplement_brand[]')
        supp_forms = request.POST.getlist('supplement_form[]')
        supp_amounts = request.POST.getlist('supplement_amount[]')
        supp_per_day = request.POST.getlist('supplement_per_day[]')
        supp_since = request.POST.getlist('supplement_since[]')

        if request.POST.get('supplements_given') == 'yes':
            for i in range(len(supp_brands)):
                if supp_brands[i].strip():
                    Supplement.objects.create(
                        pet=pet,
                        brand_name=supp_brands[i],
                        form=supp_forms[i] if i < len(supp_forms) else '',
                        amount=supp_amounts[i] if i < len(supp_amounts) else '',
                        per_day=int(supp_per_day[i]) if i < len(supp_per_day) and supp_per_day[i] else 1,
                        fed_since=supp_since[i] if i < len(supp_since) else ''
                    )

        # ── Recent Diet Changes (dynamic table) ──
        if request.POST.get('diet_changed_2_3_months') == 'yes':
            rdc_brands = request.POST.getlist('rdc_brand[]')
            rdc_products = request.POST.getlist('rdc_product[]')
            rdc_forms = request.POST.getlist('rdc_form[]')
            rdc_amounts = request.POST.getlist('rdc_amount[]')
            rdc_meals = request.POST.getlist('rdc_meals[]')
            rdc_start = request.POST.getlist('rdc_start[]')
            rdc_stop = request.POST.getlist('rdc_stop[]')
            rdc_reason = request.POST.getlist('rdc_reason[]')

            for i in range(len(rdc_products)):
                if rdc_products[i].strip():
                    RecentDietChange.objects.create(
                        pet=pet,
                        brand=rdc_brands[i] if i < len(rdc_brands) else '',
                        product_food_ingredient=rdc_products[i],
                        form_type=rdc_forms[i] if i < len(rdc_forms) else '',
                        amount_per_day=rdc_amounts[i] if i < len(rdc_amounts) else '',
                        meals_per_day=int(rdc_meals[i]) if i < len(rdc_meals) and rdc_meals[i] else 1,
                        start_date=rdc_start[i] if i < len(rdc_start) else '',
                        stop_date=rdc_stop[i] if i < len(rdc_stop) else '',
                        reason_stopped=rdc_reason[i] if i < len(rdc_reason) else ''
                    )

        # ── Diet Plan Preferences ──
        diet_plan_prefs = request.POST.getlist('diet_plan_preferences')
        DietPlanPreferences.objects.create(
            pet=pet,
            preferences=','.join(diet_plan_prefs)
        )

        # ── Fitness & Activity ──
        FitnessActivity.objects.create(
            pet=pet,
            activity_level=request.POST.get('activity_level', 'moderate'),
            exercise_duration=request.POST.get('exercise_duration', ''),
            leash_walk_frequency=request.POST.get('leash_walk_frequency', ''),
            fenced_yard_access=request.POST.get('fenced_yard') == 'yes',
            urban_rural=request.POST.get('urban_rural', ''),
            travel_buddy=request.POST.get('travel_buddy', ''),
            travel_modes=request.POST.get('travel_modes', ''),
            exercise_types=','.join(request.POST.getlist('exercise_types')),
            training_show_dog=request.POST.get('training_show_dog') == 'yes',
            training_details=request.POST.get('training_details', ''),
            recent_activity_changes=request.POST.get('recent_activity_changes') == 'yes',
            activity_change_details=request.POST.get('activity_change_details', ''),
            increase_exercise_feasible=request.POST.get('increase_exercise') == 'yes'
        )

        # ── Activity Details (table Q28) ──
        act_types = ['run', 'walk', 'fetch', 'pulling', 'agility', 'swimming']
        for act in act_types:
            duration = request.POST.get(f'activity_{act}_duration', '')
            freq = request.POST.get(f'activity_{act}_frequency', '')
            if duration or freq:
                ActivityDetail.objects.create(
                    pet=pet,
                    activity_type=act,
                    duration_distance=duration,
                    frequency_per_week=freq
                )

        # ── Rehabilitation Therapy ──
        rehab_therapies = request.POST.getlist('rehab_therapies')
        RehabilitationTherapy.objects.create(
            pet=pet,
            receives_therapy=request.POST.get('receives_rehab') == 'yes',
            therapy_types=','.join(rehab_therapies)
        )

        # ── Medical History ──
        weight_amount = request.POST.get('medical_weight_amount')
        vomit_per_day = request.POST.get('medical_vomit_per_day')
        poops_per_day = request.POST.get('medical_poops_per_day')
        stool_types = request.POST.getlist('medical_stool_types')

        # Q40: Medication admin method
        med_admin = request.POST.getlist('medication_admin')
        pill_pocket_details = request.POST.get('pill_pocket_details', '')
        food_treat_details = request.POST.get('med_food_treat_details', '')
        med_admin_str = ','.join(med_admin)
        if pill_pocket_details:
            med_admin_str += '|pill_pocket:' + pill_pocket_details
        if food_treat_details:
            med_admin_str += '|food_treat:' + food_treat_details

        MedicalHistory.objects.create(
            pet=pet,
            weight_change=request.POST.get('medical_weight_change') == 'yes',
            weight_change_type=request.POST.get('medical_weight_type', ''),
            weight_change_amount_kg=float(weight_amount) if weight_amount else None,
            weight_change_period=request.POST.get('medical_weight_period', ''),
            difficulty_chewing='difficulty_chewing' in request.POST.getlist('medical_symptoms'),
            difficulty_swallowing='difficulty_swallowing' in request.POST.getlist('medical_symptoms'),
            excessive_salivation='excessive_salivation' in request.POST.getlist('medical_symptoms'),
            symptom_details=request.POST.get('symptom_details', ''),
            vomiting_per_day=int(vomit_per_day) if vomit_per_day else None,
            vomiting_per_week=int(request.POST.get('medical_vomit_per_week', '') or 0) if request.POST.get('medical_vomit_per_week') else None,
            vomiting_colour=request.POST.get('medical_vomit_colour', ''),
            vomiting_since=request.POST.get('medical_vomit_since', ''),
            urination_changed=request.POST.get('medical_urination_changed') == 'yes',
            urination_direction=request.POST.get('medical_urination_direction', ''),
            urine_colour=request.POST.get('medical_urine_colour', ''),
            urine_change_since=request.POST.get('medical_urine_since', ''),
            drinking_changed=request.POST.get('medical_drinking_changed') == 'yes',
            drinking_direction=request.POST.get('medical_drinking_direction', ''),
            drinking_change_since=request.POST.get('medical_drinking_since', ''),
            stool_quality_changed=request.POST.get('medical_stool_changed') == 'yes',
            stool_colour=request.POST.get('medical_stool_colour', ''),
            poops_per_day=int(poops_per_day) if poops_per_day else None,
            stool_types=','.join(stool_types),
            stool_change_since=request.POST.get('medical_stool_since', ''),
            medication_admin_method=med_admin_str
        )

        # ── Q41: Adverse Reactions (dynamic table) ──
        if request.POST.get('has_adverse_reactions') == 'yes':
            ar_brands = request.POST.getlist('ar_brand[]')
            ar_products = request.POST.getlist('ar_product[]')
            ar_forms = request.POST.getlist('ar_form[]')
            ar_since = request.POST.getlist('ar_since[]')
            ar_symptoms = request.POST.getlist('ar_symptoms[]')

            for i in range(len(ar_products)):
                if ar_products[i].strip():
                    AdverseReaction.objects.create(
                        pet=pet,
                        brand=ar_brands[i] if i < len(ar_brands) else '',
                        product_ingredient_medication=ar_products[i],
                        form_type=ar_forms[i] if i < len(ar_forms) else '',
                        fed_since=ar_since[i] if i < len(ar_since) else '',
                        reaction_symptoms=ar_symptoms[i] if i < len(ar_symptoms) else ''
                    )

        # ── Q43: Chronic Condition ──
        ChronicCondition.objects.create(
            pet=pet,
            has_chronic=request.POST.get('has_chronic_condition') == 'yes',
            details=request.POST.get('chronic_condition_details', '')
        )

        # ── Vaccination Status ──
        VaccinationStatus.objects.create(
            pet=pet,
            yearly_vaccinations=request.POST.get('vacc_yearly') == 'yes',
            deworming=request.POST.get('vacc_deworming') == 'yes',
            topical_tick_flea=request.POST.get('vacc_topical_tick', 'no'),
            oral_tick_flea=request.POST.get('vacc_oral_tick', 'no')
        )

        # ── Primary Vet Info ──
        PrimaryVetInfo.objects.create(
            pet=pet,
            vet_name=request.POST.get('vet_name'),
            practice_name_location=request.POST.get('vet_practice'),
            clinic_phone=request.POST.get('vet_phone'),
            email=request.POST.get('vet_email')
        )

        # ── Consent Form ──
        ConsentForm.objects.create(
            pet_parent=pet_parent,
            agreed=request.POST.get('consent_agreed') == 'yes'
        )

        messages.success(request, f'Form submitted successfully! Your Case ID is: {pet_parent.case_id}')
        return redirect('success')

    # GET request - show the form
    return render(request, 'intake_form/form.html')


def success_view(request):
    """Success page after form submission"""
    return render(request, 'intake_form/success.html')


def case_list_view(request):
    """Dashboard: list of all submitted cases"""
    q = request.GET.get('q', '')
    parents = PetParent.objects.prefetch_related('pets').order_by('-created_at')
    if q:
        parents = parents.filter(
            db_models.Q(name__icontains=q) |
            db_models.Q(case_id__icontains=q) |
            db_models.Q(pets__name__icontains=q)
        ).distinct()
    return render(request, 'intake_form/case_list.html', {'parents': parents, 'q': q})


def case_detail_view(request, pk):
    """Detail view: all info for one pet"""
    pet = get_object_or_404(Pet.objects.select_related('owner'), pk=pk)
    return render(request, 'intake_form/case_detail.html', {'pet': pet})


def case_pdf_view(request, pk):
    """Simple printable/PDF view"""
    pet = get_object_or_404(Pet.objects.select_related('owner'), pk=pk)
    context = {
        'pet': pet,
        'blood_work_uploads': pet.vet_uploads.filter(category='blood_work'),
        'imaging_uploads': pet.vet_uploads.filter(category='diagnostic_imaging'),
    }
    return render(request, 'intake_form/case_pdf.html', context)


def vet_form_view(request, pk):
    """Clinical history form filled by the referring vet"""
    pet = get_object_or_404(Pet.objects.select_related('owner'), pk=pk)

    if request.method == 'POST':
        # Clinical History
        clinical, _ = ClinicalHistory.objects.get_or_create(pet=pet)
        clinical.additional_notes = request.POST.get('additional_notes', '')
        clinical.save()

        # Clear old rows and re-save (simple approach for dynamic tables)
        ClinicalCondition.objects.filter(clinical_history=clinical).delete()
        cond_diseases = request.POST.getlist('cond_disease[]')
        cond_symptoms = request.POST.getlist('cond_symptoms[]')
        cond_meds = request.POST.getlist('cond_medication[]')
        cond_doses = request.POST.getlist('cond_dose[]')
        cond_lengths = request.POST.getlist('cond_length[]')
        for i in range(len(cond_diseases)):
            if cond_diseases[i].strip():
                ClinicalCondition.objects.create(
                    clinical_history=clinical,
                    condition_disease=cond_diseases[i],
                    clinical_symptoms=cond_symptoms[i] if i < len(cond_symptoms) else '',
                    medication_name=cond_meds[i] if i < len(cond_meds) else '',
                    dose_frequency=cond_doses[i] if i < len(cond_doses) else '',
                    treatment_length=cond_lengths[i] if i < len(cond_lengths) else ''
                )

        # Long-term Medications
        LongTermMedication.objects.filter(pet=pet).delete()
        med_names = request.POST.getlist('med_name[]')
        med_doses = request.POST.getlist('med_dose[]')
        med_freqs = request.POST.getlist('med_frequency[]')
        for i in range(len(med_names)):
            if med_names[i].strip():
                LongTermMedication.objects.create(
                    pet=pet,
                    medication_name=med_names[i],
                    dose=med_doses[i] if i < len(med_doses) else '',
                    frequency=med_freqs[i] if i < len(med_freqs) else ''
                )

        # Surgical History
        SurgicalHistory.objects.filter(pet=pet).delete()
        surg_names = request.POST.getlist('surg_name[]')
        surg_dates = request.POST.getlist('surg_date[]')
        for i in range(len(surg_names)):
            if surg_names[i].strip():
                SurgicalHistory.objects.create(
                    pet=pet,
                    surgery_name=surg_names[i],
                    date_performed=surg_dates[i] if i < len(surg_dates) else ''
                )

        # Diagnostic Imaging
        DiagnosticImaging.objects.filter(pet=pet).delete()
        img_types = request.POST.getlist('img_type[]')
        img_dates = request.POST.getlist('img_date[]')
        for i in range(len(img_types)):
            if img_types[i].strip():
                DiagnosticImaging.objects.create(
                    pet=pet,
                    imaging_type=img_types[i],
                    date_performed=img_dates[i] if i < len(img_dates) else ''
                )

        # Vet File Uploads (additive — NOT delete-and-recreate)
        for category in ['blood_work', 'diagnostic_imaging']:
            files = request.FILES.getlist(f'vet_files_{category}')
            for f in files:
                VetUpload.objects.create(
                    pet=pet,
                    category=category,
                    file=f,
                    original_filename=f.name,
                )

        messages.success(request, 'Clinical history saved successfully.')
        return redirect('case_detail', pk=pet.pk)

    # GET - load existing data
    clinical = getattr(pet, 'clinical_history', None)
    try:
        clinical = pet.clinical_history
    except ClinicalHistory.DoesNotExist:
        clinical = None

    context = {
        'pet': pet,
        'clinical': clinical,
        'conditions': clinical.conditions.all() if clinical else [],
        'medications': pet.long_term_medications.all(),
        'surgeries': pet.surgical_history.all(),
        'imaging': pet.diagnostic_imaging.all(),
        'blood_work_uploads': pet.vet_uploads.filter(category='blood_work'),
        'imaging_uploads': pet.vet_uploads.filter(category='diagnostic_imaging'),
    }
    return render(request, 'intake_form/vet_form.html', context)


@require_POST
def delete_vet_upload(request, upload_id):
    """Delete an individual vet upload file"""
    upload = get_object_or_404(VetUpload, pk=upload_id)
    pet_pk = upload.pet.pk
    upload.delete()
    messages.success(request, 'File removed successfully.')
    return redirect('vet_form', pk=pet_pk)
