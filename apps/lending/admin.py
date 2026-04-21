from django.contrib import admin
from .models import LendingRecord, Repayment

admin.site.register(LendingRecord)
admin.site.register(Repayment)
