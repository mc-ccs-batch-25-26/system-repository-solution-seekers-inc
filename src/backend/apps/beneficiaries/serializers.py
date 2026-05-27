from rest_framework import serializers
from .models import Household, Family, Beneficiary, BeneficiaryIndicator, SECTOR_CHOICES
try:
    from ..audit.services import log_created, log_updated, snapshot
except ImportError:  # pragma: no cover - compatibility fallback for deployments using top-level `apps`
    from apps.audit.services import log_created, log_updated, snapshot


def _field(attrs, instance, field, default=None):
    """Return attrs[field] if present, otherwise fall back to the existing instance value."""
    return attrs.get(field, getattr(instance, field, default))


class UserStampMixin:
    """Injects the acting user into validated_data before the ORM save."""

    def _stamp_create(self, validated_data):
        validated_data['encoded_by'] = self.context['request'].user

    def _stamp_update(self, validated_data):
        validated_data['updated_by'] = self.context['request'].user


class HouseholdSerializer(UserStampMixin, serializers.ModelSerializer):
    encoded_by_name = serializers.CharField(source='encoded_by.full_name', read_only=True)
    family_count = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = [
            'id', 'household_code', 'address', 'status', 'purok',
            'house_no_or_blk_lot_no', 'street_name', 'purok_sitio',
            'landmark', 'length_of_residency',
            'encoded_by', 'encoded_by_name', 'updated_by',
            'family_count', 'is_deleted', 'deleted_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'address', 'purok', 'encoded_by', 'updated_by', 'is_deleted', 'deleted_at', 'deleted_by', 'created_at', 'updated_at']

    def get_family_count(self, obj):
        if hasattr(obj, 'family_count_value'):
            return obj.family_count_value
        return obj.families.count()

    def create(self, validated_data):
        self._stamp_create(validated_data)
        self._sync_structured_address(validated_data)
        instance = super().create(validated_data)
        log_created(instance, 'HOUSEHOLD', instance, self.context['request'].user)
        return instance

    def update(self, instance, validated_data):
        before = snapshot(instance, 'HOUSEHOLD')
        self._stamp_update(validated_data)
        self._sync_structured_address(validated_data, instance)
        instance = super().update(instance, validated_data)
        log_updated(instance, 'HOUSEHOLD', instance, before, self.context['request'].user)
        return instance

    def validate(self, attrs):
        instance = self.instance
        required_fields = ['house_no_or_blk_lot_no', 'street_name', 'purok_sitio']
        errors = {}
        for field in required_fields:
            value = attrs.get(field, getattr(instance, field, ''))
            if not str(value or '').strip():
                errors[field] = 'This structured address field is required.'
        length = attrs.get('length_of_residency', getattr(instance, 'length_of_residency', None))
        if length is not None and length < 0:
            errors['length_of_residency'] = 'Length of residency cannot be negative.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _sync_structured_address(self, validated_data, instance=None):
        house_no = validated_data.get('house_no_or_blk_lot_no', getattr(instance, 'house_no_or_blk_lot_no', ''))
        street = validated_data.get('street_name', getattr(instance, 'street_name', ''))
        purok = validated_data.get('purok_sitio', getattr(instance, 'purok_sitio', ''))
        landmark = validated_data.get('landmark', getattr(instance, 'landmark', ''))
        address_parts = [house_no, street, purok, 'Barangay Batobalani']
        if landmark:
            address_parts.append(f'Near {landmark}')
        validated_data['address'] = ', '.join(part for part in address_parts if str(part or '').strip())
        validated_data['purok'] = purok


class FamilySerializer(UserStampMixin, serializers.ModelSerializer):
    encoded_by_name = serializers.CharField(source='encoded_by.full_name', read_only=True)
    household_code = serializers.CharField(source='household.household_code', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = [
            'id', 'household', 'household_code', 'family_number',
            'monthly_income_bracket', 'encoded_by', 'encoded_by_name',
            'member_count', 'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'family_number', 'encoded_by', 'is_deleted', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        if hasattr(obj, 'member_count_value'):
            return obj.member_count_value
        return obj.members.count()

    def validate(self, attrs):
        instance = self.instance
        bracket = attrs.get('monthly_income_bracket', getattr(instance, 'monthly_income_bracket', None))
        if bracket == 'UNSPECIFIED':
            raise serializers.ValidationError({
                'monthly_income_bracket': '"Unspecified" cannot be used because "No Income" already exists as a valid option.'
            })
        return attrs

    def create(self, validated_data):
        self._stamp_create(validated_data)
        if 'family_number' not in validated_data:
            household = validated_data['household']
            last = Family.all_objects.filter(household=household).order_by('-family_number').first()
            validated_data['family_number'] = (last.family_number + 1) if last else 1
        instance = super().create(validated_data)
        log_created(instance, 'FAMILY', instance.household, self.context['request'].user)
        return instance

    def update(self, instance, validated_data):
        before = snapshot(instance, 'FAMILY')
        self._stamp_update(validated_data)
        instance = super().update(instance, validated_data)
        log_updated(instance, 'FAMILY', instance.household, before, self.context['request'].user)
        return instance


class BeneficiaryIndicatorSerializer(serializers.ModelSerializer):
    criterion_name = serializers.CharField(source='criterion.name', read_only=True)

    class Meta:
        model = BeneficiaryIndicator
        fields = ['id', 'criterion', 'criterion_name', 'value', 'raw_value', 'encoded_by', 'updated_at']
        read_only_fields = ['id', 'encoded_by', 'updated_at']


class BeneficiarySerializer(UserStampMixin, serializers.ModelSerializer):
    indicators = BeneficiaryIndicatorSerializer(many=True, read_only=True)
    encoded_by_name = serializers.CharField(source='encoded_by.full_name', read_only=True)
    family_detail = FamilySerializer(source='family', read_only=True)
    household_code = serializers.SerializerMethodField()

    class Meta:
        model = Beneficiary
        fields = [
            'id',
            # Hierarchy
            'family', 'family_detail', 'household', 'household_code',
            'role', 'is_household_head',
            # Fixed profile
            'first_name', 'middle_name', 'last_name',
            'full_name', 'address', 'birthdate', 'age', 'gender',
            'civil_status', 'contact_number',
            # Sectors + eligibility
            'sectors', 'is_tupad_eligible',
            # TUPAD indicators (flat)
            'monthly_income', 'employment_status', 'household_size',
            'lot_area_sqm', 'num_dependents', 'housing_condition',
            'structure_condition', 'tenure_status', 'electrical_condition',
            'water_source',
            # Soft delete
            'is_deleted', 'deleted_at',
            # Metadata
            'encoded_by', 'encoded_by_name', 'updated_by',
            'indicators', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'household', 'age', 'is_tupad_eligible',
            'is_deleted', 'deleted_at', 'encoded_by', 'updated_by',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        instance = self.instance
        family = _field(attrs, instance, 'family')
        role = _field(attrs, instance, 'role')
        birthdate = _field(attrs, instance, 'birthdate')
        gender = _field(attrs, instance, 'gender')
        civil_status = _field(attrs, instance, 'civil_status')
        sectors = _field(attrs, instance, 'sectors', default=[])
        is_household_head = _field(attrs, instance, 'is_household_head', default=False)

        errors = {}
        if family is None:
            errors['family'] = 'Resident profile must belong to a Family.'
        if not role:
            errors['role'] = 'Role is required.'
        if not birthdate:
            errors['birthdate'] = 'Birthdate is required.'
        if not gender:
            errors['gender'] = 'Gender is required.'
        if not civil_status:
            errors['civil_status'] = 'Civil status is required.'
        if not isinstance(sectors, list):
            errors['sectors'] = 'Sectors must be a list.'
        else:
            allowed = {code for code, _ in SECTOR_CHOICES}
            invalid = [code for code in sectors if code not in allowed]
            if invalid:
                errors['sectors'] = f'Invalid sector code(s): {", ".join(invalid)}.'

        effective_household_head = bool(is_household_head or role == 'head')
        if family and effective_household_head:
            attrs['is_household_head'] = True
            household_head_qs = Beneficiary.objects.filter(
                family__household=family.household,
                is_household_head=True,
            )
            if instance:
                household_head_qs = household_head_qs.exclude(pk=instance.pk)
            if household_head_qs.exists():
                errors['is_household_head'] = 'Only one resident profile per Household can be marked as household head.'
        duplicate_name = _field(attrs, instance, 'full_name', default='').strip()
        if not duplicate_name:
            name_parts = [
                _field(attrs, instance, 'first_name', default='').strip(),
                _field(attrs, instance, 'middle_name', default='').strip(),
                _field(attrs, instance, 'last_name', default='').strip(),
            ]
            duplicate_name = ' '.join(part for part in name_parts if part)
        if duplicate_name and birthdate:
            duplicate_qs = Beneficiary.objects.filter(
                full_name__iexact=duplicate_name,
                birthdate=birthdate,
            )
            if instance:
                duplicate_qs = duplicate_qs.exclude(pk=instance.pk)
            duplicate = duplicate_qs.first()
            if duplicate:
                errors['duplicate_resident'] = (
                    f'Possible duplicate resident profile: {duplicate.full_name} '
                    f'({duplicate.birthdate}) already exists.'
                )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_household_code(self, obj):
        if obj.family_id and obj.family.household_id:
            return obj.family.household.household_code
        if obj.household_id:
            return obj.household.household_code
        return None

    def create(self, validated_data):
        self._stamp_create(validated_data)
        if validated_data.get('family'):
            validated_data['household'] = validated_data['family'].household
        instance = super().create(validated_data)
        log_created(instance, 'BENEFICIARY', instance.family.household, self.context['request'].user)
        return instance

    def update(self, instance, validated_data):
        before = snapshot(instance, 'BENEFICIARY')
        self._stamp_update(validated_data)
        if validated_data.get('family'):
            validated_data['household'] = validated_data['family'].household
        instance = super().update(instance, validated_data)
        log_updated(instance, 'BENEFICIARY', instance.family.household, before, self.context['request'].user)
        return instance


class BeneficiaryIndicatorWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BeneficiaryIndicator
        fields = ['criterion', 'value', 'raw_value']

    def create(self, validated_data):
        beneficiary = self.context['beneficiary']
        if not beneficiary.is_tupad_eligible:
            raise serializers.ValidationError(
                'Indicators can only be encoded for TUPAD-eligible adult resident profiles.'
            )
        before = None
        try:
            before = snapshot(BeneficiaryIndicator.objects.get(
                beneficiary=beneficiary,
                criterion=validated_data['criterion'],
            ), 'INDICATOR')
        except BeneficiaryIndicator.DoesNotExist:
            pass
        validated_data['encoded_by'] = self.context['request'].user
        validated_data['beneficiary'] = beneficiary
        obj, created = BeneficiaryIndicator.objects.update_or_create(
            beneficiary=validated_data['beneficiary'],
            criterion=validated_data['criterion'],
            defaults={
                'value': validated_data['value'],
                'raw_value': validated_data.get('raw_value', str(validated_data['value'])),
                'encoded_by': validated_data['encoded_by'],
            },
        )
        if created:
            log_created(obj, 'INDICATOR', beneficiary.family.household, self.context['request'].user)
        elif before:
            log_updated(obj, 'INDICATOR', beneficiary.family.household, before, self.context['request'].user)
        return obj
