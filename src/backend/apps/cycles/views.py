from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from .models import ProgramCycle, ParticipationRecord, CycleApplication
from .serializers import (
    DailyAttendanceCreateSerializer,
    DailyParticipationRecordSerializer,
    ProgramCycleSerializer,
    ParticipationRecordSerializer,
    CycleApplicationSerializer,
)
from apps.users.permissions import IsAdminOrOfficial


class ProgramCycleListCreateView(generics.ListCreateAPIView):
    queryset = ProgramCycle.objects.select_related('created_by').order_by('-created_at')
    serializer_class = ProgramCycleSerializer

    def get_permissions(self):
        # Residents can read the cycle list (needed for transparency view)
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminOrOfficial()]
        return [IsAuthenticated()]


class ProgramCycleDetailView(generics.RetrieveAPIView):
    queryset = ProgramCycle.objects.all()
    serializer_class = ProgramCycleSerializer
    permission_classes = [IsAuthenticated]


class ParticipationRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = ParticipationRecordSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminOrOfficial()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = ParticipationRecord.objects.select_related(
            'beneficiary', 'cycle', 'recorded_by'
        ).prefetch_related('daily_records')
        user = self.request.user
        # Residents see only their own participation records
        if user.is_resident:
            return qs.filter(beneficiary=user.beneficiary).order_by('-created_at')
        cycle_id = self.request.query_params.get('cycle')
        beneficiary_id = self.request.query_params.get('beneficiary')
        if cycle_id:
            qs = qs.filter(cycle_id=cycle_id)
        if beneficiary_id:
            qs = qs.filter(beneficiary_id=beneficiary_id)
        return qs.order_by('-created_at')


class DailyAttendanceCreateView(generics.CreateAPIView):
    serializer_class = DailyAttendanceCreateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        daily_record = serializer.save()
        output = DailyParticipationRecordSerializer(
            daily_record,
            context={'request': request},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)


class CycleApplicationListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/cycles/<cycle_pk>/applications/ — list all applications for a cycle
    POST /api/cycles/<cycle_pk>/applications/ — mark a beneficiary as APPLIED
    """
    serializer_class = CycleApplicationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOfficial]
    pagination_class = None

    def get_queryset(self):
        return (
            CycleApplication.objects
            .select_related('beneficiary', 'applied_by')
            .filter(cycle_id=self.kwargs['cycle_pk'])
            .order_by('created_at')
        )

    def create(self, request, *args, **kwargs):
        cycle_pk = self.kwargs['cycle_pk']
        cycle = generics.get_object_or_404(ProgramCycle, pk=cycle_pk)
        today = timezone.localdate()
        if today < cycle.start_date or today > cycle.end_date:
            raise ValidationError({
                'detail': (
                    'Applicant marking is allowed only during the application period '
                    f'({cycle.start_date} to {cycle.end_date}).'
                )
            })
        is_ranked = CycleApplication.objects.filter(
            cycle_id=cycle_pk,
            status__in=[
                CycleApplication.STATUS_SELECTED,
                CycleApplication.STATUS_DEFERRED,
            ],
        ).exists()
        if is_ranked:
            raise ValidationError({
                'detail': 'This cycle already has ranking results. Applicant marking is locked.'
            })
        data = {**request.data, 'cycle': cycle_pk}
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
