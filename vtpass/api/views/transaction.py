"""
Transaction views for the VTpass API.
This module defines views for transaction operations.
"""

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from vtpass.models import Transaction
from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer
from vtpass.services.base import BaseService
from vtpass.exceptions import VTpassError, VTpassServiceError


class TransactionViewSet(
    BaseViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin
):
    """
    API endpoint for transactions.
    Provides `list`, `retrieve`, and `verify` actions.
    """
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filterset_fields = ['status', 'service_type', 'reference', 'transaction_id']
    search_fields = ['reference', 'transaction_id', 'phone', 'email']
    ordering_fields = ['created_at', 'updated_at', 'completed_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Get the transaction queryset.
        Filter transactions for the current user if not staff.
        """
        queryset = super().get_queryset()
        
        # Filter by user if not staff
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
            
        return queryset
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify a transaction.
        
        Args:
            request: The request object
            pk: The transaction ID
            
        Returns:
            Response: The API response
        """
        transaction = self.get_object()
        
        # Only pending transactions need verification
        if not transaction.is_pending:
            return self.get_success_response(
                self.get_serializer(transaction).data,
                message="Transaction already verified"
            )
        
        try:
            # Check the transaction status
            service = BaseService()
            updated_transaction = service.check_transaction_status(transaction)
            
            # Return the updated transaction
            return self.get_success_response(
                self.get_serializer(updated_transaction).data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent transactions.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Limit to 10 most recent transactions
        queryset = self.get_queryset().order_by('-created_at')[:10]
        serializer = self.get_serializer(queryset, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Recent transactions retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get transaction statistics.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with transaction statistics
        """
        queryset = self.get_queryset()
        
        # Calculate statistics
        stats = {
            'total_count': queryset.count(),
            'completed_count': queryset.filter(status='completed').count(),
            'pending_count': queryset.filter(status='pending').count(),
            'failed_count': queryset.filter(status='failed').count(),
        }
        
        return self.get_success_response(
            stats,
            message="Transaction statistics retrieved successfully"
        )