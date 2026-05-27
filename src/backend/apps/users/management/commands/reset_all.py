from datetime import date
import secrets

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from decouple import config


SAMPLE_USERS = [
    {
        'username': 'admin',
        'first_name': 'FADDSS',
        'middle_name': '',
        'last_name': 'Administrator',
        'role': 'admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'official',
        'first_name': 'Barangay',
        'middle_name': '',
        'last_name': 'Official',
        'role': 'official',
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'username': 'resident1',
        'first_name': 'Juan',
        'middle_name': 'Santos',
        'last_name': 'Dela Cruz',
        'role': 'resident',
        'is_staff': False,
        'is_superuser': False,
        'beneficiary_index': 1,
    },
    {
        'username': 'resident2',
        'first_name': 'Maria',
        'middle_name': 'Reyes',
        'last_name': 'Garcia',
        'role': 'resident',
        'is_staff': False,
        'is_superuser': False,
        'beneficiary_index': 2,
    },
    {
        'username': 'resident3',
        'first_name': 'Pedro',
        'middle_name': 'Cruz',
        'last_name': 'Mendoza',
        'role': 'resident',
        'is_staff': False,
        'is_superuser': False,
        'beneficiary_index': 3,
    },
    {
        'username': 'resident4',
        'first_name': 'Liza',
        'middle_name': 'Flores',
        'last_name': 'Santos',
        'role': 'resident',
        'is_staff': False,
        'is_superuser': False,
        'beneficiary_index': 4,
    },
    {
        'username': 'resident5',
        'first_name': 'Carlo',
        'middle_name': 'Torres',
        'last_name': 'Ramos',
        'role': 'resident',
        'is_staff': False,
        'is_superuser': False,
        'beneficiary_index': 5,
    },
]

# Delete order respects FK dependencies; raw SQL bypasses ORM PROTECT / insert-only guards.
DELETE_ORDER = [
    'token_blacklist_blacklistedtoken',
    'token_blacklist_outstandingtoken',
    'audit_logs',
    'profile_change_logs',
    'daily_participation_records',
    'participation_records',
    'cycle_applications',
    'beneficiary_indicators',
    'beneficiaries',
    'families',
    'program_cycles',
    'criteria',
    'households',
    'django_admin_log',
    'users',
]


class Command(BaseCommand):
    help = 'Wipe all application data and create fresh local user accounts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Skip the confirmation prompt.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stderr.write('reset_all is disabled when DJANGO_DEBUG is false.')
            return

        if not options['no_input']:
            confirm = input(
                'This will DELETE ALL DATA permanently. Type "yes" to continue: '
            )
            if confirm.strip().lower() != 'yes':
                self.stdout.write('Aborted.')
                return

        self.stdout.write('Wiping all data...')
        with connection.cursor() as cursor:
            for table in DELETE_ORDER:
                cursor.execute(f'DELETE FROM {table}')
                self.stdout.write(f'  cleared: {table}')

        self.stdout.write('Creating sample accounts...')
        from apps.beneficiaries.models import Beneficiary, Family, Household
        from apps.users.models import User

        official_user = None
        generated_passwords = {}
        for spec in [item for item in SAMPLE_USERS if item['role'] != 'resident']:
            password = _password_for(spec['username'])
            generated_passwords[spec['username']] = password
            user = User(
                username=spec['username'],
                first_name=spec['first_name'],
                middle_name=spec['middle_name'],
                last_name=spec['last_name'],
                email=f"{spec['username']}@example.com",
                role=spec['role'],
                is_staff=spec['is_staff'],
                is_superuser=spec['is_superuser'],
                is_active=True,
            )
            user.set_password(password)
            user.save()
            if spec['role'] == 'official':
                official_user = user
            self.stdout.write(f"  created: {spec['username']}")

        household = Household.objects.create(
            household_code='LOCAL-HH-0001',
            address='Local Test Household',
            status='ACTIVE',
            purok='Local',
            notes='Created by reset_all for local resident accounts',
            encoded_by=official_user,
        )
        family = Family.objects.create(
            household=household,
            family_number=1,
            monthly_income_bracket='BELOW_5K',
            encoded_by=official_user,
        )

        for spec in [item for item in SAMPLE_USERS if item['role'] == 'resident']:
            password = _password_for(spec['username'])
            generated_passwords[spec['username']] = password
            beneficiary = Beneficiary.objects.create(
                family=family,
                household=household,
                role='relative',
                is_household_head=False,
                first_name=spec['first_name'],
                middle_name=spec['middle_name'],
                last_name=spec['last_name'],
                full_name=f"{spec['first_name']} {spec['middle_name']} {spec['last_name']}",
                address=household.address,
                birthdate=date(1990 + spec['beneficiary_index'], 1, spec['beneficiary_index']),
                gender='male' if spec['beneficiary_index'] % 2 else 'female',
                civil_status='single',
                contact_number=f"0917000000{spec['beneficiary_index']}",
                sectors=[],
                monthly_income=0,
                employment_status='unemployed',
                household_size=5,
                num_dependents=2,
                housing_condition='makeshift',
                encoded_by=official_user,
            )
            user = User(
                username=spec['username'],
                first_name=spec['first_name'],
                middle_name=spec['middle_name'],
                last_name=spec['last_name'],
                email=f"{spec['username']}@example.com",
                role=spec['role'],
                beneficiary=beneficiary,
                is_staff=spec['is_staff'],
                is_superuser=spec['is_superuser'],
                is_active=True,
            )
            user.set_password(password)
            user.save()
            self.stdout.write(f"  created: {spec['username']}")

        self.stdout.write(self.style.SUCCESS('\nReset complete. Temporary local passwords:'))
        for username, password in generated_passwords.items():
            self.stdout.write(f'  {username:<12} / {password}')
        self.stdout.write('\nThese passwords are generated for this local reset only. Do not commit real credentials.')


def _password_for(username):
    env_name = f'LOCAL_{username.upper()}_PASSWORD'
    return config(env_name, default=secrets.token_urlsafe(12))
