from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


ADMIN_GROUP = "Admin"
VET_GROUP = "Vet"
PET_PARENT_GROUP = "Pet Parent"


def user_in_group(user, group_name):
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def user_in_any_group(user, group_names):
    return user.is_authenticated and user.groups.filter(name__in=group_names).exists()


def role_required(*group_names):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser or user_in_any_group(request.user, group_names):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return wrapped

    return decorator


admin_required = role_required(ADMIN_GROUP)
vet_required = role_required(VET_GROUP)
pet_parent_required = role_required(PET_PARENT_GROUP)
