"""
Signals for the VTpass package.
This module defines signals that are triggered by various events.
"""

import requests
import json
from datetime import datetime
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.db import transaction

from vtpass.models.transaction import Transaction
from vtpass.models.commission import Commission
from vtpass.models.wallet import Wallet, WalletTransaction
from vtpass.constants import TransactionStatus
from vtpass.settings import vtpass_settings
from vtpass.logger import logger, log_error


# Custom signals
transaction_completed = Signal()
transaction_failed = Signal()
transaction_status_changed = Signal()
commission_earned = Signal()
wallet_changed = Signal()


@receiver(pre_save, sender=Transaction)
def transaction_pre_save(sender, instance, **kwargs):
    """
    Signal handler for pre-save events on Transaction model.
    This handler is called before a transaction is saved.
    
    Args:
        sender: The model class
        instance: The actual instance being saved
        **kwargs: Additional keyword arguments
    """
    # Check if this is an existing instance being updated
    try:
        old_instance = Transaction.objects.get(pk=instance.pk)
        
        # If status has changed
        if old_instance.status != instance.status:
            # Set completed_at if status is now completed
            if instance.status == TransactionStatus.COMPLETED and not instance.completed_at:
                instance.completed_at = timezone.now()
    except Transaction.DoesNotExist:
        # This is a new instance being created
        pass


@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for post-save events on Transaction model.
    This handler is called after a transaction is saved.
    
    Args:
        sender: The model class
        instance: The actual instance being saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    # If this is a new transaction, nothing special to do
    if created:
        return
        
    # Get the previous instance to check if the status has changed
    try:
        old_instance = Transaction.objects.get(pk=instance.pk)
        
        # If status hasn't changed, nothing to do
        if old_instance.status == instance.status:
            return
    except Transaction.DoesNotExist:
        # This shouldn't happen, but just in case
        return
        
    # Send the custom signal for status change
    transaction_status_changed.send(
        sender=sender, 
        instance=instance, 
        old_status=old_instance.status, 
        new_status=instance.status
    )
    
    # If the transaction is now completed
    if instance.status == TransactionStatus.COMPLETED:
        # Create commission if enabled
        if vtpass_settings._settings['COMMISSION']['ENABLED']:
            try:
                with transaction.atomic():
                    commission = Commission.create_from_transaction(instance)
                    if commission:
                        commission_earned.send(sender=Commission, instance=commission)
                    
                    # Add to user wallet if available and enabled
                    if instance.user and hasattr(instance.user, 'vtpass_wallet'):
                        wallet = instance.user.vtpass_wallet
                        description = f"Commission for transaction {instance.reference}"
                        meta_data = {
                            'transaction_reference': instance.reference,
                            'transaction_id': instance.transaction_id,
                            'commission_id': commission.id if commission else None,
                        }
                        wallet.deposit(
                            amount=commission.amount if commission else 0,
                            description=description,
                            meta_data=meta_data
                        )
            except Exception as e:
                log_error(e, {
                    'transaction_id': instance.pk,
                    'reference': instance.reference,
                })
        
        # Send the completed signal
        transaction_completed.send(sender=sender, instance=instance)
        
        # Send callback webhook if configured
        send_transaction_webhook(instance)
    
    # If the transaction has failed
    elif instance.status == TransactionStatus.FAILED:
        # Send the failed signal
        transaction_failed.send(sender=sender, instance=instance)
        
        # Send callback webhook if configured
        send_transaction_webhook(instance)


@receiver(post_save, sender=WalletTransaction)
def wallet_transaction_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for post-save events on WalletTransaction model.
    This handler is called after a wallet transaction is saved.
    
    Args:
        sender: The model class
        instance: The actual instance being saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        # Send the wallet changed signal
        wallet_changed.send(
            sender=Wallet, 
            instance=instance.wallet, 
            transaction=instance
        )


def send_transaction_webhook(transaction):
    """
    Send a webhook notification for a transaction.
    
    Args:
        transaction: The transaction instance
    """
    # Check if webhooks are enabled
    if not vtpass_settings._settings['WEBHOOK']['ENABLED']:
        return
        
    # If no webhook URL is specified, try the callback_url from the transaction
    webhook_url = (
        vtpass_settings._settings['WEBHOOK']['URL'] or 
        transaction.callback_url
    )
    
    if not webhook_url:
        return
        
    # Prepare the payload
    payload = {
        'event': 'transaction.status_change',
        'transaction': {
            'id': str(transaction.id),
            'reference': transaction.reference,
            'transaction_id': transaction.transaction_id,
            'amount': str(transaction.amount),
            'status': transaction.status,
            'service_type': transaction.service_type,
            'service_name': transaction.service.name,
            'created_at': transaction.created_at.isoformat(),
            'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None,
        }
    }
    
    # Add webhook secret if available
    headers = {'Content-Type': 'application/json'}
    webhook_secret = vtpass_settings._settings['WEBHOOK'].get('SECRET')
    if webhook_secret:
        headers['X-VTpass-Signature'] = webhook_secret
    
    try:
        # Send the webhook
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=vtpass_settings._settings['WEBHOOK'].get('TIMEOUT', 10)
        )
        
        # Log the response
        logger.info(
            f"Webhook sent for transaction {transaction.reference}. "
            f"Status: {response.status_code}, Response: {response.text[:100]}..."
        )
    except Exception as e:
        log_error(e, {
            'webhook_url': webhook_url,
            'transaction_reference': transaction.reference,
        })


# Connect to transaction_completed signal to handle post-completion tasks
@receiver(transaction_completed)
def handle_transaction_completed(sender, instance, **kwargs):
    """
    Handle transaction completed events.
    
    Args:
        sender: The sender class
        instance: The transaction instance
        **kwargs: Additional keyword arguments
    """
    logger.info(f"Transaction {instance.reference} completed successfully")
    
    # Additional post-completion tasks can be added here
    # For example, sending notifications, updating statistics, etc.


# Connect to transaction_failed signal to handle failed transactions
@receiver(transaction_failed)
def handle_transaction_failed(sender, instance, **kwargs):
    """
    Handle transaction failed events.
    
    Args:
        sender: The sender class
        instance: The transaction instance
        **kwargs: Additional keyword arguments
    """
    logger.warning(f"Transaction {instance.reference} failed: {instance.response_message}")
    
    # Additional failure handling tasks can be added here
    # For example, sending notifications, triggering refunds, etc.


# Connect to commission_earned signal
@receiver(commission_earned)
def handle_commission_earned(sender, instance, **kwargs):
    """
    Handle commission earned events.
    
    Args:
        sender: The sender class
        instance: The commission instance
        **kwargs: Additional keyword arguments
    """
    logger.info(
        f"Commission of {instance.amount} earned for transaction {instance.transaction.reference}"
    )
    
    # Additional commission handling tasks can be added here