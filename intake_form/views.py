from django.shortcuts import render, redirect
from django.contrib import messages
from .models import (
    PetParent, Pet, HouseholdDetails, FeedingBehavior, 
    FoodPreferences, CommercialDietHistory, MedicalHistory,
    VaccinationStatus, PrimaryVetInfo, ConsentForm,
    HomemadeTreatHistory, Supplement
)

def intake_form_view(request):
    """Display and process the intake form"""
    
    if request.method == 'POST':
        # Pet Parent data
        parent_name = request.POST.get('parent_name')
        parent_email = request.POST.get('parent_email')
        parent_phone = request.POST.get('parent_phone')
        parent_location = request.POST.get('parent_location', '')
        
        # Pet data
        pet_name = request.POST.get('pet_name')
        pet_age = request.POST.get('pet_age')
        pet_species = request.POST.get('pet_species')
        pet_breed = request.POST.get('pet_breed')
        pet_colour = request.POST.get('pet_colour', '')
        pet_sex = request.POST.get('pet_sex')
        pet_neutered = request.POST.get('pet_neutered') == 'yes'
        pet_weight = request.POST.get('pet_weight')
        pet_body_condition = request.POST.get('pet_body_condition')
        pet_consultation_goals = request.POST.get('pet_consultation_goals')
        
        # Create Pet Parent
        pet_parent = PetParent.objects.create(
            name=parent_name,
            email=parent_email,
            phone=parent_phone,
            location_primary_vet=parent_location
        )
        
        # Create Pet
        pet = Pet.objects.create(
            owner=pet_parent,
            name=pet_name,
            dob_age=pet_age,
            species=pet_species,
            breed=pet_breed,
            colour=pet_colour,
            sex=pet_sex,
            neutered=pet_neutered,
            current_weight_kg=pet_weight,
            body_condition=pet_body_condition,
            consultation_goals=pet_consultation_goals
        )
        
        # Household Details
        household_avoid = request.POST.get('household_avoid_ingredients', '')
        household_arrange = request.POST.get('household_arrange_food', 'no')
        household_who_feeds = request.POST.get('household_who_feeds', 'varies')
        household_feeder_name = request.POST.get('household_feeder_name', '')
        household_other_pets = request.POST.get('household_other_pets') == 'yes'
        household_other_pets_details = request.POST.get('household_other_pets_details', '')
        household_housed = request.POST.get('household_pet_housed', 'indoors')
        
        HouseholdDetails.objects.create(
            pet=pet,
            food_ingredients_to_avoid=household_avoid,
            can_arrange_special_food=household_arrange,
            who_feeds=household_who_feeds,
            feeder_name=household_feeder_name,
            other_pets=household_other_pets,
            other_pets_details=household_other_pets_details,
            pet_housed=household_housed
        )
        
        # Feeding Behavior
        food_availability = request.POST.get('feeding_food_availability', 'always')
        food_times = request.POST.get('feeding_food_times', '')
        meals_per_day = request.POST.get('feeding_meals_per_day')
        
        # Get all checked behaviors
        feeding_behaviors = request.POST.getlist('feeding_behaviors')
        behaviors_str = ','.join(feeding_behaviors)
        
        attitude_changed = request.POST.get('feeding_attitude_changed') == 'yes'
        attitude_details = request.POST.get('feeding_attitude_details', '')
        good_appetite = request.POST.get('feeding_good_appetite', '')
        appetite_recently = request.POST.get('feeding_appetite_recently', '')
        
        # Unmonitored food sources
        unmonitored_access = request.POST.get('feeding_unmonitored') == 'yes'
        unmonitored_sources_list = request.POST.getlist('unmonitored_sources')
        unmonitored_other = request.POST.get('unmonitored_other', '')
        unmonitored_str = ','.join(unmonitored_sources_list)
        if unmonitored_other:
            unmonitored_str += ',' + unmonitored_other
        
        # Bowl types
        # Bowl types
        bowl_types_list = request.POST.getlist('bowl_types')
        bowl_types_str = ','.join(bowl_types_list)
        bowl_type_other = request.POST.get('bowl_type_other', '')
        
        bowl_material_list = request.POST.getlist('bowl_material')
        bowl_material_str = ','.join(bowl_material_list)
        bowl_material_other = request.POST.get('bowl_material_other', '')
        
        water_bowl_types_list = request.POST.getlist('water_bowl_types')
        water_bowl_types_str = ','.join(water_bowl_types_list)
        
        water_bowl_material_list = request.POST.getlist('water_bowl_material')
        water_bowl_material_str = ','.join(water_bowl_material_list)
        water_bowl_material_other = request.POST.get('water_bowl_material_other', '')
        
        # Recent changes (4 weeks)
        recent_4wks = request.POST.get('recent_diet_change_4wks') == 'yes'
        recent_4wks_details = request.POST.get('recent_change_4wks_details', '')
        
        FeedingBehavior.objects.create(
            pet=pet,
            food_availability=food_availability,
            food_availability_times=food_times,
            meals_per_day=int(meals_per_day) if meals_per_day else None,
            eating_behaviors=behaviors_str,
            attitude_changed=attitude_changed,
            attitude_change_details=attitude_details,
            unmonitored_food_access=unmonitored_access,
            unmonitored_sources=unmonitored_str,
            good_appetite=good_appetite,
            appetite_recently=appetite_recently,
            bowl_type=bowl_types_str,
            bowl_type_other=bowl_type_other,
            bowl_material=bowl_material_str,
            bowl_material_other=bowl_material_other,
            water_bowl_type=water_bowl_types_str,
            water_bowl_material=water_bowl_material_str,
            water_bowl_material_other=water_bowl_material_other,
            recent_change_4_weeks=recent_4wks,
            recent_change_4_weeks_details=recent_4wks_details
        )
        
        # Food Preferences
        food_prefs = request.POST.getlist('food_preferences')
        food_prefs_str = ','.join(food_prefs)
        
        treat_prefs = request.POST.getlist('treat_preferences')
        treat_prefs_str = ','.join(treat_prefs)
        
        refuses = request.POST.get('food_refuses') == 'yes'
        refuses_details = request.POST.get('food_refuses_details', '')
        preferred_treats = request.POST.get('preferred_treats_in_plan', '')
        
        # Brands to avoid and food factors
        brands_to_avoid = request.POST.get('brands_to_avoid', '')
        food_factors_list = request.POST.getlist('food_factors')
        food_factors_str = ','.join(food_factors_list)
        
        FoodPreferences.objects.create(
            pet=pet,
            current_food_preferences=food_prefs_str,
            current_treat_preferences=treat_prefs_str,
            refuses_food=refuses,
            refused_food_details=refuses_details,
            preferred_treats_in_plan=preferred_treats,
            food_brands_to_avoid=brands_to_avoid,
            important_food_factors=food_factors_str
        )
        
        # Commercial Diet History (Dynamic - multiple rows)
        diet_types = request.POST.getlist('diet_type[]')
        diet_brands = request.POST.getlist('diet_brand[]')
        diet_products = request.POST.getlist('diet_product[]')
        diet_amounts = request.POST.getlist('diet_amount[]')
        diet_meals = request.POST.getlist('diet_meals[]')
        diet_since = request.POST.getlist('diet_since[]')
        
        # Create a diet entry for each row
        for i in range(len(diet_types)):
            if diet_types[i] and diet_brands[i]:  # Only save if type and brand filled
                CommercialDietHistory.objects.create(
                    pet=pet,
                    diet_type=diet_types[i],
                    brand=diet_brands[i],
                    product_details=diet_products[i] if i < len(diet_products) else '',
                    amount_per_day=diet_amounts[i] if i < len(diet_amounts) else '',
                    meals_per_day=int(diet_meals[i]) if i < len(diet_meals) and diet_meals[i] else 1,
                    fed_since=diet_since[i] if i < len(diet_since) else ''
                )
        # Medical History
        weight_change = request.POST.get('medical_weight_change') == 'yes'
        weight_type = request.POST.get('medical_weight_type', '')
        weight_amount = request.POST.get('medical_weight_amount')
        weight_period = request.POST.get('medical_weight_period', '')
        
        symptoms = request.POST.getlist('medical_symptoms')
        
        vomiting = request.POST.get('medical_vomiting') == 'yes'
        vomit_per_day = request.POST.get('medical_vomit_per_day')
        vomit_colour = request.POST.get('medical_vomit_colour', '')
        vomit_since = request.POST.get('medical_vomit_since', '')
        
        urination_changed = request.POST.get('medical_urination_changed') == 'yes'
        urination_direction = request.POST.get('medical_urination_direction', '')
        urine_colour = request.POST.get('medical_urine_colour', '')
        
        drinking_changed = request.POST.get('medical_drinking_changed') == 'yes'
        drinking_direction = request.POST.get('medical_drinking_direction', '')
        
        stool_changed = request.POST.get('medical_stool_changed') == 'yes'
        stool_colour = request.POST.get('medical_stool_colour', '')
        poops_per_day = request.POST.get('medical_poops_per_day')
        stool_types = request.POST.getlist('medical_stool_types')
        stool_types_str = ','.join(stool_types)
        
        MedicalHistory.objects.create(
            pet=pet,
            weight_change=weight_change,
            weight_change_type=weight_type,
            weight_change_amount_kg=float(weight_amount) if weight_amount else None,
            weight_change_period=weight_period,
            difficulty_chewing='difficulty_chewing' in symptoms,
            difficulty_swallowing='difficulty_swallowing' in symptoms,
            excessive_salivation='excessive_salivation' in symptoms,
            vomiting_per_day=int(vomit_per_day) if vomit_per_day else None,
            vomiting_colour=vomit_colour,
            vomiting_since=vomit_since,
            urination_changed=urination_changed,
            urination_direction=urination_direction,
            urine_colour=urine_colour,
            drinking_changed=drinking_changed,
            drinking_direction=drinking_direction,
            stool_quality_changed=stool_changed,
            stool_colour=stool_colour,
            poops_per_day=int(poops_per_day) if poops_per_day else None,
            stool_types=stool_types_str
        )
        
        # Vaccination Status
        vacc_yearly = request.POST.get('vacc_yearly') == 'yes'
        vacc_deworming = request.POST.get('vacc_deworming') == 'yes'
        vacc_topical = request.POST.get('vacc_topical_tick', 'no')
        vacc_oral = request.POST.get('vacc_oral_tick', 'no')
        
        VaccinationStatus.objects.create(
            pet=pet,
            yearly_vaccinations=vacc_yearly,
            deworming=vacc_deworming,
            topical_tick_flea=vacc_topical,
            oral_tick_flea=vacc_oral
        )
        
        # Primary Vet Info
        vet_name = request.POST.get('vet_name')
        vet_practice = request.POST.get('vet_practice')
        vet_phone = request.POST.get('vet_phone')
        vet_email = request.POST.get('vet_email')
        
        PrimaryVetInfo.objects.create(
            pet=pet,
            vet_name=vet_name,
            practice_name_location=vet_practice,
            clinic_phone=vet_phone,
            email=vet_email
        )
        
        # Consent Form
        consent_agreed = request.POST.get('consent_agreed') == 'yes'
        consent_name = request.POST.get('consent_name')
        
        ConsentForm.objects.create(
            pet_parent=pet_parent,
            agreed=consent_agreed
        )
        # Homemade Treats
        treat_ingredients = request.POST.getlist('treat_ingredient[]')
        treat_preparations = request.POST.getlist('treat_preparation[]')
        treat_quantities = request.POST.getlist('treat_quantity[]')
        treat_since_list = request.POST.getlist('treat_since[]')
        
        for i in range(len(treat_ingredients)):
            if treat_ingredients[i]:
                HomemadeTreatHistory.objects.create(
                    pet=pet,
                    treat_type_form='homemade',
                    ingredient=treat_ingredients[i],
                    preparation_method=treat_preparations[i] if i < len(treat_preparations) else '',
                    quantity_per_day=treat_quantities[i] if i < len(treat_quantities) else '',
                    fed_since=treat_since_list[i] if i < len(treat_since_list) else ''
                )
        
        # Supplements
        if request.POST.get('supplements_given') == 'yes':
            supplement_brand = request.POST.get('supplement_brand', '')
            supplement_form = request.POST.get('supplement_form', '')
            supplement_amount = request.POST.get('supplement_amount', '')
            
            if supplement_brand:
                Supplement.objects.create(
                    pet=pet,
                    brand_name=supplement_brand,
                    form=supplement_form,
                    amount=supplement_amount,
                    per_day=1
                )
        # Success!
        messages.success(request, f'Form submitted successfully! Your Case ID is: {pet_parent.case_id}')
        return redirect('success')
    
    # GET request - show the form
    return render(request, 'intake_form/form.html')


def success_view(request):
    """Success page after form submission"""
    return render(request, 'intake_form/success.html')
