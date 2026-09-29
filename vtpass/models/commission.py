"""
Commission models for the VTpass package.
This module defines models for managing commissions on transactions.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import BaseModel
from vtpass.constants import ServiceType
from vtpass.settings import vtpass_settings

User = get_user_model()


class CommissionRate(BaseModel):
    """
    Model for commission rates.
    This defines the commission rate for each service type.
    """
    service_type = models.CharField(
        _('Service Type'),
        max_length=20,
        choices=ServiceType.CHOICES,
        unique=True,
        help_text=_('Type of service')
    )
    rate = models.DecimalField(
        _('Rate'),
        max_digits=5,
        decimal_places=4,
        help_text=_('Commission rate (0.01 means 1%)')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Commission rate description')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this commission rate is active')
    )
    
    class Meta:
        verbose_name = _('Commission Rate')
        verbose_name_plural = _('Commission Rates')
        ordering = ['service_type']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"{self.get_service_type_display()} - {self.rate_percentage}%"
    
    @property
    def rate_percentage(self):
        """Get the rate as a percentage."""
        return self.rate * 100
    
    @classmethod
    def get_rate_for_service_type(cls, service_type):
        """
        Get the commission rate for a specific service type.
        
        Args:
            service_type (str): The service type
            
        Returns:
            Decimal: The commission rate or default rate if not found
        """
        try:
            commission_rate = cls.objects.get(service_type=service_type, active=True)
            return commission_rate.rate
        except cls.DoesNotExist:
            # Return the default rate from settings
            return vtpass_settings.commission_rate_for_service(service_type)
    
    @classmethod
    def calculate_commission(cls, amount, service_type):
        """
        Calculate the commission amount.
        
        Args:
            amount (Decimal): The transaction amount
            service_type (str): The service type
            
        Returns:
            Decimal: The commission amount
        """
        if not vtpass_settings._settings['COMMISSION']['ENABLED']:
            return 0
            
        rate = cls.get_rate_for_service_type(service_type)
        return amount * rate


class Commission(BaseModel):
    """
    Model for commissions earned from transactions.
    Each commission represents the earning from a specific transaction.
    """
    # Reference to the transaction
    transaction = models.OneToOneField(
        'vtpass.Transaction',
        verbose_name=_('Transaction'),
        on_delete=models.CASCADE,
        related_name='commission',
        help_text=_('Transaction this commission is for')
    )
    
    # Commission details
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Commission amount')
    )
    rate = models.DecimalField(
        _('Rate'),
        max_digits=5,
        decimal_places=4,
        help_text=_('Commission rate used (0.01 means 1%)')
    )
    
    # User information (optional, can be null for anonymous transactions)
    user = models.ForeignKey(
        User,
        verbose_name=_('User'),
        on_delete=models.SET_NULL,
        related_name='vtpass_commissions',
        null=True,
        blank=True,
        help_text=_('User who earned the commission')
    )
    
    # Status
    is_paid = models.BooleanField(
        _('Is Paid'),
        default=False,
        help_text=_('Whether this commission has been paid')
    )
    paid_at = models.DateTimeField(
        _('Paid At'),
        null=True,
        blank=True,
        help_text=_('When the commission was paid')
    )
    
    # Additional information
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Commission description')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional commission metadata')
    )
    
    class Meta:
        verbose_name = _('Commission')
        verbose_name_plural = _('Commissions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_paid']),
            models.Index(fields=['paid_at']),
        ]
    
    def __str__(self):
        return f"Commission for {self.transaction.reference}"
    
    @property
    def rate_percentage(self):
        """Get the rate as a percentage."""
        return self.rate * 100
    
    @classmethod
    def get_unpaid_commissions(cls, user=None):
        """
        Get all unpaid commissions.
        
        Args:
            user (User, optional): The user to filter by. Defaults to None.
            
        Returns:
            QuerySet: A queryset of unpaid commissions
        """
        queryset = cls.objects.filter(is_paid=False)
        if user:
            queryset = queryset.filter(user=user)
        return queryset.order_by('-created_at')
    
    @classmethod
    def get_total_commission(cls, user=None, start_date=None, end_date=None):
        """
        Get the total commission amount.
        
        Args:
            user (User, optional): The user to filter by. Defaults to None.
            start_date (date, optional): Start date for filtering. Defaults to None.
            end_date (date, optional): End date for filtering. Defaults to None.
            
        Returns:
            Decimal: The total commission amount
        """
        queryset = cls.objects.all()
        
        if user:
            queryset = queryset.filter(user=user)
            
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
            
        return queryset.aggregate(total=models.Sum('amount'))['total'] or 0
    
    @classmethod
    def create_from_transaction(cls, transaction):
        """
        Create a commission from a transaction.
        
        Args:
            transaction (Transaction): The transaction
            
        Returns:
            Commission: The created commission instance
        """
        if not vtpass_settings._settings['COMMISSION']['ENABLED']:
            return None
            
        # Calculate commission
        rate = CommissionRate.get_rate_for_service_type(transaction.service_type)
        amount = transaction.amount * rate
        
        # Create commission
        commission = cls.objects.create(
            transaction=transaction,
            amount=amount,
            rate=rate,
            user=transaction.user,
            description=f"Commission for {transaction.reference}"
        )
        
        return commission