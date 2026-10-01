from django.core.management.base import BaseCommand

from vtpass.models import Transaction
from vtpass.services import VTpass


class Command(BaseCommand):
    help = "Settle pending VTpass transactions by requerying them (run every minute from cron if not using Celery)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--reference", help="Requery one transaction now, whatever its schedule.")

    def handle(self, *args, **options):
        vt = VTpass()
        if options["reference"]:
            txn = Transaction.objects.get(request_id=options["reference"])
            txn = vt.requery(txn)
            self.stdout.write(f"{txn.request_id}: {txn.status} ({txn.response_code} {txn.response_description})")
            return
        count = vt.requery_pending(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Requeried {count} transaction(s)."))
