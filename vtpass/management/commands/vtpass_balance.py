from django.core.management.base import BaseCommand

from vtpass.jobs import check_merchant_balance
from vtpass.services import VTpass


class Command(BaseCommand):
    help = "Show the VTpass merchant wallet balance (and SMS units with --sms)."

    def add_arguments(self, parser):
        parser.add_argument("--sms", action="store_true", help="Also show the SMS unit balance.")

    def handle(self, *args, **options):
        self.stdout.write(f"Wallet balance: {check_merchant_balance()}")
        if options["sms"]:
            self.stdout.write(f"SMS units: {VTpass().sms.balance()}")
