"""Wallet balance/history (built-in wallet backend) and saved beneficiaries."""

from rest_framework import generics
from rest_framework.exceptions import NotFound

from vtpass.api.serializers import BeneficiarySerializer, WalletEntrySerializer
from vtpass.api.views.base import VTpassAPIView, VTpassPagination
from vtpass.models import Beneficiary, WalletEntry
from vtpass.settings import vtpass_settings
from vtpass.wallets import get_wallet_backend


class WalletView(VTpassAPIView):
    def get(self, request):
        backend = get_wallet_backend()
        if backend is None:
            raise NotFound("Wallets are not enabled.")
        return self.ok({"balance": str(backend.balance(request.user)), "currency": vtpass_settings.CURRENCY})


class WalletEntryListView(VTpassAPIView, generics.ListAPIView):
    serializer_class = WalletEntrySerializer
    pagination_class = VTpassPagination

    def get_queryset(self):
        qs = WalletEntry.objects.filter(wallet__user=self.request.user).select_related("transaction")
        kind = self.request.query_params.get("kind")
        return qs.filter(kind=kind) if kind else qs

    def list(self, request, *args, **kwargs):
        return self.ok(super().list(request, *args, **kwargs).data)


class BeneficiaryListCreateView(VTpassAPIView, generics.ListCreateAPIView):
    serializer_class = BeneficiarySerializer
    pagination_class = VTpassPagination

    def get_queryset(self):
        qs = Beneficiary.objects.filter(user=self.request.user)
        for field in ("service_id", "category"):
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        return self.ok(super().list(request, *args, **kwargs).data)

    def create(self, request, *args, **kwargs):
        if Beneficiary.objects.filter(
            user=request.user, service_id=request.data.get("service_id"), billers_code=request.data.get("billers_code")
        ).exists():
            return self.fail("This beneficiary is already saved.", status=409)
        response = super().create(request, *args, **kwargs)
        return self.ok(response.data, "Beneficiary saved.", status=201)


class BeneficiaryDetailView(VTpassAPIView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BeneficiarySerializer
    lookup_field = "uid"
    lookup_url_kwarg = "uid"

    def get_queryset(self):
        return Beneficiary.objects.filter(user=self.request.user)
