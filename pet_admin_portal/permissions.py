from django.contrib.auth.decorators import login_required, user_passes_test


ALLOWED_GROUPS = {"Admin", "Vet", "Staff"}


def is_portal_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=ALLOWED_GROUPS).exists()


def portal_required(view_func):
    return login_required(user_passes_test(is_portal_user, login_url="login")(view_func))
