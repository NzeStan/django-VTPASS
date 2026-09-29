"""
Service models for the VTpass package.
This module defines the Service and ServiceVariation models.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import BaseModel
from vtpass.models.provider import Provider
from vtpass.constants import ServiceType


class ServiceVariation(BaseModel):
    """
    Model for service variations available on VTpass.
    Service variations represent specific options for services like
    different data plans, subscription packages, etc.
    """
    service = models.ForeignKey(
        Service,
        verbose_name=_('Service'),
        on_delete=models.CASCADE,
        related_name='variations',
        help_text=_('Service this variation belongs to')
    )
    name = models.CharField(
        _('Name'),
        max_length=100,
        help_text=_('Variation name')
    )
    variation_code = models.CharField(
        _('Variation Code'),
        max_length=50,
        help_text=_('Variation code used in the VTpass API')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Variation description')
    )
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Fixed amount for this variation')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this variation is active')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional variation metadata')
    )
    
    class Meta:
        verbose_name = _('Service Variation')
        verbose_name_plural = _('Service Variations')
        ordering = ['service', 'name']
        unique_together = [('service', 'variation_code')]
        indexes = [
            models.Index(fields=['variation_code']),
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.service.name})"
    
    @classmethod
    def get_by_code(cls, service, variation_code):
        """
        Get a variation by its code for a specific service.
        
        Args:
            service (Service): The service instance
            variation_code (str): The variation code
            
        Returns:
            ServiceVariation: The variation instance or None if not found
        """
        try:
            return cls.objects.get(
                service=service, 
                variation_code=variation_code,
                active=True
            )
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_variations_for_service(cls, service):
        """
        Get all active variations for a specific service.
        
        Args:
            service (Service): The service instance
            
        Returns:
            QuerySet: A queryset of variations
        """
        return cls.objects.filter(service=service, active=True).order_by('name')(BaseModel):
    """
    Model for services available on VTpass.
    Each service represents a specific bill payment service like
    airtime, data, electricity, etc.
    """
    name = models.CharField(
        _('Name'),
        max_length=100,
        help_text=_('Service name')
    )
    service_id = models.CharField(
        _('Service ID'),
        max_length=50,
        unique=True,
        help_text=_('Service ID used in the VTpass API')
    )
    service_type = models.CharField(
        _('Service Type'),
        max_length=20,
        choices=ServiceType.CHOICES,
        help_text=_('Type of service')
    )
    provider = models.ForeignKey(
        Provider,
        verbose_name=_('Provider'),
        on_delete=models.CASCADE,
        related_name='services',
        help_text=_('Service provider')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Service description')
    )
    icon = models.ImageField(
        _('Icon'),
        upload_to='vtpass/services/',
        null=True,
        blank=True,
        help_text=_('Service icon')
    )
    requires_verification = models.BooleanField(
        _('Requires Verification'),
        default=False,
        help_text=_('Whether this service requires verification')
    )
    verification_field = models.CharField(
        _('Verification Field'),
        max_length=50,
        blank=True,
        help_text=_('Field to be verified (e.g., meter_number, smartcard_number)')
    )
    supports_recurring = models.BooleanField(
        _('Supports Recurring'),
        default=False,
        help_text=_('Whether this service supports recurring payments')
    )
    min_amount = models.DecimalField(
        _('Minimum Amount'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Minimum transaction amount')
    )
    max_amount = models.DecimalField(
        _('Maximum Amount'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum transaction amount')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this service is active')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional service metadata')
    )
    
    class Meta:
        verbose_name = _('Service')
        verbose_name_plural = _('Services')
        ordering = ['service_type', 'name']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['service_id']),
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.provider.name})"
    
    @property
    def service_name(self):
        """Get the service type display name."""
        return self.get_service_type_display()
    
    @classmethod
    def get_by_service_id(cls, service_id):
        """
        Get a service by its service_id.
        
        Args:
            service_id (str): The service ID
            
        Returns:
            Service: The service instance or None if not found
        """
        try:
            return cls.objects.get(service_id=service_id, active=True)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_services_by_type(cls, service_type):
        """
        Get all active services for a specific service type.
        
        Args:
            service_type (str): The service type
            
        Returns:
            QuerySet: A queryset of services
        """
        return cls.objects.filter(service_type=service_type, active=True)
    
    def has_variations(self):
        """Check if this service has variations."""
        return self.variations.exists()
    
    def get_variations(self):
        """Get all variations for this service."""
        return self.variations.filter(active=True).order_by('name')


#class Service