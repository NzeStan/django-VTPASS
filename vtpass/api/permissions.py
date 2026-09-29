"""
Permissions for the VTpass API.
This module defines custom permissions for the VTpass API.
"""

from rest_framework import permissions


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or staff to access it.
    """
    def has_object_permission(self, request, view, obj):
        """
        Check if the user has permission to access the object.
        
        Args:
            request: The request object
            view: The view object
            obj: The object to check permission for
            
        Returns:
            bool: True if the user has permission, False otherwise
        """
        # Staff can access anything
        if request.user.is_staff:
            return True
            
        # Check if the object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        # Check if the object has a wallet attribute with a user
        if hasattr(obj, 'wallet') and hasattr(obj.wallet, 'user'):
            return obj.wallet.user == request.user
            
        # Check if the object has a transaction attribute with a user
        if hasattr(obj, 'transaction') and hasattr(obj.transaction, 'user'):
            return obj.transaction.user == request.user
            
        return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    """
    def has_permission(self, request, view):
        """
        Check if the user has permission to access the view.
        
        Args:
            request: The request object
            view: The view object
            
        Returns:
            bool: True if the user has permission, False otherwise
        """
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
            
        # Write permissions are only allowed to admin users
        return request.user.is_staff