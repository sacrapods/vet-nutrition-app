from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from intake_form.views import brochure_landing_view

urlpatterns = [
    path('', brochure_landing_view, name='root_brochure_landing'),
    path('intake/', include('intake_form.urls')),
    path('appointments/', include('appointments.urls')),
    path('pet-admin-portal/', include(('pet_admin_portal.urls', 'pet_admin_portal'), namespace='pet_admin_portal')),
]

if getattr(settings, 'ENABLE_DJANGO_ADMIN', False):
    urlpatterns.insert(1, path('admin/', admin.site.urls))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
