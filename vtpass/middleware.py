"""
Middleware for the VTpass package.
This module provides custom middleware for the VTpass package.
"""

import time
import json
import traceback
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.http import JsonResponse

from vtpass.logger import logger, log_error
from vtpass.utils import mask_data


class RequestLogMiddleware(MiddlewareMixin):
    """
    Middleware to log requests.
    """
    def process_request(self, request):
        """
        Process a request.
        
        Args:
            request: The request object
        """
        # Skip for non-VTpass requests
        try:
            resolver_match = resolve(request.path)
            if not resolver_match.app_name == 'vtpass':
                return None
        except:
            return None
            
        # Add request start time
        request.vtpass_start_time = time.time()
        
        # Log the request
        method = request.method
        path = request.path
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
        
        if method in ['POST', 'PUT', 'PATCH'] and request.body:
            try:
                body = json.loads(request.body)
                body = mask_data(body)
                logger.debug(f"VTpass Request: {method} {path} | User: {user} | Body: {body}")
            except:
                logger.debug(f"VTpass Request: {method} {path} | User: {user} | Body: (not JSON)")
        else:
            logger.debug(f"VTpass Request: {method} {path} | User: {user}")
        
        return None
    
    def process_response(self, request, response):
        """
        Process a response.
        
        Args:
            request: The request object
            response: The response object
            
        Returns:
            HttpResponse: The processed response
        """
        # Skip for non-VTpass requests
        try:
            resolver_match = resolve(request.path)
            if not resolver_match.app_name == 'vtpass':
                return response
        except:
            return response
            
        # Log the response time if start time was recorded
        if hasattr(request, 'vtpass_start_time'):
            duration = time.time() - request.vtpass_start_time
            path = request.path
            method = request.method
            status = response.status_code
            
            logger.debug(f"VTpass Response: {method} {path} | Status: {status} | Duration: {duration:.4f}s")
        
        return response


class APIExceptionMiddleware(MiddlewareMixin):
    """
    Middleware to handle API exceptions.
    """
    def process_exception(self, request, exception):
        """
        Process an exception.
        
        Args:
            request: The request object
            exception: The exception
            
        Returns:
            HttpResponse: The exception response or None
        """
        # Skip for non-VTpass API requests
        try:
            resolver_match = resolve(request.path)
            if not (resolver_match.app_name == 'vtpass' and '/api/' in request.path):
                return None
        except:
            return None
            
        # Log the exception
        log_error(exception, {
            'path': request.path,
            'method': request.method,
            'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous',
        })
        
        # Return a JSON response
        return JsonResponse({
            'success': False,
            'message': str(exception),
            'error': exception.__class__.__name__,
            'detail': traceback.format_exc() if 'debug' in request.GET else None,
        }, status=500)