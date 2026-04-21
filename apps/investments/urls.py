from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AssetTypeViewSet,
    ExchangeRateViewSet,
    InvestmentAccountViewSet,
    InvestmentHoldingViewSet,
    InvestmentTransactionViewSet,
    DividendRecordViewSet,
)

router = DefaultRouter()
router.register(r'asset-types', AssetTypeViewSet, basename='asset-type')
router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchange-rate')
router.register(r'investments', InvestmentAccountViewSet, basename='investment-account')
router.register(r'holdings', InvestmentHoldingViewSet, basename='holding')
router.register(r'invest-trans', InvestmentTransactionViewSet, basename='invest-transaction')
router.register(r'dividend-records', DividendRecordViewSet, basename='dividend-record')

urlpatterns = [
    path('', include(router.urls)),
]
