from django.urls import path
from .views import BalanceSheetView, ExportExcelView, NetWorthHistoryView

urlpatterns = [
    path('reports/balance-sheet/', BalanceSheetView.as_view(), name='balance-sheet'),
    path('reports/net-worth-history/', NetWorthHistoryView.as_view(), name='net-worth-history'),
    path('reports/export/', ExportExcelView.as_view(), name='export-excel'),
]
