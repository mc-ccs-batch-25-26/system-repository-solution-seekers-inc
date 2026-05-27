from datetime import date
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from apps.beneficiaries.models import Beneficiary, Family, Household
from apps.cycles.models import CycleApplication, DailyParticipationRecord, ParticipationRecord, ProgramCycle
from apps.cycles.serializers import DailyAttendanceCreateSerializer, ParticipationRecordSerializer, ProgramCycleSerializer
from apps.users.models import User


class ProgramCycleDateValidationTests(TestCase):
    def setUp(self):
        self.official = User.objects.create_user(
            username='official2',
            password='Official12345',
            first_name='Barangay',
            last_name='Official',
            full_name='Barangay Official',
            role=User.ROLE_OFFICIAL,
            position='Encoder',
            organization='Barangay Batobalani',
            email='official2@example.com',
        )
        self.request = RequestFactory().post('/')
        self.request.user = self.official

    def test_cycle_requires_valid_application_and_work_periods(self):
        serializer = ProgramCycleSerializer(
            data={
                'cycle_name': 'Invalid Date Cycle',
                'application_start_date': '2026-06-10',
                'application_end_date': '2026-06-01',
                'work_start_date': '2026-05-30',
                'work_end_date': '2026-06-20',
                'slots': 10,
                'max_per_household': 1,
            },
            context={'request': self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('application_end_date', serializer.errors)
        self.assertIn('work_start_date', serializer.errors)

    def test_participation_dates_must_fit_work_period(self):
        household = Household.objects.create(
            household_code='HH-CYCLE-001',
            address='Blk 1, Rizal Street, Purok 1, Barangay Batobalani',
            house_no_or_blk_lot_no='Blk 1',
            street_name='Rizal Street',
            purok_sitio='Purok 1',
            encoded_by=self.official,
        )
        family = Family.objects.create(
            household=household,
            family_number=1,
            monthly_income_bracket='NO_INCOME',
            encoded_by=self.official,
        )
        beneficiary = Beneficiary.objects.create(
            family=family,
            role='head',
            first_name='Pedro',
            last_name='Worker',
            full_name='Pedro Worker',
            birthdate=date(1985, 1, 1),
            gender='male',
            civil_status='married',
            encoded_by=self.official,
        )
        cycle = ProgramCycle.objects.create(
            cycle_name='Work Period Cycle',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            work_start_date=date(2026, 6, 10),
            work_end_date=date(2026, 6, 20),
            slots=5,
            max_per_household=1,
            created_by=self.official,
        )
        CycleApplication.objects.create(
            beneficiary=beneficiary,
            cycle=cycle,
            status=CycleApplication.STATUS_SELECTED,
            applied_by=self.official,
        )

        serializer = ParticipationRecordSerializer(
            data={
                'beneficiary': beneficiary.id,
                'cycle': cycle.id,
                'project_name': 'Road Clearing',
                'days_worked': 5,
                'participation_start': '2026-06-09',
                'participation_end': '2026-06-21',
            },
            context={'request': self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('participation_start', serializer.errors)

    def test_daily_attendance_uses_today_and_computes_days_worked(self):
        household = Household.objects.create(
            household_code='HH-CYCLE-002',
            address='Blk 2, Rizal Street, Purok 1, Barangay Batobalani',
            house_no_or_blk_lot_no='Blk 2',
            street_name='Rizal Street',
            purok_sitio='Purok 1',
            encoded_by=self.official,
        )
        family = Family.objects.create(
            household=household,
            family_number=1,
            monthly_income_bracket='NO_INCOME',
            encoded_by=self.official,
        )
        beneficiary = Beneficiary.objects.create(
            family=family,
            role='head',
            first_name='Ana',
            last_name='Worker',
            full_name='Ana Worker',
            birthdate=date(1988, 1, 1),
            gender='female',
            civil_status='married',
            encoded_by=self.official,
        )
        cycle = ProgramCycle.objects.create(
            cycle_name='Daily Attendance Cycle',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            work_start_date=date(2026, 6, 10),
            work_end_date=date(2026, 6, 20),
            slots=5,
            max_per_household=1,
            created_by=self.official,
        )
        CycleApplication.objects.create(
            beneficiary=beneficiary,
            cycle=cycle,
            status=CycleApplication.STATUS_SELECTED,
            applied_by=self.official,
        )

        with patch('apps.cycles.serializers.timezone.localdate', return_value=date(2026, 6, 10)):
            serializer = DailyAttendanceCreateSerializer(
                data={
                    'beneficiary': beneficiary.id,
                    'cycle': cycle.id,
                    'project_name': 'Road Clearing',
                    'status': 'present',
                    'hours_worked': 8,
                    'remarks': '',
                },
                context={'request': self.request},
            )

            self.assertTrue(serializer.is_valid(), serializer.errors)
            daily_record = serializer.save()

        participation = daily_record.participation
        self.assertEqual(participation.days_worked, 1)
        self.assertEqual(daily_record.work_date, date(2026, 6, 10))
        self.assertEqual(DailyParticipationRecord.objects.filter(participation=participation).count(), 1)

    def test_daily_attendance_rejects_duplicate_today_record(self):
        household = Household.objects.create(
            household_code='HH-CYCLE-003',
            address='Blk 3, Rizal Street, Purok 1, Barangay Batobalani',
            house_no_or_blk_lot_no='Blk 3',
            street_name='Rizal Street',
            purok_sitio='Purok 1',
            encoded_by=self.official,
        )
        family = Family.objects.create(
            household=household,
            family_number=1,
            monthly_income_bracket='NO_INCOME',
            encoded_by=self.official,
        )
        beneficiary = Beneficiary.objects.create(
            family=family,
            role='head',
            first_name='Liza',
            last_name='Worker',
            full_name='Liza Worker',
            birthdate=date(1988, 1, 1),
            gender='female',
            civil_status='married',
            encoded_by=self.official,
        )
        cycle = ProgramCycle.objects.create(
            cycle_name='Missing Daily Attendance Cycle',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            work_start_date=date(2026, 6, 10),
            work_end_date=date(2026, 6, 20),
            slots=5,
            max_per_household=1,
            created_by=self.official,
        )
        CycleApplication.objects.create(
            beneficiary=beneficiary,
            cycle=cycle,
            status=CycleApplication.STATUS_SELECTED,
            applied_by=self.official,
        )
        participation = ParticipationRecord.objects.create(
            beneficiary=beneficiary,
            cycle=cycle,
            project_name='Road Clearing',
            days_worked=0,
            participation_start=cycle.work_start_date,
            participation_end=cycle.work_end_date,
            recorded_by=self.official,
        )
        DailyParticipationRecord.objects.create(
            participation=participation,
            work_date=date(2026, 6, 10),
            status=DailyParticipationRecord.STATUS_PRESENT,
            hours_worked=8,
            recorded_by=self.official,
        )

        with patch('apps.cycles.serializers.timezone.localdate', return_value=date(2026, 6, 10)):
            serializer = DailyAttendanceCreateSerializer(
                data={
                    'beneficiary': beneficiary.id,
                    'cycle': cycle.id,
                    'project_name': 'Road Clearing',
                    'status': 'present',
                    'hours_worked': 8,
                    'remarks': '',
                },
                context={'request': self.request},
            )

            self.assertFalse(serializer.is_valid())
            self.assertIn('work_date', serializer.errors)

    def test_daily_attendance_rejects_dates_outside_work_period(self):
        household = Household.objects.create(
            household_code='HH-CYCLE-004',
            address='Blk 4, Rizal Street, Purok 1, Barangay Batobalani',
            house_no_or_blk_lot_no='Blk 4',
            street_name='Rizal Street',
            purok_sitio='Purok 1',
            encoded_by=self.official,
        )
        family = Family.objects.create(
            household=household,
            family_number=1,
            monthly_income_bracket='NO_INCOME',
            encoded_by=self.official,
        )
        beneficiary = Beneficiary.objects.create(
            family=family,
            role='head',
            first_name='Mario',
            last_name='Worker',
            full_name='Mario Worker',
            birthdate=date(1988, 1, 1),
            gender='male',
            civil_status='married',
            encoded_by=self.official,
        )
        cycle = ProgramCycle.objects.create(
            cycle_name='Closed Daily Attendance Cycle',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            work_start_date=date(2026, 6, 10),
            work_end_date=date(2026, 6, 20),
            slots=5,
            max_per_household=1,
            created_by=self.official,
        )
        CycleApplication.objects.create(
            beneficiary=beneficiary,
            cycle=cycle,
            status=CycleApplication.STATUS_SELECTED,
            applied_by=self.official,
        )

        with patch('apps.cycles.serializers.timezone.localdate', return_value=date(2026, 6, 21)):
            serializer = DailyAttendanceCreateSerializer(
                data={
                    'beneficiary': beneficiary.id,
                    'cycle': cycle.id,
                    'project_name': 'Road Clearing',
                    'status': 'present',
                    'hours_worked': 8,
                    'remarks': '',
                },
                context={'request': self.request},
            )

            self.assertFalse(serializer.is_valid())
            self.assertIn('work_date', serializer.errors)
