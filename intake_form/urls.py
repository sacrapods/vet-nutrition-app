from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('pre-consult/', views.brochure_landing_view, name='brochure_landing'),
    path('activate-account/', views.activate_account_view, name='activate_account'),
    path('activate-account/sent/', views.activation_email_sent_view, name='activation_email_sent'),
    path('verify-email/<uidb64>/<token>/', views.verify_email_view, name='verify_email'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='intake_form/registration/password_reset_form.html',
            email_template_name='intake_form/registration/password_reset_email.txt',
            html_email_template_name='intake_form/registration/password_reset_email.html',
            subject_template_name='intake_form/registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='intake_form/registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='intake_form/registration/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='intake_form/registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('register/', views.register_view, name='register'),
    path('', views.intake_form_view, name='intake_form'),
    path('success/', views.success_view, name='success'),
    path('my-submissions/', views.submission_history_view, name='submission_history'),
    path('homemade-questionnaire/', views.homemade_diet_questionnaire_view, name='homemade_diet_questionnaire'),
    path('cases/', views.case_list_view, name='case_list'),
    path('vet/cases/', views.vet_cases_view, name='vet_cases'),
    path('cases/<int:pk>/', views.case_detail_view, name='case_detail'),
    path('cases/<int:pk>/vet-link/', views.generate_vet_link_view, name='generate_vet_link'),
    path('cases/<int:pk>/pdf/', views.case_pdf_view, name='case_pdf'),
    path('cases/<int:pk>/vet/', views.vet_form_view, name='vet_form'),
    path('vet/form/<str:token>/', views.vet_form_public_view, name='vet_form_public'),
    path('vet-upload/<int:upload_id>/delete/', views.delete_vet_upload, name='delete_vet_upload'),
]
