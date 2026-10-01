"""
django-vtpass: the complete VTpass integration for Django.

    from vtpass.services import VTpass
    vt = VTpass()
    vt.airtime.buy("08011111111", 100, user=request.user)
"""

__version__ = "1.0.0"

__all__ = ["VTpass", "VTpassClient", "MessagingClient", "__version__"]


def __getattr__(name):
    # Lazy imports keep `import vtpass` cheap and safe before Django is set up.
    if name == "VTpass":
        from vtpass.services import VTpass

        return VTpass
    if name == "VTpassClient":
        from vtpass.client import VTpassClient

        return VTpassClient
    if name == "MessagingClient":
        from vtpass.messaging import MessagingClient

        return MessagingClient
    raise AttributeError(f"module 'vtpass' has no attribute {name!r}")
