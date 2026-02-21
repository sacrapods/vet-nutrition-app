from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.messages import get_messages
from django.db import models as db_models
from django.db.models import Count
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.urls import reverse
from django.http import JsonResponse
from datetime import timedelta
import secrets
import json
import re
import logging
from appointments.models import Appointment
from .decorators import (
    ADMIN_GROUP,
    VET_GROUP,
    PET_PARENT_GROUP,
    admin_required,
    pet_parent_required,
    role_required,
    user_in_group,
)
from .forms import PetParentRegistrationForm, PostPaymentActivationForm, EmailAuthenticationForm
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
    SurgicalHistory, DiagnosticImaging, VetUpload, HomemadeDietQuestionnaire,
    IntakeFormDraft, HomemadeQuestionnaireDraft, VetFormDraft, VetFormAccessLink,
    PreConsultSubmission
)

MATRIX_COLUMNS = [
    ('consumed_past', 'Consumed in the past'),
    ('currently_eating', 'Currently eating'),
    ('prefer_use', 'Prefer to use'),
    ('prefer_avoid', 'Prefer to avoid'),
    ('will_try_first_time', 'Will try this first time'),
    ('have_not_tried', 'Have not tried yet'),
]

Q1_PROTEIN_INGREDIENTS = [
    'Chicken', 'Liver', 'Turkey', 'Beef', 'Pork', 'Lamb', 'Goat',
    'Duck', 'Quail', 'Rabbit', 'Venison', 'Cod', 'Salmon', 'Tilapia', 'Tuna',
    'Fish', 'Crab Meat', 'Shrimp', 'Chicken Egg', 'Egg', 'Cheese',
    'Cottage Cheese', 'Soyabean (Tofu)', 'Yoghurt', 'Offal meat Spp:',
]

Q3_INGREDIENTS = [
    'White rice', 'Brown rice', 'Barley', 'Oats (Oatmeal)', 'Bread',
    'Pasta', 'Couscous', 'White Potato', 'Sweet Potato', 'Lentils', 'Millets',
    'Quinoa', 'Mung Bean', 'Tapioca', 'Sorghum', 'Green beans', 'Carrots',
    'Corn', 'Spinach', 'Green peas', 'Chick peas', 'Peanut butter', 'Broccoli',
    'Cream Cheese', 'Cauliflower', 'Zucchini', 'Squash', 'Pumpkin',
    'Chicken skin', 'Chicken fat', 'Pork fat', 'Beef fat', 'Goat/lamb fat',
    'Fish oil', 'Sunflower oil', 'Olive oil', 'Canola oil', 'Linseed oil',
    'Flax seed oil', 'Soyabean oil', 'Coconut oil', 'Rice bran', 'Psyllium',
    'Cellulose',
]

FREE_TEXT_ROWS = [1, 2, 3, 4, 5]
User = get_user_model()

PRECONSULT_FOCUS_CHOICES = [
    ("dry_kibble_only", "Dry Kibble only"),
    ("wet_canned_only", "Wet/canned only"),
    ("combo_dry_wet", "A combination of both commercial dry (kibble) and wet (canned) food"),
    ("combo_wet_homecooked", "A combination of commercial diet (wet) and homecooked food"),
    ("combo_dry_homecooked", "A combination of commercial diet (dry) and homecooked food"),
    ("only_home_cooked", "Only home-cooked food"),
    ("avoid_commercial_diets", "Avoid commercial diets"),
    ("include_commercial_treats", "Include commercial treats"),
    ("avoid_commercial_treats", "Avoid commercial treats"),
    ("include_home_cooked_treats", "Include home cooked treats"),
    ("unsure", "Unsure"),
]

PRECONSULT_TO_DIET_PLAN_MAP = {
    'dry_kibble_only': 'dry_kibble_only',
    'wet_canned_only': 'wet_canned_only',
    'combo_dry_wet': 'combo_dry_wet',
    'combo_wet_homecooked': 'combo_wet_homecooked',
    'combo_dry_homecooked': 'combo_dry_homecooked',
    'only_home_cooked': 'only_homecooked',
    'avoid_commercial_diets': 'avoid_commercial',
    'include_commercial_treats': 'include_commercial_treats',
    'avoid_commercial_treats': 'avoid_commercial_treats',
    'include_home_cooked_treats': 'include_homecooked_treats',
    'unsure': 'unsure',
}

logger = logging.getLogger("intake_form.auth")


def _serialize_post_data(post):
    payload = {}
    for key, values in post.lists():
        if key == "csrfmiddlewaretoken":
            continue
        payload[key] = values if len(values) > 1 else (values[0] if values else "")
    return payload


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _safe_primary_vet(pet):
    try:
        return pet.primary_vet
    except PrimaryVetInfo.DoesNotExist:
        return None


def _send_verification_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_path = reverse("verify_email", kwargs={"uidb64": uidb64, "token": token})
    verify_url = request.build_absolute_uri(verify_path)

    subject = "Verify your Poshtik NutriVet account"
    text_body = render_to_string(
        "registration/verify_email_email.txt",
        {
            "user": user,
            "verify_url": verify_url,
        },
    )
    html_body = render_to_string(
        "registration/verify_email_email.html",
        {
            "user": user,
            "verify_url": verify_url,
        },
    )

    send_mail(
        subject=subject,
        message=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )


def brochure_landing_view(request):
    if request.method == "POST":
        pet_weight = request.POST.get("pet_weight_kg", "").strip()
        focus = request.POST.getlist("consultation_focus")
        PreConsultSubmission.objects.create(
            parent_name=request.POST.get("parent_name", "").strip(),
            parent_email=request.POST.get("parent_email", "").strip(),
            parent_phone=request.POST.get("parent_phone", "").strip(),
            parent_city=request.POST.get("parent_city", "").strip(),
            pet_name=request.POST.get("pet_name", "").strip(),
            pet_species=request.POST.get("pet_species", "dog"),
            pet_breed=request.POST.get("pet_breed", "").strip(),
            pet_age=request.POST.get("pet_age", "").strip(),
            pet_sex=request.POST.get("pet_sex", ""),
            pet_neutered=request.POST.get("pet_neutered") == "yes",
            pet_weight_kg=pet_weight if pet_weight else None,
            consultation_goals=request.POST.get("consultation_goals", "").strip(),
            consultation_focus=",".join(focus),
            additional_notes=request.POST.get("additional_notes", "").strip(),
        )
        messages.success(
            request,
            "Thank you. We received your consult request. Our team will contact you for payment and account activation.",
        )
        return redirect("brochure_landing")

    return render(
        request,
        "intake_form/brochure_landing.html",
        {"focus_choices": PRECONSULT_FOCUS_CHOICES},
    )


def _is_admin(user):
    return user.is_superuser or user_in_group(user, ADMIN_GROUP)


def _is_vet(user):
    return user.is_superuser or user_in_group(user, VET_GROUP)


def _is_pet_parent(user):
    return user.is_superuser or user_in_group(user, PET_PARENT_GROUP)


def _post_login_redirect(user):
    if _is_admin(user):
        return "case_list"
    if _is_vet(user):
        return "vet_cases"
    return "submission_history"


def _pet_for_request_user_or_404(request, pk):
    if _is_admin(request.user):
        return get_object_or_404(Pet.objects.select_related("owner", "owner__user"), pk=pk)
    if _is_pet_parent(request.user):
        return get_object_or_404(
            Pet.objects.select_related("owner", "owner__user"),
            pk=pk,
            owner__user=request.user,
        )
    raise PermissionDenied


def _is_link_expired(link):
    return bool(link.expires_at and link.expires_at < timezone.now())


def _get_or_refresh_vet_access_link(pet, created_by=None, rotate=False):
    link, _ = VetFormAccessLink.objects.get_or_create(
        pet=pet,
        defaults={
            'created_by': created_by,
            'expires_at': timezone.now() + timedelta(days=30),
            'is_active': True,
        },
    )
    if rotate or (not link.is_active) or _is_link_expired(link):
        link.token = secrets.token_urlsafe(32)
        link.is_active = True
        link.expires_at = timezone.now() + timedelta(days=30)
        if created_by:
            link.created_by = created_by
        link.save()
    return link


def _field_slug(value):
    return re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')


def _checkbox_name(prefix, slug, col_key):
    return f'{prefix}_{slug}_{col_key}'


def _matrix_rows(prefix, ingredients, post):
    rows = []
    for ingredient in ingredients:
        slug = _field_slug(ingredient)
        row = {'ingredient': ingredient}
        for col_key, _ in MATRIX_COLUMNS:
            row[col_key] = post.get(_checkbox_name(prefix, slug, col_key)) == 'on'
        rows.append(row)
    return rows


def _table_rows_q2(post):
    rows = []
    for i in FREE_TEXT_ROWS:
        row = {
            'ingredient': post.get(f'q2_ingredient_{i}', '').strip(),
            'consumed_past': post.get(f'q2_{i}_consumed_past') == 'on',
            'currently_eating': post.get(f'q2_{i}_currently_eating') == 'on',
            'prefer_use': post.get(f'q2_{i}_prefer_use') == 'on',
            'prefer_avoid': post.get(f'q2_{i}_prefer_avoid') == 'on',
            'additional_comments': post.get(f'q2_{i}_additional_comments', '').strip(),
        }
        if any([row['ingredient'], row['additional_comments'], row['consumed_past'], row['currently_eating'], row['prefer_use'], row['prefer_avoid']]):
            rows.append(row)
    return rows


def _table_rows_q4(post):
    rows = []
    for i in FREE_TEXT_ROWS:
        row = {
            'ingredient': post.get(f'q4_ingredient_{i}', '').strip(),
            'consumed_past': post.get(f'q4_{i}_consumed_past') == 'on',
            'currently_eating': post.get(f'q4_{i}_currently_eating') == 'on',
            'prefer_use': post.get(f'q4_{i}_prefer_use') == 'on',
            'additional_comments': post.get(f'q4_{i}_additional_comments', '').strip(),
        }
        if any([row['ingredient'], row['additional_comments'], row['consumed_past'], row['currently_eating'], row['prefer_use']]):
            rows.append(row)
    return rows


def _table_rows_q5(post):
    rows = []
    for i in FREE_TEXT_ROWS:
        food = post.get(f'q5_food_{i}', '').strip()
        reason = post.get(f'q5_reason_{i}', '').strip()
        if food or reason:
            rows.append({'food': food, 'reason': reason})
    return rows


def _table_rows_q6(post):
    rows = []
    for i in FREE_TEXT_ROWS:
        food = post.get(f'q6_food_{i}', '').strip()
        amount = post.get(f'q6_amount_{i}', '').strip()
        since_when = post.get(f'q6_since_when_{i}', '').strip()
        if food or amount or since_when:
            rows.append({'food': food, 'amount': amount, 'since_when': since_when})
    return rows


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    form = EmailAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        request.session["last_auth_event"] = "login"
        request.session["last_auth_at"] = timezone.now().isoformat()
        logger.info(
            "login_success user_id=%s username=%s ip=%s ua=%s",
            user.pk,
            user.get_username(),
            _client_ip(request),
            request.META.get("HTTP_USER_AGENT", "")[:250],
        )
        return redirect(_post_login_redirect(user))
    return render(request, "registration/login.html", {"form": form})


@never_cache
@ensure_csrf_cookie
def activate_account_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    form = PostPaymentActivationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        submission = form.get_eligible_submission()
        if not submission:
            form.add_error(None, 'No eligible paid request found for this email and phone.')
        else:
            username = (submission.parent_email or '').strip().lower()
            if not username:
                form.add_error(None, 'No email found on your request. Please contact support.')
                return render(request, 'registration/activate_account.html', {'form': form})

            if User.objects.filter(username=username).exists():
                form.add_error(
                    None,
                    'An account with this email already exists. Please login or reset your password.',
                )
                return render(request, 'registration/activate_account.html', {'form': form})

            user = User.objects.create(
                username=username,
                email=username,
                first_name=(submission.parent_name or '').strip().split(' ')[0][:150],
                is_active=False,
            )
            user.set_password(form.cleaned_data['password1'])
            user.save()

            pet_parent_group, _ = Group.objects.get_or_create(name=PET_PARENT_GROUP)
            user.groups.add(pet_parent_group)

            submission.linked_user = user
            submission.activated_at = timezone.now()
            submission.save(update_fields=['linked_user', 'activated_at'])

            logger.info(
                "account_activated user_id=%s username=%s source_submission_id=%s ip=%s",
                user.pk,
                user.get_username(),
                submission.pk,
                _client_ip(request),
            )
            try:
                _send_verification_email(request, user)
            except Exception:
                logger.exception("verification_email_send_failed user_id=%s", user.pk)
                messages.error(
                    request,
                    "Account created, but verification email could not be sent. Please contact support.",
                )
                return redirect("activate_account")

            messages.success(request, 'Account created. Please verify your email to continue.')
            return redirect('activation_email_sent')

    return render(request, 'registration/activate_account.html', {'form': form})


def activation_email_sent_view(request):
    return render(request, "registration/activation_email_sent.html")


def verify_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
            logger.info(
                "email_verified user_id=%s username=%s ip=%s",
                user.pk,
                user.get_username(),
                _client_ip(request),
            )
        messages.success(request, "Email verified successfully. Please login.")
        return redirect("login")

    messages.error(request, "Verification link is invalid or expired. Please request a new activation.")
    return redirect("activate_account")


def logout_view(request):
    if request.user.is_authenticated:
        logger.info(
            "logout user_id=%s username=%s ip=%s",
            request.user.pk,
            request.user.get_username(),
            _client_ip(request),
        )
    logout(request)
    return redirect("login")


def register_view(request):
    if not getattr(settings, "ALLOW_SELF_REGISTRATION", False):
        messages.info(request, "Self-registration is currently disabled. Please complete pre-consult and payment first.")
        return redirect("brochure_landing")

    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    form = PetParentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        pet_parent_group, _ = Group.objects.get_or_create(name=PET_PARENT_GROUP)
        user.groups.add(pet_parent_group)
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("submission_history")
    return render(request, "registration/register.html", {"form": form})


@pet_parent_required
def intake_form_view(request):
    """Display and process the intake form"""

    if request.method == 'POST':
        if request.POST.get('action') == 'autosave':
            IntakeFormDraft.objects.update_or_create(
                user=request.user,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            return JsonResponse({'ok': True, 'saved_at': timezone.now().isoformat()})

        if request.POST.get('action') == 'save_draft':
            IntakeFormDraft.objects.update_or_create(
                user=request.user,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            messages.success(request, 'Intake form draft saved.')
            return redirect('intake_form')

        # ── Pet Parent ──
        pet_parent = PetParent.objects.create(
            user=request.user,
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

        request.session['latest_case_id'] = pet_parent.case_id
        IntakeFormDraft.objects.filter(user=request.user).delete()
        return redirect('success')

    # GET request - show the form
    intake_draft = IntakeFormDraft.objects.filter(user=request.user).first()
    draft_payload = intake_draft.payload if intake_draft else {}
    prefill_payload = {}
    submission = getattr(request.user, 'preconsult_submission', None)
    if submission:
        selected_focus = []
        if submission.consultation_focus:
            for token in [t.strip() for t in submission.consultation_focus.split(',') if t.strip()]:
                mapped = PRECONSULT_TO_DIET_PLAN_MAP.get(token)
                if mapped:
                    selected_focus.append(mapped)
        prefill_payload = {
            'parent_name': submission.parent_name or '',
            'parent_email': submission.parent_email or '',
            'parent_phone': submission.parent_phone or '',
            'parent_location': submission.parent_city or '',
            'pet_name': submission.pet_name or '',
            'pet_species': submission.pet_species or '',
            'pet_breed': submission.pet_breed or '',
            'pet_age': submission.pet_age or '',
            'pet_sex': submission.pet_sex or '',
            'pet_neutered': 'yes' if submission.pet_neutered else 'no',
            'pet_weight': str(submission.pet_weight_kg) if submission.pet_weight_kg is not None else '',
            'pet_consultation_goals': submission.consultation_goals or '',
            'diet_plan_preferences': selected_focus,
            'consent_name': submission.parent_name or '',
        }

    return render(
        request,
        'intake_form/form.html',
        {
            'draft_payload': draft_payload,
            'prefill_payload': prefill_payload,
        },
    )


@pet_parent_required
def homemade_diet_questionnaire_view(request):
    """Standalone homemade diet questionnaire form"""
    if request.method == 'POST':
        if request.POST.get('action') == 'autosave':
            HomemadeQuestionnaireDraft.objects.update_or_create(
                user=request.user,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            return JsonResponse({'ok': True, 'saved_at': timezone.now().isoformat()})

        if request.POST.get('action') == 'save_draft':
            HomemadeQuestionnaireDraft.objects.update_or_create(
                user=request.user,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            messages.success(request, 'Homemade questionnaire draft saved.')
            return redirect('homemade_diet_questionnaire')

        q1_rows = _matrix_rows('q1', Q1_PROTEIN_INGREDIENTS, request.POST)
        q1_novel = {
            'ingredient': request.POST.get('q1_novel_name', 'Novel Protein Spp:').strip() or 'Novel Protein Spp:',
            'consumed_past': request.POST.get('q1_novel_consumed_past') == 'on',
            'currently_eating': request.POST.get('q1_novel_currently_eating') == 'on',
            'prefer_use': request.POST.get('q1_novel_prefer_use') == 'on',
            'prefer_avoid': request.POST.get('q1_novel_prefer_avoid') == 'on',
            'will_try_first_time': request.POST.get('q1_novel_will_try_first_time') == 'on',
            'have_not_tried': request.POST.get('q1_novel_have_not_tried') == 'on',
        }
        q2_rows = _table_rows_q2(request.POST)
        q3_rows = _matrix_rows('q3', Q3_INGREDIENTS, request.POST)
        q4_rows = _table_rows_q4(request.POST)
        q5_rows = _table_rows_q5(request.POST)
        q6_rows = _table_rows_q6(request.POST)

        weight = request.POST.get('current_weight_kg', '').strip()
        meals = request.POST.get('homemade_meals_per_day', '').strip()

        payload = _serialize_post_data(request.POST)

        HomemadeDietQuestionnaire.objects.create(
            submitted_by=request.user,
            owner_name=request.POST.get('owner_name', '').strip() or 'Homemade Diet Questionnaire',
            owner_email=request.POST.get('owner_email', '').strip(),
            owner_phone=request.POST.get('owner_phone', '').strip(),
            pet_name=request.POST.get('pet_name', '').strip() or 'N/A',
            species=request.POST.get('species', 'dog'),
            breed=request.POST.get('breed', '').strip(),
            age=request.POST.get('age', '').strip(),
            current_weight_kg=weight or None,
            current_diet_description=request.POST.get('current_diet_description', '').strip(),
            homemade_meals_per_day=int(meals) if meals else None,
            recipe_ingredients=request.POST.get('recipe_ingredients', '').strip(),
            recipe_preparation=request.POST.get('recipe_preparation', '').strip(),
            supplements_medications=request.POST.get('supplements_medications', '').strip(),
            treat_plan_preferences='',
            homemade_diet_rows='',
            brands_to_avoid_rows='',
            q1_protein_matrix=json.dumps(q1_rows),
            q1_novel_protein=json.dumps(q1_novel),
            q2_other_proteins=json.dumps(q2_rows),
            q3_carb_fat_fibre_matrix=json.dumps(q3_rows),
            q4_other_carb_fat_fibre=json.dumps(q4_rows),
            q5_food_refusal=json.dumps(q5_rows),
            q6_palatable_options=json.dumps(q6_rows),
            questionnaire_payload=json.dumps(payload),
            concerns_or_goals=request.POST.get('concerns_or_goals', '').strip(),
            additional_notes=request.POST.get('additional_notes', '').strip(),
        )
        messages.success(request, 'Homemade diet questionnaire submitted successfully.')
        HomemadeQuestionnaireDraft.objects.filter(user=request.user).delete()
        return redirect('homemade_diet_questionnaire')

    q1_part1 = [{'name': i, 'slug': _field_slug(i)} for i in Q1_PROTEIN_INGREDIENTS[:7]]
    q1_part2 = [{'name': i, 'slug': _field_slug(i)} for i in Q1_PROTEIN_INGREDIENTS[7:]]
    q3_rows = [{'name': i, 'slug': _field_slug(i)} for i in Q3_INGREDIENTS]

    homemade_draft = HomemadeQuestionnaireDraft.objects.filter(user=request.user).first()
    draft_payload = homemade_draft.payload if homemade_draft else {}
    prefill_payload = {}
    submission = getattr(request.user, 'preconsult_submission', None)
    if submission:
        prefill_payload = {
            'owner_name': submission.parent_name or '',
            'owner_email': submission.parent_email or '',
            'owner_phone': submission.parent_phone or '',
            'pet_name': submission.pet_name or '',
            'species': submission.pet_species or 'dog',
            'breed': submission.pet_breed or '',
            'age': submission.pet_age or '',
            'current_weight_kg': str(submission.pet_weight_kg) if submission.pet_weight_kg is not None else '',
            'concerns_or_goals': submission.consultation_goals or '',
            'additional_notes': submission.additional_notes or '',
        }

    return render(request, 'intake_form/homemade_questionnaire.html', {
        'matrix_columns': MATRIX_COLUMNS,
        'q1_part1': q1_part1,
        'q1_part2': q1_part2,
        'q3_rows': q3_rows,
        'free_rows': FREE_TEXT_ROWS,
        'draft_payload': draft_payload,
        'prefill_payload': prefill_payload,
    })

@role_required(ADMIN_GROUP, PET_PARENT_GROUP)
def success_view(request):
    """Success page after form submission"""
    case_id = request.session.pop('latest_case_id', None)

    # Consume stale flash messages so unrelated notices (e.g. registration)
    # do not render inside the case-id block.
    storage = get_messages(request)
    for _ in storage:
        pass

    return render(request, 'intake_form/success.html', {'case_id': case_id})


@pet_parent_required
def submission_history_view(request):
    q = request.GET.get('q', '')
    parents = PetParent.objects.filter(user=request.user).prefetch_related('pets').order_by('-created_at')
    if q:
        parents = parents.filter(
            db_models.Q(name__icontains=q) |
            db_models.Q(case_id__icontains=q) |
            db_models.Q(pets__name__icontains=q)
        ).distinct()
    homemade_submissions = HomemadeDietQuestionnaire.objects.filter(submitted_by=request.user).order_by('-created_at')
    appointments_qs = Appointment.objects.filter(user=request.user).select_related('pet').order_by('-start_at')
    if q:
        appointments_qs = appointments_qs.filter(
            db_models.Q(pet__name__icontains=q)
        )
    else:
        appointments_qs = appointments_qs[:10]
    has_intake_draft = IntakeFormDraft.objects.filter(user=request.user).exists()
    has_homemade_draft = HomemadeQuestionnaireDraft.objects.filter(user=request.user).exists()
    stats = {
        'intake_count': parents.count(),
        'pet_count': Pet.objects.filter(owner__user=request.user).count(),
        'homemade_count': homemade_submissions.count(),
    }
    flash_messages = []
    seen = set()
    for message in get_messages(request):
        key = f"{message.level}:{message.message}"
        if key not in seen:
            flash_messages.append(message)
            seen.add(key)
    return render(
        request,
        'intake_form/submission_history.html',
        {
            'parents': parents,
            'q': q,
            'homemade_submissions': homemade_submissions,
            'appointments': appointments_qs,
            'flash_messages': flash_messages,
            'has_intake_draft': has_intake_draft,
            'has_homemade_draft': has_homemade_draft,
            'stats': stats,
        },
    )


@admin_required
def case_list_view(request):
    """Dashboard: list of all submitted cases"""
    q = request.GET.get('q', '')
    base_parents = PetParent.objects.prefetch_related('pets', 'pets__clinical_history').order_by('-created_at')
    parents = base_parents
    if q:
        parents = parents.filter(
            db_models.Q(name__icontains=q) |
            db_models.Q(case_id__icontains=q) |
            db_models.Q(pets__name__icontains=q)
        ).distinct()
    today = timezone.localdate()
    stats = {
        'total_cases': base_parents.count(),
        'total_pets': Pet.objects.count(),
        'cases_today': PetParent.objects.filter(created_at__date=today).count(),
        'open_vet_forms': Pet.objects.filter(clinical_history__isnull=True).count(),
    }
    return render(request, 'intake_form/case_list.html', {'parents': parents, 'q': q, 'stats': stats})


@role_required(ADMIN_GROUP, PET_PARENT_GROUP)
def case_detail_view(request, pk):
    """Detail view: all info for one pet"""
    pet = _pet_for_request_user_or_404(request, pk)
    vet_public_url = None
    show_vet_share = _is_admin(request.user) or _is_pet_parent(request.user)
    if show_vet_share:
        link = VetFormAccessLink.objects.filter(pet=pet, is_active=True).first()
        if link and not _is_link_expired(link):
            vet_public_url = request.build_absolute_uri(
                reverse('vet_form_public', kwargs={'token': link.token})
            )

    context = {
        'pet': pet,
        'primary_vet': _safe_primary_vet(pet),
        'show_vet_link': _is_admin(request.user) or _is_vet(request.user),
        'back_url_name': 'case_list' if _is_admin(request.user) else 'submission_history',
        'show_vet_share': show_vet_share,
        'vet_public_url': vet_public_url,
    }
    return render(request, 'intake_form/case_detail.html', context)


@role_required(ADMIN_GROUP, PET_PARENT_GROUP)
def case_pdf_view(request, pk):
    """Simple printable/PDF view"""
    pet = _pet_for_request_user_or_404(request, pk)
    context = {
        'pet': pet,
        'primary_vet': _safe_primary_vet(pet),
        'blood_work_uploads': pet.vet_uploads.filter(category='blood_work'),
        'imaging_uploads': pet.vet_uploads.filter(category='diagnostic_imaging'),
    }
    return render(request, 'intake_form/case_pdf.html', context)


@role_required(ADMIN_GROUP, VET_GROUP)
def vet_cases_view(request):
    pets = (
        Pet.objects
        .select_related('owner')
        .prefetch_related('clinical_history')
        .annotate(vet_upload_count=Count('vet_uploads'))
        .order_by('-owner__created_at')
    )
    q = request.GET.get('q', '')
    if q:
        pets = pets.filter(
            db_models.Q(name__icontains=q)
            | db_models.Q(owner__case_id__icontains=q)
            | db_models.Q(owner__name__icontains=q)
        )
    draft_pet_ids = set(
        VetFormDraft.objects.filter(user=request.user).values_list('pet_id', flat=True)
    )
    stats = {
        'total_cases': pets.count(),
        'completed_forms': pets.filter(clinical_history__isnull=False).count(),
        'draft_forms': len(draft_pet_ids),
    }
    return render(
        request,
        'intake_form/vet_case_list.html',
        {'pets': pets, 'q': q, 'draft_pet_ids': draft_pet_ids, 'stats': stats},
    )


@require_POST
@role_required(ADMIN_GROUP, PET_PARENT_GROUP)
def generate_vet_link_view(request, pk):
    pet = _pet_for_request_user_or_404(request, pk)
    rotate = request.POST.get('rotate') == '1'
    _get_or_refresh_vet_access_link(pet=pet, created_by=request.user, rotate=rotate)
    messages.success(request, 'Primary veterinarian link is ready to share.')
    return redirect('case_detail', pk=pet.pk)


def vet_form_public_view(request, token):
    link = get_object_or_404(VetFormAccessLink.objects.select_related('pet', 'pet__owner'), token=token, is_active=True)
    if _is_link_expired(link):
        raise PermissionDenied

    pet = link.pet

    session_draft_key = f'vet_public_draft_{token}'

    if request.method == 'POST':
        if request.POST.get('action') == 'autosave':
            request.session[session_draft_key] = _serialize_post_data(request.POST)
            request.session.modified = True
            return JsonResponse({'ok': True, 'saved_at': timezone.now().isoformat()})

        PrimaryVetInfo.objects.update_or_create(
            pet=pet,
            defaults={
                'vet_name': request.POST.get('vet_name', '').strip(),
                'practice_name_location': request.POST.get('vet_practice', '').strip(),
                'clinic_phone': request.POST.get('vet_phone', '').strip(),
                'email': request.POST.get('vet_email', '').strip(),
            },
        )

        clinical, _ = ClinicalHistory.objects.get_or_create(pet=pet)
        clinical.additional_notes = request.POST.get('additional_notes', '')
        clinical.save()

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

        for category in ['blood_work', 'diagnostic_imaging']:
            files = request.FILES.getlist(f'vet_files_{category}')
            for f in files:
                VetUpload.objects.create(
                    pet=pet,
                    category=category,
                    file=f,
                    original_filename=f.name,
                )

        messages.success(request, 'Clinical history submitted successfully.')
        if session_draft_key in request.session:
            del request.session[session_draft_key]
            request.session.modified = True
        return redirect('vet_form_public', token=token)

    clinical = getattr(pet, 'clinical_history', None)
    try:
        clinical = pet.clinical_history
    except ClinicalHistory.DoesNotExist:
        clinical = None

    context = {
        'pet': pet,
        'primary_vet': _safe_primary_vet(pet),
        'clinical': clinical,
        'conditions': clinical.conditions.all() if clinical else [],
        'medications': pet.long_term_medications.all(),
        'surgeries': pet.surgical_history.all(),
        'imaging': pet.diagnostic_imaging.all(),
        'blood_work_uploads': pet.vet_uploads.filter(category='blood_work'),
        'imaging_uploads': pet.vet_uploads.filter(category='diagnostic_imaging'),
        'draft_payload': request.session.get(session_draft_key, {}),
        'can_delete_uploads': False,
        'cancel_url': '',
        'submit_redirect_url': reverse('vet_form_public', kwargs={'token': token}),
        'show_draft_button': False,
    }
    return render(request, 'intake_form/vet_form.html', context)


@role_required(ADMIN_GROUP, VET_GROUP)
def vet_form_view(request, pk):
    """Clinical history form filled by the referring vet"""
    pet = get_object_or_404(Pet.objects.select_related('owner'), pk=pk)

    if request.method == 'POST':
        if request.POST.get('action') == 'autosave':
            VetFormDraft.objects.update_or_create(
                user=request.user,
                pet=pet,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            return JsonResponse({'ok': True, 'saved_at': timezone.now().isoformat()})

        if request.POST.get('action') == 'save_draft':
            VetFormDraft.objects.update_or_create(
                user=request.user,
                pet=pet,
                defaults={'payload': _serialize_post_data(request.POST)},
            )
            messages.success(request, 'Vet form draft saved.')
            return redirect('vet_form', pk=pet.pk)

        # Clinical History
        PrimaryVetInfo.objects.update_or_create(
            pet=pet,
            defaults={
                'vet_name': request.POST.get('vet_name', '').strip(),
                'practice_name_location': request.POST.get('vet_practice', '').strip(),
                'clinic_phone': request.POST.get('vet_phone', '').strip(),
                'email': request.POST.get('vet_email', '').strip(),
            },
        )

        clinical, _ = ClinicalHistory.objects.get_or_create(pet=pet)
        clinical.additional_notes = request.POST.get('additional_notes', '')
        clinical.submitted_by = request.user
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
                    uploaded_by=request.user,
                )

        messages.success(request, 'Clinical history saved successfully.')
        VetFormDraft.objects.filter(user=request.user, pet=pet).delete()
        return redirect('vet_form', pk=pet.pk)

    # GET - load existing data
    clinical = getattr(pet, 'clinical_history', None)
    try:
        clinical = pet.clinical_history
    except ClinicalHistory.DoesNotExist:
        clinical = None

    vet_draft = VetFormDraft.objects.filter(user=request.user, pet=pet).first()

    context = {
        'pet': pet,
        'primary_vet': _safe_primary_vet(pet),
        'clinical': clinical,
        'conditions': clinical.conditions.all() if clinical else [],
        'medications': pet.long_term_medications.all(),
        'surgeries': pet.surgical_history.all(),
        'imaging': pet.diagnostic_imaging.all(),
        'blood_work_uploads': pet.vet_uploads.filter(category='blood_work'),
        'imaging_uploads': pet.vet_uploads.filter(category='diagnostic_imaging'),
        'draft_payload': vet_draft.payload if vet_draft else {},
        'can_delete_uploads': True,
        'cancel_url': reverse('case_detail', kwargs={'pk': pet.pk}),
        'submit_redirect_url': reverse('vet_form', kwargs={'pk': pet.pk}),
        'show_draft_button': True,
    }
    return render(request, 'intake_form/vet_form.html', context)


@require_POST
@role_required(ADMIN_GROUP, VET_GROUP)
def delete_vet_upload(request, upload_id):
    """Delete an individual vet upload file"""
    upload = get_object_or_404(VetUpload, pk=upload_id)
    pet_pk = upload.pet.pk
    upload.delete()
    messages.success(request, 'File removed successfully.')
    return redirect('vet_form', pk=pet_pk)
