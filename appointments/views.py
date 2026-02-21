from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from intake_form.decorators import ADMIN_GROUP, PET_PARENT_GROUP, VET_GROUP, user_in_group
from intake_form.models import Pet, PetParent

from .forms import (
    AdminSLAConfigForm,
    AppointmentConfigForm,
    AppointmentBookingForm,
    AppointmentRescheduleForm,
    AppointmentStatusUpdateForm,
    ConsultationNoteForm,
    NoteTemplateForm,
    ProviderCapacityForm,
    StaffAppointmentForm,
)
from .models import (
    AdminAuditLog,
    AdminSLAConfig,
    Appointment,
    AppointmentConfig,
    AppointmentRescheduleRequest,
    BlockedDate,
    BlockedTimeSlot,
    ConsultationNote,
    NoteTemplate,
    ProviderCapacity,
)
from .services.notifications import send_appointment_reminder_email
from .services.booking import (
    acquire_slot_lock,
    create_appointment_from_lock,
    get_daily_slots,
    to_utc_from_ist,
    validate_slot_rules,
)

IST = ZoneInfo('Asia/Kolkata')
User = get_user_model()


def _is_admin_user(user):
    return user.is_superuser or user_in_group(user, ADMIN_GROUP) or user.is_staff


def _is_pet_parent_user(user):
    return user.is_authenticated and (user_in_group(user, PET_PARENT_GROUP) or user.is_superuser)


def _is_vet_user(user):
    return user.is_authenticated and (user_in_group(user, VET_GROUP) or user.is_superuser)


def _pet_parent_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not _is_pet_parent_user(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def _admin_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not _is_admin_user(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def _admin_or_vet_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not (_is_admin_user(request.user) or _is_vet_user(request.user)):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def _admin_shell_context(active_tab):
    return {'active_tab': active_tab}


def _log_admin_audit(entity_type, entity_id, action, changed_by=None, summary='', metadata=None):
    AdminAuditLog.objects.create(
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        action=action,
        changed_by=changed_by if getattr(changed_by, 'is_authenticated', False) else None,
        summary=summary or '',
        metadata=metadata or {},
    )


def _vet_providers_qs():
    return User.objects.filter(
        Q(is_superuser=True) | Q(groups__name=VET_GROUP) | Q(groups__name=ADMIN_GROUP)
    ).distinct().order_by('first_name', 'email', 'username')


def _provider_daily_load(provider, start_local_date, days=7):
    output = []
    for i in range(days):
        day = start_local_date + timedelta(days=i)
        start_dt = datetime.combine(day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
        end_dt = (datetime.combine(day, datetime.min.time()) + timedelta(days=1)).replace(tzinfo=IST).astimezone(dt_timezone.utc)
        count = Appointment.objects.filter(
            assigned_provider=provider,
            start_at__gte=start_dt,
            start_at__lt=end_dt,
        ).exclude(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_RESCHEDULED]).count()
        output.append({'date': day, 'count': count})
    return output


def _provider_limit(provider):
    cap = ProviderCapacity.objects.filter(provider=provider, active=True).first()
    if cap:
        return cap.daily_limit
    return AppointmentConfig.get_solo().daily_appointment_limit


def _provider_load_on_day(provider, local_day, exclude_appointment_id=None):
    start_dt = datetime.combine(local_day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
    end_dt = (datetime.combine(local_day, datetime.min.time()) + timedelta(days=1)).replace(tzinfo=IST).astimezone(dt_timezone.utc)
    qs = Appointment.objects.filter(
        assigned_provider=provider,
        start_at__gte=start_dt,
        start_at__lt=end_dt,
    ).exclude(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_RESCHEDULED])
    if exclude_appointment_id:
        qs = qs.exclude(id=exclude_appointment_id)
    return qs.count()


def _process_reschedule_action(request, redirect_name, action_override=None, request_id_override=None, admin_note_override=None):
    action = action_override or request.POST.get('action')
    if action not in {'approve_reschedule', 'reject_reschedule'}:
        return False

    req = get_object_or_404(
        AppointmentRescheduleRequest.objects.select_related('appointment', 'appointment__pet', 'appointment__user'),
        id=request_id_override or request.POST.get('request_id'),
    )
    if req.status != 'pending':
        messages.info(request, 'This request has already been processed.')
        return True

    if action == 'reject_reschedule':
        req.status = 'rejected'
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.admin_note = (admin_note_override if admin_note_override is not None else request.POST.get('admin_note') or '').strip()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note'])
        _log_admin_audit(
            AdminAuditLog.ENTITY_RESCHEDULE,
            req.id,
            'rejected',
            request.user,
            summary=f'Reschedule rejected for appointment #{req.appointment_id}',
            metadata={'note': req.admin_note},
        )
        messages.success(request, 'Reschedule request rejected.')
        return True

    with transaction.atomic():
        req = req.__class__.objects.select_for_update().select_related('appointment', 'appointment__pet', 'appointment__user').get(pk=req.pk)
        appointment = req.appointment
        if req.status != 'pending':
            messages.info(request, 'This request has already been processed.')
            return True

        try:
            validate_slot_rules(req.requested_start_at, exclude_appointment_id=appointment.id)
        except ValidationError as exc:
            req.status = 'rejected'
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.admin_note = f'Auto-rejected at approval: {exc.messages[0]}'
            req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note'])
            messages.error(request, f'Reschedule request cannot be approved now: {exc.messages[0]}')
            return True

        appointment.status = Appointment.STATUS_RESCHEDULED
        appointment.last_modified_by = request.user
        appointment.save(update_fields=['status', 'last_modified_by', 'updated_at'])

        new_appointment = Appointment.objects.create(
            user=appointment.user,
            pet=appointment.pet,
            start_at=req.requested_start_at,
            end_at=req.requested_end_at,
            status=Appointment.STATUS_PENDING,
            payment_status=appointment.payment_status,
            payment_reference=appointment.payment_reference,
            reschedule_count=appointment.reschedule_count + 1,
            follow_up_of=appointment.follow_up_of,
            is_follow_up=appointment.is_follow_up,
            assigned_provider=appointment.assigned_provider,
            assigned_at=appointment.assigned_at,
            last_modified_by=request.user,
        )
        req.status = 'approved'
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.admin_note = (admin_note_override if admin_note_override is not None else request.POST.get('admin_note') or '').strip()
        req.resulting_appointment = new_appointment
        req.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note', 'resulting_appointment']
        )
        _log_admin_audit(
            AdminAuditLog.ENTITY_RESCHEDULE,
            req.id,
            'approved',
            request.user,
            summary=f'Reschedule approved: #{appointment.id} -> #{new_appointment.id}',
            metadata={
                'appointment_id': appointment.id,
                'new_appointment_id': new_appointment.id,
                'requested_start_at': req.requested_start_at.isoformat(),
            },
        )
        messages.success(request, f'Reschedule approved for {appointment.pet.name}.')
    return True


@_pet_parent_required
def pet_parent_dashboard_view(request):
    now = timezone.now()
    appointments = Appointment.objects.filter(user=request.user).select_related('pet').order_by('start_at')
    upcoming = appointments.filter(start_at__gte=now).exclude(status=Appointment.STATUS_RESCHEDULED)
    past = appointments.filter(start_at__lt=now)
    pending_reschedule = (
        request.user.appointment_reschedule_requests
        .filter(status='pending')
        .select_related('appointment', 'appointment__pet')
        .order_by('-created_at')
    )
    follow_up_notice = (
        upcoming.filter(is_follow_up=True).order_by('start_at').first()
    )

    return render(
        request,
        'appointments/pet_dashboard.html',
        {
            'upcoming': upcoming,
            'past': past,
            'pending_reschedule': pending_reschedule,
            'follow_up_notice': follow_up_notice,
            'config': AppointmentConfig.get_solo(),
            'now': now,
        },
    )


@_pet_parent_required
def book_appointment_view(request):
    form = AppointmentBookingForm(request.POST or None, user=request.user)
    selected_date = request.GET.get('date') or request.POST.get('appointment_date')
    slots = []
    remaining = 0

    if selected_date:
        try:
            local_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            slots, remaining = get_daily_slots(local_date, user=request.user)
        except ValueError:
            pass

    if request.method == 'POST' and form.is_valid():
        appointment = create_appointment_from_lock(
            user=request.user,
            pet=form.cleaned_data['pet'],
            lock_token=form.cleaned_data['lock_token'],
            payment_reference=form.cleaned_data.get('payment_reference', ''),
        )
        messages.success(request, 'Appointment booked successfully.')
        return redirect('appointments:booking_success', appointment_id=appointment.id)

    return render(
        request,
        'appointments/book_appointment.html',
        {
            'form': form,
            'slots': slots,
            'remaining_slots': remaining,
            'selected_date': selected_date,
            'upi_id': AppointmentConfig.get_solo().upi_id,
        },
    )


@_pet_parent_required
def booking_success_view(request, appointment_id):
    appointment = get_object_or_404(Appointment.objects.select_related('pet'), id=appointment_id, user=request.user)
    return render(
        request,
        'appointments/booking_success.html',
        {'appointment': appointment, 'upi_id': AppointmentConfig.get_solo().upi_id},
    )


@_pet_parent_required
def appointment_detail_view(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('pet', 'consultation_note'),
        id=appointment_id,
        user=request.user,
    )
    return render(request, 'appointments/appointment_detail.html', {'appointment': appointment})


@_pet_parent_required
def reschedule_appointment_view(request, appointment_id):
    appointment = get_object_or_404(Appointment.objects.select_related('pet'), id=appointment_id, user=request.user)

    if appointment.status not in [Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED]:
        messages.error(request, 'Only pending or confirmed appointments can be rescheduled.')
        return redirect('appointments:pet_dashboard')
    if appointment.reschedule_count >= 1:
        messages.error(request, 'This appointment has already used the one-time reschedule request.')
        return redirect('appointments:pet_dashboard')
    if appointment.start_at - timezone.now() < timedelta(hours=12):
        messages.error(request, 'Reschedule request is allowed only up to 12 hours before appointment time.')
        return redirect('appointments:pet_dashboard')

    if appointment.reschedule_requests.exists():
        messages.info(request, 'A reschedule request was already submitted for this appointment.')
        return redirect('appointments:pet_dashboard')

    form = AppointmentRescheduleForm(request.POST or None)
    selected_date = request.GET.get('date') or request.POST.get('appointment_date')
    slots = []
    remaining = 0

    if selected_date:
        try:
            local_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            slots, remaining = get_daily_slots(local_date, user=request.user)
        except ValueError:
            pass

    if request.method == 'POST' and form.is_valid():
        if not form.cleaned_data.get('appointment_time'):
            messages.error(request, 'Please select a time slot.')
            return redirect('appointments:reschedule', appointment_id=appointment.id)

        requested_start = to_utc_from_ist(
            form.cleaned_data['appointment_date'],
            form.cleaned_data['appointment_time'],
        )
        try:
            validate_slot_rules(requested_start, exclude_appointment_id=appointment.id)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect('appointments:reschedule', appointment_id=appointment.id)

        appointment.reschedule_requests.create(
            requested_by=request.user,
            requested_start_at=requested_start,
            requested_end_at=requested_start + timedelta(hours=1),
        )
        messages.success(
            request,
            'Reschedule request sent. It will be confirmed only after admin or vet approval.',
        )
        return redirect('appointments:pet_dashboard')

    return render(
        request,
        'appointments/reschedule_appointment.html',
        {
            'form': form,
            'appointment': appointment,
            'slots': slots,
            'remaining_slots': remaining,
            'selected_date': selected_date,
        },
    )


@require_GET
@_pet_parent_required
def available_slots_api(request):
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'date is required'}, status=400)

    try:
        local_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    slots, remaining = get_daily_slots(local_date, user=request.user)
    return JsonResponse({'slots': slots, 'remaining': remaining})


@require_POST
@_pet_parent_required
def lock_slot_api(request):
    date_str = request.POST.get('date')
    time_str = request.POST.get('time')

    if not date_str or not time_str:
        return JsonResponse({'error': 'date and time are required'}, status=400)

    try:
        local_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        local_time = datetime.strptime(time_str, '%H:%M').time()
        lock = acquire_slot_lock(request.user, local_date, local_time)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse(
        {
            'lock_token': str(lock.lock_token),
            'expires_at': timezone.localtime(lock.expires_at, IST).isoformat(),
        }
    )


@_admin_or_vet_required
def admin_dashboard_view(request):
    appointments = Appointment.objects.select_related('user', 'pet', 'assigned_provider').order_by('-start_at')
    sla = AdminSLAConfig.get_solo()

    if request.method == 'POST':
        if request.POST.get('action') == 'send_due_24h_reminders':
            now = timezone.now()
            to_remind = Appointment.objects.filter(
                start_at__gte=now + timedelta(hours=23),
                start_at__lte=now + timedelta(hours=25),
                reminder_24h_sent_at__isnull=True,
            ).exclude(status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_RESCHEDULED])
            sent = 0
            for appt in to_remind:
                send_appointment_reminder_email(appt, '24h')
                appt.reminder_24h_sent_at = now
                appt.last_modified_by = request.user
                appt.save(update_fields=['reminder_24h_sent_at', 'last_modified_by', 'updated_at'])
                sent += 1
            _log_admin_audit(
                AdminAuditLog.ENTITY_SYSTEM,
                'dashboard',
                'bulk_send_24h_reminders',
                request.user,
                summary=f'Sent {sent} reminder(s)',
            )
            messages.success(request, f'Sent {sent} reminder(s).')
            return redirect('appointments:admin_dashboard')

        if request.POST.get('action') in {'bulk_approve_reschedule', 'bulk_reject_reschedule'}:
            selected_ids = request.POST.getlist('request_ids')
            if not selected_ids:
                messages.info(request, 'Select at least one request for bulk action.')
                return redirect('appointments:admin_dashboard')
            processed = 0
            for req_id in selected_ids:
                temp_action = 'approve_reschedule' if request.POST.get('action') == 'bulk_approve_reschedule' else 'reject_reschedule'
                if _process_reschedule_action(
                    request,
                    'appointments:admin_dashboard',
                    action_override=temp_action,
                    request_id_override=req_id,
                    admin_note_override=(request.POST.get('admin_note') or '').strip(),
                ):
                    processed += 1
            messages.success(request, f'Bulk operation processed for {processed} request(s).')
            return redirect('appointments:admin_dashboard')

        if _process_reschedule_action(request, 'appointments:admin_dashboard'):
            return redirect('appointments:admin_dashboard')

        appointment = get_object_or_404(Appointment, id=request.POST.get('appointment_id'))
        status_form = AppointmentStatusUpdateForm(request.POST, instance=appointment)
        status_form.fields['assigned_provider'].queryset = _vet_providers_qs()
        note, _ = ConsultationNote.objects.get_or_create(appointment=appointment)
        note_form = ConsultationNoteForm(request.POST, request.FILES, instance=note)

        if status_form.is_valid() and note_form.is_valid():
            before = {
                'status': appointment.status,
                'payment_status': appointment.payment_status,
                'payment_reference': appointment.payment_reference,
                'assigned_provider_id': appointment.assigned_provider_id,
            }
            updated = status_form.save(commit=False)
            updated.last_modified_by = request.user
            if updated.assigned_provider_id and not appointment.assigned_provider_id:
                updated.assigned_at = timezone.now()
            updated.save()
            note_form.save()
            _log_admin_audit(
                AdminAuditLog.ENTITY_APPOINTMENT,
                appointment.id,
                'status_or_note_update',
                request.user,
                summary=f'Appointment #{appointment.id} updated from dashboard',
                metadata={'before': before, 'after': {
                    'status': updated.status,
                    'payment_status': updated.payment_status,
                    'payment_reference': updated.payment_reference,
                    'assigned_provider_id': updated.assigned_provider_id,
                }},
            )
            messages.success(request, 'Appointment updated successfully.')
            return redirect('appointments:admin_dashboard')
    
    total = appointments.count()
    no_show_count = appointments.filter(status=Appointment.STATUS_NO_SHOW).count()
    no_show_rate = (no_show_count / total * 100) if total else 0

    weekday_counts = (
        Appointment.objects
        .extra(select={'weekday': "strftime('%%w', start_at)"})
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    weekday_map = {
        '0': 'Sunday', '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday',
        '4': 'Thursday', '5': 'Friday', '6': 'Saturday'
    }
    most_booked_day = weekday_map.get(weekday_counts[0]['weekday']) if weekday_counts else '-'
    pending_reschedule_requests = (
        AppointmentRescheduleRequest.objects
        .filter(status='pending')
        .select_related('appointment', 'appointment__pet', 'requested_by')
        .order_by('-created_at')
    )
    now = timezone.now()
    overdue_reschedules = pending_reschedule_requests.filter(
        created_at__lt=now - timedelta(hours=sla.reschedule_response_hours)
    ).count()
    open_unpaid = appointments.filter(
        status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
        payment_status__in=[Appointment.PAYMENT_UNPAID, Appointment.PAYMENT_PENDING],
    ).count()
    unassigned_upcoming = appointments.filter(
        start_at__gte=now,
        status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
        assigned_provider__isnull=True,
    ).count()
    today_local = timezone.localtime(now, IST).date()
    start_today = datetime.combine(today_local, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
    end_today = (datetime.combine(today_local, datetime.min.time()) + timedelta(days=1)).replace(tzinfo=IST).astimezone(dt_timezone.utc)
    today_count = appointments.filter(start_at__gte=start_today, start_at__lt=end_today).count()

    overdue_notes = Appointment.objects.filter(
        status=Appointment.STATUS_COMPLETED,
        end_at__lt=now - timedelta(hours=sla.note_completion_hours),
    ).filter(
        Q(consultation_note__isnull=True) | Q(consultation_note__notes__exact='')
    ).count()

    provider_capacity_map = {
        item.provider_id: item
        for item in ProviderCapacity.objects.select_related('provider').filter(active=True)
    }
    workload_cards = []
    for provider in _vet_providers_qs()[:8]:
        capacity = provider_capacity_map.get(provider.id)
        daily_limit = capacity.daily_limit if capacity else AppointmentConfig.get_solo().daily_appointment_limit
        next_7 = _provider_daily_load(provider, today_local, days=7)
        peak = max([d['count'] for d in next_7], default=0)
        workload_cards.append({
            'provider': provider,
            'daily_limit': daily_limit,
            'peak_count': peak,
            'utilization_pct': round((peak / daily_limit * 100), 1) if daily_limit else 0,
        })

    return render(
        request,
        'appointments/admin_dashboard.html',
        {
            **_admin_shell_context('dashboard'),
            'appointments': appointments[:50],
            'pending_reschedule_requests': pending_reschedule_requests[:40],
            'total_appointments': total,
            'no_show_rate': round(no_show_rate, 2),
            'most_booked_day': most_booked_day,
            'sla': sla,
            'overdue_reschedules': overdue_reschedules,
            'overdue_notes': overdue_notes,
            'open_unpaid': open_unpaid,
            'unassigned_upcoming': unassigned_upcoming,
            'today_count': today_count,
            'workload_cards': workload_cards,
        },
    )


@_admin_or_vet_required
def admin_calendar_view(request):
    view_type = request.GET.get('view', 'month')
    date_str = request.GET.get('date')

    if date_str:
        try:
            anchor = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            anchor = timezone.localdate()
    else:
        anchor = timezone.localdate()

    if request.method == 'POST' and request.POST.get('action') == 'block_day':
        block_date = datetime.strptime(request.POST['block_date'], '%Y-%m-%d').date()
        row, created = BlockedDate.objects.get_or_create(date=block_date)
        if created:
            _log_admin_audit(
                AdminAuditLog.ENTITY_BLOCKED_DATE,
                row.id,
                'created_from_calendar',
                request.user,
                summary=f'Blocked day from calendar: {block_date}',
            )
        messages.success(request, f'{block_date} blocked successfully.')
        return redirect('appointments:admin_calendar')
    if request.method == 'POST' and request.POST.get('action') == 'block_range':
        start = datetime.strptime(request.POST['block_start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(request.POST['block_end_date'], '%Y-%m-%d').date()
        reason = (request.POST.get('block_reason') or '').strip()
        if end < start:
            start, end = end, start
        cursor = start
        created_count = 0
        while cursor <= end:
            _, created = BlockedDate.objects.get_or_create(date=cursor, defaults={'reason': reason})
            if created:
                created_count += 1
            cursor += timedelta(days=1)
        _log_admin_audit(
            AdminAuditLog.ENTITY_BLOCKED_DATE,
            f'{start}->{end}',
            'created_range_from_calendar',
            request.user,
            summary=f'Blocked {created_count} day(s) from calendar range',
        )
        messages.success(request, f'Blocked {created_count} day(s) from {start} to {end}.')
        return redirect('appointments:admin_calendar')

    if view_type == 'day':
        start_day = anchor
        end_day = anchor + timedelta(days=1)
        prev_anchor = anchor - timedelta(days=1)
        next_anchor = anchor + timedelta(days=1)
    elif view_type == 'week':
        start_day = anchor - timedelta(days=anchor.weekday())  # Monday
        end_day = start_day + timedelta(days=7)
        prev_anchor = start_day - timedelta(days=7)
        next_anchor = start_day + timedelta(days=7)
    else:  # month
        view_type = 'month'
        start_day = anchor.replace(day=1)
        if start_day.month == 12:
            next_month = start_day.replace(year=start_day.year + 1, month=1, day=1)
        else:
            next_month = start_day.replace(month=start_day.month + 1, day=1)
        end_day = next_month
        prev_anchor = (start_day - timedelta(days=1)).replace(day=1)
        next_anchor = next_month

    start_dt = datetime.combine(start_day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)
    end_dt = datetime.combine(end_day, datetime.min.time()).replace(tzinfo=IST).astimezone(dt_timezone.utc)

    appts = (
        Appointment.objects
        .filter(start_at__gte=start_dt, start_at__lt=end_dt)
        .select_related('pet', 'user', 'assigned_provider')
        .order_by('start_at')
    )

    grouped = {}
    for appt in appts:
        local_day = timezone.localtime(appt.start_at, IST).date()
        grouped.setdefault(local_day, []).append(appt)

    blocked_dates_set = set(BlockedDate.objects.values_list('date', flat=True))

    # Build calendar grid for month view (weeks x days)
    cal_weeks = []
    if view_type == 'month':
        import calendar as cal_mod
        first_weekday = start_day.weekday()  # 0=Mon
        # pad start so grid begins on Monday
        grid_start = start_day - timedelta(days=first_weekday)
        # grid ends on Sunday after last day of month
        last_day_of_month = end_day - timedelta(days=1)
        last_weekday = last_day_of_month.weekday()
        grid_end = last_day_of_month + timedelta(days=(6 - last_weekday))
        cursor = grid_start
        week = []
        while cursor <= grid_end:
            week.append({
                'date': cursor,
                'is_current_month': cursor.month == anchor.month,
                'is_today': cursor == timezone.localdate(),
                'is_blocked': cursor in blocked_dates_set,
                'appointments': grouped.get(cursor, []),
            })
            if len(week) == 7:
                cal_weeks.append(week)
                week = []
            cursor += timedelta(days=1)
        if week:
            cal_weeks.append(week)

    # Build week columns for week view
    week_days = []
    if view_type == 'week':
        today = timezone.localdate()
        for i in range(7):
            d = start_day + timedelta(days=i)
            week_days.append({
                'date': d,
                'is_today': d == today,
                'is_blocked': d in blocked_dates_set,
                'appointments': grouped.get(d, []),
            })

    return render(
        request,
        'appointments/admin_calendar.html',
        {
            **_admin_shell_context('calendar'),
            'appointments_by_day': grouped,
            'anchor_date': anchor,
            'view_type': view_type,
            'blocked_dates': blocked_dates_set,
            'prev_anchor': prev_anchor,
            'next_anchor': next_anchor,
            'start_day': start_day,
            'end_day': end_day - timedelta(days=1),
            'cal_weeks': cal_weeks,
            'week_days': week_days,
            'today': timezone.localdate(),
        },
    )


@_admin_or_vet_required
def admin_pets_view(request):
    pets = (
        Pet.objects.select_related('owner', 'owner__user')
        .prefetch_related('appointments')
        .order_by('-owner__created_at', 'name')
    )
    return render(
        request,
        'appointments/admin_pets.html',
        {
            **_admin_shell_context('pets'),
            'pets': pets[:300],
        },
    )


@_admin_or_vet_required
def admin_appointments_view(request):
    appointments = Appointment.objects.select_related('pet', 'user').order_by('-start_at')
    providers = _vet_providers_qs()
    provider_capacity_map = {
        item.provider_id: item.daily_limit
        for item in ProviderCapacity.objects.filter(active=True)
    }

    if request.method == 'POST':
        if request.POST.get('action') == 'bulk_assign_provider':
            selected_ids = request.POST.getlist('appointment_ids')
            provider_id = request.POST.get('provider_id')
            if not selected_ids or not provider_id:
                messages.info(request, 'Select appointments and a provider.')
                return redirect('appointments:admin_appointments')
            provider = get_object_or_404(providers, id=provider_id)
            updated_count = 0
            skipped_count = 0
            for appt in Appointment.objects.filter(id__in=selected_ids):
                appt_local_day = timezone.localtime(appt.start_at, IST).date()
                provider_limit = _provider_limit(provider)
                provider_load = _provider_load_on_day(provider, appt_local_day, exclude_appointment_id=appt.id)
                if provider_load >= provider_limit:
                    skipped_count += 1
                    continue
                appt.assigned_provider = provider
                appt.assigned_at = timezone.now()
                appt.last_modified_by = request.user
                appt.save(update_fields=['assigned_provider', 'assigned_at', 'last_modified_by', 'updated_at'])
                _log_admin_audit(
                    AdminAuditLog.ENTITY_APPOINTMENT,
                    appt.id,
                    'provider_assigned',
                    request.user,
                    summary=f'Assigned provider {provider.email or provider.username} to appointment #{appt.id}',
                    metadata={'provider_id': provider.id},
                )
                updated_count += 1
            if skipped_count:
                messages.warning(
                    request,
                    f'Assigned {updated_count} appointment(s). Skipped {skipped_count} due to provider daily limit.',
                )
            else:
                messages.success(request, f'Assigned provider for {updated_count} appointment(s).')
            return redirect('appointments:admin_appointments')

    status = request.GET.get('status', '').strip()
    q = request.GET.get('q', '').strip()
    if status:
        appointments = appointments.filter(status=status)
    if q:
        appointments = appointments.filter(Q(pet__name__icontains=q) | Q(user__email__icontains=q) | Q(user__username__icontains=q))
    provider_load = []
    start_local = timezone.localtime(timezone.now(), IST).date()
    default_limit = AppointmentConfig.get_solo().daily_appointment_limit
    for provider in providers:
        next_7 = _provider_daily_load(provider, start_local, days=7)
        peak = max([d['count'] for d in next_7], default=0)
        limit = provider_capacity_map.get(provider.id, default_limit)
        provider_load.append({
            'provider': provider,
            'peak': peak,
            'daily_limit': limit,
            'utilization_pct': round((peak / limit * 100), 1) if limit else 0,
        })
    return render(
        request,
        'appointments/admin_appointments.html',
        {
            **_admin_shell_context('appointments'),
            'appointments': appointments[:300],
            'status': status,
            'q': q,
            'status_choices': Appointment.STATUS_CHOICES,
            'providers': providers,
            'provider_load': provider_load,
        },
    )


@_admin_or_vet_required
def admin_appointment_detail_view(request, appointment_id):
    appointment = get_object_or_404(Appointment.objects.select_related('pet', 'user', 'assigned_provider'), id=appointment_id)
    note, _ = ConsultationNote.objects.get_or_create(appointment=appointment)
    status_form = AppointmentStatusUpdateForm(request.POST or None, instance=appointment)
    status_form.fields['assigned_provider'].queryset = _vet_providers_qs()
    note_form = ConsultationNoteForm(request.POST or None, request.FILES or None, instance=note)
    active_templates = NoteTemplate.objects.filter(active=True).order_by('title')

    if request.method == 'POST' and request.POST.get('action') == 'apply_note_template':
        template_obj = get_object_or_404(NoteTemplate, id=request.POST.get('template_id'))
        existing = (note.notes or '').strip()
        note.notes = f'{existing}\n\n{template_obj.body}'.strip() if existing else template_obj.body
        note.save(update_fields=['notes', 'updated_at'])
        _log_admin_audit(
            AdminAuditLog.ENTITY_NOTE_TEMPLATE,
            template_obj.id,
            'applied_to_appointment',
            request.user,
            summary=f'Applied template "{template_obj.title}" to appointment #{appointment.id}',
            metadata={'appointment_id': appointment.id},
        )
        messages.success(request, f'Applied note template: {template_obj.title}')
        return redirect('appointments:admin_appointment_detail', appointment_id=appointment.id)

    if request.method == 'POST' and status_form.is_valid() and note_form.is_valid():
        before = {
            'status': appointment.status,
            'payment_status': appointment.payment_status,
            'payment_reference': appointment.payment_reference,
            'assigned_provider_id': appointment.assigned_provider_id,
        }
        updated = status_form.save(commit=False)
        if updated.assigned_provider_id:
            local_day = timezone.localtime(updated.start_at, IST).date()
            limit = _provider_limit(updated.assigned_provider)
            load = _provider_load_on_day(updated.assigned_provider, local_day, exclude_appointment_id=updated.id)
            if load >= limit:
                messages.error(
                    request,
                    f'Provider daily limit reached for {local_day}. Increase capacity in settings or choose another provider.',
                )
                return redirect('appointments:admin_appointment_detail', appointment_id=appointment.id)
        updated.last_modified_by = request.user
        if updated.assigned_provider_id and not appointment.assigned_provider_id:
            updated.assigned_at = timezone.now()
        updated.save()
        note_form.save()
        _log_admin_audit(
            AdminAuditLog.ENTITY_APPOINTMENT,
            appointment.id,
            'detail_updated',
            request.user,
            summary=f'Appointment #{appointment.id} updated from detail page',
            metadata={'before': before, 'after': {
                'status': updated.status,
                'payment_status': updated.payment_status,
                'payment_reference': updated.payment_reference,
                'assigned_provider_id': updated.assigned_provider_id,
            }},
        )
        messages.success(request, 'Appointment details updated.')
        return redirect('appointments:admin_appointment_detail', appointment_id=appointment.id)
    return render(
        request,
        'appointments/admin_appointment_detail.html',
        {
            **_admin_shell_context('appointments'),
            'appointment': appointment,
            'status_form': status_form,
            'note_form': note_form,
            'reschedule_requests': appointment.reschedule_requests.select_related('requested_by', 'reviewed_by'),
            'note_templates': active_templates,
            'audit_logs': AdminAuditLog.objects.filter(
                Q(entity_type=AdminAuditLog.ENTITY_APPOINTMENT, entity_id=str(appointment.id))
                | Q(entity_type=AdminAuditLog.ENTITY_RESCHEDULE, entity_id__in=[str(x.id) for x in appointment.reschedule_requests.all()])
            )[:40],
        },
    )


@_admin_or_vet_required
def admin_reschedule_requests_view(request):
    if request.method == 'POST':
        if request.POST.get('action') in {'bulk_approve_reschedule', 'bulk_reject_reschedule'}:
            selected_ids = request.POST.getlist('request_ids')
            if not selected_ids:
                messages.info(request, 'Select at least one request for bulk action.')
                return redirect('appointments:admin_reschedule_requests')
            processed = 0
            for req_id in selected_ids:
                temp_action = 'approve_reschedule' if request.POST.get('action') == 'bulk_approve_reschedule' else 'reject_reschedule'
                if _process_reschedule_action(
                    request,
                    'appointments:admin_reschedule_requests',
                    action_override=temp_action,
                    request_id_override=req_id,
                    admin_note_override=(request.POST.get('admin_note') or '').strip(),
                ):
                    processed += 1
            messages.success(request, f'Bulk operation processed for {processed} request(s).')
            return redirect('appointments:admin_reschedule_requests')
        if _process_reschedule_action(request, 'appointments:admin_reschedule_requests'):
            return redirect('appointments:admin_reschedule_requests')
    reqs = (
        AppointmentRescheduleRequest.objects
        .select_related('appointment', 'appointment__pet', 'requested_by', 'reviewed_by')
        .order_by('-created_at')
    )
    return render(
        request,
        'appointments/admin_reschedule_requests.html',
        {
            **_admin_shell_context('reschedules'),
            'requests': reqs[:400],
        },
    )


@_admin_or_vet_required
def admin_blocked_dates_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            target = BlockedDate.objects.filter(id=request.POST.get('id')).first()
            BlockedDate.objects.filter(id=request.POST.get('id')).delete()
            if target:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_DATE,
                    target.id,
                    'deleted',
                    request.user,
                    summary=f'Removed blocked date {target.date}',
                )
            messages.success(request, 'Blocked date removed.')
            return redirect('appointments:admin_blocked_dates')
        if action == 'create_single':
            block_date = datetime.strptime(request.POST['block_date'], '%Y-%m-%d').date()
            row, created = BlockedDate.objects.get_or_create(date=block_date, defaults={'reason': request.POST.get('reason', '')})
            if created:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_DATE,
                    row.id,
                    'created',
                    request.user,
                    summary=f'Blocked single date {row.date}',
                    metadata={'reason': row.reason},
                )
            messages.success(request, 'Blocked date added.')
            return redirect('appointments:admin_blocked_dates')
        if action == 'create_range':
            start = datetime.strptime(request.POST['block_start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(request.POST['block_end_date'], '%Y-%m-%d').date()
            reason = request.POST.get('reason', '')
            if end < start:
                start, end = end, start
            cursor = start
            created_count = 0
            while cursor <= end:
                _, created = BlockedDate.objects.get_or_create(date=cursor, defaults={'reason': reason})
                if created:
                    created_count += 1
                cursor += timedelta(days=1)
            _log_admin_audit(
                AdminAuditLog.ENTITY_BLOCKED_DATE,
                f'{start}->{end}',
                'created_range',
                request.user,
                summary=f'Blocked {created_count} day(s) from {start} to {end}',
                metadata={'start': start.isoformat(), 'end': end.isoformat(), 'reason': reason},
            )
            messages.success(request, 'Date range blocked successfully.')
            return redirect('appointments:admin_blocked_dates')
        if action == 'create_slot':
            slot_date = datetime.strptime(request.POST['slot_date'], '%Y-%m-%d').date()
            slot_time = datetime.strptime(request.POST['slot_time'], '%H:%M').time()
            slot_utc = to_utc_from_ist(slot_date, slot_time)
            row, created = BlockedTimeSlot.objects.get_or_create(
                start_at=slot_utc,
                defaults={'reason': request.POST.get('reason', '')},
            )
            if created:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_SLOT,
                    row.id,
                    'created',
                    request.user,
                    summary=f'Blocked slot {timezone.localtime(slot_utc, IST).strftime("%d %b %Y, %I:%M %p")}',
                    metadata={'reason': row.reason},
                )
            messages.success(request, 'Blocked time slot added.')
            return redirect('appointments:admin_blocked_dates')
        if action == 'delete_slot':
            target = BlockedTimeSlot.objects.filter(id=request.POST.get('id')).first()
            BlockedTimeSlot.objects.filter(id=request.POST.get('id')).delete()
            if target:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_SLOT,
                    target.id,
                    'deleted',
                    request.user,
                    summary=f'Removed blocked slot {timezone.localtime(target.start_at, IST).isoformat()}',
                )
            messages.success(request, 'Blocked slot removed.')
            return redirect('appointments:admin_blocked_dates')
    dates = BlockedDate.objects.order_by('date')
    slots = BlockedTimeSlot.objects.order_by('start_at')[:500]
    return render(
        request,
        'appointments/admin_blocked_dates.html',
        {
            **_admin_shell_context('blocked_dates'),
            'blocked_dates': dates,
            'blocked_slots': slots,
        },
    )


@_admin_or_vet_required
def admin_blocked_slots_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            target = BlockedTimeSlot.objects.filter(id=request.POST.get('id')).first()
            BlockedTimeSlot.objects.filter(id=request.POST.get('id')).delete()
            if target:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_SLOT,
                    target.id,
                    'deleted',
                    request.user,
                    summary=f'Removed blocked slot {timezone.localtime(target.start_at, IST).isoformat()}',
                )
            messages.success(request, 'Blocked slot removed.')
            return redirect('appointments:admin_blocked_slots')
        if action == 'create':
            slot_date = datetime.strptime(request.POST['slot_date'], '%Y-%m-%d').date()
            slot_time = datetime.strptime(request.POST['slot_time'], '%H:%M').time()
            slot_utc = to_utc_from_ist(slot_date, slot_time)
            row, created = BlockedTimeSlot.objects.get_or_create(
                start_at=slot_utc,
                defaults={'reason': request.POST.get('reason', '')},
            )
            if created:
                _log_admin_audit(
                    AdminAuditLog.ENTITY_BLOCKED_SLOT,
                    row.id,
                    'created',
                    request.user,
                    summary=f'Blocked slot {timezone.localtime(slot_utc, IST).strftime("%d %b %Y, %I:%M %p")}',
                    metadata={'reason': row.reason},
                )
            messages.success(request, 'Blocked slot added.')
            return redirect('appointments:admin_blocked_slots')
    slots = BlockedTimeSlot.objects.order_by('start_at')
    return render(
        request,
        'appointments/admin_blocked_slots.html',
        {
            **_admin_shell_context('blocked_slots'),
            'blocked_slots': slots[:500],
        },
    )


@_admin_or_vet_required
def admin_notes_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'create_template':
        template_form = NoteTemplateForm(request.POST)
        if template_form.is_valid():
            tpl = template_form.save(commit=False)
            tpl.created_by = request.user
            tpl.updated_by = request.user
            tpl.save()
            _log_admin_audit(
                AdminAuditLog.ENTITY_NOTE_TEMPLATE,
                tpl.id,
                'created',
                request.user,
                summary=f'Created note template "{tpl.title}"',
            )
            messages.success(request, 'Note template created.')
            return redirect('appointments:admin_notes')
    elif request.method == 'POST' and request.POST.get('action') == 'toggle_template':
        tpl = get_object_or_404(NoteTemplate, id=request.POST.get('template_id'))
        tpl.active = not tpl.active
        tpl.updated_by = request.user
        tpl.save(update_fields=['active', 'updated_by', 'updated_at'])
        _log_admin_audit(
            AdminAuditLog.ENTITY_NOTE_TEMPLATE,
            tpl.id,
            'toggled_active',
            request.user,
            summary=f'{"Activated" if tpl.active else "Deactivated"} template "{tpl.title}"',
        )
        messages.success(request, 'Template status updated.')
        return redirect('appointments:admin_notes')

    notes = ConsultationNote.objects.select_related('appointment', 'appointment__pet', 'appointment__user').order_by('-updated_at')
    return render(
        request,
        'appointments/admin_notes.html',
        {
            **_admin_shell_context('notes'),
            'notes': notes[:300],
            'template_form': NoteTemplateForm(),
            'templates': NoteTemplate.objects.order_by('title'),
        },
    )


@_admin_or_vet_required
def admin_settings_view(request):
    config = AppointmentConfig.get_solo()
    sla = AdminSLAConfig.get_solo()
    form = AppointmentConfigForm(prefix='cfg', data=request.POST or None, instance=config)
    sla_form = AdminSLAConfigForm(prefix='sla', data=request.POST or None, instance=sla)
    provider_form = ProviderCapacityForm(prefix='provider', data=request.POST or None)
    provider_form.fields['provider'].queryset = _vet_providers_qs()

    if request.method == 'POST' and request.POST.get('action') == 'save_config' and form.is_valid():
        form.save()
        _log_admin_audit(
            AdminAuditLog.ENTITY_SETTINGS,
            'appointment_config',
            'updated',
            request.user,
            summary='Updated appointment configuration',
        )
        messages.success(request, 'Appointment settings saved successfully.')
        return redirect('appointments:admin_settings')

    if request.method == 'POST' and request.POST.get('action') == 'save_sla' and sla_form.is_valid():
        sla_form.save()
        _log_admin_audit(
            AdminAuditLog.ENTITY_SETTINGS,
            'admin_sla',
            'updated',
            request.user,
            summary='Updated SLA configuration',
            metadata=sla_form.cleaned_data,
        )
        messages.success(request, 'SLA settings saved successfully.')
        return redirect('appointments:admin_settings')

    if request.method == 'POST' and request.POST.get('action') == 'save_provider_capacity' and provider_form.is_valid():
        capacity, _ = ProviderCapacity.objects.update_or_create(
            provider=provider_form.cleaned_data['provider'],
            defaults={
                'daily_limit': provider_form.cleaned_data['daily_limit'],
                'active': provider_form.cleaned_data['active'],
            },
        )
        _log_admin_audit(
            AdminAuditLog.ENTITY_PROVIDER,
            capacity.provider_id,
            'capacity_updated',
            request.user,
            summary=f'Provider capacity set to {capacity.daily_limit}/day',
            metadata={'active': capacity.active},
        )
        messages.success(request, 'Provider capacity updated.')
        return redirect('appointments:admin_settings')

    return render(
        request,
        'appointments/admin_settings.html',
        {
            **_admin_shell_context('settings'),
            'form': form,
            'sla_form': sla_form,
            'provider_form': provider_form,
            'provider_capacities': ProviderCapacity.objects.select_related('provider').order_by('provider__email'),
        },
    )


@_admin_or_vet_required
def admin_workload_view(request):
    providers = _vet_providers_qs()
    today = timezone.localtime(timezone.now(), IST).date()
    default_limit = AppointmentConfig.get_solo().daily_appointment_limit
    capacities = {c.provider_id: c for c in ProviderCapacity.objects.select_related('provider')}

    rows = []
    for provider in providers:
        next_7 = _provider_daily_load(provider, today, days=7)
        weekly_total = sum(x['count'] for x in next_7)
        peak = max((x['count'] for x in next_7), default=0)
        limit = capacities.get(provider.id).daily_limit if capacities.get(provider.id) else default_limit
        rows.append({
            'provider': provider,
            'daily_limit': limit,
            'weekly_total': weekly_total,
            'peak_day_load': peak,
            'utilization_pct': round((peak / limit * 100), 1) if limit else 0,
            'next_7': next_7,
        })
    return render(
        request,
        'appointments/admin_workload.html',
        {
            **_admin_shell_context('workload'),
            'rows': rows,
            'today': today,
        },
    )


@_admin_or_vet_required
def admin_audit_history_view(request):
    q = request.GET.get('q', '').strip()
    logs = AdminAuditLog.objects.select_related('changed_by').order_by('-created_at')
    if q:
        logs = logs.filter(
            Q(action__icontains=q)
            | Q(summary__icontains=q)
            | Q(entity_type__icontains=q)
            | Q(entity_id__icontains=q)
            | Q(changed_by__email__icontains=q)
            | Q(changed_by__username__icontains=q)
        )
    return render(
        request,
        'appointments/admin_audit_history.html',
        {
            **_admin_shell_context('audit'),
            'logs': logs[:400],
            'q': q,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Staff Manual Booking
# ─────────────────────────────────────────────────────────────────────────────

@_admin_or_vet_required
def admin_book_appointment_view(request):
    """Staff-driven manual appointment creation page."""
    from .services.booking import to_utc_from_ist, validate_slot_rules

    prefill_date = request.GET.get('date', '')
    slots = []
    config = AppointmentConfig.get_solo()

    form = StaffAppointmentForm(
        request.POST or None,
        initial={
            'appointment_date': prefill_date,
            'status': Appointment.STATUS_CONFIRMED,
            'duration_minutes': config.appointment_duration_minutes,
        },
    )

    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        pet_parent = cd['pet_parent']
        pet = cd['pet']
        appt_date = cd['appointment_date']
        appt_time = cd['appointment_time']
        override = cd.get('override_slot_rules', False)
        dur = int(cd.get('duration_minutes') or config.appointment_duration_minutes)

        # Ensure selected pet belongs to selected parent
        if pet.owner_id != pet_parent.pk:
            form.add_error('pet', 'The selected pet does not belong to this pet parent.')
        else:
            slot_start_utc = to_utc_from_ist(appt_date, appt_time)
            end_at = slot_start_utc + timedelta(minutes=dur)

            validation_error = None
            if not override:
                try:
                    # Staff bookings allow sub-hour times and custom duration
                    validate_slot_rules(
                        slot_start_utc,
                        duration_minutes=dur,
                        allow_subhour=True,
                    )
                except ValidationError as exc:
                    validation_error = exc.messages[0]
                    form.add_error(None, f'Slot conflict: {validation_error}  (tick "Override" to force-book.)')

            if not validation_error or override:
                try:
                    with transaction.atomic():
                        appt_user = pet_parent.user if pet_parent.user_id else request.user
                        appointment = Appointment.objects.create(
                            user=appt_user,
                            pet=pet,
                            assigned_provider=cd.get('assigned_provider'),
                            start_at=slot_start_utc,
                            end_at=end_at,
                            status=cd['status'],
                            payment_status=Appointment.PAYMENT_UNPAID,
                            appt_type=cd.get('appt_type') or Appointment.APPT_TYPE_CONSULTATION,
                            staff_notes=cd.get('staff_notes', ''),
                            last_modified_by=request.user,
                        )
                        if appointment.assigned_provider:
                            appointment.assigned_at = timezone.now()
                            appointment.save(update_fields=['assigned_at'])
                        _log_admin_audit(
                            AdminAuditLog.ENTITY_APPOINTMENT,
                            appointment.id,
                            'staff_manual_booking',
                            request.user,
                            summary=(
                                f'Staff booked: {pet.name} for {pet_parent.name} '
                                f'on {appt_date} at {appt_time} '
                                f'[{appointment.get_appt_type_display()}] {dur}min'
                            ),
                        )
                    messages.success(
                        request,
                        f'Appointment for {pet.name} on {appt_date} at {appt_time.strftime("%I:%M %p")} ({dur} min) created successfully.',
                    )
                    return redirect('appointments:admin_appointment_detail', appointment_id=appointment.id)
                except Exception as exc:
                    form.add_error(None, f'Could not create appointment: {exc}')

    # Determine duration for slot preview (from POST data or config default)
    try:
        preview_dur = int(form.data.get('duration_minutes') or config.appointment_duration_minutes)
    except (ValueError, TypeError):
        preview_dur = config.appointment_duration_minutes

    # Build available slots preview for the selected date
    if prefill_date or (form.is_bound and form.data.get('appointment_date')):
        try:
            preview_date_str = (form.data.get('appointment_date') or prefill_date).strip()
            preview_date = datetime.strptime(preview_date_str, '%Y-%m-%d').date()
            slots, _ = get_daily_slots(
                preview_date,
                duration_minutes=preview_dur,
                allow_subhour=True,
            )
        except (ValueError, AttributeError):
            slots = []

    return render(
        request,
        'appointments/admin_book_appointment.html',
        {
            **_admin_shell_context('appointments'),
            'form': form,
            'prefill_date': prefill_date,
            'slots': slots,
            'config': config,
        },
    )


@_admin_or_vet_required
@require_GET
def admin_slots_api(request):
    """JSON API: return available slots for a given date (staff access).

    Query params:
        date        YYYY-MM-DD  (required)
        duration    int minutes (optional, defaults to config value)
        subhour     '1'/'true'  (optional, enables sub-hour slot generation)
    """
    date_str = request.GET.get('date', '').strip()
    if not date_str:
        return JsonResponse({'error': 'date required'}, status=400)
    try:
        local_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    # Parse optional duration override
    duration_minutes = None
    raw_dur = request.GET.get('duration', '').strip()
    if raw_dur:
        try:
            duration_minutes = int(raw_dur)
            if duration_minutes not in (15, 30, 45, 60, 90, 120):
                duration_minutes = None  # ignore invalid values
        except ValueError:
            pass

    # Sub-hour mode: enabled when duration < 60 or explicitly requested
    allow_subhour = request.GET.get('subhour', '') in ('1', 'true') or (
        duration_minutes is not None and duration_minutes < 60
    )

    slots, remaining = get_daily_slots(
        local_date,
        duration_minutes=duration_minutes,
        allow_subhour=allow_subhour,
    )
    return JsonResponse({'slots': slots, 'remaining': remaining})


@_admin_or_vet_required
@require_GET
def admin_pets_by_parent_api(request):
    """JSON API: return pets for a given pet parent (for dynamic dropdown)."""
    parent_id = request.GET.get('parent_id', '').strip()
    if not parent_id:
        return JsonResponse({'pets': []})
    try:
        parent = PetParent.objects.get(pk=int(parent_id))
    except (PetParent.DoesNotExist, ValueError):
        return JsonResponse({'pets': []})

    pets = parent.pets.values('id', 'name', 'species', 'breed').order_by('name')
    return JsonResponse({
        'pets': [
            {
                'id': p['id'],
                'label': f"{p['name']} ({p['species'].title()}{', ' + p['breed'] if p['breed'] else ''})",
            }
            for p in pets
        ]
    })
