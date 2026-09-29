"""
Wallet models for the VTpass package.
This module defines models for managing wallet and wallet transactions.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction as db_transaction

from vtpass.models.base import BaseModel

User = get_user_model()


class Wallet(BaseModel):
    """
    Model for user wallets.
    Each user can have a wallet for storing funds for transactions.
    """
    user = models.OneToOneField(
        User,
        verbose_name=_('User'),
        on_delete=models.CASCADE,
        related_name='vtpass_wallet',
        help_text=_('User this wallet belongs to')
    )
    balance = models.DecimalField(
        _('Balance'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Current wallet balance')
    )
    last_deposit_at = models.DateTimeField(
        _('Last Deposit At'),
        null=True,
        blank=True,
        help_text=_('When the last deposit was made')
    )
    last_withdrawal_at = models.DateTimeField(
        _('Last Withdrawal At'),
        null=True,
        blank=True,
        help_text=_('When the last withdrawal was made')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this wallet is active')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional wallet metadata')
    )
    
    class Meta:
        verbose_name = _('Wallet')
        verbose_name_plural = _('Wallets')
        ordering = ['user__username']
        indexes = [
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"Wallet for {self.user.username}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """
        Get or create a wallet for a user.
        
        Args:
            user (User): The user
            
        Returns:
            Wallet: The wallet instance
        """
        wallet, created = cls.objects.get_or_create(user=user)
        return wallet
    
    @db_transaction.atomic
    def deposit(self, amount, description=None, meta_data=None):
        """
        Deposit funds into the wallet.
        
        Args:
            amount (Decimal): The amount to deposit
            description (str, optional): Transaction description. Defaults to None.
            meta_data (dict, optional): Transaction metadata. Defaults to None.
            
        Returns:
            WalletTransaction: The created transaction
        """
        if amount <= 0:
            raise ValueError(_("Deposit amount must be positive"))
            
        self.balance += amount
        self.last_deposit_at = models.functions.Now()
        self.save(update_fields=['balance', 'last_deposit_at', 'updated_at'])
        
        # Create a transaction record
        transaction = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type=WalletTransaction.TransactionType.DEPOSIT,
            description=description or _("Deposit"),
            meta_data=meta_data or {},
        )
        
        return transaction
    
    @db_transaction.atomic
    def withdraw(self, amount, description=None, meta_data=None):
        """
        Withdraw funds from the wallet.
        
        Args:
            amount (Decimal): The amount to withdraw
            description (str, optional): Transaction description. Defaults to None.
            meta_data (dict, optional): Transaction metadata. Defaults to None.
            
        Returns:
            WalletTransaction: The created transaction
            
        Raises:
            ValueError: If the amount is not positive or if the balance is insufficient
        """
        if amount <= 0:
            raise ValueError(_("Withdrawal amount must be positive"))
            
        if self.balance < amount:
            raise ValueError(_("Insufficient balance"))
            
        self.balance -= amount
        self.last_withdrawal_at = models.functions.Now()
        self.save(update_fields=['balance', 'last_withdrawal_at', 'updated_at'])
        
        # Create a transaction record
        transaction = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
            description=description or _("Withdrawal"),
            meta_data=meta_data or {},
        )
        
        return transaction
    
    def get_transactions(self, **filters):
        """
        Get all transactions for this wallet.
        
        Args:
            **filters: Additional filters
            
        Returns:
            QuerySet: A queryset of transactions
        """
        return self.transactions.filter(**filters).order_by('-created_at')


class WalletTransaction(BaseModel):
    """
    Model for wallet transactions.
    Each transaction represents a change in the wallet balance.
    """
    class TransactionType(models.TextChoices):
        """Transaction types for wallet transactions."""
        DEPOSIT = 'deposit', _('Deposit')
        WITHDRAWAL = 'withdrawal', _('Withdrawal')
        TRANSFER = 'transfer', _('Transfer')
        COMMISSION = 'commission', _('Commission')
        PAYMENT = 'payment', _('Payment')
        REFUND = 'refund', _('Refund')
        OTHER = 'other', _('Other')
    
    wallet = models.ForeignKey(
        Wallet,
        verbose_name=_('Wallet'),
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text=_('Wallet this transaction belongs to')
    )
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Transaction amount')
    )
    transaction_type = models.CharField(
        _('Transaction Type'),
        max_length=20,
        choices=TransactionType.choices,
        help_text=_('Type of transaction')
    )
    reference = models.CharField(
        _('Reference'),
        max_length=100,
        blank=True,
        help_text=_('Transaction reference')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Transaction description')
    )
    meta_data = models.JSONField(
        _('Meta Data'),
        default=dict,
        blank=True,
        help_text=_('Additional transaction metadata')
    )
    
    class Meta:
        verbose_name = _('Wallet Transaction')
        verbose_name_plural = _('Wallet Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_type']),
            models.Index(fields=['reference']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} for {self.wallet.user.username}"
    
    @property
    def is_deposit(self):
        """Check if the transaction is a deposit."""
        return self.transaction_type == self.TransactionType.DEPOSIT
    
    @property
    def is_withdrawal(self):
        """Check if the transaction is a withdrawal."""
        return self.transaction_type == self.TransactionType.WITHDRAWAL
    
    @classmethod
    def get_by_reference(cls, reference):
        """
        Get a transaction by its reference.
        
        Args:
            reference (str): The transaction reference
            
        Returns:
            WalletTransaction: The transaction instance or None if not found
        """
        try:
            return cls.objects.get(reference=reference)
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
        return cls.objects.filter(wallet__user=user, **filters).order_by('-created_at')