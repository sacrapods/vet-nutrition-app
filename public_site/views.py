from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from intake_form.decorators import ADMIN_GROUP, PET_PARENT_GROUP, VET_GROUP, user_in_group

from .forms import ContactForm


def _role_redirect_for_authenticated_user(user):
    if user.is_superuser or user_in_group(user, ADMIN_GROUP):
        return reverse("case_list")
    if user_in_group(user, VET_GROUP):
        return reverse("vet_cases")
    if user_in_group(user, PET_PARENT_GROUP):
        return reverse("appointments:pet_dashboard")
    return reverse("submission_history")


def _base_context(request, page_title, page_description):
    dashboard_url = None
    if request.user.is_authenticated:
        dashboard_url = _role_redirect_for_authenticated_user(request.user)
    return {
        "page_title": page_title,
        "page_description": page_description,
        "dashboard_url": dashboard_url,
        "nav_links": [
            ("public_site:home", "Home"),
            ("public_site:services", "Services"),
            ("public_site:about", "About"),
            ("public_site:testimonials", "Testimonials"),
            ("public_site:faq", "FAQ"),
            ("public_site:contact", "Contact Us"),
        ],
    }


def home_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))

    context = _base_context(
        request,
        "Poshtik NutriVet | Evidence-Based Veterinary Nutrition Consultations",
        "Scientific veterinary nutrition consultations with personalized plans for dogs and cats.",
    )
    context.update(
        {
            "hero_slides": [
                {
                    "image": "https://images.pexels.com/photos/4587995/pexels-photo-4587995.jpeg?auto=compress&cs=tinysrgb&w=1920",
                    "headline": "Medical-Grade Nutrition Strategy For Your Pet",
                    "sub": "Evidence-based, veterinarian-guided consultations designed for measurable outcomes.",
                },
                {
                    "image": "https://images.pexels.com/photos/406014/pexels-photo-406014.jpeg?auto=compress&cs=tinysrgb&w=1920",
                    "headline": "Precision Plans For Complex Nutrition Needs",
                    "sub": "From weight management to disease-specific support, each plan is personalized and clinically reasoned.",
                },
                {
                    "image": "https://images.pexels.com/photos/7210754/pexels-photo-7210754.jpeg?auto=compress&cs=tinysrgb&w=1920",
                    "headline": "Online Consultations, Clinical Standards",
                    "sub": "Structured onboarding, one-on-one consults, and practical plans your family can follow consistently.",
                },
            ],
            "services": [
                ("Customized Diet Plans", "Individualized plans based on health history, appetite pattern, and clinical goals."),
                ("One-Hour Consultation", "Focused tele-consult with detailed case review and nutrition direction."),
                ("Weight Loss Programs", "Safe fat-loss protocols with progressive monitoring and adjustments."),
                ("Puppy Nutrition", "Growth-stage feeding strategy for skeletal and metabolic development."),
                ("Senior Pet Care", "Age-aware nutrition to support digestion, mobility, and vitality."),
                ("Disease-Specific Diets", "Nutrition support for chronic conditions coordinated with primary veterinarians."),
                ("Follow-Up Sessions", "Review progress and adapt plans to improve adherence and outcomes."),
                ("Monthly Monitoring", "Ongoing checkpoints for body weight, appetite, stool, and energy trends."),
            ],
            "testimonials_preview": [
                {
                    "quote": "Our pet’s GI episodes reduced significantly after the structured nutrition plan.",
                    "name": "A. Mehta, Mumbai",
                },
                {
                    "quote": "The consult was deeply clinical yet practical. We finally had a clear feeding roadmap.",
                    "name": "R. Sharma, Bengaluru",
                },
                {
                    "quote": "Follow-up tracking made the difference. We saw steady progress month by month.",
                    "name": "D. Iyer, Pune",
                },
            ],
        }
    )
    return render(request, "public_site/home.html", context)


def services_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "Veterinary Nutrition Services | Poshtik NutriVet",
        "Explore premium veterinary nutrition programs including customized plans, disease-specific care, and follow-up monitoring.",
    )
    return render(request, "public_site/services.html", context)


def about_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "About Poshtik NutriVet | Scientific Nutrition Care",
        "Learn our mission, medical philosophy, and evidence-based consultation model for pet nutrition.",
    )
    return render(request, "public_site/about.html", context)


def testimonials_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "Client Outcomes | Poshtik NutriVet Testimonials",
        "Read pet parent experiences and outcomes after structured veterinary nutrition consultations.",
    )
    context["stories"] = [
        {
            "pet": "Milo",
            "image": "https://images.pexels.com/photos/58997/pexels-photo-58997.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "text": "Milo’s coat quality and stool consistency improved within weeks of a tailored plan.",
        },
        {
            "pet": "Luna",
            "image": "https://images.pexels.com/photos/1170986/pexels-photo-1170986.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "text": "A measured calorie protocol helped Luna lose weight safely while keeping energy stable.",
        },
        {
            "pet": "Bruno",
            "image": "https://images.pexels.com/photos/2071882/pexels-photo-2071882.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "text": "Disease-specific adjustments were clear and practical. Appetite and comfort improved.",
        },
    ]
    return render(request, "public_site/testimonials.html", context)


def faq_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "FAQ | Online Veterinary Nutrition Consultation",
        "Common questions about consultation workflow, information required, payment process, and follow-up care.",
    )
    context["faqs"] = [
        ("How does the online consultation work?", "You submit onboarding details first, then schedule a one-on-one virtual consultation."),
        ("What information is required?", "Diet history, medical background, lifestyle details, and clinical records where relevant."),
        ("How is payment handled?", "After request review, our team shares payment and account activation instructions."),
        ("Do you provide follow-up care?", "Yes. Follow-up sessions and monitoring are available based on clinical need."),
        ("Is this suitable for all pets?", "Dogs and cats across life stages can benefit, including pets with complex conditions."),
    ]
    return render(request, "public_site/faq.html", context)


def pricing_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "Consultation Pricing Approach | Poshtik NutriVet",
        "Understand our consultation pricing framework and request a tailored quote based on case complexity.",
    )
    return render(request, "public_site/pricing.html", context)


def contact_view(request):
    if request.user.is_authenticated:
        return redirect(_role_redirect_for_authenticated_user(request.user))
    context = _base_context(
        request,
        "Contact Poshtik NutriVet | Request Consultation",
        "Contact our veterinary nutrition team to request consultation and onboarding support.",
    )
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        messages.success(request, "Thank you. Our consultation team will contact you shortly.")
        return redirect("public_site:contact")
    context["form"] = form
    return render(request, "public_site/contact.html", context)


def brochure_entry_view(request):
    return redirect("brochure_landing")
