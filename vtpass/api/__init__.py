"""
Optional REST API built on Django REST framework.

    pip install django-vtpass[drf]
    path("api/vtpass/", include("vtpass.api.urls"))

Every endpoint is a thin wrapper over :class:`vtpass.services.VTpass`; mount
only what you need, or subclass the views to change permissions/behaviour.
"""
