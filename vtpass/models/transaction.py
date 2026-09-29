"""
Transaction model for the VTpass package.
This module defines the Transaction model for tracking VTpass transactions.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import BaseModel
from vtpass.models.service import Service, ServiceVariation
from vtpass.constants import TransactionStatus, ServiceType

User = get_user_model()


class Transaction(BaseModel):
    """
    Model for VTpass transactions.
    Each transaction represents a payment for a service through VTpass.
    """
    # Basic transaction information
    reference = models.CharField(
        _('Reference'),
        max_length=100,
        unique=True,
        help_text=_('Unique transaction reference')
    )
    transaction_id = models.CharField(
        _('Transaction ID'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('VTpass transaction ID')
    )
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Transaction amount')
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=TransactionStatus.CHOICES,
        default=TransactionStatus.PENDING,
        help_text=_('Transaction status')
    )
    
    # Service information
    service_type = models.CharField(
        _('Service Type'),
        max_length=20,
        choices=ServiceType.CHOICES,
        help_text=_('Type of service')
    )
    service = models.ForeignKey(
        Service,
        verbose_name=_('Service'),
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text=_('Service for this transaction')
    )
    service_variation = models.ForeignKey(
        ServiceVariation,
        verbose_name=_('Service Variation'),
        on_delete=models.PROTECT,
        related_name='transactions',
        null=True,
        blank=True,
        help_text=_('Service variation for this transaction')
    )
    
    # Customer information
    phone = models.CharField(
        _('Phone'),
        max_length=20,
        help_text=_('Customer phone number')
    )
    email = models.EmailField(
        _('Email'),
        blank=True,
        help_text=_('Customer email address')
    )
    customer_data = models.JSONField(
        _('Customer Data'),
        default=dict,
        blank=True,
        help_text=_('Additional customer data')
    )
    
    # Verification information
    verification_code = models.CharField(
        _('Verification Code'),
        max_length=100,
        blank=True,
        help_text=_('Verification code (meter number, smartcard number, etc.)')
    )
    
    # Response information
    response_data = models.JSONField(
        _('Response Data'),
        default=dict,
        blank=True,
        help_text=_('Response data from VTpass API')
    )
    response_message = models.TextField(
        _('Response Message'),
        blank=True,
        help_text=_('Response message from VTpass API')
    )
    
    # User information (optional, can be null for anonymous transactions)
    user = models.ForeignKey(
        User,
        verbose_name=_('User'),
        on_delete=models.SET_NULL,
        related_name='vtpass_transactions',
        null=True,
        blank=True,
        help_text=_('User who initiated the transaction')
    )
    
    # Additional information
    callback_url = models.URLField(
        _('Callback URL'),
        blank=True,
        help_text=_('URL to call when transaction status changes')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional transaction metadata')
    )
    
    # Completed timestamp
    completed_at = models.DateTimeField(
        _('Completed At'),
        null=True,
        blank=True,
        help_text=_('When the transaction was completed')
    )
    
    class Meta:
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['service_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['completed_at']),
        ]
    
    def __str__(self):
        return f"{self.reference} - {self.get_status_display()}"
    
    @property
    def is_completed(self):
        """Check if the transaction is completed."""
        return self.status == TransactionStatus.COMPLETED
    
    @property
    def is_pending(self):
        """Check if the transaction is pending."""
        return self.status == TransactionStatus.PENDING
    
    @property
    def is_failed(self):
        """Check if the transaction is failed."""
        return self.status == TransactionStatus.FAILED
    
    @property
    def is_reversed(self):
        """Check if the transaction is reversed."""
        return self.status == TransactionStatus.REVERSED
    
    @property
    def service_name(self):
        """Get the service name."""
        return self.service.name
    
    @property
    def variation_name(self):
        """Get the variation name."""
        if self.service_variation:
            return self.service_variation.name
        return None
    
    @classmethod
    def get_by_reference(cls, reference):
        """
        Get a transaction by its reference.
        
        Args:
            reference (str): The transaction reference
            
        Returns:
            Transaction: The transaction instance or None if not found
        """
        try:
            return cls.objects.get(reference=reference)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_by_transaction_id(cls, transaction_id):
        """
        Get a transaction by its VTpass transaction ID.
        
        Args:
            transaction_id (str): The VTpass transaction ID
            
        Returns:
            Transaction: The transaction instance or None if not found
        """
        try:
            return cls.objects.get(transaction_id=transaction_id)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_user_transactions(cls, user, **filters):
        """
        Get all transactions for a specific user.
        
        Args:
            user (User): The user instance
            **filters: Additional filters
            
        Returns:
            QuerySet: A queryset of transactions
        """
        return cls.objects.filter(user=user, **filters).order_by('-created_at')
    
    @classmethod
    def get_transactions_by_service_type(cls, service_type, **filters):
        """
        Get all transactions for a specific service type.
        
        Args:
            service_type (str): The service type
            **filters: Additional filters
            
        Returns:
            QuerySet: A queryset of transactions
        """
        return cls.objects.filter(
            service_type=service_type, **filters
        ).order_by('-created_at')