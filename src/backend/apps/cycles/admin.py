from django.contrib import admin
from .models import ProgramCycle, ParticipationRecord, DailyParticipationRecord, CycleApplication

admin.site.register(ProgramCycle)
admin.site.register(ParticipationRecord)
admin.site.register(DailyParticipationRecord)
admin.site.register(CycleApplication)
