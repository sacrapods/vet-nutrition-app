from django.urls import path

from . import views

app_name = "pet_admin_portal"

urlpatterns = [
    path("", views.parent_list, name="parent_list"),
    path("inventory/", views.clinic_inventory, name="clinic_inventory"),
    path("parent/<int:parent_id>/", views.profile_hub, name="profile_hub"),
    path("parent/<int:parent_id>/tab/", views.tab_content, name="tab_content"),

    path("parent/<int:parent_id>/edit/", views.edit_parent, name="edit_parent"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/edit/", views.edit_pet, name="edit_pet"),

    path("parent/<int:parent_id>/pet/<int:pet_id>/vitals/create/", views.create_vitals, name="create_vitals"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/nutrition/create/", views.create_nutrition, name="create_nutrition"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/medical-note/create/", views.create_medical_note, name="create_medical_note"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/memo/create/", views.create_memo, name="create_memo"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/prescription/create/", views.create_prescription, name="create_prescription"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/attachment/create/", views.create_attachment, name="create_attachment"),
    path("parent/<int:parent_id>/pet/<int:pet_id>/reminder/create/", views.create_reminder, name="create_reminder"),
    path("inventory-item/create/", views.create_inventory_item, name="create_inventory_item"),
    path("inventory-tx/create/", views.create_inventory_tx, name="create_inventory_tx"),

    path("record/<str:model_name>/<int:record_id>/archive/", views.soft_delete_record, name="soft_delete_record"),
    path("record/<str:model_name>/<int:record_id>/restore/", views.restore_record, name="restore_record"),

    path("parent/<int:parent_id>/pet/<int:pet_id>/export.json", views.emr_export_json, name="emr_export_json"),
]
