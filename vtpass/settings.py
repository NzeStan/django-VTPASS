"""
Settings module for the VTpass package.
This module handles the configuration options and defaults.
"""

import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


# Default settings for VTpass
VTPASS_DEFAULTS = {
    'API_KEY': None,
    'SECRET_KEY': None,
    'ENVIRONMENT': 'development',  # 'development' or 'production'
    'BASE_URL': {
        'development': 'https://sandbox.vtpass.com/api',
        'production': 'https://vtpass.com/api',
    },
    'VERIFY_SSL': True,
    'TIMEOUT': 30,  # seconds
    'MAX_RETRIES': 3,
    'BACKOFF_FACTOR': 0.3,
    'USE_UUID': False,  # If True, UUIDs will be used for primary keys
    'LOG_LEVEL': 'INFO',
    'LOG_FILE': None,  # None means log to console
    'COMMISSION': {
        'ENABLED': True,
        'DEFAULT_RATE': 0.02,  # 2%
        'RATES': {
            # Service-specific commission rates
            # 'service_name': rate,
            'airtime': 0.02,
            'data': 0.02,
            'electricity': 0.01,
            'cable': 0.01,
            'education': 0.015,
        },
    },
    'WEBHOOK': {
        'ENABLED': False,
        'URL': None,
        'SECRET': None,
        'TIMEOUT': 10,
    },
    'ADMIN': {
        'DASHBOARD_WIDGETS': [
            'recent_transactions', 
            'service_stats',
            'revenue_chart',
            'commission_summary',
        ],
        'ITEMS_PER_PAGE': 20,
    },
}


class VTpassSettings:
    """
    Settings handler for the VTpass package.
    This class provides access to all settings with appropriate defaults.
    """
    def __init__(self):
        """Initialize with values from Django settings or defaults."""
        self._settings = VTPASS_DEFAULTS.copy()
        
        # Update with user settings from settings.py
        user_settings = getattr(settings, 'VTPASS', {})
        self._settings.update(user_settings)
        
        # Validate required settings
        self._validate_settings()

    def _validate_settings(self):
        """Validate that all required settings are provided."""
        if self._settings['ENVIRONMENT'] not in ['development', 'production']:
            raise ImproperlyConfigured(
                "VTPASS['ENVIRONMENT'] must be either 'development' or 'production'"
            )
            
        # In production, API_KEY and SECRET_KEY are required
        if self._settings['ENVIRONMENT'] == 'production':
            if not self._settings['API_KEY']:
                raise ImproperlyConfigured("VTPASS['API_KEY'] is required in production")
            if not self._settings['SECRET_KEY']:
                raise ImproperlyConfigured("VTPASS['SECRET_KEY'] is required in production")
        
        # Webhook validation
        if self._settings['WEBHOOK']['ENABLED'] and not self._settings['WEBHOOK']['URL']:
            raise ImproperlyConfigured(
                "VTPASS['WEBHOOK']['URL'] is required when webhooks are enabled"
            )

    def __getattr__(self, name):
        """
        Get a setting value by name.
        First checks the user-defined settings, then falls back to defaults.
        """
        if name in self._settings:
            return self._settings[name]
        
        # Handle nested settings
        for section, section_settings in self._settings.items():
            if isinstance(section_settings, dict) and name in section_settings:
                return section_settings[name]
                
        raise AttributeError(f"Setting '{name}' not found")
    
    @property
    def base_url(self):
        """Get the base URL based on the current environment."""
        environment = self._settings['ENVIRONMENT']
        return self._settings['BASE_URL'][environment]
    
    @property
    def log_level(self):
        """Get the log level as a logging constant."""
        level = self._settings['LOG_LEVEL'].upper()
        return getattr(logging, level, logging.INFO)
    
    @property
    def commission_rate(self):
        """Get the default commission rate."""
        if not self._settings['COMMISSION']['ENABLED']:
            return 0
        return self._settings['COMMISSION']['DEFAULT_RATE']
    
    def commission_rate_for_service(self, service_name):
        """Get the commission rate for a specific service."""
        if not self._settings['COMMISSION']['ENABLED']:
            return 0
            
        rates = self._settings['COMMISSION']['RATES']
        return rates.get(service_name, self._settings['COMMISSION']['DEFAULT_RATE'])


# Create a global instance of the settings
vtpass_settings = VTpassSettings()