from datetime import date

from django.test import RequestFactory, TestCase

from apps.beneficiaries.models import Beneficiary, Family, Household
from apps.beneficiaries.serializers import BeneficiarySerializer, FamilySerializer, HouseholdSerializer
from apps.users.models import User


class ProfileValidationTests(TestCase):
    def setUp(self):
        self.official = User.objects.create_user(
            username='official',
            password='Official12345',
            first_name='Barangay',
            last_name='Official',
            full_name='Barangay Official',
            role=User.ROLE_OFFICIAL,
            position='Encoder',
            organization='Barangay Batobalani',
            email='official@example.com',
        )
        self.request = RequestFactory().post('/')
        self.request.user = self.official
        self.household = Household.objects.create(
            household_code='HH-001',
            address='Blk 1, Rizal Street, Purok 1, Barangay Batobalani',
            house_no_or_blk_lot_no='Blk 1',
            street_name='Rizal Street',
            purok_sitio='Purok 1',
            encoded_by=self.official,
        )
        self.family = Family.objects.create(
            household=self.household,
            family_number=1,
            monthly_income_bracket='NO_INCOME',
            encoded_by=self.official,
        )

    def test_household_requires_structured_address_fields(self):
        serializer = HouseholdSerializer(
            data={'household_code': 'HH-002', 'status': 'ACTIVE'},
            context={'request': self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('house_no_or_blk_lot_no', serializer.errors)
        self.assertIn('street_name', serializer.errors)
        self.assertIn('purok_sitio', serializer.errors)

    def test_unspecified_income_bracket_is_rejected(self):
        serializer = FamilySerializer(
            data={'household': self.household.id, 'monthly_income_bracket': 'UNSPECIFIED'},
            context={'request': self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('monthly_income_bracket', serializer.errors)

    def test_head_role_sets_household_head_and_blocks_second_head(self):
        first_head = Beneficiary.objects.create(
            family=self.family,
            role='head',
            first_name='Juan',
            last_name='Resident',
            full_name='Juan Resident',
            birthdate=date(1980, 1, 1),
            gender='male',
            civil_status='married',
            encoded_by=self.official,
        )

        self.assertTrue(first_head.is_household_head)

        serializer = BeneficiarySerializer(
            data={
                'family': self.family.id,
                'role': 'head',
                'first_name': 'Maria',
                'last_name': 'Resident',
                'full_name': 'Maria Resident',
                'birthdate': '1985-01-01',
                'gender': 'female',
                'civil_status': 'married',
                'monthly_income': 0,
                'employment_status': 'unemployed',
                'num_dependents': 0,
                'housing_condition': 'informal_settler',
            },
            context={'request': self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('is_household_head', serializer.errors)
