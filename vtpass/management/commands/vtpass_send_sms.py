from django.core.management.base import BaseCommand

from vtpass.constants import SMSRoute
from vtpass.services import VTpass


class Command(BaseCommand):
    help = "Send an SMS through VTpass Messaging."

    def add_arguments(self, parser):
        parser.add_argument("recipients", help="Comma separated phone numbers.")
        parser.add_argument("message")
        parser.add_argument("--sender")
        parser.add_argument("--route", choices=SMSRoute.values)

    def handle(self, *args, **options):
        result = VTpass().sms.send(
            options["recipients"], options["message"], sender=options["sender"], route=options["route"],
            purpose="cli",
        )
        self.stdout.write(self.style.SUCCESS(f"{result.response_code} {result.response} batch={result.batch_id}"))
