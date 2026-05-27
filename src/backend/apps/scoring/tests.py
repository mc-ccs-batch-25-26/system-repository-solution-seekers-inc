from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.beneficiaries.models import Beneficiary, BeneficiaryIndicator, Family, Household
from apps.criteria.models import Criterion
from apps.cycles.models import CycleApplication, ParticipationRecord, ProgramCycle
from apps.scoring.engine import run_ranking
from apps.users.models import User


class RankingEngineTests(TestCase):
    def setUp(self):
        self.official = User.objects.create_user(
            username='official',
            password='Official12345',
            first_name='Barangay',
            last_name='Official',
            full_name='Barangay Official',
            role=User.ROLE_OFFICIAL,
            email='official@example.com',
        )
        self.criterion = Criterion.objects.create(
            name='Need Score',
            weight=Decimal('1.0000'),
            type=Criterion.TYPE_BENEFIT,
            updated_by=self.official,
        )
        self.household = Household.objects.create(
            household_code='HH-001',
            address='Test Address',
            encoded_by=self.official,
        )
        self.family = Family.objects.create(
            household=self.household,
            family_number=1,
            encoded_by=self.official,
        )

    def make_beneficiary(self, name, value):
        beneficiary = Beneficiary.objects.create(
            family=self.family,
            role='child',
            first_name=name,
            last_name='Resident',
            full_name=f'{name} Resident',
            birthdate=date(1990, 1, 1),
            gender='male',
            civil_status='single',
            encoded_by=self.official,
        )
        BeneficiaryIndicator.objects.create(
            beneficiary=beneficiary,
            criterion=self.criterion,
            value=Decimal(str(value)),
            raw_value=str(value),
            encoded_by=self.official,
        )
        return beneficiary

    def make_cycle(self, name, slots, max_per_household=1):
        return ProgramCycle.objects.create(
            cycle_name=name,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            slots=slots,
            max_per_household=max_per_household,
            created_by=self.official,
        )

    def apply(self, cycle, beneficiary):
        return CycleApplication.objects.create(
            cycle=cycle,
            beneficiary=beneficiary,
            applied_by=self.official,
        )

    def test_ranking_orders_by_score_before_prior_participation_tiebreak(self):
        high_score_prior = self.make_beneficiary('High', 100)
        low_score_first_time = self.make_beneficiary('Low', 10)

        old_cycle = self.make_cycle('Old Cycle', 1)
        ParticipationRecord.objects.create(
            beneficiary=high_score_prior,
            cycle=old_cycle,
            project_name='Old Project',
            days_worked=10,
            participation_start=date(2025, 1, 1),
            participation_end=date(2025, 1, 10),
            recorded_by=self.official,
        )

        cycle = self.make_cycle('Current Cycle', 1)
        self.apply(cycle, high_score_prior)
        self.apply(cycle, low_score_first_time)

        results = run_ranking(cycle)

        self.assertEqual(results[0]['beneficiary_id'], high_score_prior.id)
        self.assertEqual(results[0]['rank'], 1)
        self.assertEqual(results[0]['status'], CycleApplication.STATUS_SELECTED)

    def test_ranking_still_computes_scores_when_all_applicants_fit_slots(self):
        top = self.make_beneficiary('Top', 100)
        bottom = self.make_beneficiary('Bottom', 10)
        cycle = self.make_cycle('Enough Slots Cycle', 2, max_per_household=2)
        self.apply(cycle, top)
        self.apply(cycle, bottom)

        results = run_ranking(cycle)
        applications = {
            app.beneficiary_id: app
            for app in CycleApplication.objects.filter(cycle=cycle)
        }

        self.assertEqual([row['rank'] for row in results], [1, 2])
        self.assertEqual(applications[top.id].status, CycleApplication.STATUS_SELECTED)
        self.assertEqual(applications[bottom.id].status, CycleApplication.STATUS_SELECTED)
        self.assertIsNotNone(applications[top.id].computed_score)
        self.assertIsNotNone(applications[bottom.id].computed_score)
        self.assertEqual(applications[top.id].rank_position, 1)
        self.assertEqual(applications[bottom.id].rank_position, 2)

    def test_household_deferred_applicants_keep_score_and_rank(self):
        top = self.make_beneficiary('HouseholdTop', 100)
        bottom = self.make_beneficiary('HouseholdBottom', 10)
        cycle = self.make_cycle('Household Limit Cycle', 2, max_per_household=1)
        self.apply(cycle, top)
        self.apply(cycle, bottom)

        results = run_ranking(cycle)
        applications = {
            app.beneficiary_id: app
            for app in CycleApplication.objects.filter(cycle=cycle)
        }
        bottom_result = next(row for row in results if row['beneficiary_id'] == bottom.id)

        self.assertEqual(applications[top.id].status, CycleApplication.STATUS_SELECTED)
        self.assertEqual(applications[bottom.id].status, CycleApplication.STATUS_DEFERRED)
        self.assertTrue(bottom_result['deferred_by_household'])
        self.assertIsNotNone(applications[bottom.id].computed_score)
        self.assertEqual(applications[bottom.id].rank_position, 2)
