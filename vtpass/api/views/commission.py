"""Admin reporting: revenue, VTpass commission, fees, discounts, cashback and profit."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from vtpass.api.permissions import admin_permissions
from vtpass.api.views.base import VTpassAPIView
from vtpass.constants import Status
from vtpass.models import Transaction


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.make_aware(datetime.strptime(value, "%Y-%m-%d"))
    except ValueError:
        return None


class EarningsReportView(VTpassAPIView):
    """``GET ?start=YYYY-MM-DD&end=YYYY-MM-DD`` – totals of successful sales, grouped by category."""

    def get_permissions(self):
        return [p() for p in admin_permissions()]

    def get(self, request):
        qs = Transaction.objects.filter(status=Status.SUCCESSFUL)
        start, end = _parse_date(request.query_params.get("start")), _parse_date(request.query_params.get("end"))
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lt=end + timedelta(days=1))

        def summarise(rows):
            count = rows.pop("count", 0) or 0
            totals = {k: Decimal(v or 0) for k, v in rows.items()}
            totals["profit"] = totals["charged"] - totals["cost"] - totals["cashback"]
            return {"count": count, **{k: str(v.quantize(Decimal("0.01"))) for k, v in totals.items()}}

        aggregates = dict(
            count=Count("id"), face_value=Sum("amount"), charged=Sum("amount_charged"), cost=Sum("cost"),
            vtpass_commission=Sum("vtpass_commission"), fees=Sum("fee"), discounts=Sum("discount"),
        )
        overall = qs.aggregate(**aggregates)
        overall["cashback"] = qs.filter(cashback_paid=True).aggregate(v=Sum("cashback"))["v"]
        by_category = []
        for row in qs.values("category").annotate(**aggregates).order_by("category"):
            category = row.pop("category")
            row["cashback"] = qs.filter(category=category, cashback_paid=True).aggregate(v=Sum("cashback"))["v"]
            by_category.append({"category": category, **summarise(row)})
        return self.ok({"overall": summarise(overall), "by_category": by_category})
