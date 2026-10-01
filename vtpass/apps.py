from django.apps import AppConfig
from django.core import checks
from django.utils.translation import gettext_lazy as _


class VTpassConfig(AppConfig):
    name = "vtpass"
    label = "vtpass"
    verbose_name = _("VTpass")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from vtpass import receivers  # noqa: F401  (connects built-in receivers)

        checks.register(check_configuration, "vtpass")


def check_configuration(app_configs=None, **kwargs):
    from vtpass.settings import vtpass_settings

    messages = []
    for problem in vtpass_settings.check():
        messages.append(checks.Warning(problem, id="vtpass.W001"))
    if not vtpass_settings.SANDBOX and not vtpass_settings.WEBHOOK.get("TOKEN"):
        messages.append(checks.Warning(
            "VTPASS['WEBHOOK']['TOKEN'] is empty in live mode; anyone who finds your webhook URL can post to it.",
            hint="Set a long random token and register https://<host>/<prefix>/webhook/<token>/ on VTpass.",
            id="vtpass.W002",
        ))
    if vtpass_settings.USE_CELERY:
        try:
            import celery  # noqa: F401
        except ImportError:
            messages.append(checks.Error(
                "VTPASS['USE_CELERY'] is True but Celery is not installed.",
                hint="pip install django-vtpass[celery]", id="vtpass.E001",
            ))
    wallet = vtpass_settings.WALLET_BACKEND
    if wallet:
        try:
            vtpass_settings.import_from_setting("WALLET_BACKEND")
        except Exception as exc:
            messages.append(checks.Error(str(exc), id="vtpass.E002"))
    if vtpass_settings.NOTIFICATIONS.get("ENABLED") and not vtpass_settings.NOTIFICATIONS.get("BACKENDS"):
        messages.append(checks.Warning(
            "Notifications are enabled but no BACKENDS are configured.", id="vtpass.W003"
        ))
    return messages
