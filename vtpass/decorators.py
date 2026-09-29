"""
Decorators for the VTpass package.
This module provides custom decorators for the VTpass package.
"""

import time
import functools
import threading
from django.db import transaction

from vtpass.logger import logger, log_error


def log_execution_time(func):
    """
    Decorator to log the execution time of a function.
    
    Args:
        func: The function to decorate
        
    Returns:
        function: The decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        logger.debug(f"Function {func.__name__} executed in {execution_time:.4f}s")
        
        return result
    return wrapper


def transaction_atomic(func):
    """
    Decorator to wrap a function in a database transaction.
    
    Args:
        func: The function to decorate
        
    Returns:
        function: The decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)
    return wrapper


def retry(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Decorator to retry a function on exceptions.
    
    Args:
        max_retries (int, optional): The maximum number of retries. Defaults to 3.
        delay (int, optional): The initial delay between retries in seconds. Defaults to 1.
        backoff (int, optional): The backoff factor for the delay. Defaults to 2.
        exceptions (tuple, optional): The exceptions to catch. Defaults to (Exception,).
        
    Returns:
        function: The decorator
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            num_retries = 0
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    num_retries += 1
                    
                    if num_retries > max_retries:
                        # Log the error and re-raise the exception
                        log_error(e, {
                            'function': func.__name__,
                            'retries': num_retries,
                            'args': args,
                            'kwargs': kwargs,
                        })
                        raise
                    
                    # Log the retry
                    logger.warning(
                        f"Retrying {func.__name__} ({num_retries}/{max_retries}) "
                        f"after {current_delay}s due to {e.__class__.__name__}: {str(e)}"
                    )
                    
                    # Sleep before retrying
                    time.sleep(current_delay)
                    
                    # Increase the delay for the next retry
                    current_delay *= backoff
        
        return wrapper
    return decorator


def async_task(func):
    """
    Decorator to run a function asynchronously in a separate thread.
    
    Args:
        func: The function to decorate
        
    Returns:
        function: The decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper


def require_params(*required_params):
    """
    Decorator to require specific parameters in a request.
    
    Args:
        *required_params: The required parameters
        
    Returns:
        function: The decorator
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get parameters from request
            params = request.GET if request.method == 'GET' else request.POST
            
            # Check for missing parameters
            missing_params = [param for param in required_params if param not in params]
            
            if missing_params:
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': f"Missing required parameters: {', '.join(missing_params)}",
                }, status=400)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def webhook_receiver(secret_param='signature'):
    """
    Decorator to handle webhook requests.
    
    Args:
        secret_param (str, optional): The parameter name for the webhook secret. Defaults to 'signature'.
        
    Returns:
        function: The decorator
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from vtpass.settings import vtpass_settings
            
            # Check if webhook is enabled
            if not vtpass_settings._settings['WEBHOOK']['ENABLED']:
                from django.http import HttpResponse
                return HttpResponse("Webhooks are disabled", status=404)
            
            # Verify webhook signature if provided
            webhook_secret = vtpass_settings._settings['WEBHOOK'].get('SECRET')
            if webhook_secret:
                signature = request.headers.get(f'X-VTpass-{secret_param}')
                
                if not signature:
                    from django.http import HttpResponse
                    return HttpResponse("Missing signature", status=401)
                
                # Verify signature
                # TODO: Implement signature verification
            
            # Log the webhook request
            logger.info(f"Received webhook: {request.path} | Method: {request.method}")
            
            # Process the webhook
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator