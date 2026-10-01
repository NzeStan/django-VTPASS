"""Customers see only their own transactions; staff can see all of them."""

import uuid

from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import NotFound

from vtpass.api.serializers import TransactionSerializer, public_message
from vtpass.api.views.base import VTpassAPIView, VTpassPagination
from vtpass.models import Transaction


def visible_transactions(request):
    qs = Transaction.objects.all()
    if not getattr(request.user, "is_staff", False):
        qs = qs.filter(user=request.user)
    return qs


def lookup(request, reference):
    lookup_q = Q(request_id=reference)
    try:
        lookup_q |= Q(uid=uuid.UUID(str(reference)))
    except ValueError:
        pass
    txn = visible_transactions(request).filter(lookup_q).first()
    if txn is None:
        raise NotFound("Transaction not found.")
    return txn


class TransactionListView(VTpassAPIView, generics.ListAPIView):
    serializer_class = TransactionSerializer
    pagination_class = VTpassPagination

    def get_queryset(self):
        qs = visible_transactions(self.request)
        params = self.request.query_params
        for field in ("status", "service_id", "category"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("search"):
            term = params["search"]
            qs = qs.filter(Q(billers_code__icontains=term) | Q(phone__icontains=term) | Q(request_id=term))
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return self.ok(response.data)


class TransactionDetailView(VTpassAPIView):
    def get(self, request, reference):
        return self.ok(TransactionSerializer(lookup(request, reference)).data)


class TransactionRequeryView(VTpassAPIView):
    """Refresh a pending transaction from VTpass (owners may call it; it is read-only on VTpass)."""

    def post(self, request, reference):
        txn = lookup(request, reference)
        if txn.is_open:
            txn = self.vt.requery(txn)
        return self.ok(TransactionSerializer(txn).data, public_message(txn))
