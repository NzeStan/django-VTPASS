"""
Webhook URLs (no DRF required)::

    path("vtpass/", include("vtpass.urls"))

The optional REST API lives in ``vtpass.api.urls``::

    path("api/vtpass/", include("vtpass.api.urls"))
"""

from django.urls import path

from vtpass import views

app_name = "vtpass"

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("webhook/<str:token>/", views.webhook, name="webhook-token"),
]
