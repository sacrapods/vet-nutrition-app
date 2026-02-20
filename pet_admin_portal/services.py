import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import AuditLog


def _json_safe(value):
    if value is None:
        return {}
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, default=str))


def log_audit(actor, action, instance, changes=None):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        model_label=instance._meta.label,
        object_pk=str(instance.pk),
        object_repr=str(instance),
        changes=_json_safe(changes),
    )
