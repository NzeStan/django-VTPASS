from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class VTpassConfig(AppConfig):
    """
    Django app configuration for VTpass integration.
    """
    name = 'vtpass'
    verbose_name = _('VTpass Integration')
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        This method imports and registers signals.
        """
        # Import signals to register them
        import vtpass.signals  # noqa