"""
Views for the VTpass API.
This module imports all views for easier access.
"""

from vtpass.api.views.base import BaseViewSet
from vtpass.api.views.transaction import TransactionViewSet
from vtpass.api.views.service import ServiceViewSet
from vtpass.api.views.provider import ProviderViewSet
from vtpass.api.views.wallet import WalletViewSet
from vtpass.api.views.commission import CommissionViewSet
from vtpass.api.views.airtime import AirtimeViewSet
from vtpass.api.views.data import DataViewSet
from vtpass.api.views.electricity import ElectricityViewSet
from vtpass.api.views.cable import CableTVViewSet
from vtpass.api.views.education import EducationViewSet
from vtpass.api.views.internet import InternetViewSet
from vtpass.api.views.betting import BettingViewSet
from vtpass.api.views.water import WaterViewSet