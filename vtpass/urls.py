"""
URL configuration for the VTpass package.
This module defines URL patterns for the VTpass package.
"""

from django.urls import path, include
from django.contrib import admin

from vtpass.api.urls import router as api_router


app_name = 'vtpass'

# URLs for admin dashboard (if needed beyond Django admin)
dashboard_urlpatterns = [
    # Add custom dashboard views here if needed
]

# URLs for webhook handlers
webhook_urlpatterns = [
    # Add webhook handlers here if needed
    # path('webhook/', views.webhook_handler, name='webhook'),
]

# Main URL patterns
urlpatterns = [
    # API URLs
    path('api/', include(api_router.urls)),
    
    # Dashboard URLs
    path('dashboard/', include((dashboard_urlpatterns, 'dashboard'))),
    
    # Webhook URLs
    path('webhooks/', include((webhook_urlpatterns, 'webhooks'))),
]