"""
Wallet views for the VTpass API.
This module defines views for wallet operations.
"""

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from vtpass.models import Wallet, WalletTransaction
from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import (
    WalletSerializer, WalletTransactionSerializer,
    WalletDepositSerializer, WalletWithdrawSerializer
)
from vtpass.exceptions import VTpassError


class WalletViewSet(
    BaseViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin
):
    """
    API endpoint for wallets.
    Provides `list`, `retrieve`, `transactions`, `deposit`, and `withdraw` actions.
    """
    queryset = Wallet.objects.filter(active=True)
    serializer_class = WalletSerializer
    filterset_fields = ['active']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['created_at', 'updated_at', 'balance']
    ordering = ['-balance']
    
    def get_queryset(self):
        """
        Get the wallet queryset.
        Filter wallets for the current user if not staff.
        """
        queryset = super().get_queryset()
        
        # Filter by user if not staff
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
            
        return queryset
    
    def get_object(self):
        """
        Get the wallet object.
        If pk is 'me', get the current user's wallet.
        """
        if self.kwargs.get('pk') == 'me':
            # Get or create wallet for current user
            wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
            self.check_object_permissions(self.request, wallet)
            return wallet
            
        return super().get_object()
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """
        Get transactions for a wallet.
        
        Args:
            request: The request object
            pk: The wallet ID
            
        Returns:
            Response: The API response with wallet transactions
        """
        wallet = self.get_object()
        
        # Get transactions
        transactions = wallet.transactions.all().order_by('-created_at')
        
        # Apply pagination
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = WalletTransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = WalletTransactionSerializer(transactions, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Wallet transactions retrieved successfully"
        )
    
    @action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        """
        Deposit funds into a wallet.
        
        Args:
            request: The request object
            pk: The wallet ID
            
        Returns:
            Response: The API response
        """
        wallet = self.get_object()
        
        # Validate the deposit data
        serializer = WalletDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Make the deposit
            transaction = wallet.deposit(
                amount=serializer.validated_data['amount'],
                description=serializer.validated_data.get('description', 'API Deposit'),
                meta_data=serializer.validated_data.get('meta_data', {})
            )
            
            # Return the transaction and updated wallet
            data = {
                'transaction': WalletTransactionSerializer(transaction).data,
                'wallet': WalletSerializer(wallet).data
            }
            
            return self.get_success_response(
                data,
                message="Funds deposited successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """
        Withdraw funds from a wallet.
        
        Args:
            request: The request object
            pk: The wallet ID
            
        Returns:
            Response: The API response
        """
        wallet = self.get_object()
        
        # Validate the withdrawal data
        serializer = WalletWithdrawSerializer(
            data=request.data,
            context={'wallet': wallet}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Make the withdrawal
            transaction = wallet.withdraw(
                amount=serializer.validated_data['amount'],
                description=serializer.validated_data.get('description', 'API Withdrawal'),
                meta_data=serializer.validated_data.get('meta_data', {})
            )
            
            # Return the transaction and updated wallet
            data = {
                'transaction': WalletTransactionSerializer(transaction).data,
                'wallet': WalletSerializer(wallet).data
            }
            
            return self.get_success_response(
                data,
                message="Funds withdrawn successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['get'])
    def my_wallet(self, request):
        """
        Get the current user's wallet.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with the user's wallet
        """
        # Get or create wallet for current user
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(wallet)
        
        message = "Wallet created successfully" if created else "Wallet retrieved successfully"
        
        return self.get_success_response(
            serializer.data,
            message=message
        )