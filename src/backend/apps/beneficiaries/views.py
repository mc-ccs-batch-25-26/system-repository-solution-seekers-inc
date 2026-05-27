from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch, Q
from decimal import Decimal, InvalidOperation
from .models import Household, Family, Beneficiary, BeneficiaryIndicator
from .serializers import (
    HouseholdSerializer, FamilySerializer,
    BeneficiarySerializer, BeneficiaryIndicatorWriteSerializer,
)
from apps.users.permissions import IsAdminOrOfficial, IsResident
from apps.audit.models import ProfileChangeLog
from apps.audit.services import log_state_change


NO_PAGE_LIMIT = 500

INDICATOR_PREFETCH = Prefetch(
    'indicators',
    queryset=BeneficiaryIndicator.objects.select_related('criterion'),
)

# Base querysets shared by list and detail views to avoid duplication.
_HOUSEHOLD_QS = Household.objects.select_related('encoded_by').annotate(
    family_count_value=Count('families', distinct=True),
)
_BENEFICIARY_QS = Beneficiary.objects.select_related(
    'encoded_by', 'family', 'family__household', 'household'
).prefetch_related(INDICATOR_PREFETCH)
_FAMILY_QS = Family.objects.select_related('household', 'encoded_by').annotate(
    member_count_value=Count('members', distinct=True),
)


class HouseholdListCreateView(generics.ListCreateAPIView):
    serializer_class = HouseholdSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def get_queryset(self):
        qs = _HOUSEHOLD_QS
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(household_code__icontains=search) | Q(address__icontains=search))
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by('household_code')

    def list(self, request, *args, **kwargs):
        # ?no_page=true returns all records unpaginated — used by dropdown selects
        if request.query_params.get('no_page'):
            qs = self.filter_queryset(self.get_queryset())[:NO_PAGE_LIMIT]
            return Response(self.get_serializer(qs, many=True).data)
        return super().list(request, *args, **kwargs)


class HouseholdDetailView(generics.RetrieveUpdateAPIView):
    queryset = _HOUSEHOLD_QS
    serializer_class = HouseholdSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]


class HouseholdSoftDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def delete(self, request, pk):
        hh = get_object_or_404(Household, pk=pk)
        hh.soft_delete(deleted_by_user=request.user)
        log_state_change(hh, 'HOUSEHOLD', hh, ProfileChangeLog.Action.SOFT_DELETED, request.user)
        return Response({'detail': 'Household soft-deleted.'}, status=status.HTTP_200_OK)

    def post(self, request, pk):
        hh = get_object_or_404(Household.all_objects, pk=pk)
        hh.restore()
        log_state_change(hh, 'HOUSEHOLD', hh, ProfileChangeLog.Action.RESTORED, request.user)
        return Response({'detail': 'Household restored.'}, status=status.HTTP_200_OK)


class FamilyListCreateView(generics.ListCreateAPIView):
    serializer_class = FamilySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def get_queryset(self):
        qs = _FAMILY_QS
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(household_id=household_id)
        return qs.order_by('household__household_code', 'family_number')


class FamilyDetailView(generics.RetrieveUpdateAPIView):
    queryset = _FAMILY_QS
    serializer_class = FamilySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]


class BeneficiaryListCreateView(generics.ListCreateAPIView):
    serializer_class = BeneficiarySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def get_queryset(self):
        qs = _BENEFICIARY_QS
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(full_name__icontains=search)
        family_id = self.request.query_params.get('family')
        if family_id:
            qs = qs.filter(family_id=family_id)
        household_id = self.request.query_params.get('household')
        if household_id:
            qs = qs.filter(family__household_id=household_id)
        eligible = self.request.query_params.get('eligible')
        if eligible == 'true':
            qs = qs.filter(is_tupad_eligible=True)
        sector = self.request.query_params.get('sector')
        if sector:
            qs = qs.filter(sectors__contains=[sector])
        participation_status = self.request.query_params.get('participation_status')
        if participation_status == 'participated':
            qs = qs.filter(participation_records__isnull=False)
        elif participation_status == 'not_participated':
            qs = qs.filter(participation_records__isnull=True)

        min_score = self.request.query_params.get('min_score')
        max_score = self.request.query_params.get('max_score')
        if min_score not in (None, ''):
            try:
                qs = qs.filter(applications__computed_score__gte=Decimal(min_score))
            except InvalidOperation:
                pass
        if max_score not in (None, ''):
            try:
                qs = qs.filter(applications__computed_score__lte=Decimal(max_score))
            except InvalidOperation:
                pass
        return qs.distinct().order_by('full_name')


class BeneficiaryDetailView(generics.RetrieveUpdateAPIView):
    queryset = _BENEFICIARY_QS
    serializer_class = BeneficiarySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]


class BeneficiarySoftDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def delete(self, request, pk):
        b = get_object_or_404(Beneficiary, pk=pk)
        b.soft_delete(deleted_by_user=request.user)
        log_state_change(b, 'BENEFICIARY', b.family.household, ProfileChangeLog.Action.SOFT_DELETED, request.user)
        return Response({'detail': 'Resident profile soft-deleted.'}, status=status.HTTP_200_OK)

    def post(self, request, pk):
        b = get_object_or_404(Beneficiary.all_objects, pk=pk)
        b.restore()
        log_state_change(b, 'BENEFICIARY', b.family.household, ProfileChangeLog.Action.RESTORED, request.user)
        return Response({'detail': 'Resident profile restored.'}, status=status.HTTP_200_OK)


class ResidentProfileView(APIView):
    """GET /api/resident-profiles/me/ - resident reads their own profile."""
    permission_classes = [IsAuthenticated, IsResident]

    def get(self, request):
        # OneToOne reverse accessor raises RelatedObjectDoesNotExist (not None) when missing.
        try:
            beneficiary = request.user.beneficiary
        except Beneficiary.DoesNotExist:
            return Response(
                {'detail': 'No resident profile linked to this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = Beneficiary.objects.select_related(
            'encoded_by', 'family', 'family__household', 'household'
        ).prefetch_related(INDICATOR_PREFETCH).get(pk=beneficiary.pk)
        return Response(BeneficiarySerializer(instance).data)


class BeneficiaryIndicatorView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def post(self, request, pk):
        beneficiary = get_object_or_404(Beneficiary, pk=pk)
        serializer = BeneficiaryIndicatorWriteSerializer(
            data=request.data,
            context={'request': request, 'beneficiary': beneficiary},
        )
        serializer.is_valid(raise_exception=True)
        indicator = serializer.save()
        return Response(
            BeneficiaryIndicatorWriteSerializer(indicator).data,
            status=status.HTTP_201_CREATED,
        )
