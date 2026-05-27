from datetime import timedelta
from decimal import Decimal
import base64
import binascii
import uuid

from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import serializers
from .models import ProgramCycle, ParticipationRecord, DailyParticipationRecord, CycleApplication


def _field(attrs, instance, field, default=None):
    """Return attrs[field] if present, otherwise fall back to the existing instance value."""
    return attrs.get(field, getattr(instance, field, default))


class ProgramCycleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    application_start_date = serializers.DateField(source='start_date', required=False)
    application_end_date = serializers.DateField(source='end_date', required=False)

    class Meta:
        model = ProgramCycle
        fields = [
            'id', 'cycle_name',
            'start_date', 'end_date',
            'application_start_date', 'application_end_date',
            'work_start_date', 'work_end_date',
            'slots', 'max_per_household',
            'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']
        extra_kwargs = {
            'start_date': {'required': False},
            'end_date': {'required': False},
        }

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, attrs):
        instance = self.instance
        start_date = _field(attrs, instance, 'start_date')
        end_date = _field(attrs, instance, 'end_date')
        work_start_date = _field(attrs, instance, 'work_start_date')
        work_end_date = _field(attrs, instance, 'work_end_date')
        slots = _field(attrs, instance, 'slots')
        max_per_household = _field(attrs, instance, 'max_per_household')

        errors = {}
        cycle_name = _field(attrs, instance, 'cycle_name')
        if cycle_name:
            duplicate_qs = ProgramCycle.objects.filter(cycle_name__iexact=cycle_name)
            if instance:
                duplicate_qs = duplicate_qs.exclude(pk=instance.pk)
            if duplicate_qs.exists():
                errors['cycle_name'] = 'A program cycle with this name already exists.'
        if not start_date:
            errors['application_start_date'] = 'Application start date is required.'
        if not end_date:
            errors['application_end_date'] = 'Application end date is required.'
        if not work_start_date:
            errors['work_start_date'] = 'TUPAD work start date is required.'
        if not work_end_date:
            errors['work_end_date'] = 'TUPAD work end date is required.'
        if start_date and end_date and end_date < start_date:
            errors['application_end_date'] = 'Application end date cannot be before application start date.'
        if work_start_date and work_end_date and work_end_date < work_start_date:
            errors['work_end_date'] = 'TUPAD work end date cannot be before work start date.'
        if end_date and work_start_date and work_start_date < end_date:
            errors['work_start_date'] = 'TUPAD work start date should be on or after the application end date.'
        if slots is not None and slots < 1:
            errors['slots'] = 'Slots must be at least 1.'
        if max_per_household is not None and max_per_household < 1:
            errors['max_per_household'] = 'Maximum per household must be at least 1.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class DailyParticipationRecordSerializer(serializers.ModelSerializer):
    photo_data = serializers.CharField(write_only=True, required=False, allow_blank=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = DailyParticipationRecord
        fields = [
            'id', 'work_date', 'status', 'hours_worked', 'remarks',
            'photo', 'photo_url', 'photo_data', 'recorded_by', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get('request')
        url = obj.photo.url
        return request.build_absolute_uri(url) if request else url


class ParticipationRecordSerializer(serializers.ModelSerializer):
    beneficiary_name = serializers.CharField(source='beneficiary.full_name', read_only=True)
    cycle_name = serializers.CharField(source='cycle.cycle_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    daily_records = DailyParticipationRecordSerializer(many=True, read_only=True)

    class Meta:
        model = ParticipationRecord
        fields = [
            'id', 'beneficiary', 'beneficiary_name', 'cycle', 'cycle_name',
            'project_name', 'days_worked', 'participation_start', 'participation_end',
            'recorded_by', 'recorded_by_name', 'daily_records', 'created_at',
        ]
        read_only_fields = ['id', 'days_worked', 'recorded_by', 'created_at']

    def validate(self, attrs):
        instance = self.instance
        beneficiary = _field(attrs, instance, 'beneficiary')
        cycle = _field(attrs, instance, 'cycle')
        participation_start = _field(attrs, instance, 'participation_start')
        participation_end = _field(attrs, instance, 'participation_end')
        if participation_start and participation_end and participation_end < participation_start:
            raise serializers.ValidationError({
                'participation_end': 'Participation end date cannot be before start date.'
            })
        if beneficiary and cycle:
            is_selected = CycleApplication.objects.filter(
                beneficiary=beneficiary,
                cycle=cycle,
                status=CycleApplication.STATUS_SELECTED,
            ).exists()
            if not is_selected:
                raise serializers.ValidationError(
                    'Participation can only be recorded for selected cycle applicants.'
                )
            if cycle.work_start_date and participation_start and participation_start < cycle.work_start_date:
                raise serializers.ValidationError({
                    'participation_start': 'Participation start date must be within the TUPAD work period.'
                })
            if cycle.work_end_date and participation_end and participation_end > cycle.work_end_date:
                raise serializers.ValidationError({
                    'participation_end': 'Participation end date must be within the TUPAD work period.'
                })
        return attrs

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        validated_data['days_worked'] = 0
        return super().create(validated_data)


class DailyAttendanceCreateSerializer(serializers.Serializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=ProgramCycle.objects.all())
    beneficiary = serializers.PrimaryKeyRelatedField(queryset=CycleApplication.objects.none())
    project_name = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=DailyParticipationRecord.STATUS_CHOICES)
    hours_worked = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal('0'), required=False)
    remarks = serializers.CharField(required=False, allow_blank=True)
    photo_data = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.beneficiaries.models import Beneficiary
        self.fields['beneficiary'].queryset = Beneficiary.objects.all()

    def validate(self, attrs):
        cycle = attrs['cycle']
        beneficiary = attrs['beneficiary']
        today = timezone.localdate()

        if not cycle.work_start_date or not cycle.work_end_date:
            raise serializers.ValidationError({
                'cycle': 'This cycle has no TUPAD work period configured.'
            })
        if today < cycle.work_start_date or today > cycle.work_end_date:
            raise serializers.ValidationError({
                'work_date': (
                    'Daily attendance can only be recorded during the TUPAD work period '
                    f'({cycle.work_start_date} to {cycle.work_end_date}).'
                )
            })
        is_selected = CycleApplication.objects.filter(
            beneficiary=beneficiary,
            cycle=cycle,
            status=CycleApplication.STATUS_SELECTED,
        ).exists()
        if not is_selected:
            raise serializers.ValidationError({
                'beneficiary': 'Daily attendance can only be recorded for selected cycle applicants.'
            })
        participation = ParticipationRecord.objects.filter(
            beneficiary=beneficiary,
            cycle=cycle,
        ).order_by('created_at').first()
        if DailyParticipationRecord.objects.filter(
            participation__beneficiary=beneficiary,
            participation__cycle=cycle,
            work_date=today,
        ).exists():
            raise serializers.ValidationError({
                'work_date': 'Attendance for today has already been recorded and cannot be modified.'
            })

        if attrs['status'] != DailyParticipationRecord.STATUS_PRESENT:
            attrs['hours_worked'] = 0
        elif attrs.get('hours_worked') in (None, ''):
            attrs['hours_worked'] = 8

        attrs['work_date'] = today
        attrs['participation'] = participation
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        cycle = validated_data['cycle']
        beneficiary = validated_data['beneficiary']
        participation = validated_data.pop('participation')
        photo_data = validated_data.pop('photo_data', '')
        photo_file = _photo_file_from_data_url(photo_data, field_name='photo_data') if photo_data else None

        if participation is None:
            participation = ParticipationRecord.objects.create(
                beneficiary=beneficiary,
                cycle=cycle,
                project_name=validated_data['project_name'],
                days_worked=0,
                participation_start=cycle.work_start_date,
                participation_end=cycle.work_end_date,
                recorded_by=request.user,
            )

        return DailyParticipationRecord.objects.create(
            participation=participation,
            work_date=validated_data['work_date'],
            status=validated_data['status'],
            hours_worked=validated_data['hours_worked'],
            remarks=validated_data.get('remarks', ''),
            photo=photo_file,
            recorded_by=request.user,
        )


class CycleApplicationSerializer(serializers.ModelSerializer):
    beneficiary_name = serializers.CharField(source='beneficiary.full_name', read_only=True)
    applied_by_name = serializers.CharField(source='applied_by.full_name', read_only=True)

    class Meta:
        model = CycleApplication
        fields = [
            'id', 'beneficiary', 'beneficiary_name', 'cycle',
            'application_date', 'status',
            'computed_score', 'rank_position',
            'applied_by', 'applied_by_name', 'created_at',
        ]
        read_only_fields = [
            'id', 'application_date', 'status',
            'computed_score', 'rank_position',
            'applied_by', 'applied_by_name', 'created_at',
        ]

    def validate(self, attrs):
        beneficiary = attrs.get('beneficiary', getattr(self.instance, 'beneficiary', None))
        if beneficiary and not beneficiary.is_tupad_eligible:
            raise serializers.ValidationError({
                'beneficiary': 'Only TUPAD-eligible adult beneficiaries can be marked as applicants.'
            })
        return attrs

    def create(self, validated_data):
        validated_data['applied_by'] = self.context['request'].user
        return super().create(validated_data)


def _date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _inclusive_day_count(start_date, end_date):
    return (end_date - start_date).days + 1


def _photo_file_from_data_url(data_url, field_name='daily_records'):
    if ';base64,' not in data_url:
        raise serializers.ValidationError({field_name: 'Invalid photo data.'})
    header, encoded = data_url.split(';base64,', 1)
    extension = header.split('/')[-1].lower()
    if extension not in {'jpg', 'jpeg', 'png', 'webp'}:
        raise serializers.ValidationError({field_name: 'Daily attendance photos must be JPG, PNG, or WEBP.'})
    try:
        decoded = base64.b64decode(encoded)
    except (binascii.Error, ValueError) as exc:
        raise serializers.ValidationError({field_name: 'Invalid photo data.'}) from exc
    if len(decoded) > 5 * 1024 * 1024:
        raise serializers.ValidationError({field_name: 'Daily attendance photos must be 5MB or smaller.'})
    return ContentFile(decoded, name=f'{uuid.uuid4()}.{extension}')
