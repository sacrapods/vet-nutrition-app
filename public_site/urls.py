from django.urls import path

from . import views

app_name = "public_site"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("services/", views.services_view, name="services"),
    path("about/", views.about_view, name="about"),
    path("testimonials/", views.testimonials_view, name="testimonials"),
    path("faq/", views.faq_view, name="faq"),
    path("pricing/", views.pricing_view, name="pricing"),
    path("contact/", views.contact_view, name="contact"),
    path("brochure/", views.brochure_entry_view, name="brochure"),
]
