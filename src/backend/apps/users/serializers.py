from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'middle_name', 'last_name',
            'full_name', 'position', 'organization', 'role', 'is_active',
            'beneficiary', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            'username', 'password', 'first_name', 'middle_name', 'last_name',
            'full_name', 'position', 'organization', 'role', 'is_active', 'beneficiary',
        ]

    def validate(self, attrs):
        role = attrs.get('role', User.ROLE_OFFICIAL)
        beneficiary = attrs.get('beneficiary')
        if role == User.ROLE_RESIDENT and beneficiary is None:
            raise serializers.ValidationError({
                'beneficiary': 'A resident account must be linked to an existing resident profile.'
            })
        if role != User.ROLE_RESIDENT and beneficiary is not None:
            raise serializers.ValidationError({
                'beneficiary': 'Only resident accounts can be linked to resident profiles.'
            })
        if role in {User.ROLE_ADMIN, User.ROLE_OFFICIAL}:
            if not attrs.get('position', '').strip():
                raise serializers.ValidationError({'position': 'Position is required for barangay staff accounts.'})
            if not attrs.get('organization', '').strip():
                raise serializers.ValidationError({'organization': 'Organization is required for barangay staff accounts.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'middle_name', 'last_name',
            'full_name', 'position', 'organization', 'role', 'is_active', 'beneficiary',
        ]

    def validate(self, attrs):
        role = attrs.get('role', getattr(self.instance, 'role', User.ROLE_OFFICIAL))
        beneficiary = attrs.get('beneficiary', getattr(self.instance, 'beneficiary', None))
        if role == User.ROLE_RESIDENT and beneficiary is None:
            raise serializers.ValidationError({
                'beneficiary': 'A resident account must be linked to an existing resident profile.'
            })
        if role != User.ROLE_RESIDENT and beneficiary is not None:
            raise serializers.ValidationError({
                'beneficiary': 'Only resident accounts can be linked to resident profiles.'
            })
        if role in {User.ROLE_ADMIN, User.ROLE_OFFICIAL}:
            position = attrs.get('position', getattr(self.instance, 'position', ''))
            organization = attrs.get('organization', getattr(self.instance, 'organization', ''))
            if not position.strip():
                raise serializers.ValidationError({'position': 'Position is required for barangay staff accounts.'})
            if not organization.strip():
                raise serializers.ValidationError({'organization': 'Organization is required for barangay staff accounts.'})
        return attrs


class UserPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def save(self, **kwargs):
        user = self.context['user']
        user.set_password(self.validated_data['password'])
        user.save(update_fields=['password'])
        return user
