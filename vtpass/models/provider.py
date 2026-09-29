"""
Provider model for the VTpass package.
This module defines the Provider model for service providers.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import BaseModel
from vtpass.constants import ServiceType


class Provider(BaseModel):
    """
    Model for service providers.
    This represents providers for different services like mobile networks,
    electricity companies, etc.
    """
    name = models.CharField(
        _('Name'),
        max_length=100,
        help_text=_('Provider name')
    )
    code = models.CharField(
        _('Code'),
        max_length=50,
        unique=True,
        help_text=_('Provider code used in the VTpass API')
    )
    service_type = models.CharField(
        _('Service Type'),
        max_length=20,
        choices=ServiceType.CHOICES,
        help_text=_('Type of service this provider offers')
    )
    logo = models.ImageField(
        _('Logo'),
        upload_to='vtpass/providers/',
        null=True,
        blank=True,
        help_text=_('Provider logo')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Provider description')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this provider is active')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional provider metadata')
    )
    
    class Meta:
        verbose_name = _('Provider')
        verbose_name_plural = _('Providers')
        ordering = ['name']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['code']),
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()})"
    
    @property
    def service_name(self):
        """Get the service type display name."""
        return self.get_service_type_display()
    
    @classmethod
    def get_by_code(cls, code):
        """
        Get a provider by its code.
        
        Args:
            code (str): The provider code
            
        Returns:
            Provider: The provider instance or None if not found
        """
        try:
            return cls.objects.get(code=code, active=True)
        except cls.DoesNotExist:
            return None
            
    @classmethod
    def get_providers_by_service_type(cls, service_type):
        """
        Get all active providers for a specific service type.
        
        Args:
            service_type (str): The service type
            
        Returns:
            QuerySet: A queryset of providers
        """
        return cls.objects.filter(service_type=service_type, active=True)