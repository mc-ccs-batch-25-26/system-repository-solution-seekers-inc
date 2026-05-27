from django.db import models
import uuid


class ProgramCycle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cycle_name = models.CharField(max_length=255, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    work_start_date = models.DateField(null=True, blank=True)
    work_end_date = models.DateField(null=True, blank=True)
    slots = models.PositiveIntegerField(default=0)
    max_per_household = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='created_cycles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'program_cycles'

    def __str__(self):
        return self.cycle_name


class ParticipationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    beneficiary = models.ForeignKey(
        'beneficiaries.Beneficiary',
        on_delete=models.PROTECT,
        related_name='participation_records',
    )
    cycle = models.ForeignKey(
        ProgramCycle,
        on_delete=models.PROTECT,
        related_name='participation_records',
    )
    project_name = models.CharField(max_length=255)
    days_worked = models.PositiveIntegerField()
    participation_start = models.DateField()
    participation_end = models.DateField()
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='recorded_participations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'participation_records'

    def save(self, *args, **kwargs):
        # INSERT-ONLY enforcement at the model layer
        if not self._state.adding:
            raise PermissionError('Participation records cannot be updated.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError('Participation records cannot be deleted.')

    def __str__(self):
        return f'{self.beneficiary.full_name} — {self.cycle.cycle_name}'

    def recalculate_days_worked(self):
        present_count = self.daily_records.filter(status=DailyParticipationRecord.STATUS_PRESENT).count()
        if self.days_worked != present_count:
            self.days_worked = present_count
            models.Model.save(self, update_fields=['days_worked'])
        return present_count


class DailyParticipationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_EXCUSED = 'excused'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present / Worked'),
        (STATUS_ABSENT, 'Absent / No Work'),
        (STATUS_EXCUSED, 'Excused'),
    ]

    participation = models.ForeignKey(
        ParticipationRecord,
        on_delete=models.PROTECT,
        related_name='daily_records',
    )
    work_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    remarks = models.TextField(blank=True, default='')
    photo = models.FileField(upload_to='daily_participation_photos/', null=True, blank=True)
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='recorded_daily_participations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_participation_records'
        unique_together = ['participation', 'work_date']
        ordering = ['work_date']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError('Daily participation records cannot be updated.')
        super().save(*args, **kwargs)
        self.participation.recalculate_days_worked()

    def delete(self, *args, **kwargs):
        raise PermissionError('Daily participation records cannot be deleted.')

    def __str__(self):
        return f'{self.participation.beneficiary.full_name} - {self.work_date} ({self.status})'


class CycleApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_APPLIED = 'applied'
    STATUS_SELECTED = 'selected'
    STATUS_DEFERRED = 'deferred'
    STATUS_CHOICES = [
        (STATUS_APPLIED, 'Applied'),
        (STATUS_SELECTED, 'Selected'),
        (STATUS_DEFERRED, 'Deferred'),
    ]

    beneficiary = models.ForeignKey(
        'beneficiaries.Beneficiary',
        on_delete=models.PROTECT,
        related_name='applications',
    )
    cycle = models.ForeignKey(
        ProgramCycle,
        on_delete=models.PROTECT,
        related_name='applications',
    )
    application_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    computed_score = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    rank_position = models.IntegerField(null=True, blank=True)
    applied_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='marked_applications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cycle_applications'
        unique_together = ['beneficiary', 'cycle']

    def __str__(self):
        return f'{self.beneficiary.full_name} — {self.cycle.cycle_name} ({self.status})'
