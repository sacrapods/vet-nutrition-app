# Authentication and RBAC Setup

## 1) Apply migrations

```bash
python3 manage.py migrate
```

## 2) Create required groups

```bash
python3 manage.py setup_roles
```

This creates:
- `Admin`
- `Vet`
- `Pet Parent`

## 3) Create a superuser

```bash
python3 manage.py createsuperuser
```

## 4) Admin workflow for account management

1. Sign in to Django admin at `/admin/`.
2. Create users in `Authentication and Authorization > Users`.
3. Assign one group per user:
   - Dashboard users -> `Admin`
   - Veterinary clinicians -> `Vet`
   - Client users -> `Pet Parent`

## 5) URL entry points

- Login: `/intake/login/`
- Register (Pet Parent only): `/intake/register/`
- Pet Parent history: `/intake/my-submissions/`
- Admin dashboard: `/intake/cases/`
- Vet form list: `/intake/vet/cases/`
