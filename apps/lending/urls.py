from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LendingRecordViewSet, RepaymentViewSet

router = DefaultRouter()
router.register(r'lending-records', LendingRecordViewSet, basename='lending-record')
router.register(r'repayments', RepaymentViewSet, basename='repayment')

urlpatterns = [
    path('', include(router.urls)),
]
