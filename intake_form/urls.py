from django.urls import path
from . import views

urlpatterns = [
    path('', views.intake_form_view, name='intake_form'),
    path('success/', views.success_view, name='success'),
    path('cases/', views.case_list_view, name='case_list'),
    path('cases/<int:pk>/', views.case_detail_view, name='case_detail'),
    path('cases/<int:pk>/pdf/', views.case_pdf_view, name='case_pdf'),
    path('cases/<int:pk>/vet/', views.vet_form_view, name='vet_form'),
    path('vet-upload/<int:upload_id>/delete/', views.delete_vet_upload, name='delete_vet_upload'),
]
