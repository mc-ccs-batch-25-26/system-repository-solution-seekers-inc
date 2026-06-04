from django.contrib import admin
from .models import Household, Family, Beneficiary, BeneficiaryIndicator

admin.site.register(Household)
admin.site.register(Family)
admin.site.register(Beneficiary)
admin.site.register(BeneficiaryIndicator)
