"""
Constants for the VTpass package.
This module defines constants used throughout the package.
"""

from django.utils.translation import gettext_lazy as _


# Service Types
class ServiceType:
    """Service types available on VTpass."""
    AIRTIME = 'airtime'
    DATA = 'data'
    ELECTRICITY = 'electricity'
    CABLE_TV = 'cable'
    EDUCATION = 'education'
    INTERNET = 'internet'
    BETTING = 'betting'
    WATER = 'water'
    OTHER = 'other'
    
    CHOICES = (
        (AIRTIME, _('Airtime')),
        (DATA, _('Data')),
        (ELECTRICITY, _('Electricity')),
        (CABLE_TV, _('Cable TV')),
        (EDUCATION, _('Education')),
        (INTERNET, _('Internet')),
        (BETTING, _('Betting')),
        (WATER, _('Water')),
        (OTHER, _('Other')),
    )


# Transaction Statuses
class TransactionStatus:
    """Transaction statuses for VTpass transactions."""
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REVERSED = 'reversed'
    
    CHOICES = (
        (PENDING, _('Pending')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
        (REVERSED, _('Reversed')),
    )


# API Endpoints
class Endpoints:
    """API endpoints for the VTpass API."""
    # Merchant Account
    BALANCE = 'merchant-balance'
    BANKS = 'banks'
    
    # Services
    SERVICE_CATEGORIES = 'service-categories'
    SERVICE_VARIATIONS = 'service-variations'
    
    # Transactions
    PURCHASE = 'pay'
    VERIFY_TRANSACTION = 'requery'
    
    # Verifications
    VERIFY_SMILE = 'smile/verify'
    VERIFY_CUSTOMER = 'merchant-verify'
    VERIFY_SMARTCARD = 'verify/smartcard'
    VERIFY_METER = 'verify/metre'


# Network Providers
class NetworkProvider:
    """Mobile network providers for airtime and data services."""
    MTN = 'mtn'
    AIRTEL = 'airtel'
    GLO = 'glo'
    ETISALAT = '9mobile'
    
    CHOICES = (
        (MTN, 'MTN'),
        (AIRTEL, 'Airtel'),
        (GLO, 'Glo'),
        (ETISALAT, '9mobile'),
    )
    
    # Service codes for each provider
    CODES = {
        MTN: 'mtn',
        AIRTEL: 'airtel',
        GLO: 'glo',
        ETISALAT: 'etisalat',
    }


# Electricity Providers
class ElectricityProvider:
    """Electricity distribution companies."""
    EKEDC = 'ekedc'  # Eko Electric
    IKEDC = 'ikedc'  # Ikeja Electric
    AEDC = 'aedc'    # Abuja Electric
    KEDCO = 'kedco'  # Kano Electric
    PHED = 'phed'    # Port Harcourt Electric
    JED = 'jed'      # Jos Electric
    KAEDCO = 'kaedco'  # Kaduna Electric
    IBEDC = 'ibedc'  # Ibadan Electric
    EEDC = 'eedc'    # Enugu Electric
    BEDC = 'bedc'    # Benin Electric
    
    CHOICES = (
        (EKEDC, 'Eko Electric'),
        (IKEDC, 'Ikeja Electric'),
        (AEDC, 'Abuja Electric'),
        (KEDCO, 'Kano Electric'),
        (PHED, 'Port Harcourt Electric'),
        (JED, 'Jos Electric'),
        (KAEDCO, 'Kaduna Electric'),
        (IBEDC, 'Ibadan Electric'),
        (EEDC, 'Enugu Electric'),
        (BEDC, 'Benin Electric'),
    )
    
    # Service codes for each provider
    CODES = {
        EKEDC: 'eko-electric',
        IKEDC: 'ikeja-electric',
        AEDC: 'abuja-electric',
        KEDCO: 'kano-electric',
        PHED: 'portharcourt-electric',
        JED: 'jos-electric',
        KAEDCO: 'kaduna-electric',
        IBEDC: 'ibadan-electric',
        EEDC: 'enugu-electric',
        BEDC: 'benin-electric',
    }


# Cable TV Providers
class CableTVProvider:
    """Cable TV providers."""
    DSTV = 'dstv'
    GOTV = 'gotv'
    STARTIMES = 'startimes'
    
    CHOICES = (
        (DSTV, 'DSTV'),
        (GOTV, 'GOTV'),
        (STARTIMES, 'StarTimes'),
    )
    
    # Service codes for each provider
    CODES = {
        DSTV: 'dstv',
        GOTV: 'gotv',
        STARTIMES: 'startimes',
    }


# Internet Providers
class InternetProvider:
    """Internet service providers."""
    SMILE = 'smile'
    SPECTRANET = 'spectranet'
    
    CHOICES = (
        (SMILE, 'Smile'),
        (SPECTRANET, 'Spectranet'),
    )
    
    # Service codes for each provider
    CODES = {
        SMILE: 'smile-direct',
        SPECTRANET: 'spectranet',
    }


# Education Service Providers
class EducationProvider:
    """Education service providers."""
    WAEC = 'waec'
    JAMB = 'jamb'
    NCEE = 'ncee'
    NABTEB = 'nabteb'
    
    CHOICES = (
        (WAEC, 'WAEC'),
        (JAMB, 'JAMB'),
        (NCEE, 'NCEE'),
        (NABTEB, 'NABTEB'),
    )
    
    # Service codes for each provider
    CODES = {
        WAEC: 'waec',
        JAMB: 'jamb',
        NCEE: 'ncee',
        NABTEB: 'nabteb',
    }


# Electricity Meter Types
class MeterType:
    """Electricity meter types."""
    PREPAID = 'prepaid'
    POSTPAID = 'postpaid'
    
    CHOICES = (
        (PREPAID, _('Prepaid')),
        (POSTPAID, _('Postpaid')),
    )


# API Response Codes
class ResponseCode:
    """Response codes from the VTpass API."""
    SUCCESS = '000'
    PENDING = '099'
    FAILED = '100'
    
    # Map response codes to transaction statuses
    STATUS_MAP = {
        SUCCESS: TransactionStatus.COMPLETED,
        PENDING: TransactionStatus.PENDING,
        FAILED: TransactionStatus.FAILED,
    }