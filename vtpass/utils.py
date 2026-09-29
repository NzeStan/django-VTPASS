"""
Utility functions for the VTpass package.
This module provides common utility functions used throughout the package.
"""

import uuid
import hashlib
import random
import string
from datetime import datetime, timedelta
from django.conf import settings
from django.utils.crypto import get_random_string


def generate_reference(prefix='vtpass', length=12):
    """
    Generate a unique reference.
    
    Args:
        prefix (str, optional): The reference prefix. Defaults to 'vtpass'.
        length (int, optional): The length of the random part. Defaults to 12.
        
    Returns:
        str: The generated reference
    """
    random_part = get_random_string(length, allowed_chars=string.ascii_lowercase + string.digits)
    return f"{prefix}-{random_part}"


def generate_uuid():
    """
    Generate a UUID.
    
    Returns:
        str: The generated UUID
    """
    return str(uuid.uuid4())


def generate_token(length=32):
    """
    Generate a random token.
    
    Args:
        length (int, optional): The token length. Defaults to 32.
        
    Returns:
        str: The generated token
    """
    return get_random_string(length)


def calculate_hash(text, salt=None):
    """
    Calculate a hash for a text.
    
    Args:
        text (str): The text to hash
        salt (str, optional): The salt to use. Defaults to None.
        
    Returns:
        str: The calculated hash
    """
    salt = salt or settings.SECRET_KEY
    return hashlib.sha256(f"{text}{salt}".encode()).hexdigest()


def format_currency(amount, currency='NGN'):
    """
    Format an amount as currency.
    
    Args:
        amount (float): The amount to format
        currency (str, optional): The currency code. Defaults to 'NGN'.
        
    Returns:
        str: The formatted amount
    """
    if currency == 'NGN':
        return f"₦{amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"


def format_phone_number(phone):
    """
    Format a phone number.
    
    Args:
        phone (str): The phone number to format
        
    Returns:
        str: The formatted phone number
    """
    # Remove non-numeric characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Nigerian phone number format
    if len(phone) >= 10:
        if phone.startswith('0'):
            # Convert to international format
            phone = f"+234{phone[1:]}"
        elif not phone.startswith('+'):
            # Assume Nigerian number
            if phone.startswith('234'):
                phone = f"+{phone}"
            else:
                phone = f"+234{phone}"
    
    return phone


def parse_date(date_str, formats=None):
    """
    Parse a date string.
    
    Args:
        date_str (str): The date string to parse
        formats (list, optional): The date formats to try. Defaults to None.
        
    Returns:
        datetime: The parsed date or None if parsing fails
    """
    if not date_str:
        return None
        
    formats = formats or [
        '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y',
        '%Y-%m-%d %H:%M:%S', '%d-%m-%Y %H:%M:%S',
        '%Y/%m/%d %H:%M:%S', '%d/%m/%Y %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    return None


def date_range(start_date, end_date):
    """
    Generate a range of dates.
    
    Args:
        start_date (datetime): The start date
        end_date (datetime): The end date
        
    Returns:
        list: A list of dates in the range
    """
    delta = end_date - start_date
    days = delta.days + 1
    return [start_date + timedelta(days=i) for i in range(days)]


def mask_data(data, fields_to_mask=None, mask_char='*'):
    """
    Mask sensitive data.
    
    Args:
        data (dict): The data to mask
        fields_to_mask (list, optional): The fields to mask. Defaults to None.
        mask_char (str, optional): The character to use for masking. Defaults to '*'.
        
    Returns:
        dict: The masked data
    """
    if not isinstance(data, dict):
        return data
        
    fields_to_mask = fields_to_mask or [
        'api_key', 'secret_key', 'password', 'pin', 'token',
        'card_number', 'cvv', 'account_number', 'phone', 'bvn',
    ]
    
    masked_data = data.copy()
    
    for field in fields_to_mask:
        if field in masked_data and masked_data[field]:
            value = str(masked_data[field])
            if len(value) > 6:
                # Mask all but first and last two characters
                masked_data[field] = value[:2] + mask_char * (len(value) - 4) + value[-2:]
            else:
                # Mask all characters
                masked_data[field] = mask_char * len(value)
    
    # Recursively process nested dictionaries
    for key, value in masked_data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_data(value, fields_to_mask, mask_char)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_data(item, fields_to_mask, mask_char) if isinstance(item, dict) else item
                for item in value
            ]
    
    return masked_data


def parse_commission_rate(rate):
    """
    Parse a commission rate.
    
    Args:
        rate (str or float): The commission rate
        
    Returns:
        float: The parsed rate as a decimal
    """
    if isinstance(rate, (int, float)):
        return float(rate)
        
    # Parse percentage
    if isinstance(rate, str) and '%' in rate:
        rate = rate.replace('%', '').strip()
        try:
            return float(rate) / 100
        except ValueError:
            pass
    
    try:
        return float(rate)
    except (ValueError, TypeError):
        return 0


def calculate_commission(amount, rate):
    """
    Calculate a commission amount.
    
    Args:
        amount (float): The amount
        rate (float or str): The commission rate
        
    Returns:
        float: The calculated commission
    """
    rate = parse_commission_rate(rate)
    return float(amount) * rate


def validate_phone_number(phone):
    """
    Validate a phone number.
    
    Args:
        phone (str): The phone number to validate
        
    Returns:
        bool: True if the phone number is valid, False otherwise
    """
    # Remove non-numeric characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Check if the phone number has a valid length
    if len(phone) < 10 or len(phone) > 15:
        return False
    
    # Check if the phone number starts with a valid country code or 0
    if not (phone.startswith('0') or phone.startswith('234') or phone.startswith('+234')):
        return False
    
    return True


def extract_url_params(url):
    """
    Extract parameters from a URL.
    
    Args:
        url (str): The URL to extract parameters from
        
    Returns:
        dict: The extracted parameters
    """
    if not url or '?' not in url:
        return {}
        
    params_str = url.split('?', 1)[1]
    params = {}
    
    for param in params_str.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value
    
    return params


def build_url_with_params(url, params):
    """
    Build a URL with parameters.
    
    Args:
        url (str): The base URL
        params (dict): The parameters to add
        
    Returns:
        str: The URL with parameters
    """
    if not params:
        return url
        
    # Remove existing parameters
    if '?' in url:
        url = url.split('?', 1)[0]
    
    # Build the parameters string
    params_str = '&'.join(f"{key}={value}" for key, value in params.items())
    
    return f"{url}?{params_str}"