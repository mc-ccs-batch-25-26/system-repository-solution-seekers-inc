from django.forms.models import model_to_dict
from .models import ProfileChangeLog


def snapshot(instance, target_type):
    """Return a flat dict of the instance's current field values (for before/after comparison)."""
    try:
        data = model_to_dict(instance)
    except Exception:
        data = {}
    # Also capture non-editable fields that model_to_dict skips
    for field in instance._meta.get_fields():
        if hasattr(field, 'attname') and field.attname not in data:
            data[field.attname] = getattr(instance, field.attname, None)
    # Serialize non-serialisable values to string so they can be stored in JSON
    return {k: str(v) if v is not None else None for k, v in data.items()}


def log_created(instance, target_type, household, user):
    """Write a CREATED ProfileChangeLog row."""
    ProfileChangeLog.log_change(
        household=household,
        target_type=target_type,
        target_id=instance.pk,
        action=ProfileChangeLog.Action.CREATED,
        changed_fields={},
        changed_by=user,
    )


def log_updated(instance, target_type, household, before, user):
    """Write an UPDATED ProfileChangeLog row recording the diff between before and after."""
    after = snapshot(instance, target_type)
    changed_fields = {
        key: {'before': before.get(key), 'after': after.get(key)}
        for key in after
        if str(before.get(key)) != str(after.get(key))
    }
    ProfileChangeLog.log_change(
        household=household,
        target_type=target_type,
        target_id=instance.pk,
        action=ProfileChangeLog.Action.UPDATED,
        changed_fields=changed_fields,
        changed_by=user,
    )


def log_state_change(instance, target_type, household, action, user):
    """Write a SOFT_DELETED or RESTORED ProfileChangeLog row."""
    ProfileChangeLog.log_change(
        household=household,
        target_type=target_type,
        target_id=instance.pk,
        action=action,
        changed_fields={},
        changed_by=user,
    )
