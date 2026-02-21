import json
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from intake_form.models import Pet, PetParent

from .forms import (
    AttachmentForm,
    InventoryItemForm,
    InventoryTransactionForm,
    MedicalNoteForm,
    MemoForm,
    NutritionRecordForm,
    PetEditForm,
    PetParentEditForm,
    PetPortalMetaForm,
    PrescriptionForm,
    ReminderForm,
    VitalsExamForm,
)
from .models import (
    Attachment,
    InventoryItem,
    InventoryTransaction,
    MedicalNote,
    Memo,
    NutritionRecord,
    PetPortalMeta,
    Prescription,
    Reminder,
    VitalsExam,
)
from .permissions import portal_required
from .services import log_audit

User = get_user_model()

TABS = [
    "overview",
    "exams",
    "medical_notes",
    "memo",
    "prescription",
    "attach_files",
    "reminders",
    "emr_export",
]
TAB_LABELS = {
    "overview": "Overview",
    "exams": "Exams",
    "medical_notes": "Medical Notes",
    "memo": "Memo",
    "prescription": "Prescription",
    "attach_files": "Attach Files",
    "reminders": "Reminders",
    "emr_export": "EMR Export",
}


def _flat_form_errors(form):
    return {
        field: [err["message"] for err in errs]
        for field, errs in form.errors.get_json_data().items()
    }


def _redirect_inventory_with_anchor(request):
    base = request.META.get("HTTP_REFERER", reverse("pet_admin_portal:clinic_inventory"))
    anchor = (request.POST.get("return_anchor") or "").strip().lstrip("#")
    if not anchor:
        return redirect(base)
    base_no_fragment = base.split("#", 1)[0]
    return redirect(f"{base_no_fragment}#{anchor}")


def _append_query_params(url, params):
    parts = urlsplit(url)
    current = dict(parse_qsl(parts.query, keep_blank_values=True))
    current.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(current), parts.fragment))


def _remove_query_params(url, keys):
    parts = urlsplit(url)
    current = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key in keys:
        current.pop(key, None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(current), parts.fragment))


def _portal_meta_for_pet(pet):
    meta, _ = PetPortalMeta.objects.get_or_create(pet=pet)
    return meta


def _safe_pet_choice(parent, pet_id=None):
    pets = parent.pets.all().order_by("name")
    if not pets.exists():
        return None, pets
    if pet_id:
        pet = get_object_or_404(pets, pk=pet_id)
    else:
        pet = pets.first()
    return pet, pets


def _header_context(parent, pet):
    pets_qs = parent.pets.all()
    total_pets = pets_qs.count()
    statuses = PetPortalMeta.objects.filter(pet__owner=parent).values("status").annotate(c=Count("id"))
    status_map = {row["status"]: row["c"] for row in statuses}

    selected_meta = _portal_meta_for_pet(pet) if pet else None

    return {
        "parent": parent,
        "selected_pet": pet,
        "selected_pet_meta": selected_meta,
        "pet_count": total_pets,
        "status_counts": {
            "active": status_map.get(PetPortalMeta.STATUS_ALIVE, 0),
            "inactive": status_map.get(PetPortalMeta.STATUS_INACTIVE, 0),
            "deceased": status_map.get(PetPortalMeta.STATUS_DECEASED, 0),
        },
    }


def _tab_context(tab, parent, pet):
    if pet is None:
        return {"tab": tab, "parent": parent, "pet": None}
    base = {
        "tab": tab,
        "parent": parent,
        "pet": pet,
        "vitals_form": VitalsExamForm(),
        "nutrition_form": NutritionRecordForm(),
        "note_form": MedicalNoteForm(),
        "memo_form": MemoForm(),
        "prescription_form": PrescriptionForm(),
        "attachment_form": AttachmentForm(),
        "reminder_form": ReminderForm(),
    }

    vitals = VitalsExam.objects.filter(pet_parent=parent, pet=pet).order_by("exam_at")
    nutrition = NutritionRecord.objects.filter(pet_parent=parent, pet=pet).order_by("measured_at")
    notes = MedicalNote.objects.filter(pet_parent=parent, pet=pet)
    memos = Memo.objects.filter(pet_parent=parent).prefetch_related("assigned_to")
    prescriptions = Prescription.objects.filter(pet_parent=parent, pet=pet)
    attachments = Attachment.objects.filter(pet_parent=parent, pet=pet)
    reminders = Reminder.objects.filter(pet_parent=parent, pet=pet)

    latest_vitals = vitals.last()
    latest_nutrition = nutrition.last()

    upcoming_reminders = reminders.filter(is_completed=False, due_date__gte=timezone.localdate()).order_by("due_date")[:5]
    active_prescriptions = prescriptions.filter(Q(end_date__isnull=True) | Q(end_date__gte=timezone.localdate()))[:5]

    base.update(
        {
            "latest_vitals": latest_vitals,
            "latest_nutrition": latest_nutrition,
            "upcoming_reminders": upcoming_reminders,
            "active_prescriptions": active_prescriptions,
            "recent_visits": vitals.order_by("-exam_at")[:10],
            "vitals": vitals.order_by("-exam_at"),
            "nutrition_records": nutrition.order_by("-measured_at"),
            "medical_notes": notes,
            "memos": memos,
            "prescriptions": prescriptions,
            "attachments": attachments,
            "reminders": reminders,
            "staff_users": User.objects.filter(Q(is_staff=True) | Q(groups__name__in=["Admin", "Vet", "Staff"]))
            .distinct()
            .order_by("email", "username"),
        }
    )

    base["weight_points"] = [
        {"x": v.exam_at.isoformat(), "y": float(v.weight_kg)} for v in vitals if v.weight_kg is not None
    ]
    base["temp_points"] = [
        {"x": v.exam_at.isoformat(), "y": float(v.temperature_c)} for v in vitals if v.temperature_c is not None
    ]
    base["heart_points"] = [
        {"x": v.exam_at.isoformat(), "y": v.heart_rate_bpm} for v in vitals if v.heart_rate_bpm is not None
    ]
    base["nutrition_points"] = {
        "bcs": [{"x": n.measured_at.isoformat(), "y": float(n.bcs)} for n in nutrition if n.bcs is not None],
        "mcs": [{"x": n.measured_at.isoformat(), "y": float(n.mcs)} for n in nutrition if n.mcs is not None],
        "wtr": [{"x": n.measured_at.isoformat(), "y": float(n.wtr)} for n in nutrition if n.wtr is not None],
        "body_fat_percent": [
            {"x": n.measured_at.isoformat(), "y": float(n.body_fat_percent)}
            for n in nutrition
            if n.body_fat_percent is not None
        ],
        "bfi": [{"x": n.measured_at.isoformat(), "y": float(n.bfi)} for n in nutrition if n.bfi is not None],
    }
    base["weight_points_json"] = json.dumps(base["weight_points"], cls=DjangoJSONEncoder)
    base["temp_points_json"] = json.dumps(base["temp_points"], cls=DjangoJSONEncoder)
    base["heart_points_json"] = json.dumps(base["heart_points"], cls=DjangoJSONEncoder)
    base["nutrition_points_json"] = {
        "bcs": json.dumps(base["nutrition_points"]["bcs"], cls=DjangoJSONEncoder),
        "mcs": json.dumps(base["nutrition_points"]["mcs"], cls=DjangoJSONEncoder),
        "wtr": json.dumps(base["nutrition_points"]["wtr"], cls=DjangoJSONEncoder),
        "body_fat_percent": json.dumps(base["nutrition_points"]["body_fat_percent"], cls=DjangoJSONEncoder),
        "bfi": json.dumps(base["nutrition_points"]["bfi"], cls=DjangoJSONEncoder),
    }
    return base


@portal_required
def parent_list(request):
    q = request.GET.get("q", "").strip()
    parents = PetParent.objects.annotate(pet_count=Count("pets", distinct=True)).order_by("-created_at")
    if q:
        parents = parents.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q) | Q(case_id__icontains=q))
    return render(request, "pet_admin_portal/parent_list.html", {"parents": parents, "q": q})


@portal_required
def clinic_inventory(request):
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    tx_type = request.GET.get("tx_type", "").strip()
    tx_from = request.GET.get("tx_from", "").strip()
    tx_to = request.GET.get("tx_to", "").strip()

    sort_map = {
        "name": "name",
        "category": "category",
        "stock": "stock_quantity",
        "updated": "updated_at",
    }
    sort_field = sort_map.get(sort, "name")
    order_by = f"-{sort_field}" if direction == "desc" else sort_field

    items = InventoryItem.objects.all()
    if q:
        items = items.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(category__icontains=q))
    items = items.order_by(order_by)

    transactions = InventoryTransaction.objects.select_related("inventory_item", "created_by").all()
    if tx_type in {InventoryTransaction.TYPE_PURCHASE, InventoryTransaction.TYPE_CONSUMPTION, InventoryTransaction.TYPE_ADJUSTMENT}:
        transactions = transactions.filter(transaction_type=tx_type)

    if tx_from:
        try:
            from_dt = datetime.strptime(tx_from, "%Y-%m-%d").date()
            transactions = transactions.filter(created_at__date__gte=from_dt)
        except ValueError:
            tx_from = ""
    if tx_to:
        try:
            to_dt = datetime.strptime(tx_to, "%Y-%m-%d").date()
            transactions = transactions.filter(created_at__date__lte=to_dt)
        except ValueError:
            tx_to = ""

    total_items = InventoryItem.objects.count()
    low_stock_items = InventoryItem.objects.filter(stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold"))
    out_of_stock_items = InventoryItem.objects.filter(stock_quantity__lte=0)
    tx_today_count = InventoryTransaction.objects.filter(created_at__date=timezone.localdate()).count()
    recent_items = InventoryItem.objects.order_by("-created_at")[:5]

    stock_chart_items = InventoryItem.objects.order_by("-stock_quantity", "name")[:12]
    stock_levels_chart = {
        "labels": [item.name for item in stock_chart_items],
        "values": [float(item.stock_quantity) for item in stock_chart_items],
    }

    trend_start = timezone.localdate() - timedelta(days=9)
    trend_rows = (
        InventoryTransaction.objects.filter(created_at__date__gte=trend_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            purchases=Coalesce(
                Sum("quantity", filter=Q(transaction_type=InventoryTransaction.TYPE_PURCHASE)),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
            consumption=Coalesce(
                Sum("quantity", filter=Q(transaction_type=InventoryTransaction.TYPE_CONSUMPTION)),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
            adjustments=Coalesce(
                Sum("quantity", filter=Q(transaction_type=InventoryTransaction.TYPE_ADJUSTMENT)),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
        )
        .order_by("day")
    )
    trend_map = {row["day"]: row for row in trend_rows}
    tx_trend_chart = {"labels": [], "purchases": [], "consumption": [], "adjustments": []}
    for i in range(10):
        day = trend_start + timedelta(days=i)
        row = trend_map.get(day)
        tx_trend_chart["labels"].append(day.strftime("%d %b"))
        tx_trend_chart["purchases"].append(float(row["purchases"]) if row else 0.0)
        tx_trend_chart["consumption"].append(float(row["consumption"]) if row else 0.0)
        tx_trend_chart["adjustments"].append(float(row["adjustments"]) if row else 0.0)

    top_consumed_rows = (
        InventoryItem.objects.annotate(
            consumed=Coalesce(
                Sum("transactions__quantity", filter=Q(transactions__transaction_type=InventoryTransaction.TYPE_CONSUMPTION)),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
            )
        )
        .filter(consumed__gt=0)
        .order_by("-consumed", "name")[:8]
    )
    top_consumed_chart = {
        "labels": [row.name for row in top_consumed_rows],
        "values": [float(row.consumed) for row in top_consumed_rows],
    }

    context = {
        "inventory_item_form": InventoryItemForm(),
        "inventory_tx_form": InventoryTransactionForm(),
        "inventory_items": items,
        "inventory_transactions": transactions[:200],
        "total_items": total_items,
        "low_stock_count": low_stock_items.count(),
        "out_of_stock_count": out_of_stock_items.count(),
        "tx_today_count": tx_today_count,
        "recent_items": recent_items,
        "q": q,
        "sort": sort,
        "direction": direction,
        "tx_type": tx_type,
        "tx_from": tx_from,
        "tx_to": tx_to,
        "stock_levels_chart_json": json.dumps(stock_levels_chart, cls=DjangoJSONEncoder),
        "tx_trend_chart_json": json.dumps(tx_trend_chart, cls=DjangoJSONEncoder),
        "top_consumed_chart_json": json.dumps(top_consumed_chart, cls=DjangoJSONEncoder),
    }
    return render(request, "pet_admin_portal/inventory_hub.html", context)


@portal_required
def profile_hub(request, parent_id):
    parent = get_object_or_404(PetParent.objects.prefetch_related("pets"), pk=parent_id)
    pet_id = request.GET.get("pet")
    tab = request.GET.get("tab", "overview")
    if tab not in TABS:
        tab = "overview"

    selected_pet, pets = _safe_pet_choice(parent, pet_id)

    context = {
        "tabs": TABS,
        "tab_labels": TAB_LABELS,
        "active_tab": tab,
        "pets": pets,
        "attachment_uploaded": request.GET.get("attachment_uploaded") == "1",
    }
    context.update(_header_context(parent, selected_pet))
    context.update(_tab_context(tab, parent, selected_pet))
    return render(request, "pet_admin_portal/profile_hub.html", context)


@portal_required
@require_GET
def tab_content(request, parent_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet, _ = _safe_pet_choice(parent, request.GET.get("pet"))
    tab = request.GET.get("tab", "overview")
    if tab not in TABS:
        return HttpResponse(status=400)
    if pet is None:
        return HttpResponse('<section class="card"><p>No pet records are linked to this parent yet.</p></section>')
    context = _tab_context(tab, parent, pet)
    context["attachment_uploaded"] = request.GET.get("attachment_uploaded") == "1"
    return render(request, f"pet_admin_portal/tabs/{tab}.html", context)


@portal_required
@require_POST
def edit_parent(request, parent_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    form = PetParentEditForm(request.POST, instance=parent)
    if form.is_valid():
        old = {"name": parent.name, "phone": parent.phone, "email": parent.email}
        parent = form.save()
        log_audit(request.user, "update", parent, {"before": old, "after": form.cleaned_data})
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "errors": _flat_form_errors(form)}, status=400)


@portal_required
@require_POST
def edit_pet(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    meta = _portal_meta_for_pet(pet)

    pet_form = PetEditForm(request.POST, instance=pet, prefix="pet")
    meta_form = PetPortalMetaForm(request.POST, request.FILES, instance=meta, prefix="meta")

    if pet_form.is_valid() and meta_form.is_valid():
        pet_form.save()
        meta_form.save()
        log_audit(request.user, "update", pet, {"pet": pet_form.cleaned_data, "meta": meta_form.cleaned_data})
        return JsonResponse({"ok": True})

    errors = {"pet": _flat_form_errors(pet_form), "meta": _flat_form_errors(meta_form)}
    return JsonResponse({"ok": False, "errors": errors}, status=400)


def _parse_datetime_local(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@portal_required
@require_POST
def create_vitals(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = VitalsExamForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.recorded_by = request.user
        obj.save()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Vitals exam saved.")
    else:
        messages.error(request, "Unable to save vitals exam.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=exams")


@portal_required
@require_POST
def create_nutrition(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = NutritionRecordForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.recorded_by = request.user
        obj.save()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Nutrition record saved.")
    else:
        messages.error(request, "Unable to save nutrition record.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=exams")


@portal_required
@require_POST
def create_medical_note(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = MedicalNoteForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.created_by = request.user
        obj.save()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Medical note saved.")
    else:
        messages.error(request, "Unable to save medical note.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=medical_notes")


@portal_required
@require_POST
def create_memo(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = MemoForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.created_by = request.user
        obj.save()
        form.save_m2m()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Memo saved.")
    else:
        messages.error(request, "Unable to save memo.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=memo")


@portal_required
@require_POST
def create_prescription(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = PrescriptionForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.prescribing_vet = request.user
        obj.save()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Prescription saved.")
    else:
        messages.error(request, "Unable to save prescription.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=prescription")


@portal_required
@require_POST
def create_attachment(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.uploaded_by = request.user
        obj.save()
        log_audit(request.user, "create", obj, {"title": obj.title, "file": obj.file.name})
        return redirect(
            f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}"
            f"?pet={pet.id}&tab=attach_files&attachment_uploaded=1"
        )
    else:
        messages.error(request, "Unable to upload file.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=attach_files")


@portal_required
@require_POST
def create_reminder(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)
    form = ReminderForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.pet_parent = parent
        obj.pet = pet
        obj.save()
        log_audit(request.user, "create", obj, form.cleaned_data)
        messages.success(request, "Reminder created.")
    else:
        messages.error(request, "Unable to create reminder.")
    return redirect(f"{reverse('pet_admin_portal:profile_hub', args=[parent.id])}?pet={pet.id}&tab=reminders")


@portal_required
@require_POST
def create_inventory_item(request):
    form = InventoryItemForm(request.POST)
    if form.is_valid():
        item = form.save()
        log_audit(request.user, "create", item, form.cleaned_data)
        messages.success(request, "Inventory item created.")
    else:
        messages.error(request, "Unable to create inventory item.")
    return _redirect_inventory_with_anchor(request)


@portal_required
@require_POST
def create_inventory_tx(request):
    form = InventoryTransactionForm(request.POST)
    if form.is_valid():
        tx = form.save(commit=False)
        tx.created_by = request.user
        tx.save()

        item = tx.inventory_item
        if tx.transaction_type == InventoryTransaction.TYPE_PURCHASE:
            item.stock_quantity += tx.quantity
        else:
            item.stock_quantity -= tx.quantity
        item.save(update_fields=["stock_quantity", "updated_at"])
        log_audit(request.user, "create", tx, form.cleaned_data)
        messages.success(request, "Inventory transaction logged.")
    else:
        messages.error(request, "Unable to log inventory transaction.")
    return _redirect_inventory_with_anchor(request)


@portal_required
@require_POST
def update_inventory_item(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    form = InventoryItemForm(request.POST, instance=item)
    if form.is_valid():
        form.save()
        log_audit(request.user, "update", item, form.cleaned_data)
        messages.success(request, "Inventory item updated.")
    else:
        messages.error(request, "Unable to update inventory item.")
    return _redirect_inventory_with_anchor(request)


@portal_required
@require_POST
def soft_delete_record(request, model_name, record_id):
    model_map = {
        "vitals": VitalsExam,
        "nutrition": NutritionRecord,
        "note": MedicalNote,
        "memo": Memo,
        "prescription": Prescription,
        "attachment": Attachment,
        "reminder": Reminder,
        "inventory_item": InventoryItem,
        "inventory_tx": InventoryTransaction,
    }
    model = model_map.get(model_name)
    if model is None:
        return HttpResponse(status=404)
    record = get_object_or_404(model.all_objects, pk=record_id)
    record.soft_delete(user=request.user)
    log_audit(request.user, "soft_delete", record, {})
    messages.success(request, "Record archived.")
    anchor = (request.POST.get("return_anchor") or "").strip().lstrip("#")
    base = request.META.get("HTTP_REFERER", reverse("pet_admin_portal:parent_list"))
    base = _append_query_params(base, {"undo_model": model_name, "undo_id": str(record_id)})
    if anchor:
        base = f"{base.split('#', 1)[0]}#{anchor}"
    return redirect(base)


@portal_required
@require_POST
def restore_record(request, model_name, record_id):
    model_map = {
        "vitals": VitalsExam,
        "nutrition": NutritionRecord,
        "note": MedicalNote,
        "memo": Memo,
        "prescription": Prescription,
        "attachment": Attachment,
        "reminder": Reminder,
        "inventory_item": InventoryItem,
        "inventory_tx": InventoryTransaction,
    }
    model = model_map.get(model_name)
    if model is None:
        return HttpResponse(status=404)
    record = get_object_or_404(model.all_objects, pk=record_id)
    record.restore()
    log_audit(request.user, "restore", record, {})
    messages.success(request, "Record restored.")
    target = request.META.get("HTTP_REFERER", reverse("pet_admin_portal:parent_list"))
    target = _remove_query_params(target, {"undo_model", "undo_id"})
    return redirect(target)


@portal_required
def emr_export_json(request, parent_id, pet_id):
    parent = get_object_or_404(PetParent, pk=parent_id)
    pet = get_object_or_404(Pet, pk=pet_id, owner=parent)

    payload = {
        "parent": {
            "name": parent.name,
            "email": parent.email,
            "phone": parent.phone,
            "case_id": parent.case_id,
        },
        "pet": {
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "age": pet.dob_age,
            "weight": float(pet.current_weight_kg) if pet.current_weight_kg else None,
        },
        "vitals": [
            {
                "exam_at": v.exam_at.isoformat(),
                "weight_kg": float(v.weight_kg) if v.weight_kg is not None else None,
                "temperature_c": float(v.temperature_c) if v.temperature_c is not None else None,
                "heart_rate_bpm": v.heart_rate_bpm,
                "respiratory_rate_bpm": v.respiratory_rate_bpm,
            }
            for v in VitalsExam.objects.filter(pet_parent=parent, pet=pet)[:100]
        ],
        "notes": [
            {
                "created_at": n.created_at.isoformat(),
                "subjective": n.subjective,
                "objective": n.objective,
                "assessment": n.assessment,
                "plan": n.plan,
            }
            for n in MedicalNote.objects.filter(pet_parent=parent, pet=pet)[:100]
        ],
    }

    response = HttpResponse(json.dumps(payload, indent=2), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="emr-{parent.case_id}-{pet.id}.json"'
    return response
