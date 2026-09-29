"""
API URL configuration for the VTpass package.
This module defines URL patterns for the VTpass API.
"""

from rest_framework import routers

from vtpass.api.views import (
    TransactionViewSet, ServiceViewSet, ProviderViewSet,
    WalletViewSet, CommissionViewSet, AirtimeViewSet,
    DataViewSet, ElectricityViewSet, CableTVViewSet,
    EducationViewSet, InternetViewSet, BettingViewSet,
    WaterViewSet
)


# Initialize the router
router = routers.DefaultRouter()

# Register viewsets
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'providers', ProviderViewSet, basename='provider')
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'commissions', CommissionViewSet, basename='commission')

# Register service-specific viewsets
router.register(r'airtime', AirtimeViewSet, basename='airtime')
router.register(r'data', DataViewSet, basename='data')
router.register(r'electricity', ElectricityViewSet, basename='electricity')
router.register(r'cable', CableTVViewSet, basename='cable')
router.register(r'education', EducationViewSet, basename='education')
router.register(r'internet', InternetViewSet, basename='internet')
router.register(r'betting', BettingViewSet, basename='betting')
router.register(r'water', WaterViewSet, basename='water')

# URLPatterns are automatically determined by the router
urlpatterns = router.urls