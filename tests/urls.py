from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("vtpass/", include("vtpass.urls")),
    path("api/vtpass/", include("vtpass.api.urls")),
]
