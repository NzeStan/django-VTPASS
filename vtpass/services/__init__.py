"""
Services for the VTpass package.
This module imports all service classes for easier access.
"""

from vtpass.services.base import BaseService
from vtpass.services.airtime import AirtimeService
from vtpass.services.data import DataService
from vtpass.services.electricity import ElectricityService
from vtpass.services.cable import CableTVService
from vtpass.services.education import EducationService
from vtpass.services.internet import InternetService
from vtpass.services.betting import BettingService
from vtpass.services.water import WaterService

__all__ = [
    'BaseService',
    'AirtimeService',
    'DataService',
    'ElectricityService',
    'CableTVService',
    'EducationService',
    'InternetService',
    'BettingService',
    'WaterService',
]