"""
Base views for the VTpass API.
This module defines base views that other views inherit from.
"""

from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from vtpass.exceptions import VTpassError, VTpassValidationError, VTpassServiceError
from vtpass.logger import logger, log_error


class BaseViewSet(viewsets.GenericViewSet):
    """
    Base viewset for all VTpass API viewsets.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'view': self,
        })
        return context
    
    def handle_exception(self, exc):
        """
        Handle exceptions and provide appropriate responses.
        """
        if isinstance(exc, VTpassValidationError):
            # Handle validation errors
            data = {
                'success': False,
                'message': str(exc),
                'errors': exc.errors,
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, VTpassServiceError):
            # Handle service errors
            data = {
                'success': False,
                'message': str(exc),
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, VTpassError):
            # Handle other VTpass errors
            data = {
                'success': False,
                'message': str(exc),
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
            
        # Let the parent handle other exceptions
        return super().handle_exception(exc)
    
    def get_success_response(self, data=None, message=None, status_code=status.HTTP_200_OK):
        """
        Get a success response.
        
        Args:
            data: The response data
            message: The success message
            status_code: The HTTP status code
            
        Returns:
            Response: The API response
        """
        response_data = {
            'success': True,
            'message': message or 'Operation successful',
        }
        
        if data is not None:
            response_data['data'] = data
            
        return Response(response_data, status=status_code)
    
    def get_error_response(self, message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        """
        Get an error response.
        
        Args:
            message: The error message
            errors: The validation errors
            status_code: The HTTP status code
            
        Returns:
            Response: The API response
        """
        response_data = {
            'success': False,
            'message': message,
        }
        
        if errors is not None:
            response_data['errors'] = errors
            
        return Response(response_data, status=status_code)