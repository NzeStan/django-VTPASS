"""
Django VTpass package - A comprehensive integration with VTpass API.
"""

__version__ = '0.1.0'
default_app_config = 'vtpass.apps.VTpassConfig'

# Import for easier access from other modules
from vtpass.client import VTpassClient
from vtpass.exceptions import VTpassError, VTpassAPIError