"""
Logging module for the VTpass package.
This module sets up a configurable logger for the package.
"""

import logging
import os
import sys
from datetime import datetime
from django.conf import settings
from vtpass.settings import vtpass_settings


# Create a logger for the package
logger = logging.getLogger('vtpass')

# Initialize logger once
_logger_initialized = False


def setup_logger():
    """
    Set up the VTpass logger with the configured log level and handlers.
    This function can be called multiple times but will only set up the logger once.
    """
    global _logger_initialized
    
    if _logger_initialized:
        return
    
    # Set the log level from settings
    logger.setLevel(vtpass_settings.log_level)
    
    # Clear any existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers = []
    
    # Create a formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if LOG_FILE is specified
    log_file = vtpass_settings._settings.get('LOG_FILE')
    if log_file:
        # Ensure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _logger_initialized = True


def log_api_request(endpoint, method, data=None, params=None):
    """
    Log an API request to VTpass.
    
    Args:
        endpoint (str): The API endpoint being called
        method (str): The HTTP method
        data (dict, optional): The request data
        params (dict, optional): The query parameters
    """
    setup_logger()
    logger.debug(
        f"VTpass API Request: {method} {endpoint} | Data: {data} | Params: {params}"
    )


def log_api_response(endpoint, method, status_code, data):
    """
    Log an API response from VTpass.
    
    Args:
        endpoint (str): The API endpoint that was called
        method (str): The HTTP method
        status_code (int): The HTTP status code
        data (dict): The response data
    """
    setup_logger()
    
    # Determine log level based on status code
    if 200 <= status_code < 300:
        log_level = logging.DEBUG
    elif 400 <= status_code < 500:
        log_level = logging.WARNING
    else:
        log_level = logging.ERROR
    
    # Mask sensitive information
    masked_data = mask_sensitive_data(data)
    
    logger.log(
        log_level,
        f"VTpass API Response: {method} {endpoint} | Status: {status_code} | Data: {masked_data}"
    )


def log_transaction(transaction_type, transaction_id, amount, status, metadata=None):
    """
    Log a transaction.
    
    Args:
        transaction_type (str): The type of transaction
        transaction_id (str): The transaction ID
        amount (float): The transaction amount
        status (str): The transaction status
        metadata (dict, optional): Additional transaction metadata
    """
    setup_logger()
    logger.info(
        f"Transaction: {transaction_type} | ID: {transaction_id} | "
        f"Amount: {amount} | Status: {status} | Metadata: {metadata}"
    )


def log_error(error, context=None):
    """
    Log an error.
    
    Args:
        error (Exception): The error that occurred
        context (dict, optional): Additional context for the error
    """
    setup_logger()
    
    if isinstance(error, Exception):
        error_message = str(error)
        error_type = type(error).__name__
    else:
        error_message = str(error)
        error_type = "Unknown"
    
    logger.error(
        f"Error: {error_type} - {error_message} | Context: {context}",
        exc_info=isinstance(error, Exception)
    )


def mask_sensitive_data(data):
    """
    Mask sensitive information in the data for logging.
    
    Args:
        data (dict): The data to mask
        
    Returns:
        dict: The masked data
    """
    if not isinstance(data, dict):
        return data
        
    masked_data = data.copy()
    
    # List of sensitive fields to mask
    sensitive_fields = [
        'api_key', 'secret_key', 'password', 'pin', 'token',
        'card_number', 'cvv', 'expiry_month', 'expiry_year',
        'phone', 'phone_number', 'account_number', 'bvn',
    ]
    
    for field in sensitive_fields:
        if field in masked_data and masked_data[field]:
            # Mask the value, keeping the first and last characters visible
            value = str(masked_data[field])
            if len(value) > 6:
                masked_data[field] = value[:2] + '*' * (len(value) - 4) + value[-2:]
            else:
                masked_data[field] = '*' * len(value)
    
    # Recursively process nested dictionaries
    for key, value in masked_data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value)
    
    return masked_data


# Set up the logger when the module is imported
setup_logger()