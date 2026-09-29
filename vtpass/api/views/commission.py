"""
Commission views for the VTpass API.
This module defines views for commission operations.
"""

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from vtpass.models import Commission, CommissionRate
from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import CommissionSerializer, CommissionRateSerializer
from vtpass.exceptions import VTpassError


class CommissionViewSet(
    BaseViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin
):
    """
    API endpoint for commissions.
    Provides `list`, `retrieve`, `rates`, and `summary` actions.
    """
    queryset = Commission.objects.all()
    serializer_class = CommissionSerializer
    filterset_fields = ['is_paid', 'transaction__service_type']
    search_fields = ['transaction__reference', 'user__username', 'user__email']
    ordering_fields = ['created_at', 'paid_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Get the commission queryset.
        Filter commissions for the current user if not staff.
        """
        queryset = super().get_queryset()
        
        # Filter by user if not staff
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def rates(self, request):
        """
        Get commission rates.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with commission rates
        """
        # Get active commission rates
        rates = CommissionRate.objects.filter(active=True)
        serializer = CommissionRateSerializer(rates, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Commission rates retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get commission summary.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with commission summary
        """
        queryset = self.get_queryset()
        
        # Filter by date range if provided
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Calculate summary statistics
        summary = {
            'total_amount': queryset.aggregate(Sum('amount'))['amount__sum'] or 0,
            'total_count': queryset.count(),
            'paid_amount': queryset.filter(is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0,
            'paid_count': queryset.filter(is_paid=True).count(),
            'unpaid_amount': queryset.filter(is_paid=False).aggregate(Sum('amount'))['amount__sum'] or 0,
            'unpaid_count': queryset.filter(is_paid=False).count(),
        }
        
        # Get summary by service type
        service_types = queryset.values('transaction__service_type').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        summary['by_service_type'] = service_types
        
        # Get summary by month for the last 6 months
        now = timezone.now()
        months = []
        
        for i in range(5, -1, -1):
            month_start = (now - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = month_start.month + 1
            next_month_year = month_start.year
            
            if next_month > 12:
                next_month = 1
                next_month_year += 1
                
            month_end = month_start.replace(year=next_month_year, month=next_month, day=1) - timedelta(seconds=1)
            
            month_amount = queryset.filter(
                created_at__gte=month_start,
                created_at__lte=month_end
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            months.append({
                'month': month_start.strftime('%b %Y'),
                'amount': month_amount,
            })
        
        summary['by_month'] = months
        
        return self.get_success_response(
            summary,
            message="Commission summary retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def unpaid(self, request):
        """
        Get unpaid commissions.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with unpaid commissions
        """
        # Get unpaid commissions
        queryset = self.get_queryset().filter(is_paid=False)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Unpaid commissions retrieved successfully"
        )