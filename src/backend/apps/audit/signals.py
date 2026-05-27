from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(post_save, sender='beneficiaries.Family')
def log_family_change(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    action = 'CREATED_FAMILY' if created else 'UPDATED_FAMILY'
    AuditLog.objects.create(
        user=instance.encoded_by,
        action=action,
        target_table='families',
        target_id=str(instance.id),
        details={
            'household_code': instance.household.household_code,
            'family_number': instance.family_number,
        },
    )


@receiver(post_save, sender='beneficiaries.Household')
def log_household_change(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    action = 'CREATED_HOUSEHOLD' if created else 'UPDATED_HOUSEHOLD'
    AuditLog.objects.create(
        user=instance.encoded_by,
        action=action,
        target_table='households',
        target_id=str(instance.id),
        details={
            'household_code': instance.household_code,
            'status': instance.status,
        },
    )


@receiver(post_save, sender='beneficiaries.Beneficiary')
def log_beneficiary_change(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    action = 'CREATED_BENEFICIARY' if created else 'UPDATED_BENEFICIARY'
    user = instance.encoded_by if created else (instance.updated_by or instance.encoded_by)
    AuditLog.objects.create(
        user=user,
        action=action,
        target_table='beneficiaries',
        target_id=str(instance.id),
        details={
            'first_name': instance.first_name,
            'middle_name': instance.middle_name,
            'last_name': instance.last_name,
            'full_name': instance.full_name,
            'is_tupad_eligible': instance.is_tupad_eligible,
        },
    )


CRITERION_AUDIT_FIELDS = ['name', 'weight', 'type', 'field_key', 'is_active']


def _criterion_audit_snapshot(instance):
    return {
        'name': instance.name,
        'weight': str(instance.weight),
        'type': instance.type,
        'field_key': instance.field_key,
        'is_active': instance.is_active,
    }


@receiver(pre_save, sender='criteria.Criterion')
def capture_previous_criterion_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._audit_previous_state = None
        return

    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._audit_previous_state = None
        return

    instance._audit_previous_state = _criterion_audit_snapshot(previous)


@receiver(post_save, sender='criteria.Criterion')
def log_criterion_change(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog

    current = _criterion_audit_snapshot(instance)
    previous = getattr(instance, '_audit_previous_state', None)
    changed_fields = {
        field: {
            'old': previous[field] if previous else None,
            'new': current[field],
        }
        for field in CRITERION_AUDIT_FIELDS
        if created or previous is None or previous[field] != current[field]
    }

    action = 'CHANGED_CRITERIA'
    AuditLog.objects.create(
        user=instance.updated_by,
        action=action,
        target_table='criteria',
        target_id=str(instance.id),
        details={
            'change_type': 'created' if created else 'updated',
            'changed_fields': changed_fields,
            **current,
        },
    )


@receiver(post_save, sender='cycles.ProgramCycle')
def log_cycle_create(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    if created:
        AuditLog.objects.create(
            user=instance.created_by,
            action='CREATED_CYCLE',
            target_table='program_cycles',
            target_id=str(instance.id),
            details={
                'cycle_name': instance.cycle_name,
                'application_start_date': str(instance.start_date),
                'application_end_date': str(instance.end_date),
                'work_start_date': str(instance.work_start_date) if instance.work_start_date else None,
                'work_end_date': str(instance.work_end_date) if instance.work_end_date else None,
                'slots': instance.slots,
                'max_per_household': instance.max_per_household,
            },
        )


@receiver(post_save, sender='cycles.CycleApplication')
def log_application_marked(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    if created:
        AuditLog.objects.create(
            user=instance.applied_by,
            action='MARKED_APPLICANT',
            target_table='cycle_applications',
            target_id=str(instance.id),
            details={
                'beneficiary_id': str(instance.beneficiary_id),
                'cycle_id': str(instance.cycle_id),
            },
        )


@receiver(post_save, sender='cycles.ParticipationRecord')
def log_participation_record(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    if created:
        AuditLog.objects.create(
            user=instance.recorded_by,
            action='RECORDED_PARTICIPATION',
            target_table='participation_records',
            target_id=str(instance.id),
            details={
                'beneficiary_id': str(instance.beneficiary_id),
                'cycle_id': str(instance.cycle_id),
                'days_worked': instance.days_worked,
            },
        )


@receiver(post_save, sender='cycles.DailyParticipationRecord')
def log_daily_participation_record(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    if created:
        AuditLog.objects.create(
            user=instance.recorded_by,
            action='RECORDED_DAILY_PARTICIPATION',
            target_table='daily_participation_records',
            target_id=str(instance.id),
            details={
                'participation_id': str(instance.participation_id),
                'beneficiary_id': str(instance.participation.beneficiary_id),
                'cycle_id': str(instance.participation.cycle_id),
                'work_date': str(instance.work_date),
                'status': instance.status,
                'hours_worked': str(instance.hours_worked),
                'has_photo': bool(instance.photo),
            },
        )


@receiver(post_save, sender='users.User')
def log_resident_account_creation(sender, instance, created, **kwargs):
    from apps.audit.models import AuditLog
    if created and instance.role == 'resident':
        AuditLog.objects.create(
            user=None,
            action='CREATED_RESIDENT_ACCOUNT',
            target_table='users',
            target_id=str(instance.id),
            details={
                'username': instance.username,
                'first_name': instance.first_name,
                'middle_name': instance.middle_name,
                'last_name': instance.last_name,
                'full_name': instance.full_name,
            },
        )
