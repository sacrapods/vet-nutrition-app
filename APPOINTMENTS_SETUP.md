# Appointments App Setup

## 1) Migrations

```bash
python3 manage.py makemigrations appointments
python3 manage.py migrate
```

## 2) Create / configure groups

Ensure users are assigned correct groups:
- `Pet Parent`: can book and reschedule
- `Admin`: can manage calendar and appointment statuses

## 3) Seed appointment config

Open admin:
- `/admin/appointments/appointmentconfig/`

Configure:
- Buffer minutes
- Daily appointment limit
- Follow-up automation toggle
- Follow-up days
- Slot lock minutes
- UPI ID

## 4) Reminder automation job (placeholder senders)

Run periodically (every 10 mins recommended):

```bash
python3 manage.py send_appointment_notifications
```

The command marks reminder timestamps and calls placeholder notification functions.

## 5) URLs

- Pet parent dashboard: `/appointments/`
- Booking page: `/appointments/book/`
- Admin dashboard: `/appointments/admin/dashboard/`
- App-level calendar: `/appointments/admin/calendar/`
- Django admin calendar: `/admin/appointments/appointment/calendar/`
